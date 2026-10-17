"""Visible enemy remains, decay and harvest compatibility on disposable saves."""
import copy
import json
from pathlib import Path
import random
import tempfile
import unittest

from engine import Game
from expedition import CORPSE_DESCRIPTIONS

ROOT = Path(__file__).resolve().parents[1]


class EnemyCorpseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / 'world.json'
        world = json.loads((ROOT / 'content/world.json').read_text(encoding='utf-8'))
        world.pop('regions', None)
        for room in world['rooms'].values():
            room['population'] = []
            room['roaming'] = False
        for enemy in world['enemies'].values():
            enemy['aggressive'] = False
        world['settings']['hit_chance'] = 1
        world['revision']['rare_drop_chance'] = 0
        self.path.write_text(json.dumps(world), encoding='utf-8')
        self.db = Path(self.tmp.name) / 'save.db'
        self.now = 1000.
        self.g = Game(self.path, self.db, random.Random(5), lambda: self.now)
        self.g.create('Traveler', 'human', 'warrior')
        self.g.p['room'] = 'meadow'

    def tearDown(self):
        self.g.db.close()
        self.tmp.cleanup()

    def look(self):
        self.g.state['log'] = []
        self.g.command('look')
        return '\n'.join(line['text'] for line in self.g.state['log'])

    def kill(self, kind='beetle'):
        enemy = self.g.spawn_creature(kind, self.g.p['room'])
        self.g.victory(enemy)
        return self.g.state['corpses'][-1]

    def test_combat_kill_leaves_named_body_and_look_keeps_rewards_unchanged(self):
        enemy = self.g.enemy()
        enemy['hp'] = 1
        spec = self.g.w['enemies'][enemy['type']]
        spec.update(gold=[2, 2], loot=[dict(item='apple', weight=1)])
        xp, gold = self.g.p['xp'], self.g.p['gold']
        apples = self.g.p['inventory'].count('apple')
        self.g.command('kill beetle')
        self.g.strike()
        corpse = self.g.state['corpses'][0]
        self.assertEqual(enemy['hp'], 0)
        self.assertEqual(corpse['uid'], enemy['uid'])
        self.assertIn(corpse['name'], corpse['description'])
        self.assertIn(corpse['description'], self.look())
        self.assertIn(corpse['description'], self.look())
        snapshot = self.g.snapshot()
        self.assertEqual(snapshot['corpses'][0]['description'], corpse['description'])
        self.assertNotIn(enemy['uid'], [e['id'] for e in snapshot['enemies']])
        self.assertEqual(self.g.p['xp'], xp + spec['xp'])
        self.assertEqual(self.g.p['gold'], gold + 2)
        self.assertEqual(self.g.p['inventory'].count('apple'), apples + 1)

    def test_nonharvestable_body_is_visible_without_blocking_harvesting(self):
        corpse = self.kill('goblin')
        self.assertFalse(self.g.w['enemies']['goblin'].get('harvest'))
        self.assertIn(corpse['description'], self.look())
        self.assertFalse(self.g.snapshot()['corpses'][0]['harvestable'])
        inventory = list(self.g.p['inventory'])
        with self.assertRaises(ValueError):
            self.g.harvest(corpse['uid'])
        self.assertEqual(self.g.p['inventory'], inventory)
        beetle = self.kill()
        self.g.harvest('')
        self.assertTrue(beetle['harvested'])
        self.assertIn('beetle_meat', self.g.p['inventory'])
        self.assertEqual([c['id'] for c in self.g.snapshot()['corpses']], [corpse['uid']])
        self.assertNotIn(beetle['description'], self.look())
        with self.assertRaises(ValueError):
            self.g.harvest(beetle['uid'])

    def test_random_description_is_preserved_by_look_and_save_reload(self):
        corpses = [self.kill() for _ in range(12)]
        self.assertGreater(len({c['description'] for c in corpses}), 1)
        for corpse in corpses:
            self.assertIn(corpse['description'], [s.format(name=corpse['name']) for s in CORPSE_DESCRIPTIONS])
        before = copy.deepcopy(corpses)
        self.look()
        self.g.save()
        self.g.db.close()
        self.g = Game(self.path, self.db, clock=lambda: self.now)
        self.look()
        self.assertEqual(self.g.state['corpses'], before)
        self.assertEqual([c['description'] for c in self.g.snapshot()['corpses']], [c['description'] for c in before])

    def test_older_saved_remains_work_without_new_fields(self):
        corpse = self.kill()
        del corpse['description']
        del corpse['released']
        self.g.save()
        self.g.db.close()
        self.g = Game(self.path, self.db, clock=lambda: self.now)
        expected = f'The corpse of {corpse["name"]} lies here.'
        self.assertIn(expected, self.look())
        self.assertEqual(self.g.snapshot()['corpses'][0]['description'], expected)
        self.assertTrue(self.g.snapshot()['corpses'][0]['harvestable'])
        self.g.harvest(corpse['uid'])
        self.assertIn('beetle_meat', self.g.p['inventory'])

    def test_room_darkness_and_configured_expiry_apply_to_look_and_panel(self):
        self.g.w['revision']['corpse_seconds'] = 17
        corpse = self.kill()
        self.g.p['room'] = 'square'
        self.assertNotIn(corpse['description'], self.look())
        self.assertEqual(self.g.snapshot()['corpses'], [])
        self.g.p['room'] = 'meadow'
        self.g.w['rooms']['meadow']['dark'] = True
        self.assertFalse(self.g.visible())
        self.assertNotIn(corpse['description'], self.look())
        self.assertEqual(self.g.snapshot()['corpses'], [])
        self.g.p['inventory'].append('lantern')
        self.now += 16
        self.assertIn(corpse['description'], self.look())
        self.now += 1
        self.assertNotIn(corpse['description'], self.look())
        self.assertEqual(self.g.snapshot()['corpses'], [])
        self.assertEqual(self.g.state['corpses'], [])

    def test_respawn_keeps_distinct_old_and_new_corpses(self):
        enemy = self.g.enemy()
        self.g.victory(enemy)
        first = self.g.state['corpses'][-1]
        enemy['respawn_at'] = self.now
        replacement = self.g.enemy()
        self.assertNotEqual(replacement['uid'], first['uid'])
        self.assertIn(first['description'], self.look())
        self.g.victory(replacement)
        corpses = self.g.snapshot()['corpses']
        self.assertEqual(len(corpses), 2)
        self.assertEqual(len({c['id'] for c in corpses}), 2)

    def test_released_creature_leaves_body_without_rewards_or_harvest(self):
        enemy = self.g.spawn_creature('beetle', 'meadow')
        enemy['released'] = True
        before = (self.g.p['xp'], self.g.p['gold'], list(self.g.p['inventory']))
        self.g.victory(enemy)
        corpse = self.g.state['corpses'][-1]
        self.assertIn(corpse['description'], self.look())
        self.assertFalse(self.g.snapshot()['corpses'][0]['harvestable'])
        with self.assertRaises(ValueError):
            self.g.harvest(enemy['uid'])
        self.assertEqual((self.g.p['xp'], self.g.p['gold'], self.g.p['inventory']), before)


if __name__ == '__main__':
    unittest.main()
