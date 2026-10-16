"""Death recovery, expiry and account ownership on disposable character saves."""
import copy
from collections import Counter
import json
from pathlib import Path
import random
import tempfile
import unittest

from engine import Game, validate
from revision_rules import SCHEMA

ROOT = Path(__file__).resolve().parents[1]


class BodiesBankingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name)/'world.json'
        world = json.loads((ROOT/'content/world.json').read_text(encoding='utf-8'))
        world.pop('regions', None)
        for enemy in world['enemies'].values():
            enemy['aggressive'] = False
        self.path.write_text(json.dumps(world), encoding='utf-8')
        self.db = Path(self.tmp.name)/'save.db'
        self.now = 1000.
        self.g = Game(self.path, self.db, random.Random(3), lambda: self.now)
        self.g.create('Traveler')

    def tearDown(self):
        self.g.db.close()
        self.tmp.cleanup()

    def reload(self):
        self.g.save(); self.g.db.close()
        self.g = Game(self.path, self.db, random.Random(3), lambda: self.now)

    def die(self, room='meadow'):
        self.g.p['room'] = room
        self.g.death()
        return self.g.state['player_bodies'][-1]

    def test_death_transfers_all_belongings_and_returns_to_fountain(self):
        self.g.p['inventory'].extend(['lantern', 'potion'])
        before = copy.deepcopy(self.g.p)
        body = self.die()
        self.assertEqual(Counter(body['items']), Counter(before['inventory']+list(before['equipment'].values())))
        self.assertEqual(body['gold'], before['gold'])
        self.assertEqual(body['room'], 'meadow')
        self.assertEqual(body['expires'], self.now+900)
        self.assertEqual((self.g.p['inventory'], self.g.p['equipment'], self.g.p['gold']), ([], {}, 0))
        self.assertEqual(self.g.p['room'], 'square')
        self.assertEqual(self.g.p['hp'], self.g.max_hp())
        self.assertEqual(self.g.p['mana'], self.g.max_mana())
        self.assertEqual(self.g.p['xp'], before['xp'])
        self.assertIn('You blink awake from death feeling strange and disoriented.', [r['text'] for r in self.g.state['log']])
        self.reload()
        self.assertEqual(self.g.state['player_bodies'], [body])
        self.assertEqual(self.g.p['id'], before['id'])

    def test_recovery_in_darkness_and_no_duplicate_loot(self):
        self.g.p['inventory'].append('lantern')
        body = self.die('dungeon'); original = body['items'][:]; gold = body['gold']
        self.g.p['room'] = 'dungeon'
        self.assertFalse(self.g.visible())
        self.g.command('look corpse')
        self.assertIn('Gold: '+str(gold), self.g.state['log'][-1]['text'])
        self.g.command('get lantern from body')
        self.assertTrue(self.g.visible())
        self.g.command('get all from body')
        self.assertEqual(Counter(self.g.p['inventory']), Counter(original))
        self.assertEqual(self.g.p['gold'], gold)
        self.g.command('loot corpse')
        self.assertEqual(Counter(self.g.p['inventory']), Counter(original))
        self.assertEqual(self.g.p['gold'], gold)
        self.assertEqual(body['items'], [])

    def test_recovery_ignores_legacy_capacity_and_weight_limits(self):
        body = self.die(); original = Counter(body['items']); self.g.p['room'] = 'meadow'
        self.g.w['settings']['bag_capacity'] = 1
        self.g.w['classes'][self.g.p['class']]['carry_capacity'] = 1
        self.g.command('get all from body')
        self.assertEqual(Counter(self.g.p['inventory']), original)
        self.assertEqual(body['items'], [])
        body['items'] = ['greatsword']
        self.g.command('get greatsword from body')
        self.assertEqual(body['items'], [])
        self.assertIn('greatsword', self.g.p['inventory'])

    def test_enchanted_item_and_container_contents_survive_recovery(self):
        sword = self.g.new_instance(dict(kind='weapon', item='iron_sword', bonus=-1, magic_xp=100,
                                        enchantment=dict(bonus=3, until=self.now+1200)))
        chest = self.g.grant('storage_chest')
        self.g.state['instances'][chest]['contents'] = [sword, 'potion']
        self.g.p['inventory'].append(chest)
        before = copy.deepcopy(self.g.state['instances'])
        self.die(); self.g.p['room'] = 'meadow'
        self.g.command('get all from body')
        self.assertIn(chest, self.g.p['inventory'])
        for iid, instance in before.items():
            self.assertEqual(self.g.state['instances'][iid], instance)

    def test_expiry_removes_nested_contents_but_not_recovered_instances(self):
        saved = self.g.new_instance(dict(kind='weapon', item='iron_sword', bonus=1))
        lost = self.g.new_instance(dict(kind='weapon', item='iron_sword', bonus=2))
        chest = self.g.grant('storage_chest')
        self.g.state['instances'][chest]['contents'] = [lost, 'potion']
        self.g.p['inventory'] = [saved, chest]
        body = self.die(); self.g.p['room'] = 'meadow'
        self.g.command('get '+saved+' from body')
        self.now += 899; self.g.tick()
        self.assertIn(body, self.g.state['player_bodies'])
        self.now += 1; self.g.tick()
        self.assertFalse(self.g.state['player_bodies'])
        self.assertIn(saved, self.g.state['instances'])
        self.assertNotIn(lost, self.g.state['instances'])
        self.assertNotIn(chest, self.g.state['instances'])
        self.assertIn('potion', self.g.w['items'])
        self.g.command('get all from body')
        self.assertIn('already faded', self.g.state['log'][-1]['text'])

    def test_offline_time_counts_toward_body_expiry(self):
        self.die(); self.now += 901; self.reload()
        self.assertFalse(self.g.state['player_bodies'])
        self.assertEqual(self.g.p['gold'], 0)

    def test_multiple_bodies_require_selection_and_ownership(self):
        a = self.die(); self.g.p['gold'] = 7; b = self.die()
        with self.assertRaisesRegex(ValueError, 'not here'):
            self.g.loot_player_body(a['id'])
        self.g.p['room'] = 'meadow'
        with self.assertRaisesRegex(ValueError, 'More than one'):
            self.g.loot_player_body('body')
        self.g.command('get gold from body 2')
        self.assertEqual(self.g.p['gold'], 7); self.assertEqual(a['gold'], 30)
        a['owner'] = 'another-player'
        with self.assertRaisesRegex(ValueError, 'own body'):
            self.g.loot_player_body(a['id'])
        self.assertEqual(a['gold'], 30)

    def test_one_body_per_combat_death_and_no_post_respawn_attacks(self):
        self.g.w['rooms']['meadow']['population'] = [dict(id='crowd', enemy='beetle', count=2, chance=100)]
        self.g.w['enemies']['beetle'].update(aggressive=True, damage=[1000,1000], dodge=0)
        self.g.w['settings']['hit_chance'] = 1
        self.g.p.update(room='meadow', hp=1, attack_ready=self.now+100)
        self.g.tick()
        self.assertEqual(len(self.g.state['player_bodies']), 1)
        self.assertEqual(self.g.p['room'], 'square')
        self.assertEqual(self.g.p['hp'], self.g.max_hp())
        self.assertIsNone(self.g.p['combat'])

    def test_owner_body_duration_and_reference_protection(self):
        self.assertEqual(SCHEMA['revision']['player_body_seconds']['default'], 900)
        world = copy.deepcopy(self.g.w); world['revision']['player_body_seconds'] = 60
        self.g.update_world(world); body = self.die()
        self.assertEqual(body['expires'], self.now+60)
        world = copy.deepcopy(self.g.w); world['items'].pop('rusted_sword')
        with self.assertRaisesRegex(ValueError, 'body'):
            self.g.check_body_references(world)
        world = copy.deepcopy(self.g.w); world['rooms'].pop('meadow')
        with self.assertRaisesRegex(ValueError, 'body'):
            self.g.check_body_references(world)
        for value in (0,-1,'900',float('nan')):
            world = copy.deepcopy(self.g.w); world['revision']['player_body_seconds'] = value
            with self.assertRaises(ValueError): validate(world)

    def bank(self):
        self.g.p['room'] = 'brass_badger_bank'

    def test_bank_transfers_persist_and_survive_death(self):
        self.bank(); self.g.command('deposit 20')
        self.assertEqual((self.g.p['gold'],self.g.bank_balance()),(10,20))
        self.reload(); self.g.command('withdraw 5 gold')
        self.assertEqual((self.g.p['gold'],self.g.bank_balance()),(15,15))
        body = self.die()
        self.assertEqual(body['gold'],15); self.assertEqual(self.g.bank_balance(),15)
        self.bank(); self.g.command('withdraw all')
        self.assertEqual((self.g.p['gold'],self.g.bank_balance()),(15,0))
        self.g.command('deposit all')
        self.assertEqual((self.g.p['gold'],self.g.bank_balance()),(0,15))

    def test_accounts_are_bound_to_id_not_character_name_or_request(self):
        self.bank(); self.g.command('deposit all'); first = self.g.p['id']
        other = copy.deepcopy(self.g.p); other.update(id='different-player',gold=7)
        self.g.p = self.g.state['player'] = other
        self.g.command('withdraw 1')
        self.assertEqual(self.g.bank_balance(),0); self.assertEqual(self.g.p['gold'],7)
        self.g.command('withdraw 30 from '+first)
        self.assertEqual(self.g.state['bank_accounts'][first],30)
        self.g.command('deposit all'); self.assertEqual(self.g.bank_balance(),7)
        self.g.p['id'] = first; self.g.p['name'] = 'Renamed'
        self.g.command('withdraw all'); self.assertEqual(self.g.p['gold'],30)
        self.assertEqual(self.g.state['bank_accounts']['different-player'],7)
        snapshot=self.g.snapshot()
        self.assertNotIn('bank_accounts',snapshot)
        self.assertEqual(snapshot['player']['bank_gold'],0)

    def test_invalid_bank_transactions_and_wrong_location_are_atomic(self):
        before = copy.deepcopy(self.g.p)
        self.g.command('deposit all'); self.assertEqual(self.g.p,before)
        self.bank()
        for command in ('deposit -5','deposit 0','deposit 1.5','deposit 1000','withdraw all','withdraw 1','deposit 10 to someone'):
            before = copy.deepcopy(self.g.p); accounts = dict(self.g.state['bank_accounts'])
            self.g.command(command)
            self.assertEqual(self.g.p,before,command); self.assertEqual(self.g.state['bank_accounts'],accounts,command)

    def test_new_characters_have_distinct_stable_ids_and_bank_is_connected(self):
        other = Game(self.path, ':memory:'); other.create('Traveler')
        try:self.assertNotEqual(self.g.p['id'],other.p['id'])
        finally:other.db.close()
        self.g.command('south'); self.g.command('west')
        self.assertEqual(self.g.p['room'],'brass_badger_bank')
        self.assertTrue(self.g.snapshot()['room']['bank_service'])
        self.g.command('say hello to Osric Tallywick')
        self.assertIn('Welcome, welcome!',self.g.state['log'][-1]['text'])
        self.g.command('east'); self.g.command('north')
        self.assertEqual(self.g.p['room'],'square')


if __name__ == '__main__':
    unittest.main()
