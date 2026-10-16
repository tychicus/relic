"""Descriptions must agree with real casts, spending and race/class progression."""
import copy
import json
import random
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from engine import Game, validate

ROOT = Path(__file__).resolve().parents[1]


class SkillDetailsBalanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'world.json'
        world = json.loads((ROOT / 'content/world.json').read_bytes())
        world['regions'] = {}
        self.path.write_text(json.dumps(world), encoding='utf-8')
        self.now = 1000.
        self.db = Path(self.temp.name) / 'game.db'
        self.g = Game(self.path, self.db, random.Random(9), lambda: self.now)
        self.g.create('Tester', 'human', 'mage')

    def tearDown(self):
        self.g.db.close()
        self.temp.cleanup()

    def fight(self):
        self.g.p.update(room='meadow', mana=1000)
        self.g.w['settings']['hit_chance'] = 1
        self.g.w['enemies']['beetle'].update(hp=10000, dodge=0, resistances=[])
        enemy = self.g.enemy()
        enemy['hp'] = 10000
        return enemy

    def text(self, command):
        before = self.g.state['sequence']
        self.g.command(command)
        return '\n'.join(r['text'] for r in self.g.state['log'] if r['id'] > before and r['kind'] != 'command')

    def test_fireball_descriptions_match_casts_for_each_class(self):
        for cls, damage, mana in [('mage', 16, 6), ('warrior', 6, 12), ('rogue', 8, 9), ('cleric', 10, 8)]:
            with self.subTest(cls=cls):
                self.g.p.update(**{'class': cls}, cooldowns={}, action_ready=0, combat=None)
                enemy = self.fight()
                self.g.w['skills']['fireball']['description'] = 'No mana cost; 999 damage.'
                profile = self.g.skill_profile('fireball')
                self.assertEqual((profile['damage'], profile['mana']), ([damage, damage], mana))
                for text in [self.text('help fireball'), self.text('skills'), next(s for s in self.g.snapshot()['player_skills'] if s['id'] == 'fireball')['description']]:
                    self.assertNotIn('999 damage', text)
                    self.assertNotIn('No mana cost', text)
                before_mana = self.g.p['mana']
                with patch.object(self.g.rng, 'random', return_value=0):
                    self.g.activate_skill('fireball')
                self.assertEqual(10000 - enemy['hp'], damage)
                self.assertEqual(self.g.p['mana'], before_mana - mana)
                self.assertEqual(self.g.p['cooldowns']['fireball'], self.now + profile['cooldown'])
                self.assertEqual(self.g.p['action_ready'], self.now + profile['recovery'])
                self.now += 30

    def test_next_rank_matches_purchase_and_cast_without_preview_side_effects(self):
        self.g.p['level'] = 6
        before, rng = copy.deepcopy(self.g.state), self.g.rng.getstate()
        for sid in self.g.w['skills']:
            self.g.skill_facts(sid)
            self.g.next_skill_rank(sid)
        self.assertEqual(self.g.state, before)
        self.assertEqual(self.g.rng.getstate(), rng)
        preview = self.g.next_skill_rank('fireball')
        self.assertIn('16 → 18', ' '.join(preview['lines']))
        self.assertEqual((preview['rank'], preview['cost'], preview['required_level']), (2, 1, 6))
        self.assertIn('16 → 18', self.text('learn'))
        self.assertEqual(self.g.ability_points(), 1)
        self.g.learn_ability('fireball')
        self.assertEqual(self.g.ability_points(), 0)
        enemy = self.fight()
        with patch.object(self.g.rng, 'random', return_value=0): self.g.activate_skill('fireball')
        self.assertEqual(10000 - enemy['hp'], 18)
        self.assertEqual(self.g.skill_profile('fireball')['damage'], [18, 18])

    def test_physical_range_includes_dual_wield_and_temporary_enchantment(self):
        self.g.p.update(**{'class': 'warrior'}, level=15)
        self.g.p['learned_skills']['kick'] = 2
        right = self.g.new_instance(dict(kind='weapon', item='rusted_sword', bonus=0, enchantment=dict(bonus=4, until=self.now + 60)))
        self.g.p['equipment'] = dict(weapon=right, left_hand='iron_sword')
        profile = self.g.skill_profile('kick')
        cls = self.g.w['classes']['warrior']
        base_extra = self.g.item(right)['damage'] + self.g.item('iron_sword')['damage'] * self.g.rules()['offhand_scale'] + 14 * self.g.w['settings']['damage_per_level']
        expected = [max(1, round((roll + base_extra) * 1.25 * 1.1)) for roll in cls['damage']]
        self.assertEqual(profile['damage'], expected)
        enemy = self.fight()
        for roll, damage in zip(cls['damage'], expected):
            enemy['hp'] = 10000
            self.g.p.update(cooldowns={}, action_ready=0)
            with patch.object(self.g.rng, 'random', return_value=0), patch.object(self.g.rng, 'randint', return_value=roll):
                self.g.activate_skill('kick')
            self.assertEqual(10000 - enemy['hp'], damage)

    def test_spell_and_weapon_status_effects_follow_actual_rules(self):
        self.g.p['spell_xp'] = {'fireball': 100}
        self.g.p['learned_skills']['fireball'] = 2
        skill = self.g.w['skills']['fireball']
        skill['magic_levels'][1].update(effect_damage=7, mana_cost=13)
        self.g.w['status_effects']['scorched']['duration'] = 5
        skill['status_effects'][0]['duration'] = 0
        profile = self.g.skill_profile('fireball')
        self.assertEqual(profile['mana'], 13)
        self.assertEqual(profile['effects'][0]['damage'], 8)
        self.assertEqual(profile['effects'][0]['duration'], 5)
        enemy = self.fight()
        with patch.object(self.g.rng, 'random', return_value=0): self.g.activate_skill('fireball')
        active = enemy['effects'][0]
        self.assertEqual((active['remaining'], active['damage_override']), (5, 8))
        before = enemy['hp']; self.g.pulse_effects(enemy)
        self.assertEqual(before - enemy['hp'], 8)
        self.g.w['items']['rusted_sword']['status_effects'] = [dict(effect='slowed', chance=50, duration=2)]
        self.assertEqual(self.g.skill_profile('kick')['effects'][0]['source'], 'weapon')
        self.assertFalse(any(e['source'] == 'weapon' for e in self.g.skill_profile('fireball')['effects']))
        self.assertEqual(self.g.skill_profile('enchanting')['effects'], [])  # Legacy authored attachment is not applied by crafting.

    def test_passive_and_crafting_rank_previews_do_not_invent_benefits(self):
        self.g.p.update(**{'class': 'warrior'}, level=6)
        self.g.p['learned_skills'] = {'swordplay': 1}
        expected = self.g.skill_profile('swordplay', 2)['damage']
        self.assertIn('Automatic-attack bonus: 0% → 10%', ' '.join(self.g.next_skill_rank('swordplay')['lines']))
        self.g.learn_ability('swordplay')
        self.assertEqual(self.g.skill_profile('swordplay')['damage'], expected)
        self.g.p['learned_skills']['sharpening'] = 1
        self.assertIsNone(self.g.next_skill_rank('sharpening'))
        self.g.w['skills']['sharpening']['max_rank'] = 2
        self.assertIn('No numeric benefit', ' '.join(self.g.next_skill_rank('sharpening')['lines']))
        self.g.w['revision']['learning_enabled'] = False
        self.assertIsNone(self.g.next_skill_rank('swordplay'))
        self.assertFalse(self.g.skill_profile('swordplay')['passive'])

    def test_zero_modifiers_and_disabled_mana_are_reported(self):
        self.g.w['revision']['mana_enabled'] = False
        self.g.w['races']['human']['magic_power'] = 0
        self.assertEqual(self.g.skill_profile('fireball')['damage'], [0, 0])
        self.assertEqual(self.g.skill_profile('fireball')['mana'], 0)
        self.assertEqual(self.g.skill_profile('fireball')['effects'][0]['chance'], 0)
        self.assertEqual(self.g.skill_profile('mend')['healing'], 1)

    def test_class_roles_hold_at_all_character_levels(self):
        for race in ('human', 'elf'):
            for level in range(1, 101):
                stats = {c: self.g.character_stats(race, c, level, 10) for c in self.g.w['classes']}
                self.assertGreater(stats['warrior']['hp'], stats['rogue']['hp'])
                self.assertGreater(stats['rogue']['hp'], stats['mage']['hp'])
                self.assertGreater(stats['mage']['hp'], stats['cleric']['hp'])
                self.assertGreater(stats['cleric']['mana'], stats['mage']['mana'])
                self.assertGreater(stats['mage']['mana'], stats['rogue']['mana'])
        for cls in ('warrior', 'rogue'):
            for level in (1, 25, 100):
                hp = [self.g.character_stats(race, cls, level)['hp'] for race in ('elf', 'human', 'orc')]
                self.assertTrue(hp[0] < hp[1] < hp[2])
                self.assertEqual(self.g.character_stats('orc', cls, level)['mana'], 0)

    def test_elf_magic_bonus_and_practice_are_real_but_character_xp_is_unchanged(self):
        self.g.p.update(race='elf', mana=1000)
        self.assertEqual(self.g.max_hp(), 42)
        self.assertEqual(self.g.max_mana(), 46)
        enemy = self.fight()
        with patch.object(self.g.rng, 'random', return_value=0): self.g.activate_skill('fireball')
        self.assertEqual(10000 - enemy['hp'], 18)
        self.assertEqual(self.g.p['spell_xp']['fireball'], 2.5)
        self.assertEqual(self.g.p['mana_xp'], 2.5)
        self.assertEqual(self.g.p['xp'], 0)
        self.assertEqual(self.g.ability_points(), 0)

    def test_elf_mana_practice_bonus_also_applies_to_paid_crafting(self):
        self.g.p.update(race='elf', level=10, gold=1000, mana=1000)
        self.g.p['learned_skills']['enchanting'] = 1
        self.g.w['revision']['enchant_base'] = 100
        self.g.activate_skill('enchanting', 'right')
        self.assertEqual(self.g.p['mana_xp'], 1.25)
        self.assertEqual(self.g.enchant_progress()['xp'], 1)  # Crafting mastery is separate.

    def test_cleric_starter_heals_and_divine_affinity_beats_mage(self):
        other = Game(self.path, ':memory:', clock=lambda: self.now)
        try:
            state = other.create('Healer', 'human', 'cleric')
            self.assertEqual((other.p['hp'], other.p['mana']), (40, 55))
            self.assertEqual(other.p['learned_skills'], {'healing_light': 1})
            self.assertEqual(next(s for s in state['player_skills'] if s['id'] == 'healing_light')['details']['profile']['healing'], 21)
            other.p['hp'] = 10
            other.activate_skill('healing_light')
            self.assertEqual((other.p['hp'], other.p['mana']), (31, 51))
            self.assertEqual(other.p['spell_xp']['healing_light'], 1.25)
            self.assertEqual(other.p['mana_xp'], 1.25)
            for sid in ('mend', 'holy_ward'):
                key = 'healing' if sid == 'mend' else 'reduction'
                self.assertGreater(other.skill_profile(sid)[key], self.g.skill_profile(sid)[key])
                self.assertLess(other.mana_cost(sid), self.g.mana_cost(sid))
            self.assertLess(other.skill_profile('fireball')['damage'][0], self.g.skill_profile('fireball')['damage'][0])
        finally: other.db.close()

    def test_ward_cast_reduces_real_attacks_expires_and_is_atomic_on_rejection(self):
        self.g.p.update(**{'class': 'cleric'}, level=5)
        self.g.learn_ability('holy_ward')
        self.g.w['skills']['holy_ward']['cooldown'] = 3
        profile = self.g.skill_profile('holy_ward')
        before = copy.deepcopy(self.g.p)
        with self.assertRaisesRegex(ValueError, 'affect you'): self.g.activate_skill('holy_ward', 'beetle')
        self.assertEqual(self.g.p, before)
        self.g.activate_skill('holy_ward')
        self.assertEqual(self.g.active_ward()['power'], 26)
        self.assertEqual(self.g.p['mana'], before['mana'] - profile['mana'])
        self.assertEqual(self.g.p['action_ready'], self.now + profile['recovery'])
        self.now += 3
        before = copy.deepcopy(self.g.p)
        with self.assertRaisesRegex(ValueError, 'already active'): self.g.activate_skill('holy_ward')
        self.assertEqual(self.g.p, before)
        enemy = self.fight()
        self.g.p.update(hp=500, equipment={})
        self.g.w['enemies']['beetle'].update(damage=[20,20], status_effects=[])
        with patch.object(self.g.rng, 'random', return_value=0): self.g.enemy_strike(enemy)
        self.assertEqual(self.g.p['hp'], 485)  # round(20 * .74)
        self.assertEqual(self.g.warded_damage(1), 1)
        self.g.p['effects'] = [dict(id='scorched', remaining=1, stacks=1, damage_override=10)]
        self.g.pulse_effects(self.g.p)
        self.assertEqual(self.g.p['hp'], 475)  # Wards do not reduce status damage.
        self.now += 9
        self.assertIsNone(self.g.active_ward())
        with patch.object(self.g.rng, 'random', return_value=0): self.g.enemy_strike(enemy)
        self.assertEqual(self.g.p['hp'], 455)

    def test_ward_cap_rank_preview_save_and_death(self):
        self.g.p.update(**{'class': 'cleric'}, race='elf', level=30, mana=1000)
        self.g.p['learned_skills']['holy_ward'] = 4
        self.g.p['spell_xp'] = {'holy_ward': 252450}
        preview = self.g.next_skill_rank('holy_ward')
        self.assertIn('No numeric benefit', ' '.join(preview['lines']))
        self.assertEqual(self.g.skill_profile('holy_ward')['reduction'], 60)
        self.g.activate_skill('holy_ward')
        self.g.save(); self.g.db.close()
        self.g = Game(self.path, self.db, clock=lambda: self.now)
        self.assertEqual(self.g.active_ward()['power'], 60)
        self.assertLessEqual(self.g.p['hp'], self.g.max_hp())
        self.g.death()
        self.assertIsNone(self.g.active_ward())

    def test_shared_recovery_description_keeps_existing_deadline_after_owner_edit(self):
        self.g.p['action_ready'] = self.now + 2
        self.g.w['revision']['action_recovery'] = 0
        self.assertEqual(self.g.skill_recovery_lines('fireball'), ['Shared recovery remaining: 2s.'])
        self.assertEqual(self.g.skill_recovery_lines('sharpening'), [])
        self.assertNotIn('Does not use or wait', ' '.join(self.g.skill_facts('fireball')['lines']))

    def test_owner_edits_refresh_real_values_and_validate_new_fields(self):
        world = copy.deepcopy(self.g.w)
        world['races']['human'].update(hp_scale=.8, magic_power=1.5, magic_practice=1.4, mana_scale=1.25)
        world['classes']['mage']['hp_per_level'] = 5
        world['skills']['fireball']['magic_levels'][0].update(power=20, mana_cost=11)
        self.g.update_world(world)
        self.assertEqual((self.g.max_hp(), self.g.max_mana()), (40, 50))
        self.assertEqual(self.g.skill_profile('fireball')['damage'], [30,30])
        self.assertEqual(self.g.skill_profile('fireball')['mana'], 11)
        creation = Game(self.path, ':memory:')
        try:
            elf = next(r for r in creation.snapshot()['creation']['races'] if r['id'] == 'elf')
            self.assertEqual(elf['class_stats']['cleric']['hp'], 34)
            self.assertIn('cleric', elf['available_classes'])
        finally: creation.db.close()
        for group, ident, key, value in [('races','elf','hp_scale',0), ('races','elf','magic_practice',float('nan')), ('classes','cleric','hp_per_level',0), ('skills','holy_ward','duration',0)]:
            bad = copy.deepcopy(world); bad[group][ident][key] = value
            with self.assertRaises(ValueError): validate(bad)


if __name__ == '__main__': unittest.main()
