from legacy_fixture import disable_regions
"""Dodge regression tests. Uses temporary data, never the player's live save."""
import copy
import json
import random
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock
from engine import Game, validate

ROOT = Path(__file__).resolve().parents[1]

class DodgeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'world.json'
        self.path.write_bytes((ROOT / 'content/world.json').read_bytes())
        disable_regions(self.path);self.g = Game(self.path, Path(self.temp.name) / 'test.sqlite3', random.Random(17), lambda: 1000.0)
        self.g.create('Dodge tester')
        self.g.p['room'] = 'meadow'
        self.spec = self.g.w['enemies']['beetle']
        self.spec.pop('dodge', None)
        self.g.w['settings']['hit_chance'] = 1
        self.g.enemy()['hp'] = 1000
    def tearDown(self):
        self.g.db.close()
        self.temp.cleanup()

    def test_legacy_and_explicit_zero_preserve_same_random_outcome(self):
        self.g.strike()
        legacy_hp = self.g.enemy()['hp']
        legacy_rng = self.g.rng.getstate()
        self.g.enemy()['hp'] = 1000
        self.g.rng = random.Random(17)
        self.spec['dodge'] = 0
        self.g.strike()
        self.assertEqual(self.g.enemy()['hp'], legacy_hp)
        self.assertEqual(self.g.rng.getstate(), legacy_rng)

    def test_full_dodge_consumes_basic_turn_without_damage_or_rewards(self):
        self.spec['dodge'] = 100
        before = (self.g.p['xp'], self.g.p['gold'], self.g.p['inventory'][:])
        self.g.start_combat(); self.g.tick()
        self.assertEqual(self.g.enemy()['hp'], 1000)
        self.assertEqual(self.g.p['combat']['turn'], 'enemy')
        self.assertIn('dodges your attack', self.g.state['log'][-1]['text'])
        self.assertEqual(before, (self.g.p['xp'], self.g.p['gold'], self.g.p['inventory']))

    def test_dodged_bash_still_uses_its_cooldown(self):
        self.spec['dodge'] = 100
        self.g.start_combat()
        self.g.p['combat']['next_at'] = 1002
        self.g.command('bash')
        self.assertEqual(self.g.enemy()['hp'], 1000)
        self.assertIn('dodges your Bash', self.g.state['log'][-1]['text'])
        self.assertEqual(self.g.p['cooldowns']['bash'], 1010)
        self.g.command('bash')
        self.assertIn('ready in', self.g.state['log'][-1]['text'])

    def test_percent_roll_boundary(self):
        self.spec['dodge'] = 20
        rng = Mock()
        rng.random.side_effect = [0.1, 0.1999]
        self.g.rng = rng
        self.g.strike()
        self.assertEqual(self.g.enemy()['hp'], 1000)
        rng.randint.assert_not_called()
        rng.random.side_effect = [0.1, 0.2]
        rng.randint.return_value = 5
        self.g.strike()
        self.assertLess(self.g.enemy()['hp'], 1000)

    def test_misses_do_not_also_roll_dodge(self):
        self.spec['dodge'] = 100
        self.g.w['settings']['hit_chance'] = 0.5
        rng = Mock(); rng.random.return_value = 0.9
        self.g.rng = rng
        self.g.strike()
        self.assertEqual(rng.random.call_count, 1)
        self.assertIn('misses', self.g.state['log'][-1]['text'])

    def test_invalid_percentages_are_rejected_without_writing(self):
        before = self.path.read_bytes()
        for value in (-1, 101, '20', True, None, float('nan'), float('inf')):
            with self.subTest(value=value):
                new = copy.deepcopy(self.g.w)
                new['enemies']['beetle']['dodge'] = value
                with self.assertRaisesRegex(ValueError, 'dodge'):
                    self.g.update_world(new)
                self.assertEqual(self.path.read_bytes(), before)
        for value in (0, 0.5, 20, 100):
            new = copy.deepcopy(self.g.w)
            new['enemies']['beetle']['dodge'] = value
            validate(new)

    def test_owner_dodge_change_survives_restart(self):
        new = copy.deepcopy(self.g.w)
        new['enemies']['beetle']['dodge'] = 37.5
        self.g.update_world(new)
        self.assertEqual(json.loads(self.path.read_text())['enemies']['beetle']['dodge'], 37.5)
        db = Path(self.temp.name) / 'test.sqlite3'
        self.g.db.close()
        self.g = Game(self.path, db, random.Random(17), lambda: 1000.0)
        self.assertEqual(self.g.w['enemies']['beetle']['dodge'], 37.5)
        self.assertEqual(self.g.p['name'], 'Dodge tester')

if __name__ == '__main__':
    unittest.main()
