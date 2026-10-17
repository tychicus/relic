"""On-demand recipe information uses live rules without cooking or learning."""
import copy
import json
from pathlib import Path
import random
import tempfile
import unittest

from engine import Game
from multiplayer import MultiplayerGame

ROOT = Path(__file__).resolve().parents[1]


class CookbookTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.path = self.root / 'world.json'
        world = json.loads((ROOT / 'content/world.json').read_bytes())
        world['regions'] = {}
        self.path.write_text(json.dumps(world), encoding='utf-8')
        self.database = self.root / 'game.sqlite3'
        self.g = Game(self.path, self.database, random.Random(5), lambda: 1000.)
        self.g.create('Cook', 'human', 'mage')

    def tearDown(self):
        self.g.db.close()
        self.temp.cleanup()

    def command(self, text):
        before = self.g.state['sequence']
        self.g.command(text)
        return '\n'.join(row['text'] for row in self.g.state['log']
                         if row['id'] > before and row['kind'] != 'command')

    def test_reading_lists_live_recipes_without_using_resources_or_rng(self):
        self.g.p['inventory'] += ['beetle_meat', 'beetle_meat']
        before = copy.deepcopy(self.g.p)
        rng = self.g.rng.getstate()
        result = self.command('LOOK COOKBOOK')
        self.assertIn('Beetle toast', result)
        self.assertIn('Ingredients: 1 × Beetle meat (carrying 2)', result)
        self.assertIn('Makes: 1 × Beetle toast', result)
        self.assertIn('restores up to 8 HP per serving', result)
        self.assertIn('Success chance: 100%', result)
        self.assertIn('COOK BEETLE TOAST', result)
        self.assertIn('a cooking fire', result)
        self.assertEqual(before, self.g.p)
        self.assertEqual(rng, self.g.rng.getstate())
        self.assertNotIn('Ingredients:', self.command('LOOK'))

    def test_owner_rules_and_readiness_update_with_inventory_and_location(self):
        recipe = self.g.w['recipes']['toast_beetle']
        self.g.w['recipes'] = {'toast_beetle': recipe}
        recipe.update(count=2, output_count=3, chance=65, consume_failure=True,
                      tool='lantern', skill='enchanting')
        self.g.p['inventory'] = ['beetle_meat']
        result = self.command('LOOK COOKBOOK')
        for text in ('Ingredients: 2 × Beetle meat (carrying 1)', 'Makes: 3 × Beetle toast',
                     'not carried', 'not learned', '65%', 'ingredients are consumed',
                     'not enough ingredients', 'a cooking fire', 'the required tool', 'the required skill'):
            self.assertIn(text, result)
        self.g.p['inventory'] += ['beetle_meat', 'lantern']
        self.g.p['learned_skills']['enchanting'] = 1
        self.g.p['room'] = next(rid for rid, room in self.g.w['rooms'].items() if room.get('cooking_fire'))
        result = self.command('LOOK COOKBOOK')
        self.assertIn('Ready to cook.', result)
        self.assertNotIn('Not ready:', result)
        self.assertIn('(carried)', result)
        self.assertIn('(ready)', result)
        recipe.update(fire=False, consume_failure=False)
        self.g.p['room'] = 'square'
        self.assertIn('Cooking fire: not required.', self.command('LOOK COOKBOOK'))
        self.assertIn('ingredients are kept', self.command('LOOK COOKBOOK'))
        self.g.w['items']['toasted_beetle']['heal'] = 11
        self.assertIn('up to 11 HP', self.command('LOOK COOKBOOK'))

    def test_reading_works_in_darkness_and_combat_without_preparing_food(self):
        self.g.w['rooms']['square']['dark'] = True
        self.g.p['inventory'] = []
        self.assertIn('COOKBOOK', self.command('LOOK COOKBOOK'))
        self.g.p['combat'] = {'engaged': [], 'next_at': 2000.}
        before = copy.deepcopy(self.g.p)
        # Direct inspection avoids advancing combat; commands retain their normal tick.
        self.g.look('cookbook')
        self.assertIn('finish combat', self.g.state['log'][-1]['text'])
        self.assertEqual(before, self.g.p)
        with self.assertRaisesRegex(ValueError, 'Finish combat'):
            self.g.cook('beetle toast')

    def test_renamed_food_cooks_and_existing_saved_food_keeps_working(self):
        self.g.p['inventory'] = ['toasted_beetle', 'beetle_meat']
        self.g.save()
        self.g.db.close()
        self.g = Game(self.path, self.database, clock=lambda: 1000.)
        self.assertEqual(self.g.item('toasted_beetle')['name'], 'Beetle toast')
        self.g.p['room'] = next(rid for rid, room in self.g.w['rooms'].items() if room.get('cooking_fire'))
        self.assertIn('Beetle toast is ready.', self.command('COOK BEETLE TOAST'))
        self.assertEqual(self.g.p['inventory'], ['toasted_beetle', 'toasted_beetle'])
        self.g.p['hp'] -= 8
        self.assertIn('recover 8 HP', self.command('EAT BEETLE TOAST'))
        self.assertEqual(self.g.p['inventory'], ['toasted_beetle'])
        self.assertIn('Beetle toast', self.command('COOK'))
        self.assertIn('LOOK COOKBOOK', self.command('COOK'))

    def test_help_and_inspection_aliases_and_empty_cookbook(self):
        help_text = self.command('HELP COOKBOOK')
        self.assertIn('LOOK COOKBOOK', help_text)
        self.assertIn('COOK BEETLE TOAST', help_text)
        for alias in ('HELP LOOK COOKBOOK', 'HELP RECIPES'):
            self.assertEqual(help_text, self.command(alias))
        for query in ('SYNTAX COOKBOOK', 'SYNTAX LOOK COOKBOOK', 'SYNTAX LOOK'):
            self.assertIn('COOKBOOK', self.command(query))
        self.assertIn('HELP COOKBOOK', self.command('HELP'))
        self.assertIn('LOOK COOKBOOK', self.command('HELP COOKING'))
        self.assertEqual(self.command('LOOK COOKBOOK'), self.command('inspect   cookbook'))
        self.g.w['recipes'] = {}
        self.assertIn('There are no recipes', self.command('LOOK COOKBOOK'))

    def test_multiplayer_cookbook_uses_only_requesting_players_inventory_and_log(self):
        self.g.db.close()
        self.g = MultiplayerGame(self.path, self.root / 'multiplayer.sqlite3', clock=lambda: 1000.)
        alice = self.g.create_character('Alice', owner=True)
        bob = self.g.create_character('Bob')
        with self.g.as_player(bob):
            bob_log = copy.deepcopy(self.g.state['log'])
        with self.g.as_player(alice):
            self.g.p['inventory'] += ['beetle_meat']
            self.assertIn('Beetle meat (carrying 1)', self.command('LOOK COOKBOOK'))
        with self.g.as_player(bob):
            self.assertEqual(bob_log, self.g.state['log'])
            self.assertIn('Beetle meat (carrying 0)', self.command('LOOK COOKBOOK'))


if __name__ == '__main__':
    unittest.main()
