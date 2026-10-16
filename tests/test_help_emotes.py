"""Player-facing command help and owner-authored cosmetic actions."""
import copy
import json
import random
import tempfile
import unittest
from pathlib import Path

from engine import Game, validate
from help_system import COMMANDS, TOPICS

ROOT = Path(__file__).resolve().parents[1]


class HelpEmoteTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.path = self.root / 'world.json'
        world = json.loads((ROOT / 'content/world.json').read_bytes())
        world['regions'] = {}  # Keep current learning/mana rules; isolate roaming.
        self.path.write_text(json.dumps(world), encoding='utf-8')
        self.now = 1000.
        self.database = self.root / 'game.sqlite3'
        self.g = Game(self.path, self.database, random.Random(5), lambda: self.now)
        self.g.create('Traveler', 'human', 'mage')

    def tearDown(self):
        self.g.db.close()
        self.temp.cleanup()

    def command(self, text):
        before = self.g.state['sequence']
        self.g.command(text)
        return '\n'.join(row['text'] for row in self.g.state['log']
                         if row['id'] > before and row['kind'] != 'command')

    def test_help_is_a_short_index_and_topics_are_specific(self):
        index = self.command('HELP')
        self.assertLess(len(index), 650)
        self.assertIn('HELP FIREBALL', index)
        self.assertIn('SYNTAX', index)
        combat = self.command('HELP COMBAT')
        self.assertIn('automatic attacks', combat)
        self.assertNotIn('DEPOSIT', combat)
        self.assertIn('PUT <creature> IN CAGE', self.command('HELP CAPTURE'))
        bank = self.command('HELP BANK')
        self.assertIn('DEPOSIT', bank)
        self.assertIn('survives death', bank)
        self.assertNotIn('KNOCKOUT', bank)

    def test_every_topic_skill_and_command_has_help(self):
        for topic in [*TOPICS, *COMMANDS, *self.g.w['skills']]:
            with self.subTest(topic=topic):
                result = self.command('HELP ' + topic)
                self.assertTrue(result)
                self.assertNotIn('No help found', result)
        for command in COMMANDS:
            with self.subTest(command=command):
                self.assertNotIn('No help found', self.command('SYNTAX ' + command))

    def test_skill_help_uses_live_cost_cooldown_and_power(self):
        skill = self.g.w['skills']['fireball']
        skill.update(mana_cost=17, cooldown=23)
        skill['magic_levels'][0]['mana_cost'] = 17
        self.g.p['cooldowns']['fireball'] = self.now + 7
        self.g.p['learned_skills']['fireball'] = 2
        result = self.command('HELP FIREBALL')
        self.assertIn(f'Mana: {self.g.mana_cost("fireball")} per use', result)
        self.assertIn('Cooldown: 23s', result)
        self.assertIn('Currently recovering: 7s', result)
        power = self.g.skill_power('fireball', self.g.spell_progress('fireball')['power'])
        self.assertIn(f'Damage on a hit: {power}', result)
        self.assertIn('Learned rank: 2/', result)
        self.assertNotIn('No mana cost', result)
        self.assertNotIn('Banked gold', result)

    def test_locked_and_ineligible_skill_help_explains_requirements(self):
        result = self.command('HELP FROSTBOLT')
        self.assertIn('Not learned yet', result)
        self.assertIn('Next rank:', result)
        self.g.p.update(race='orc', **{'class': 'warrior'})
        result = self.command('HELP FIREBALL')
        self.assertIn('Unavailable to your class or race', result)
        self.assertIn('CAST FIREBALL', result)

    def test_passive_help_and_syntax_do_not_suggest_casting(self):
        self.assertIn('is passive; it cannot be cast', self.command('SYNTAX SWORDPLAY'))
        self.assertIn('automatic-attack damage', self.command('HELP SWORDPLAY'))
        self.assertIn('Passive: 0 mana; no cooldown or shared recovery.', self.command('HELP SWORDPLAY'))

    def test_skill_and_topic_help_aliases(self):
        self.assertEqual(self.command('HELP QUICK STRIKE'), self.command('HELP QUICKSTRIKE'))
        self.assertEqual(self.command('HELP BANK'), self.command('HELP BANKING'))
        self.assertEqual(self.command('? combat'), self.command('HELP COMBAT'))
        self.assertIn('QUAFF <consumable>', self.command('SYNTAX DRINK'))
        self.assertIn('Example:', self.command('USAGE TALK'))

    def test_unknown_help_and_commands_suggest_without_actions(self):
        before = copy.deepcopy(self.g.p)
        self.assertIn('FIREBALL', self.command('HELP FIRBALL'))
        self.assertIn('Did you mean', self.command('SYNTAX DEPOST'))
        self.assertIn('ATTACK', self.command('ATACK BEETLE'))
        self.assertIn('Did you mean FIREBALL', self.command('CAST FIRBALL'))
        self.assertEqual(before, self.g.p)
        self.assertNotIn('choose a topic', self.command('HELP completelyunknown'))

    def test_malformed_commands_offer_specific_syntax(self):
        self.assertIn('SYNTAX CAST', self.command('CAST'))
        self.assertIn('SYNTAX PUT', self.command('PUT POTION'))
        self.assertIn('TALK <person>', self.command('TALK'))
        self.assertIn('TALK <person>', self.command('TALK TAMSIN ABOUT'))
        self.assertIn('GO <direction>', self.command('GO SIDEWAYS'))

    def test_conversation_aliases_reuse_authored_dialogue(self):
        expected = self.command('SAY HELLO TO TAMSIN')
        for command in ('TALK TAMSIN', 'TALK TO TAMSIN', 'CHAT TAMSIN', 'talk tam'):
            with self.subTest(command=command):
                self.assertEqual(expected, self.command(command))
        expected = self.command('SAY COOKING TO TAMSIN')
        self.assertEqual(expected, self.command('ASK TAMSIN ABOUT COOKING'))
        self.assertEqual(expected, self.command('TALK TO TAMSIN ABOUT COOKING'))
        self.assertIn('TAMSIN', self.command('TALK TAMSIM'))
        self.assertIn('ABOUT <phrase>', self.command('ASK TAMSIN'))

    def test_ambiguous_npc_names_require_clarification(self):
        self.g.w['npcs']['tamsin_two'] = dict(self.g.w['npcs']['tamsin'], name='Tamsin Younger')
        self.assertIn('Be more specific', self.command('TALK TAM'))
        self.assertIn('Hello, traveler', self.command('TALK TAMSIN'))

    def test_movement_inventory_and_item_aliases_preserve_actions(self):
        self.assertEqual(self.command('INVENTORY'), self.command('INV'))
        self.assertEqual(self.command('LOOK SELF'), self.command('INSPECT SELF'))
        self.command('GO W')
        self.assertEqual(self.g.p['room'], self.g.w['rooms']['square']['exits']['west'])
        self.command('MOVE EAST')
        self.assertEqual(self.g.p['room'], 'square')
        self.assertIn('full health', self.command('DRINK POTION'))

    def test_multiword_skills_route_to_existing_cast_parser(self):
        self.assertEqual(self.command('CAST QUICK STRIKE'), self.command('QUICK STRIKE'))
        self.g.w['skills']['custom_bolt'] = dict(self.g.w['skills']['fireball'], name='Silver Bolt')
        self.g.p['learned_skills']['custom_bolt'] = 1
        self.assertIn('SILVER BOLT', self.command('HELP SILVER BOLT'))
        self.assertEqual(self.command('CAST SILVER BOLT'), self.command('SILVER BOLT'))

    def test_duplicate_skill_names_never_silently_pick_one(self):
        self.g.w['skills']['other_fire'] = dict(self.g.w['skills']['fireball'])
        self.assertIn('unique full skill name or its ID', self.command('HELP FIREBALL'))
        self.assertIn('unique full skill name or its ID', self.command('FIREBALL'))

    def test_emotes_list_help_aliases_and_targeting(self):
        self.assertIn('WAVE [target]', self.command('HELP EMOTES'))
        self.assertIn('Cosmetic only', self.command('HELP WAVE'))
        self.assertIn('WAVEHELLO', self.command('SYNTAX WAVE'))
        self.assertEqual(self.command('WAVE TAMSIN'), 'Traveler waves to Tamsin.')
        self.assertEqual(self.command('EMOTE WAVE TAMSIN'), 'Traveler waves to Tamsin.')
        self.assertEqual(self.command('WAVEHELLO SELF'), 'Traveler waves to Traveler.')
        self.assertEqual(self.command('SOCIAL SMILE'), 'Traveler smiles.')
        self.assertIn('does not take a target', self.command('SIGH TAMSIN'))
        self.assertIn('Did you mean WAVE', self.command('EMOTE WAE'))

    def test_emotes_do_not_change_character_resources_or_trigger_dialogue(self):
        self.g.w['npcs']['tamsin']['dialogue'].append(dict(phrase='wave', response='DIALOGUE_TRIGGER'))
        before = copy.deepcopy(self.g.p)
        for command in ('WAVE TAMSIN', 'CHEER', 'ME Waves toward Tamsin.'):
            self.assertNotIn('DIALOGUE_TRIGGER', self.command(command))
        self.assertEqual(before, self.g.p)
        self.assertEqual(self.g.state['log'][-1]['kind'], 'emote')
        self.assertEqual(self.g.state['log'][-1]['text'], 'Traveler Waves toward Tamsin.')

    def test_emote_targets_must_be_visible_here(self):
        self.assertIn('do not see', self.command('WAVE LILLA'))
        self.g.w['rooms']['square']['dark'] = True
        self.g.p['inventory'] = []
        self.assertIn('too dark', self.command('WAVE TAMSIN'))
        self.assertEqual(self.command('WAVE SELF'), 'Traveler waves to Traveler.')

    def test_custom_emotes_save_reload_and_disable(self):
        world = copy.deepcopy(self.g.w)
        world['emotes']['salute'] = dict(name='Royal Salute', command='salute', aliases=['sal'],
            enabled=True, description='A formal greeting.', message='{actor} salutes.',
            target_message='{actor} salutes {target}.')
        self.g.update_world(world)
        self.assertIn('A formal greeting', self.command('HELP ROYAL SALUTE'))
        self.assertEqual(self.command('EMOTE ROYAL SALUTE TAMSIN'), 'Traveler salutes Tamsin.')
        self.g.db.close()
        self.g = Game(self.path, self.database, clock=lambda: self.now)
        self.assertEqual(self.command('SAL'), 'Traveler salutes.')
        world['emotes']['salute']['enabled'] = False
        self.g.update_world(world)
        self.assertIn('Unknown command', self.command('SAL'))
        self.assertNotIn('SALUTE', self.command('HELP EMOTES'))
        self.assertIn('No help found', self.command('HELP SALUTE'))

    def test_legacy_world_without_emotes_keeps_help_and_freeform_actions(self):
        world = copy.deepcopy(self.g.w)
        world.pop('emotes')
        self.g.update_world(world)
        self.assertIn('No preset emotes', self.command('EMOTES'))
        self.assertEqual(self.command('ME waits.'), 'Traveler waits.')
        self.assertIn('CAST FIREBALL', self.command('HELP FIREBALL'))

    def test_conflicting_commands_and_unsafe_templates_rejected_atomically(self):
        original = copy.deepcopy(self.g.w)
        disk = self.path.read_bytes()
        for field, value in [('command', 'attack'), ('command', 'fireball'),
                             ('command', 'bad command'), ('aliases', ['look']),
                             ('aliases', ['smile']), ('aliases', ['wave']),
                             ('name', 'Fireball'), ('name', 'Smile'),
                             ('message', '{actor.__class__}'), ('message', '{target}'),
                             ('message', ''), ('target_message', '{unknown}'),
                             ('enabled', 'yes')]:
            with self.subTest(field=field, value=value):
                bad = copy.deepcopy(original)
                bad['emotes']['wave'][field] = value
                with self.assertRaises(ValueError): self.g.update_world(bad)
                self.assertEqual(self.g.w, original)
                self.assertEqual(self.path.read_bytes(), disk)
        validate(original)

    def test_no_hidden_conversation_phrases_in_help(self):
        for enemy in self.g.w['enemies'].values():
            enemy['conversations'] = [dict(phrase='SECRET_TEST_PHRASE', response='secret', attack=True)]
        for topic in TOPICS:
            self.assertNotIn('SECRET_TEST_PHRASE', self.command('HELP ' + topic))


if __name__ == '__main__':
    unittest.main()
