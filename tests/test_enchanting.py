from legacy_fixture import disable_regions
import copy
import json
import random
import tempfile
import unittest
from pathlib import Path

from engine import Game, validate
from revision_rules import SCHEMA

ROOT = Path(__file__).resolve().parents[1]


class EnchantingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name)/'world.json'
        world = json.loads((ROOT/'content/world.json').read_bytes())
        # Crafting tests choose their own eligibility, independent of owner edits.
        world['skills']['enchanting'].update(unlock_level=3, allowed_classes=None)
        self.path.write_text(json.dumps(world), encoding='utf-8')
        self.db = Path(self.temp.name)/'save.sqlite3'
        self.now = 1000
        disable_regions(self.path);self.g = Game(self.path, self.db, random.Random(2), lambda:self.now)
        self.g.create('Tester')
        self.g.p.update(level=7, gold=10000)
        self.g.w['revision'].update(enchant_base=100, enchant_destroy=0)

    def tearDown(self):
        self.g.db.close()
        self.temp.cleanup()

    def log(self):
        return '\n'.join(x['text'] for x in self.g.state['log'][-8:])

    def reload(self):
        self.path.write_text(json.dumps(self.g.w), encoding='utf-8')
        self.g.save()
        self.g.db.close()
        self.g = Game(self.path, self.db, clock=lambda:self.now)

    def test_kill_alias_matches_attack_and_target_errors(self):
        self.g.p['room'] = 'meadow'
        self.g.w['enemies']['beetle']['aggressive'] = False
        before = copy.deepcopy(self.g.state)
        attack = self.g.command('attack beetle')['player']
        self.g.state = before
        self.g.p = before['player']
        kill = self.g.command('KiLl beetle')['player']
        self.assertEqual(attack, kill)
        self.assertIsNotNone(kill['combat'])

    def test_kill_no_target_ambiguity_and_visibility(self):
        self.g.command('kill missing')
        self.assertIsNone(self.g.p['combat'])
        self.g.p['room'] = 'meadow'
        self.g.w['enemies']['beetle']['aggressive'] = False
        self.g.w['enemies']['iron_beetle'] = dict(self.g.w['enemies']['beetle'],name='Iron beetle')
        self.g.w['rooms']['meadow']['population'] = [dict(id='extra',enemy='iron_beetle',count=1,chance=100)]
        self.g.command('kill beetle')
        self.assertIsNone(self.g.p['combat'])
        self.assertIn('distinct', self.log())
        self.g.w['rooms']['meadow']['dark'] = True
        self.g.command('kill')
        self.assertIn('dark', self.log())
        self.assertIsNone(self.g.p['combat'])
        self.g.w['rooms']['meadow']['dark'] = False
        self.g.command('kill')
        self.assertIsNotNone(self.g.p['combat'])

    def test_named_weapon_only_changes_held_copy(self):
        self.g.p['inventory'] += ['iron_sword', 'iron_sword']
        self.g.command('equip iron sword')
        self.g.command('enchant Iron Sword')
        iid = self.g.p['equipment']['weapon']
        item = self.g.item(iid)
        self.assertEqual(item['damage'], self.g.w['items']['iron_sword']['damage']+1)
        self.assertTrue(item['enchanted'])
        self.assertIn('iron_sword', self.g.p['inventory'])
        self.assertNotIn('enchanted', self.g.item('iron_sword'))
        self.assertIn('shimmers', item['description'])

    def test_named_target_is_not_ignored_and_invalid_spends_nothing(self):
        self.g.p['inventory'].append('iron_sword')
        before = copy.deepcopy(self.g.p)
        for command in ('enchant iron sword', 'enchant nonexistent', 'enchant potion'):
            self.g.command(command)
            self.assertEqual(before, self.g.p)
        self.assertEqual(self.g.state['instances'], {})

    def test_left_weapon_target_and_explicit_hand_with_identical_items(self):
        self.g.p['inventory'].append('rusted_sword')
        self.g.command('equip rusted sword left')
        self.g.command('enchant rusted sword')
        self.assertNotIn('proficiencies', self.g.p)
        self.assertIn('ENCHANT LEFT', self.log())
        self.g.command('enchant left')
        self.assertEqual(self.g.p['equipment']['weapon'], 'rusted_sword')
        self.assertTrue(self.g.item(self.g.p['equipment']['left_hand'])['enchanted'])

    def test_armor_worn_and_held_are_eligible(self):
        self.g.command('enchant leather vest')
        iid = self.g.p['equipment']['armor']
        self.assertEqual(self.g.item(iid)['armor'], self.g.w['items']['leather_vest']['armor']+1)
        self.g.command('unequip armor')
        self.g.command('hold '+iid)
        self.now += 16
        self.g.command('enchant left')
        self.assertEqual(self.g.p['equipment']['left_hand'], iid)
        self.reload()
        self.assertTrue(self.g.item(iid)['enchanted'])
        self.g.command('unequip left')
        self.g.command('equip '+iid+' right')
        self.now += 16
        self.g.command('enchant right')
        self.reload()
        self.assertEqual(self.g.p['equipment']['weapon'], iid)

    def test_shield_can_be_enchanted(self):
        self.g.p['inventory'].append('buckler')
        self.g.command('equip buckler')
        self.g.command('enchant buckler')
        iid = self.g.p['equipment']['left_hand']
        self.assertEqual(self.g.item(iid)['armor'], self.g.w['items']['buckler']['armor']+1)

    def test_armor_bonus_affects_combat_and_expires(self):
        self.g.command('enchant leather vest')
        iid = self.g.p['equipment']['armor']
        self.g.p['room'] = 'meadow'
        self.g.w['settings']['hit_chance'] = 1
        self.g.w['enemies']['beetle']['damage'] = [20,20]
        enemy = self.g.enemy()
        hp = self.g.p['hp']
        self.g.enemy_strike(enemy)
        boosted_damage = hp-self.g.p['hp']
        self.now += 300
        hp = self.g.p['hp']
        self.g.enemy_strike(enemy)
        self.assertEqual(hp-self.g.p['hp'], boosted_damage+1)
        self.assertFalse(self.g.item(iid)['enchanted'])

    def test_weapon_bonus_changes_real_damage_and_returns_to_base(self):
        self.g.command('enchant rusted sword')
        self.g.p['room'] = 'meadow'
        self.g.w['settings']['hit_chance'] = 1
        self.g.w['classes']['warrior']['damage'] = [5,5]
        self.g.w['enemies']['beetle']['dodge'] = 0
        e = self.g.enemy()
        e['hp'] = 10000
        self.g.strike()
        enchanted = 10000-e['hp']
        hp = e['hp']
        self.now += 300
        self.g.strike()
        self.assertEqual(enchanted, hp-e['hp']+1)

    def test_display_in_look_inventory_equipment_and_snapshot(self):
        self.g.w['items']['leather_vest']['armor'] = 10
        self.g.w['revision']['enchant_bonus'] = 3
        self.g.command('enchant leather vest')
        iid = self.g.p['equipment']['armor']
        for cmd in ('look '+iid, 'look self', 'equipment', 'unequip armor', 'inventory'):
            self.g.command(cmd)
            if cmd != 'unequip armor':
                self.assertIn('Armor 10 (+3)', self.log())
                self.assertIn('Enchanted:', self.log())
        item = self.g.snapshot()['items'][iid]
        self.assertEqual((item['base_armor'],item['armor'],item['enchantment_bonus']), (10,13,3))
        self.assertIn('enchanted', item['name'])
        self.g.state['log'] = []
        self.now += 300
        self.g.command('look '+iid)
        self.assertNotIn('(+3)', self.log())
        self.assertNotIn('Enchanted:', self.log())
        self.assertIn('fades', self.log())

    def test_slow_leveling_valid_failures_count_and_higher_levels_scale(self):
        self.g.w['revision'].update(enchant_base=0, enchant_level_gain=2)
        for n in range(99):
            self.g.activate_skill('enchanting','armor')
            self.now += 16
        self.assertEqual(self.g.enchant_progress()['level'], 1)
        self.assertEqual(self.g.enchant_progress()['xp'], 99)
        self.g.activate_skill('enchanting','armor')
        self.assertEqual(self.g.enchant_progress()['level'], 2)
        self.assertEqual(self.g.enchant_progress()['next_xp'], 150)
        self.assertEqual(self.g.enchant_progress()['chance'], 2)
        self.assertEqual(self.g.enchant_progress()['duration'], 360)
        self.g.p['proficiencies']['enchanting'] = 450
        p = self.g.enchant_progress()
        self.assertEqual((p['level'],p['bonus'],p['duration']), (4,2,480))
        self.assertIn('level 2', self.log())
        self.reload()
        self.assertEqual(self.g.enchant_progress()['level'], 4)

    def test_invalid_cost_cooldown_unlock_combat_and_class_no_xp(self):
        self.g.p['gold'] = 0
        with self.assertRaises(ValueError):self.g.activate_skill('enchanting')
        self.g.p['gold'] = 100
        self.g.p['cooldowns']['enchanting'] = self.now+10
        with self.assertRaises(ValueError):self.g.activate_skill('enchanting')
        self.g.p['cooldowns'] = {}
        self.g.p['level'] = 1
        with self.assertRaises(ValueError):self.g.activate_skill('enchanting')
        self.g.p['level'] = 7
        self.g.w['skills']['enchanting']['allowed_classes'] = []
        with self.assertRaises(ValueError):self.g.activate_skill('enchanting')
        self.g.w['skills']['enchanting']['allowed_classes'] = None
        self.g.p['combat'] = {'test':True}
        with self.assertRaises(ValueError):self.g.activate_skill('enchanting')
        self.assertNotIn('proficiencies', self.g.p)
        self.assertEqual(self.g.p['gold'], 100)
        self.assertEqual(self.g.state['instances'], {})

    def test_refresh_does_not_stack_and_offline_expiration_persists(self):
        self.g.command('enchant rusted sword')
        iid = self.g.p['equipment']['weapon']
        self.now += 200
        self.g.command('enchant '+iid)
        self.assertEqual(self.g.item(iid)['damage'], 3)
        self.reload()
        self.now += 299
        self.assertTrue(self.g.item(iid)['enchanted'])
        self.now += 1
        self.reload()
        self.assertEqual(self.g.item(iid)['damage'], 2)
        self.assertFalse(self.g.item(iid)['enchanted'])
        self.g.tick()
        self.assertNotIn('enchantment', self.g.state['instances'][iid])

    def test_stored_armor_preserves_identity_but_time_keeps_passing(self):
        self.g.command('enchant leather vest')
        iid = self.g.p['equipment']['armor']
        chest = self.g.grant('storage_chest')
        self.g.p['inventory'].append(chest)
        self.g.command('unequip armor')
        self.g.command('put '+iid+' in '+chest)
        self.reload()
        self.now += 300
        self.g.command('get '+iid+' from '+chest)
        self.g.command('equip '+iid)
        self.assertEqual(self.g.p['equipment']['armor'], iid)
        self.assertFalse(self.g.item(iid)['enchanted'])

    def test_legacy_proficiency_and_positive_bonus_migrate_once(self):
        self.g.p['proficiencies'] = {'enchanting':40}
        iid = self.g.new_instance(dict(kind='weapon',item='iron_sword',bonus=3,rank=3))
        self.g.p['equipment']['weapon'] = iid
        self.reload()
        inst = self.g.state['instances'][iid]
        deadline = inst['enchantment']['until']
        self.assertEqual(self.g.p['proficiencies']['enchanting'],40)
        self.assertEqual(self.g.item(iid)['enchantment_bonus'],3)
        self.now += 50
        self.reload()
        self.assertEqual(self.g.state['instances'][iid]['enchantment']['until'], deadline)
        self.now = deadline
        self.assertEqual(self.g.item(iid)['damage'], self.g.w['items']['iron_sword']['damage'])

    def test_weapon_failure_risk_respects_selected_slot_and_armor_is_unchanged(self):
        self.g.w['revision'].update(enchant_base=0,enchant_destroy=100)
        self.g.p['inventory'].append('iron_sword')
        self.g.command('equip iron sword left')
        self.g.command('enchant iron sword')
        self.assertNotIn('left_hand',self.g.p['equipment'])
        self.assertEqual(self.g.p['equipment']['weapon'],'rusted_sword')
        self.assertEqual(self.g.enchant_progress()['xp'],1)
        self.now += 16
        self.g.command('enchant armor')
        self.assertEqual(self.g.item(self.g.p['equipment']['armor'])['armor'],self.g.w['items']['leather_vest']['armor'])
        self.assertEqual(self.g.enchant_progress()['xp'],2)

    def test_cast_aliases_and_skills_report_progress(self):
        self.g.command('cast enchanting leather vest')
        self.assertTrue(self.g.item(self.g.p['equipment']['armor'])['enchanted'])
        self.now += 16
        self.g.command('skill enchant rusted sword')
        self.assertTrue(self.g.item(self.g.p['equipment']['weapon'])['enchanted'])
        self.g.command('skills')
        self.assertIn('skill level 1',self.log())
        self.assertIn('2/100 XP',self.log())
        self.assertEqual(self.g.snapshot()['player']['enchanting']['enchanting']['level'],1)

    def test_editor_controls_validation_and_modified_armor_reference(self):
        fields = SCHEMA['revision']
        for key in ('enchant_seconds','enchant_xp_per_attempt','enchant_level_cap','enchant_bonus_levels'):
            self.assertIn(key,fields)
            w = copy.deepcopy(self.g.w)
            w['revision'][key] = -1
            with self.assertRaises(ValueError):validate(w)
        self.g.command('enchant armor')
        w = copy.deepcopy(self.g.w)
        del w['items']['leather_vest']
        with self.assertRaises(ValueError):self.g.check_live_references(w)


if __name__ == '__main__':
    unittest.main()
