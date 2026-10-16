from legacy_fixture import disable_regions
import copy
import hashlib
import json
import random
import shutil
import tempfile
import unittest
from pathlib import Path
from engine import Game,validate

ROOT=Path(__file__).resolve().parents[1]
class FrontierTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.path=self.root/'world.json'
        shutil.copyfile(ROOT/'content/world.json',self.path);self.db=self.root/'save.sqlite3';self.now=1000
        disable_regions(self.path);self.g=Game(self.path,self.db,random.Random(5),lambda:self.now);self.g.create('Tester'); self.g.p['inventory'].append('lantern')  # Regression fixture: acquired light; new starts are tested separately.
    def tearDown(self):self.g.db.close();self.temp.cleanup()
    def reload(self):
        self.g.save();self.g.db.close();self.g=Game(self.path,self.db,random.Random(5),lambda:self.now)
    def log(self):return self.g.state['log'][-1]['text']
    def chest(self):
        iid=self.g.grant('storage_chest');self.g.p['inventory'].append(iid);return iid
    def cage(self,count=0,eid=None):
        iid=self.g.new_cage('iron_cage');self.g.state['instances'][iid].update(count=count,enemy=eid);self.g.p['inventory'].append(iid);return iid
    def pool(self,initial='beetle',pool=None):
        # Replace the fixture's already-initialized fixed resident.
        self.g.state['spawns'].pop('meadow',None)
        r=self.g.w['rooms']['meadow'];r['spawn_pool']=pool if pool is not None else [{'enemy':'horned_hare','weight':1}];r['respawn_seconds']=10
        if initial:r['enemy']=initial
        else:r.pop('enemy',None)
        self.g.p['room']='meadow';return r
    def test_drops_expire_exactly_after_ten_minutes(self):
        self.g.command('drop potion');self.now+=599;self.g.tick();self.assertIn('potion',self.g.state['ground']['square'])
        self.now+=1;self.g.tick();self.assertNotIn('potion',self.g.state['ground']['square'])
    def test_duplicate_drops_keep_separate_timers_and_get_resets(self):
        self.g.command('drop potion');self.now+=100;self.g.command('drop potion');self.now+=100
        self.g.command('get potion');self.g.command('drop potion');self.now=1700;self.g.tick()
        self.assertEqual(self.g.state['ground']['square'].count('potion'),1)
        self.now=1800;self.g.tick();self.assertNotIn('potion',self.g.state['ground']['square'])
    def test_timers_survive_restart_and_offline_time(self):
        self.g.command('drop potion');self.now+=601;self.reload();self.assertNotIn('potion',self.g.state['ground']['square'])
    def test_keys_cages_chests_and_contents_never_expire(self):
        chest=self.chest();cage=self.cage(2,'vampire');self.g.p['inventory'].append('rusty_crypt_key')
        self.g.command('put potion in '+chest);self.g.command('drop '+chest);self.g.command('drop '+cage);self.g.command('drop rusty key')
        self.now+=999999;self.reload();pile=self.g.state['ground']['square']
        for i in (chest,cage,'rusty_crypt_key'):self.assertIn(i,pile)
        self.assertEqual(self.g.state['instances'][chest]['contents'],['potion']);self.assertEqual(self.g.state['instances'][cage]['count'],2)
    def test_uncollected_treasure_and_legacy_ground_are_not_player_drops(self):
        self.g.state['ground']['square']=['dawnfang'];self.now+=1000;self.g.tick();self.assertEqual(self.g.state['ground']['square'],['dawnfang'])
    def test_chest_move_reload_and_retrieve_cage_keeps_occupants(self):
        chest=self.chest();cage=self.cage(3,'beetle');self.g.command('put '+cage+' in '+chest)
        self.g.command('drop '+chest);self.g.command('east');self.g.command('west');self.g.command('get '+chest);self.reload()
        self.g.command('get '+cage+' from '+chest);self.assertIn(cage,self.g.p['inventory']);self.assertEqual(self.g.state['instances'][cage]['count'],3)
    def test_chest_capacity_unlimited_bag_nesting_and_sale_guards(self):
        chest=self.chest();other=self.chest();self.g.command('put '+other+' in '+chest);self.assertIn('cannot',self.log())
        self.g.state['instances'][chest]['contents']=['potion']*30
        self.g.command('put potion in '+chest);self.assertIn('full',self.log());self.assertEqual(len(self.g.state['instances'][chest]['contents']),30)
        self.g.w['settings']['bag_capacity']=len(self.g.p['inventory']);self.g.command('get potion from '+chest);self.assertIn('Retrieved',self.log());self.assertEqual(len(self.g.state['instances'][chest]['contents']),29)
        self.g.p['room']='shop';self.g.command('sell '+chest);self.assertIn(chest,self.g.p['inventory'])
    def test_stored_items_are_protected_against_editor_removal(self):
        chest=self.chest();self.g.state['instances'][chest]['contents']=['rubber_boots']
        new=copy.deepcopy(self.g.w);del new['items']['rubber_boots']
        with self.assertRaises(ValueError):self.g.update_world(new)
        new=copy.deepcopy(self.g.w);new['items']['storage_chest']['capacity']=0
        with self.assertRaises(ValueError):self.g.update_world(new)
    def test_two_chests_keep_independent_contents(self):
        a=self.chest();b=self.chest();self.g.command('put potion in '+a)
        self.assertEqual(self.g.state['instances'][a]['contents'],['potion']);self.assertEqual(self.g.state['instances'][b]['contents'],[])
        self.g.command('look chest '+str(self.g.state['instances'][a]['number']));self.assertIn('Healing potion',self.log())
    def test_jake_route_counted_payment_and_cage_removed(self):
        self.g.p['room']='shop'
        for command in ['west','south','east']:self.g.command(command)
        self.assertEqual(self.g.p['room'],'jakes_critters');cage=self.cage(3,'beetle');gold=self.g.p['gold']
        self.g.command('sell '+cage);self.assertEqual(self.g.p['gold'],gold+30);self.assertNotIn(cage,self.g.p['inventory']);self.assertNotIn(cage,self.g.state['instances'])
        self.g.command('sell '+cage);self.assertEqual(self.g.p['gold'],gold+30)
    def test_jake_refuses_empty_unpriced_and_uncontained_creatures(self):
        self.g.p['room']='jakes_critters';empty=self.cage();unpriced=self.cage(1,'sentinel');gold=self.g.p['gold']
        for i in [empty,unpriced,'potion']:self.g.command('sell '+i);self.assertIn(i,self.g.p['inventory'])
        self.assertEqual(self.g.p['gold'],gold)
    def test_pool_start_then_new_species_and_room_timer(self):
        self.pool();e=self.g.enemy();self.assertEqual(e['type'],'beetle');self.g.victory(e)
        self.assertEqual(e['respawn_at'],1010);self.now=1009;self.assertIsNone(self.g.enemy());self.now=1010
        self.assertEqual(self.g.enemy()['type'],'horned_hare');self.g.look('');self.assertEqual(self.g.enemy()['type'],'horned_hare')
    def test_pool_none_start_waits_and_empty_pool_stops(self):
        self.pool(initial=None);self.assertIsNone(self.g.enemy());self.now+=10;self.assertEqual(self.g.enemy()['type'],'horned_hare')
        self.g.w['rooms']['meadow']['spawn_pool']=[];self.g.victory(self.g.enemy());self.now+=999;self.assertIsNone(self.g.enemy())
    def test_capture_uses_room_respawn_delay(self):
        self.pool();e=self.g.enemy();e.update(unconscious=True,hp=1);self.g.command('get beetle')
        self.assertEqual(e['respawn_at'],1010);self.now+=10;self.assertEqual(self.g.enemy()['type'],'horned_hare')
    def test_pool_weights_persistence_and_validation(self):
        r=self.pool(pool=[{'enemy':'beetle','weight':1},{'enemy':'horned_hare','weight':9}]);self.path.write_text(json.dumps(self.g.w));self.g.enemy();self.g.victory(self.g.enemy());self.reload();self.now+=10
        self.assertEqual(self.g.enemy()['type'],'horned_hare')
        self.g.p['combat']=None;new=copy.deepcopy(self.g.w);new['rooms']['meadow']['spawn_pool'][0]['weight']=0
        with self.assertRaises(ValueError):validate(new)
        new=copy.deepcopy(self.g.w);new['rooms']['meadow']['encounter']={'enemy':'beetle','chance':5,'cooldown':30}
        with self.assertRaises(ValueError):validate(new)
    def test_pool_enemy_can_reveal_discovery(self):
        r=self.pool(initial='horned_hare');r['discoveries']=[{'id':'hare_find','name':'A potion','kind':'item','item':'potion','trigger':'defeat','target':'horned_hare'}]
        validate(self.g.w);self.g.victory(self.g.enemy());self.assertTrue(self.g.state['discoveries']['meadow']['hare_find']['revealed'])
    def test_conversation_exact_case_insensitive_and_attack(self):
        self.g.p['room']='dungeon';self.g.command('say HELLO to vampire');self.assertIn('polite visitor',self.log());self.assertIsNone(self.g.p['combat'])
        self.g.command('say hello there to vampire');self.assertIn('no reply',self.log())
        self.g.command("say you don't scare me to vampire");self.assertIsNotNone(self.g.p['combat'])
    def test_caged_conversation_cannot_attack_and_no_rules_exposed(self):
        cage=self.cage(1,'vampire');self.g.command("say you don't scare me to "+cage)
        self.assertIsNone(self.g.p['combat']);self.assertIn('cannot attack',self.log())
        self.assertNotIn('conversations',json.dumps(self.g.snapshot()))
    def test_conversation_default_and_unavailable_creature(self):
        self.g.p['room']='dungeon';self.g.w['enemies']['vampire']['conversation_default']='She says nothing.'
        self.g.command('say unknown to vampire');self.assertEqual(self.log(),'She says nothing.')
        self.g.command('say hello to goblin');self.assertIn('No matching',self.log())
    def test_codes_unique_immutable_and_coordinates_validate(self):
        codes=[r['code'] for r in self.g.w['rooms'].values()];self.assertEqual(len(codes),len(set(codes)))
        new=copy.deepcopy(self.g.w);new['rooms']['square']['code']='TOWN-999'
        with self.assertRaises(ValueError):self.g.update_world(new)
        new=copy.deepcopy(self.g.w);new['rooms']['shop']['map_position']=new['rooms']['square']['map_position']
        with self.assertRaises(ValueError):validate(new)
        new=copy.deepcopy(self.g.w);new['rooms']['square']['name']='New Square Name';self.g.update_world(new);self.assertEqual(self.g.w['rooms']['square']['code'],'TOWN-001')
    def test_world_edit_keeps_live_pool_enemy_and_stored_state(self):
        self.pool();self.g.victory(self.g.enemy());self.now+=10;e=self.g.enemy();e['hp']=5
        self.g.update_world(copy.deepcopy(self.g.w));self.assertEqual(self.g.enemy()['hp'],5)

if __name__=='__main__':unittest.main()
