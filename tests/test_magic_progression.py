from legacy_fixture import disable_regions
import copy
import json
from pathlib import Path
import random
import tempfile
import unittest

from engine import Game, validate
from magic_progression import default_magic_levels

ROOT = Path(__file__).resolve().parents[1]


class MagicProgressionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'world.json'
        self.path.write_bytes((ROOT / 'content/world.json').read_bytes())
        self.db = Path(self.temp.name) / 'test.sqlite3'
        self.now = 1000
        disable_regions(self.path);self.g = Game(self.path, self.db, random.Random(2), lambda: self.now)
        self.g.create('Mage', 'human', 'mage')
        self.g.p.update(level=7, gold=10000)
        self.g.p['hp'] = self.g.max_hp()
        self.g.w['settings']['hit_chance'] = 1
        self.g.w['enemies']['beetle'].update(hp=10000, dodge=0, damage=[1, 1], aggressive=False)
        self.g.w['skills']['fireball']['status_effects'] = []
        self.g.w['skills']['lightning']['status_effects'] = []

    def tearDown(self):
        self.g.db.close()
        self.temp.cleanup()

    def fight(self):
        self.g.p['room'] = 'meadow'
        enemy = self.g.enemy()
        enemy['hp'] = 10000
        self.g.start_combat()
        return enemy

    def reload(self):
        self.path.write_text(json.dumps(self.g.w), encoding='utf-8')
        self.g.save()
        self.g.db.close()
        self.g = Game(self.path, self.db, random.Random(2), lambda: self.now)

    def test_defaults_are_slow_and_start_weak(self):
        for spec in (self.g.w['skills']['fireball'], self.g.w['skills']['lightning'], self.g.w['items']['elven_sword']):
            self.assertEqual(spec['magic_xp_per_use'], 1)
            self.assertEqual([r['xp'] for r in spec['magic_levels'][:3]], [0, 100, 250])
            self.assertEqual(spec['magic_levels'][-1]['xp'], 252450)
            self.assertLess(spec['magic_levels'][0]['power'], spec['magic_levels'][-1]['power'])
        self.assertEqual(default_magic_levels(16, 2), [{k:v for k,v in row.items() if k not in ('effect_damage','mana_cost')} for row in self.g.w['skills']['fireball']['magic_levels']])

    def test_spell_damage_is_exact_and_does_not_train_or_use_weapon(self):
        weapon = self.g.grant('elven_sword')
        self.g.p['equipment']['weapon'] = weapon
        self.g.w['classes']['mage']['damage'] = [999, 999]
        self.g.w['skills']['fireball']['multiplier'] = 30
        enemy = self.fight()
        self.g.activate_skill('fireball')
        self.assertEqual(enemy['hp'], 9984)
        self.assertEqual(self.g.p['spell_xp'], {'fireball': 1})
        self.assertEqual(self.g.state['instances'][weapon]['magic_xp'], 0)

    def test_spells_level_independently_and_damage_changes_on_next_use(self):
        enemy = self.fight()
        self.g.p['spell_xp'] = {'fireball': 99}
        self.g.activate_skill('fireball')
        self.assertEqual(enemy['hp'], 9984)
        self.assertEqual(self.g.spell_progress('fireball')['level'], 2)
        self.assertEqual(self.g.spell_progress('lightning')['level'], 1)
        self.now += 20
        self.g.activate_skill('fireball')
        self.assertEqual(enemy['hp'], 9966)
        self.now += 2
        self.g.activate_skill('lightning')
        self.assertEqual(self.g.p['spell_xp'], {'fireball': 101, 'lightning': 1})
        self.reload()
        self.assertEqual(self.g.spell_progress('fireball')['level'], 2)

    def test_no_xp_for_rejected_uses_but_misses_and_dodges_train(self):
        with self.assertRaises(ValueError): self.g.activate_skill('fireball')
        self.assertNotIn('spell_xp', self.g.p)
        enemy = self.fight()
        self.g.w['enemies']['beetle']['dodge'] = 100
        self.g.activate_skill('fireball')
        self.assertEqual(enemy['hp'], 10000)
        with self.assertRaises(ValueError): self.g.activate_skill('fireball')
        self.assertEqual(self.g.p['spell_xp']['fireball'], 1)
        self.now += 20
        self.g.w['settings']['hit_chance'] = 0
        self.g.activate_skill('fireball')
        self.assertEqual(self.g.p['spell_xp']['fireball'], 2)
        self.now += 20
        self.g.p['effects'] = [dict(id='stunned', remaining=2, stacks=1)]
        with self.assertRaises(ValueError): self.g.activate_skill('fireball')
        self.assertEqual(self.g.p['spell_xp']['fireball'], 2)

    def test_spell_status_damage_uses_cast_level_and_survives_reload(self):
        self.g.w['skills']['fireball']['status_effects'] = [dict(effect='scorched', chance=100, duration=3)]
        self.g.w['skills']['fireball']['magic_levels'][0]['effect_damage'] = 4
        enemy = self.fight()
        self.g.activate_skill('fireball')
        self.assertEqual(enemy['effects'][0]['damage_override'], 4)
        self.reload()
        enemy = self.g.enemy()
        before = enemy['hp']
        self.g.pulse_effects(enemy)
        self.assertEqual(before - enemy['hp'], 4)
        self.assertEqual(self.g.w['status_effects']['scorched']['damage'], 2)

    def test_healing_and_knockout_spells_can_use_level_tables(self):
        self.g.w['skills']['mend'] = dict(name='Mend', effect='heal', heal=50, cooldown=10, multiplier=1, allowed_classes=None, magic=True, magic_levels=[dict(xp=0,power=4),dict(xp=100,power=8)])
        with self.assertRaises(ValueError): self.g.activate_skill('mend')
        self.g.p['hp'] = 1
        self.g.activate_skill('mend')
        self.assertEqual(self.g.p['hp'], 5)
        self.assertEqual(self.g.p['spell_xp']['mend'], 1)
        self.g.w['skills']['sleep'] = dict(name='Sleep', effect='knockout', chance=0, cooldown=10, multiplier=1, allowed_classes=None, magic=True, magic_levels=[dict(xp=0,power=100)])
        enemy = self.fight(); enemy['hp'] = 1
        self.g.w['enemies']['beetle']['capture_resistance'] = 0
        self.now += 2
        self.g.activate_skill('sleep')
        self.assertTrue(enemy['unconscious'])

    def test_two_item_copies_train_separately_on_hits_and_misses(self):
        first, second = self.g.grant('elven_sword'), self.g.grant('elven_sword')
        self.assertNotEqual(first, second)
        self.g.p['equipment']['weapon'] = first
        self.g.p['inventory'].append(second)
        self.g.state['instances'][first]['magic_xp'] = 99
        self.fight(); self.g.strike()
        self.assertEqual(self.g.item(first)['damage'], 11)
        self.assertEqual(self.g.item(second)['damage'], 10)
        self.g.w['settings']['hit_chance'] = 0
        self.g.strike()
        self.assertEqual(self.g.state['instances'][first]['magic_xp'], 101)
        self.assertEqual(self.g.state['instances'][second]['magic_xp'], 0)

    def test_armor_trains_only_when_it_protects_against_a_hit(self):
        for iid in ('leather_vest','buckler'):
            self.g.w['items'][iid].update(magic=True,magic_levels=[dict(xp=0,power=1),dict(xp=100,power=3)])
        worn, held = self.g.grant('leather_vest'), self.g.grant('leather_vest')
        self.g.p['equipment'] = dict(armor=worn, left_hand=held)
        enemy = self.fight()
        self.g.enemy_strike(enemy)
        self.assertEqual(self.g.state['instances'][worn]['magic_xp'],1)
        self.assertEqual(self.g.state['instances'][held]['magic_xp'],0)
        shield = self.g.grant('buckler');self.g.p['equipment']['left_hand']=shield
        self.g.enemy_strike(enemy)
        self.assertEqual(self.g.state['instances'][shield]['magic_xp'],1)
        self.g.w['settings']['hit_chance']=0
        self.g.enemy_strike(enemy)
        self.assertEqual(self.g.state['instances'][worn]['magic_xp'],2)

    def test_old_items_migrate_in_equipment_inventory_chests_and_ground(self):
        chest_type = next(k for k,v in self.g.w['items'].items() if v['kind']=='chest')
        chest = self.g.new_chest(chest_type)
        self.g.state['instances'][chest]['contents']=['elven_sword']
        self.g.p['inventory']=['elven_sword','elven_sword',chest]
        self.g.p['equipment']['weapon']='elven_sword'
        self.g.state['ground']['square']=['elven_sword']
        self.g.state.setdefault('drop_timers',{})['square']=[dict(item='elven_sword',expires=self.now+600)]
        self.reload()
        ids=self.g.p['inventory'][:2]+[self.g.p['equipment']['weapon'],self.g.state['instances'][chest]['contents'][0],self.g.state['ground']['square'][0]]
        self.assertEqual(len(set(ids)),5)
        self.assertTrue(all(self.g.state['instances'][iid]['magic_xp']==0 for iid in ids))
        self.assertEqual(self.g.state['drop_timers']['square'][0]['item'],ids[-1])
        sequence=self.g.state['instance_sequence'];self.reload()
        self.assertEqual(self.g.state['instance_sequence'],sequence)

    def test_item_progress_persists_through_drop_storage_and_save(self):
        iid=self.g.grant('elven_sword');self.g.state['instances'][iid]['magic_xp']=250
        self.g.p['inventory'].append(iid)
        self.g.drop_item(iid);self.g.get_item(iid)
        chest_type=next(k for k,v in self.g.w['items'].items() if v['kind']=='chest')
        chest=self.g.grant(chest_type);self.g.p['inventory'].append(chest)
        self.g.command(f'put {iid} in {chest}')
        self.assertIn(iid,self.g.state['instances'][chest]['contents'])
        self.reload();self.g.command(f'get {iid} from {chest}')
        self.assertIn(iid,self.g.p['inventory'])
        self.assertEqual(self.g.item(iid)['magic_progress']['level'],3)

    def test_enchantment_bonus_is_separate_and_expires_without_losing_item_xp(self):
        self.g.w['skills']['enchanting'].update(unlock_level=1,allowed_classes=None)
        self.g.w['revision'].update(enchant_base=100)
        iid=self.g.grant('elven_sword');self.g.p['equipment']['weapon']=iid
        self.g.state['instances'][iid]['magic_xp']=100
        self.g.activate_skill('enchanting',iid)
        self.assertEqual(self.g.item(iid)['damage'],12)
        self.assertIn('Damage 11 (+1)',self.g.item(iid)['description'])
        self.now+=301
        self.assertEqual(self.g.item(iid)['damage'],11)
        self.assertEqual(self.g.item(iid)['magic_progress']['level'],2)

    def test_owner_can_adjust_every_level_without_resetting_xp(self):
        self.g.p['spell_xp']={'fireball':100}
        w=copy.deepcopy(self.g.w);w['skills']['fireball']['magic_levels'][1]['power']=42
        self.g.update_world(w);self.reload()
        enemy=self.fight();self.g.activate_skill('fireball')
        self.assertEqual(enemy['hp'],9958)
        self.assertEqual(self.g.p['spell_xp']['fireball'],101)

    def test_invalid_tables_are_rejected_without_writing_world_or_save(self):
        invalid=[[],[dict(xp=1,power=6)],[dict(xp=0,power=6),dict(xp=0,power=8)],[dict(xp=0,power=-1)],[dict(xp=0,power=1.5)],[dict(xp=0,power=True)],[dict(xp=0,power=6,effect_damage=-1)],[dict(xp=float('nan'),power=6)]]
        before=self.path.read_bytes();state=copy.deepcopy(self.g.state)
        for rows in invalid:
            w=copy.deepcopy(self.g.w);w['skills']['fireball']['magic_levels']=rows
            with self.assertRaises(ValueError):self.g.update_world(w)
            self.assertEqual(self.path.read_bytes(),before);self.assertEqual(self.g.state,state)
        for group,key in [('items','recall_scroll'),('skills','enchanting')]:
            w=copy.deepcopy(self.g.w);w[group][key].update(magic=True,magic_levels=default_magic_levels(1))
            with self.assertRaises(ValueError):validate(w)

    def test_cap_display_and_skills_command(self):
        self.g.p['spell_xp']={'fireball':252450}
        self.fight();self.g.activate_skill('fireball')
        self.assertEqual(self.g.p['spell_xp']['fireball'],252450)
        self.g.command('skills')
        text='\n'.join(row['text'] for row in self.g.state['log'])
        self.assertIn('Fireball: Level 100',text)
        progress=next(s for s in self.g.snapshot()['player_skills'] if s['id']=='fireball')['magic_progress']
        self.assertIsNone(progress['next_xp'])
        self.assertEqual(progress['power'],214)
        self.assertEqual(self.g.snapshot()['items']['elven_sword']['damage'],10)


if __name__=='__main__':unittest.main()
