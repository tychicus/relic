import copy
import json
from pathlib import Path
import random
import tempfile
import unittest
from unittest.mock import patch
from engine import Game,validate

ROOT=Path(__file__).resolve().parents[1]


class ManaRogueTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)/'world.json'
        w=json.loads((ROOT/'content/world.json').read_text(encoding='utf-8'));w.pop('regions')
        w.setdefault('revision',{})['learning_enabled']=False
        for cls in w['classes'].values():cls.pop('starting_ability',None)
        w['skills']['mend']['unlock_level']=2;w['skills']['hamstring']['unlock_level']=4
        w['skills']['fireball']['allowed_classes']=['mage']
        self.path.write_text(json.dumps(w),encoding='utf-8');self.db=Path(self.temp.name)/'game.db'
        self.now=1000.
        self.g=Game(self.path,self.db,random.Random(3),lambda:self.now)
        self.g.create('Mage','human','mage')

    def tearDown(self):
        self.g.db.close();self.temp.cleanup()

    def fight(self):
        self.g.p.update(room='meadow',attack_ready=self.now+1000)
        self.g.w['skills']['fireball']['status_effects']=[]
        self.g.w['settings']['hit_chance']=1
        e=self.g.enemy();e['hp']=10000
        return e

    def reload(self):
        self.g.save();self.g.db.close();self.path.write_text(json.dumps(self.g.w),encoding='utf-8')
        self.g=Game(self.path,self.db,random.Random(3),lambda:self.now)

    def test_starting_reserve_and_valid_cast_cost(self):
        self.assertEqual(self.g.p['mana'],40);self.assertEqual(self.g.max_mana(),40)
        self.fight();self.g.activate_skill('fireball')
        self.assertEqual(self.g.p['mana'],34)
        self.assertEqual(self.g.p['mana_xp'],2);self.assertEqual(self.g.p['spell_xp']['fireball'],2)

    def test_invalid_actions_do_not_spend_mana_or_award_practice(self):
        self.fight()
        before=copy.deepcopy(self.g.p)
        with self.assertRaises(ValueError):self.g.activate_skill('fireball','missing dragon')
        self.assertEqual(self.g.p,before)
        self.g.p['mana']=5
        before=copy.deepcopy(self.g.p)
        with self.assertRaisesRegex(ValueError,'needs 6 mana'):self.g.activate_skill('fireball')
        self.assertEqual(self.g.p,before)
        self.g.p.update(room='shop',mana=40)
        self.g.p['level']=2
        self.g.p['hp']=self.g.max_hp()
        with self.assertRaisesRegex(ValueError,'full health'):self.g.activate_skill('mend')
        self.assertEqual(self.g.p['mana'],40)

    def test_cooldown_retry_does_not_spend_or_train(self):
        self.fight();self.g.activate_skill('fireball');before=copy.deepcopy(self.g.p)
        with self.assertRaises(ValueError):self.g.activate_skill('fireball')
        self.assertEqual(self.g.p,before)

    def test_enchanting_spends_mana_on_valid_success_and_failure_only(self):
        self.g.p.update(level=10,gold=1000)
        self.g.w['revision']['enchant_base']=100
        self.g.activate_skill('enchanting','right')
        self.assertEqual(self.g.p['mana'],32);self.assertEqual(self.g.p['mana_xp'],1)
        self.now+=15;self.g.w['revision'].update(enchant_base=0,enchant_destroy=0)
        self.g.activate_skill('enchanting','right')
        self.assertEqual(self.g.p['mana'],24);self.assertEqual(self.g.p['mana_xp'],2)
        self.now+=15
        with self.assertRaises(ValueError):self.g.activate_skill('enchanting','missing')
        self.assertEqual(self.g.p['mana'],24);self.assertEqual(self.g.p['mana_xp'],2)

    def test_misses_and_harder_targets_train_but_released_targets_get_no_bonus(self):
        e=self.fight();self.g.w['settings']['hit_chance']=0
        self.g.w['enemies']['beetle']['level']=4
        self.g.activate_skill('fireball');self.assertEqual(self.g.p['spell_xp']['fireball'],3)
        self.assertEqual(e['hp'],10000);self.assertEqual(self.g.p['mana'],34)
        e['released']=True;self.now+=8;self.g.activate_skill('fireball')
        self.assertEqual(self.g.p['spell_xp']['fireball'],4)
        self.assertEqual(self.g.p['mana_xp'],4)

    def test_practice_and_character_levels_both_grow_capacity(self):
        self.fight();self.g.p['mana_xp']=99
        self.g.activate_skill('fireball')
        self.assertEqual(self.g.mana_progress()['level'],2);self.assertEqual(self.g.max_mana(),42)
        self.assertEqual(self.g.p['mana'],36)
        self.g.p['level']=2;self.assertEqual(self.g.max_mana(),45)

    def test_recovery_rest_and_no_offline_practice(self):
        self.g.p['mana']=10;self.now+=5;self.g.tick()
        self.assertEqual(self.g.p['mana'],15);self.assertEqual(self.g.p['mana_xp'],0)
        self.fight();self.g.start_combat();self.now+=5;self.g.tick()
        self.assertEqual(self.g.p['mana'],15)
        self.g.p.update(room='inn',combat=None);self.g.command('rest')
        self.assertEqual(self.g.p['mana'],40)
        self.g.p['mana']=12;self.g.save();self.now+=99999;self.reload();self.g.tick()
        self.assertEqual(self.g.p['mana'],12);self.assertEqual(self.g.p['mana_xp'],0)

    def test_paid_healing_trains_and_free_skills_do_not_train_mana(self):
        self.g.p.update(level=2,hp=20)
        self.g.activate_skill('mend');self.assertEqual(self.g.p['hp'],38)
        self.assertEqual(self.g.p['mana'],33);self.assertEqual(self.g.p['mana_xp'],1)
        self.assertEqual(self.g.p['spell_xp']['mend'],1)
        self.g.w['revision']['mana_enabled']=False
        self.now+=12;self.g.p['hp']=10;self.g.activate_skill('mend')
        self.assertEqual(self.g.p['mana'],33);self.assertEqual(self.g.p['mana_xp'],1)

    def test_level_specific_costs_and_owner_rules_persist(self):
        w=copy.deepcopy(self.g.w);w['skills']['fireball']['magic_levels'][1]['mana_cost']=11
        w['revision'].update(mana_regen=2,practice_challenge_bonus=4)
        self.g.update_world(w);self.g.p['spell_xp']={'fireball':100}
        self.fight();self.g.activate_skill('fireball');self.assertEqual(self.g.p['mana'],29)
        self.assertEqual(self.g.p['mana_xp'],5)
        self.reload();self.assertEqual(self.g.p['mana'],29);self.assertEqual(self.g.mana_cost('fireball'),11)
        self.assertEqual(self.g.w['revision']['mana_regen'],2)

    def test_equipment_practice_uses_challenge_for_attacks_and_protection(self):
        e=self.fight();self.g.w['enemies']['beetle'].update(level=4,damage=[5,5])
        sword=self.g.grant('elven_sword');self.g.p['equipment']['weapon']=sword
        self.g.strike();self.assertEqual(self.g.state['instances'][sword]['magic_xp'],3)
        self.g.w['items']['chain_vest'].update(magic=True,magic_levels=[dict(xp=0,power=2),dict(xp=100,power=3)])
        armor=self.g.grant('chain_vest');self.g.p['equipment']['armor']=armor
        self.g.enemy_strike(e);self.assertEqual(self.g.state['instances'][armor]['magic_xp'],3)

    def test_rogue_skills_dodge_and_class_eligibility(self):
        self.g.p.update(**{'class':'rogue','level':4});self.g.p['hp']=self.g.max_hp()
        e=self.fight()
        self.g.activate_skill('backstab',e['uid'])
        self.assertLess(e['hp'],10000);self.assertEqual(self.g.p['mana_xp'],0)
        with self.assertRaisesRegex(ValueError,'not available'):self.g.activate_skill('fireball')
        hp=self.g.p['hp']
        with patch.object(self.g.rng,'random',return_value=.1):self.g.enemy_strike(e)
        self.assertEqual(self.g.p['hp'],hp)
        self.now+=2;self.g.activate_skill('hamstring')
        self.assertTrue(any(s['id']=='slowed' for s in e['effects']))
        self.assertIn('rogue',self.g.rules()['dual_classes'])
        self.reload();self.assertEqual(self.g.p['class'],'rogue')

    def test_mana_and_challenge_validation_is_atomic(self):
        before=self.path.read_bytes()
        for group,ident,field,value in [('classes','mage','mana',-1),('classes','rogue','dodge',101),('enemies','beetle','level',0),('skills','fireball','mana_cost',-1)]:
            w=copy.deepcopy(self.g.w);w[group][ident][field]=value
            with self.assertRaises(ValueError):self.g.update_world(w)
            self.assertEqual(self.path.read_bytes(),before)
        w=copy.deepcopy(self.g.w);w['skills']['fireball']['magic_levels'][0]['mana_cost']=1.5
        with self.assertRaises(ValueError):validate(w)

    def test_character_level_refills_reserve_and_new_mastery_caps_are_reachable(self):
        e=self.fight();self.g.p.update(xp=29,mana=0)
        self.g.victory(e);self.assertEqual(self.g.p['level'],2);self.assertEqual(self.g.p['mana'],43)
        for sid in ('fireball','lightning','mend'):
            self.assertEqual(len(self.g.w['skills'][sid]['magic_levels']),100)
            self.g.p.setdefault('spell_xp',{})[sid]=252450
            self.assertEqual(self.g.spell_progress(sid)['level'],100)
        self.g.p['mana_xp']=252450;self.assertEqual(self.g.mana_progress()['level'],100)


if __name__=='__main__':unittest.main()
