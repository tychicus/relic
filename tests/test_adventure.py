from legacy_fixture import disable_regions
"""Mechanics and migration checks use isolated saves, never the bundled character."""
import copy
import hashlib
import json
import random
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock
from engine import Game, validate

ROOT=Path(__file__).resolve().parents[1]

class AdventureTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.path=self.root/'world.json';shutil.copyfile(ROOT/'content/world.json',self.path)
        self.db=self.root/'test.sqlite3';self.now=1000
        disable_regions(self.path);self.g=Game(self.path,self.db,random.Random(42),lambda:self.now);self.g.create('Test'); self.g.p['inventory'].append('lantern')  # Regression fixture: acquired light; new starts are tested separately.
    def tearDown(self):self.g.db.close();self.temp.cleanup()
    def reload(self):
        self.g.save();self.g.db.close();self.g=Game(self.path,self.db,random.Random(42),lambda:self.now)
    def logs(self):return '\n'.join(x['text'] for x in self.g.state['log'])
    def cage(self):
        i=self.g.new_cage('iron_cage');self.g.p['inventory'].append(i);return i
    def captive(self,eid='vampire'):
        i=self.g.new_instance({'kind':'captive','enemy':eid});self.g.p['inventory'].append(i);return i
    def weakened(self,eid='vampire',rid='dungeon'):
        self.g.p['room']=rid;self.g.p['combat']=None
        e=self.g.enemy();self.assertEqual(e['type'],eid);e['hp']=1
        self.g.w['skills']['knockout']['chance']=100;self.g.w['enemies'][eid]['capture_resistance']=0
        # Keep automatic attacks from landing before the requested skill.
        self.g.start_combat();self.g.p['combat']['next_at']=self.now+2
        return e
    def test_shop_vertical_plain_grouped(self):
        self.g.p['room']='shop';self.g.w['rooms']['shop']['shop'].append('potion')
        self.g.command('buy');text=self.g.state['log'][-1]['text']
        self.assertIn('For sale:\n',text);self.assertIn('Healing potion (x2)',text)
        self.assertIn('\nIron sword —',text);self.assertNotIn(';',text)
    def test_prairie_connected_troll_settings(self):
        w=self.g.w;self.assertEqual(w['rooms']['meadow']['exits']['west'],'prairie_3_0')
        opposite={'north':'south','south':'north','east':'west','west':'east'}
        rooms={r:v for r,v in w['rooms'].items() if r.startswith('prairie_')}
        self.assertEqual(len(rooms),16)
        for rid,r in rooms.items():
            for d,dest in r['exits'].items():self.assertEqual(w['rooms'][dest]['exits'][opposite[d]],rid)
        for x in range(4):self.assertEqual(rooms[f'prairie_{x}_3']['encounter'],{'enemy':'cave_troll','chance':5,'cooldown':300})
    def test_entry_rolls_not_polling_and_independent_cooldown(self):
        self.g.p['room']='prairie_0_3';self.g.w['enemies']['cave_troll']['aggressive']=False
        self.g.rng=Mock();self.g.rng.random.return_value=.99
        self.g.command('east');self.assertEqual(self.g.rng.random.call_count,1)
        for _ in range(4):self.g.command('look');self.g.snapshot();self.g.tick()
        self.assertEqual(self.g.rng.random.call_count,1)
        self.g.command('west');self.assertEqual(self.g.rng.random.call_count,2)
        self.g.command('east');self.assertEqual(self.g.rng.random.call_count,2)
        self.now+=301;self.g.rng.random.return_value=0
        self.g.command('west');e=self.g.enemy();self.assertEqual(e['type'],'cave_troll')
        self.g.command('east');self.assertEqual(self.g.enemy()['type'],'cave_troll')
        self.g.command('west');self.assertIs(self.g.enemy(),e);self.assertEqual(self.g.rng.random.call_count,4)
        self.reload();self.assertEqual(self.g.enemy()['type'],'cave_troll')
    def test_random_defeat_waits_for_reentry_and_respawn(self):
        rid='prairie_0_3';self.g.p['room']=rid;self.g.w['rooms'][rid]['encounter']['chance']=100
        self.g.roll_encounter(rid);e=self.g.enemy();self.g.victory(e)
        self.now+=400;self.g.tick();self.assertIsNone(self.g.enemy())
        self.g.roll_encounter(rid);self.assertIsNotNone(self.g.enemy())
    def test_hidden_treasure_kill_key_consumption_once_and_restart(self):
        self.g.p['room']='dungeon';self.g.look('');self.assertFalse(self.g.containers())
        self.g.command('unlock box');self.assertNotIn('rusty_crypt_key',self.g.state['ground'].get('dungeon',[]))
        self.g.victory(self.g.enemy());self.assertEqual(len(self.g.containers()),1)
        self.g.command('unlock box');self.assertIn('need',self.g.state['log'][-1]['text'])
        self.g.command('get rusty key');self.g.command('unlock box')
        self.assertNotIn('rusty_crypt_key',self.g.p['inventory']);self.assertEqual(self.g.state['ground']['dungeon'].count('dawnfang'),1)
        self.g.command('unlock box');self.g.command('get dawnfang');self.reload()
        self.now+=301;self.g.look('');self.g.victory(self.g.enemy());self.g.command('unlock box')
        self.assertEqual(self.g.p['inventory'].count('dawnfang'),1);self.assertNotIn('rusty_crypt_key',self.g.state['ground']['dungeon'])
    def test_respawn_hides_discoveries_without_resetting_treasure(self):
        self.g.p['room']='dungeon';self.g.victory(self.g.enemy())
        self.assertIn('rusty_crypt_key',self.g.snapshot()['ground'])
        self.now+=301
        self.assertFalse(self.g.snapshot()['containers'])
        self.assertNotIn('rusty_crypt_key',self.g.snapshot()['ground'])
        before=copy.deepcopy(self.g.state['discoveries']['dungeon'])
        self.g.look('');self.assertNotIn('Old rusty key',self.g.state['log'][-1]['text'])
        self.g.command('get rusty key');self.assertNotIn('rusty_crypt_key',self.g.p['inventory'])
        self.g.command('open crypt box');self.assertFalse(self.g.containers())
        self.assertEqual(before,self.g.state['discoveries']['dungeon'])
        self.reload();self.assertFalse(self.g.snapshot()['containers'])
        self.g.victory(self.g.enemy());self.g.command('get rusty key')
        self.assertIn('rusty_crypt_key',self.g.p['inventory'])
        self.now+=301;self.assertFalse(self.g.containers())
        self.assertIn('rusty_crypt_key',self.g.p['inventory'])
        self.g.victory(self.g.enemy());self.g.command('unlock box')
        self.assertTrue(self.g.containers()[0][1]['opened'])
        self.now+=301;self.assertFalse(self.g.containers());self.reload()
        self.assertFalse(self.g.containers())
        self.g.victory(self.g.enemy());self.assertTrue(self.g.containers()[0][1]['opened'])
        self.assertEqual(self.g.state['ground']['dungeon'].count('dawnfang'),1)
        self.assertNotIn('rusty_crypt_key',self.g.state['ground']['dungeon'])

    def test_discovery_respawn_visibility_can_be_disabled(self):
        self.g.p['room']='dungeon';self.g.victory(self.g.enemy())
        for d in self.g.w['rooms']['dungeon']['discoveries']:d['hide_on_respawn']=False
        self.now+=301
        self.assertTrue(self.g.containers())
        self.assertIn('rusty_crypt_key',self.g.snapshot()['ground'])

    def test_inspect_and_visible_placements_are_reusable_and_single_use(self):
        self.g.w['rooms']['square']['discoveries']=[{'id':'find','name':'A coin','kind':'item','item':'scrap','trigger':'inspect','target':'fountain'},{'id':'plain','name':'A potion','kind':'item','item':'potion','trigger':'visible'}]
        self.g.look('');self.assertEqual(self.g.state['ground']['square'],['potion'])
        self.g.look('fountain');self.g.look('fountain');self.assertEqual(self.g.state['ground']['square'].count('scrap'),1)
    def test_capture_stops_combat_without_kill_rewards_or_reveal(self):
        e=self.weakened();before=(self.g.p['xp'],self.g.p['gold'])
        self.g.command('knockout vampire');self.assertTrue(e['unconscious']);self.assertIsNone(self.g.p['combat'])
        self.now+=30;self.g.tick();self.assertIsNone(self.g.p['combat']);self.assertIsNone(self.g.enemy())
        self.assertEqual(before,(self.g.p['xp'],self.g.p['gold']));self.assertFalse(self.g.containers())
        self.g.command('get vampire');self.assertEqual(e['hp'],0);self.assertFalse(self.g.containers())
        self.assertTrue(any(self.g.item(i)['kind']=='captive' for i in self.g.p['inventory']))
        self.now+=301;self.assertIsNotNone(self.g.enemy())
    def test_capture_health_resistance_and_cooldown(self):
        self.g.p['room']='dungeon';e=self.g.enemy();self.g.command('knockout vampire')
        self.assertIn('Weaken',self.g.state['log'][-1]['text']);self.assertNotIn('knockout',self.g.p['cooldowns'])
        e=self.weakened();self.g.w['enemies']['vampire']['capture_resistance']=100
        self.g.command('knockout');self.assertFalse(e.get('unconscious'));self.assertIsNotNone(self.g.p['combat'])
        self.g.command('knockout');self.assertIn('ready in',self.g.state['log'][-1]['text'])
    def test_legacy_bag_limit_does_not_prevent_capture(self):
        e=self.weakened();self.g.command('knockout');self.g.w['settings']['bag_capacity']=len(self.g.p['inventory'])
        self.g.command('get vampire');self.assertFalse(e['unconscious']);self.assertEqual(e['hp'],0)
        iid=self.g.p['inventory'][-1];self.assertEqual(self.g.state['instances'][iid]['enemy'],'vampire')
        self.reload();self.assertIn(iid,self.g.p['inventory']);self.assertIsNone(self.g.enemy())
    def test_cages_stack_one_type_move_reload_and_sell_guards(self):
        cage=self.cage();other=self.cage();number=self.g.state['instances'][cage]['number']
        self.captive();self.captive();self.g.command(f'put vampire in cage {number}');self.g.command(f'put vampire in cage {number}')
        self.assertEqual(self.g.state['instances'][cage]['count'],2);self.assertEqual(self.g.state['instances'][other]['count'],0)
        goblin=self.captive('goblin');self.g.command(f'put goblin in cage {number}');self.assertIn(goblin,self.g.p['inventory'])
        self.g.command(f'drop cage {number}');self.g.command('east');self.g.command('west');self.g.command(f'get cage {number}');self.reload()
        self.assertEqual(self.g.state['instances'][cage]['count'],2);self.g.command(f'look cage {number}');self.assertIn('vampire',self.logs().lower())
        self.g.command('east');gold=self.g.p['gold'];self.g.command(f'sell cage {number}');self.assertEqual(self.g.p['gold'],gold);self.assertIn(cage,self.g.p['inventory'])
    def test_cage_capacity_and_ambiguous_target_do_not_lose_creature(self):
        first=self.cage();self.cage();c=self.captive();self.g.command('put vampire in cage');self.assertIn(c,self.g.p['inventory'])
        inst=self.g.state['instances'][first];inst.update(enemy='vampire',count=5)
        self.g.command(f'put vampire in cage {inst["number"]}');self.assertIn(c,self.g.p['inventory']);self.assertEqual(inst['count'],5)
    def test_buy_individual_cages_and_sell_empty(self):
        self.g.p['room']='shop';self.g.p['gold']=200
        self.g.command('buy iron cage');self.g.command('buy iron cage')
        cages=[i for i in self.g.p['inventory'] if self.g.item(i)['kind']=='cage'];self.assertEqual(len(set(cages)),2)
        self.g.command('sell '+cages[0]);self.assertNotIn(cages[0],self.g.state['instances']);self.assertEqual(self.g.p['gold'],132)
    def test_release_no_rewards_or_discovery_and_no_safe_room(self):
        cage=self.cage();inst=self.g.state['instances'][cage];inst.update(enemy='vampire',count=2)
        self.g.command('release '+cage);self.assertEqual(inst['count'],2)
        self.g.p['room']='road';self.g.command('release '+cage);self.assertEqual(inst['count'],1)
        self.g.command('release '+cage);self.assertEqual(inst['count'],1)
        before=(self.g.p['gold'],self.g.p['xp']);self.g.victory(self.g.enemy());self.assertEqual(before,(self.g.p['gold'],self.g.p['xp']))
    def test_dialogue_and_editor_validation(self):
        e=self.weakened();spec=self.g.w['enemies']['vampire'];spec['battle_cry_chance']=100;spec['battle_cries']=['Custom battle'];spec['defeat_messages']=['Custom death']
        self.g.enemy_strike(e);self.assertIn('Custom battle',self.logs());self.g.victory(e);self.assertIn('Custom death',self.logs())
        for key,value in [('battle_cry_chance',101),('capture_health',-1),('capture_resistance','bad'),('captive_actions','not a list')]:
            w=copy.deepcopy(self.g.w);w['enemies']['vampire'][key]=value
            with self.assertRaises(ValueError):validate(w)
        cage=self.cage();self.g.state['instances'][cage].update(enemy='vampire',count=2)
        w=copy.deepcopy(self.g.w);w['items']['iron_cage']['capacity']=1
        with self.assertRaises(ValueError):self.g.update_world(w)
    def test_bundled_save_migrates_without_changing_original(self):
        if not (ROOT/'saves/game.sqlite3').is_file():
            self.skipTest('Optional personal-save migration check: no local save is present.')
        original=ROOT/'saves/game.sqlite3';digest=hashlib.sha256(original.read_bytes()).hexdigest()
        target=self.root/'imported.sqlite3';shutil.copyfile(original,target)
        import sqlite3
        db=sqlite3.connect(target);old=json.loads(db.execute("SELECT body FROM state WHERE id='world'").fetchone()[0]);db.close()
        migration_world=self.root/'migration-world.json'
        migration_world.write_bytes((ROOT/'content/world.json').read_bytes())
        game=Game(migration_world,target,clock=lambda:self.now)
        try:
            expected=copy.deepcopy(old['player'])
            if expected.get('combat'):
                expected['combat']['next_at']=self.now+game.w['settings']['attack_interval']
            self.assertEqual({k:game.p[k] for k in expected},expected);self.assertEqual(game.state['ground'],old['ground'])
            self.assertEqual(game.p['mana_xp'],old['player'].get('mana_xp',0))
            self.assertEqual(game.p['mana'],old['player'].get('mana',game.max_mana()))
            self.assertIn('instances',game.state);game.snapshot();game.command('buy')
        finally:game.db.close()
        self.assertEqual(hashlib.sha256(original.read_bytes()).hexdigest(),digest)

if __name__=='__main__':unittest.main()
