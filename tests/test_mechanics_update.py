from legacy_fixture import disable_regions
"""Combat timing, targeting, repairs and level-100 regression checks."""
import copy
import json
from pathlib import Path
import random
import tempfile
import unittest

from engine import Game, validate

ROOT = Path(__file__).resolve().parents[1]


class MechanicsUpdateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'world.json'
        self.path.write_bytes((ROOT / 'content/world.json').read_bytes())
        self.db = Path(self.temp.name) / 'save.db'
        self.now = 1000.
        disable_regions(self.path);self.g = Game(self.path, self.db, random.Random(3), lambda: self.now)
        self.g.create('Tester', 'human', 'mage')

    def tearDown(self):
        self.g.db.close()
        self.temp.cleanup()

    def reload(self):
        self.path.write_text(json.dumps(self.g.w), encoding='utf-8')
        self.g.save()
        self.g.db.close()
        self.g = Game(self.path, self.db, random.Random(3), lambda: self.now)

    def arena(self):
        self.g.p.update(level=4, room='meadow')
        self.g.w['settings']['hit_chance'] = 1
        self.g.w['enemies']['beetle']['dodge'] = 0
        self.g.w['skills']['fireball']['status_effects'] = []
        self.g.w['rooms']['meadow']['population'] = [dict(id='test', enemy='grassland_boar', count=1, chance=100)]
        self.g.w['enemies']['grassland_boar']['dodge'] = 0
        rows = self.g.creatures()
        for e in rows: e['hp'] = 1000
        self.g.p['attack_ready'] = self.now+100
        return {e['type']: e for e in rows}

    def damaged(self, equipped=True):
        iid = self.g.grant('elven_sword')
        self.g.state['instances'][iid].update(bonus=-3, magic_xp=700, enchantment=dict(bonus=2, until=self.now+300), sharpen_bonus=2, sharpen_until=self.now+120)
        if equipped: self.g.p['equipment']['weapon'] = iid
        else: self.g.p['inventory'].append(iid)
        self.g.p.update(room='shop', gold=100)
        return iid

    def test_level_table_and_mage_defaults(self):
        xp = self.g.w['settings']['level_xp']
        self.assertEqual(len(xp), 100)
        self.assertEqual(xp[:8], [0,30,100,250,550,1100,2200,4500])
        self.assertTrue(all(a<b for a,b in zip(xp,xp[1:])))
        self.assertEqual(self.g.max_hp(),50)
        self.assertIn('fireball',self.g.available_skill_ids())
        self.assertEqual(self.g.skill_power('fireball',0),16)
        self.g.p['level']=10
        self.g.require_skill('enchanting')

    def test_level_100_is_reached_and_survives_reload(self):
        self.g.p.update(level=99, xp=self.g.w['settings']['level_xp'][99]-1, room='meadow')
        self.g.w['enemies']['beetle']['xp']=1
        self.g.victory(self.g.enemy())
        self.assertEqual(self.g.p['level'],100)
        self.assertIsNone(self.g.snapshot()['player']['next_xp'])
        self.reload()
        self.assertEqual(self.g.p['level'],100)
        self.g.p['xp']+=1000000
        self.assertIsNone(self.g.snapshot()['player']['next_xp'])

    def test_unreachable_unlock_rejected_without_changing_world(self):
        before=self.path.read_bytes()
        w=copy.deepcopy(self.g.w);w['settings']['level_xp']=w['settings']['level_xp'][:8]
        with self.assertRaisesRegex(ValueError,'progression ends'):self.g.update_world(w)
        self.assertEqual(self.path.read_bytes(),before)
        w['skills']['enchanting']['unlock_level']=8
        validate(w)

    def test_named_shorthand_and_cast_spell_choose_requested_enemy(self):
        rows=self.arena()
        self.g.command('fireball grassland boar')
        self.assertEqual(rows['grassland_boar']['hp'],984)
        self.assertEqual(rows['beetle']['hp'],1000)
        self.g.p['combat']['next_at']=self.now+100
        self.now+=8
        self.g.command('cast fireball beetle')
        self.assertEqual(rows['beetle']['hp'],984)
        self.assertEqual(self.g.p['target'],rows['beetle']['uid'])
        self.assertIn(rows['beetle']['uid'],self.g.p['combat']['engaged'])

    def test_multiword_skill_name_and_target(self):
        rows=self.arena()
        self.g.w['skills']['sun_bolt']=dict(self.g.w['skills']['fireball'],name='Sun Bolt')
        self.g.command('cast Sun Bolt grassland boar')
        self.assertEqual(rows['grassland_boar']['hp'],984)

    def test_missing_ambiguous_and_dark_targets_spend_nothing(self):
        self.arena()
        self.g.w['enemies']['iron_beetle']=dict(self.g.w['enemies']['beetle'],name='Iron beetle')
        self.g.w['rooms']['meadow']['population'].append(dict(id='extra',enemy='iron_beetle',count=1,chance=100))
        for target in ('missing','beetle'):
            before=copy.deepcopy(self.g.p)
            self.g.command('fireball '+target)
            self.assertEqual(self.g.p,before)
        self.g.w['rooms']['meadow']['dark']=True
        before=copy.deepcopy(self.g.p);self.g.command('fireball grassland boar')
        self.assertEqual(self.g.p,before)

    def test_shared_recovery_and_individual_cooldown(self):
        self.arena()
        self.g.activate_skill('fireball','grassland boar')
        before=copy.deepcopy(self.g.p)
        with self.assertRaisesRegex(ValueError,'Recover'):self.g.activate_skill('lightning','beetle')
        self.assertEqual(self.g.p,before)
        self.now+=2
        self.g.activate_skill('lightning','beetle')
        with self.assertRaisesRegex(ValueError,'ready in'):self.g.activate_skill('fireball')

    def test_misses_train_but_rejected_retries_do_not(self):
        self.arena();self.g.w['enemies']['grassland_boar']['dodge']=100
        self.g.activate_skill('fireball','grassland boar')
        self.assertEqual(self.g.p['spell_xp']['fireball'],1)
        with self.assertRaises(ValueError):self.g.activate_skill('fireball','grassland boar')
        self.assertEqual(self.g.p['spell_xp']['fireball'],1)

    def test_recovery_does_not_stop_automatic_attacks(self):
        rows=self.arena();self.g.p['attack_ready']=0
        self.g.w['revision']['action_recovery']=20
        self.g.activate_skill('fireball','grassland boar')
        hp=rows['grassland_boar']['hp'];self.g.tick()
        self.assertLess(rows['grassland_boar']['hp'],hp)
        self.assertGreater(self.g.p['action_ready'],self.now)

    def test_potion_aliases_share_timer_and_preserve_rejected_item(self):
        self.g.p.update(level=8,hp=1)
        self.g.command('use potion');self.g.command('quaff potion')
        self.assertEqual(self.g.p['hp'],36)
        self.assertEqual(self.g.p['inventory'].count('potion'),1)
        self.reload();self.g.command('quaff potion')
        self.assertEqual(self.g.p['hp'],36)
        self.now+=10;self.g.command('quaff potion')
        self.assertEqual(self.g.p['hp'],71)

    def test_owner_can_disable_recovery_and_change_repair_cost(self):
        w=copy.deepcopy(self.g.w);w['revision'].update(action_recovery=0,potion_recovery=0,repair_base_cost=7,repair_cost_per_point=2)
        self.g.update_world(w)
        self.g.p.update(level=8,hp=1)
        self.g.command('quaff potion');self.g.command('use potion')
        self.assertEqual(self.g.p['hp'],71)
        iid=self.damaged();self.assertEqual(self.g.item(iid)['repair_cost'],13)
        self.arena();self.g.activate_skill('fireball','beetle');self.g.activate_skill('lightning','beetle')

    def test_repair_preserves_item_identity_xp_and_buffs(self):
        iid=self.damaged();before=copy.deepcopy(self.g.state['instances'][iid]);damage=self.g.item(iid)['damage']
        self.g.command('repair right')
        self.assertEqual(self.g.p['gold'],85)
        self.assertEqual(self.g.item(iid)['damage'],damage+3)
        self.assertEqual(self.g.p['equipment']['weapon'],iid)
        before['bonus']=0
        self.assertEqual(self.g.state['instances'][iid],before)
        self.reload();self.assertEqual(self.g.state['instances'][iid],before)

    def test_repair_quote_does_not_charge_and_bag_item_can_be_repaired(self):
        iid=self.damaged(False);self.g.command('repair')
        self.assertEqual(self.g.p['gold'],100)
        self.assertIn('15 gold',self.g.state['log'][-1]['text'])
        self.g.command('repair '+iid)
        self.assertEqual(self.g.state['instances'][iid]['bonus'],0)
        self.assertIn(iid,self.g.p['inventory'])
        self.g.command('repair '+iid);self.assertEqual(self.g.p['gold'],85)

    def test_repair_rejections_do_not_consume_gold_or_change_item(self):
        iid=self.damaged();inst=copy.deepcopy(self.g.state['instances'][iid])
        self.g.p['gold']=14;self.g.command('repair '+iid)
        self.assertEqual(self.g.p['gold'],14)
        self.g.p.update(room='square',gold=100);self.g.command('repair '+iid)
        self.assertEqual(self.g.p['gold'],100)
        self.g.w['revision']['repair_anywhere']=True;self.g.w['revision']['repair_enabled']=False
        self.g.command('repair '+iid);self.assertEqual(self.g.p['gold'],100)
        self.g.w['revision']['repair_enabled']=True;self.g.p['room']='meadow';self.g.start_combat()
        self.g.p['attack_ready']=self.now+100
        self.g.command('repair '+iid);self.assertEqual(self.g.p['gold'],100)
        self.assertEqual(self.g.state['instances'][iid],inst)

    def test_scouting_reveals_fixed_resident_without_rng_or_encounters(self):
        self.g.p['room']='road';state=self.g.rng.getstate()
        self.g.look('north')
        self.assertIn('Copper beetle',self.g.state['log'][-1]['text'])
        self.assertEqual(self.g.rng.getstate(),state)
        self.g.p['room']='prairie_0_2';rolls=copy.deepcopy(self.g.state['encounter_rolls'])
        self.g.look('north')
        self.assertEqual(self.g.state['encounter_rolls'],rolls)
        self.assertNotIn('prairie_0_3',self.g.state['spawns'])

    def test_scouting_honors_darkness_and_hidden_rooms(self):
        self.g.p['room']='mouth';self.g.look('north')
        self.assertNotIn('Relic goblin',self.g.state['log'][-1]['text'])
        self.g.p['inventory'].append('lantern');self.g.look('north')
        self.assertIn('Relic goblin',self.g.state['log'][-1]['text'])
        self.g.w['rooms']['tunnel']['obscured_from_outside']=True;self.g.look('north')
        self.assertNotIn('Relic goblin',self.g.state['log'][-1]['text'])

    def test_invalid_timing_and_repair_settings_rejected(self):
        for key,value in [('action_recovery',-1),('potion_recovery',float('nan')),('repair_cost_per_point',1.5),('repair_enabled','yes')]:
            w=copy.deepcopy(self.g.w);w['revision'][key]=value
            with self.assertRaises(ValueError):validate(w)


if __name__=='__main__':unittest.main()
