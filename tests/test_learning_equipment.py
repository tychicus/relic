"""End-to-end learning, class penalties, slots and unlimited inventory on the current world."""
import copy
import json
from pathlib import Path
import random
import tempfile
import unittest
from engine import Game, validate

ROOT=Path(__file__).resolve().parents[1]


class LearningEquipmentTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'world.json'
        w=json.loads((ROOT/'content/world.json').read_text(encoding='utf-8'));w.pop('regions')
        self.path.write_text(json.dumps(w),encoding='utf-8');self.db=Path(self.tmp.name)/'save.db'
        self.now=1000.;self.g=Game(self.path,self.db,random.Random(2),lambda:self.now)
        self.g.create('Tester','human','warrior')

    def tearDown(self):self.g.db.close();self.tmp.cleanup()

    def level(self,n):
        self.g.p.update(level=n,xp=self.g.w['settings']['level_xp'][n-1],hp=500,mana=500)

    def reload(self):
        self.g.save();self.g.db.close()
        self.g=Game(self.path,self.db,random.Random(2),lambda:self.now)

    def arena(self):
        self.g.p.update(room='meadow',attack_ready=self.now+1000)
        self.g.w['settings']['hit_chance']=1
        e=self.g.enemy();e['hp']=10000
        for s in self.g.w['skills'].values():s['status_effects']=[]
        return e

    def test_exactly_one_starting_ability_per_class(self):
        for cls,starter in [('warrior','swordplay'),('mage','fireball'),('rogue','backstab')]:
            g=Game(self.path,':memory:');g.create('New','human',cls)
            self.assertEqual(g.p['learned_skills'],{starter:1});self.assertEqual(g.ability_points(),0)
            self.assertEqual(g.available_skill_ids(),[starter]);g.db.close()

    def test_real_level_gain_awards_points_not_abilities(self):
        self.g.p.update(room='meadow',xp=29)
        self.g.w['enemies']['beetle']['xp']=1;self.g.victory(self.g.enemy())
        self.assertEqual(self.g.p['level'],2);self.assertEqual(self.g.ability_points(),0)
        self.assertEqual(self.g.available_skill_ids(),['swordplay'])
        self.level(4);self.g.p['xp']=549;self.g.victory(self.g.spawn_creature('beetle','meadow'))
        self.assertEqual(self.g.p['level'],5);self.assertEqual(self.g.ability_points(),1)
        self.g.learn_ability('fireball');self.assertEqual(self.g.ability_points(),0)
        self.assertEqual(self.g.ability_rank('fireball'),1)

    def test_gates_points_and_combat_rejections_are_atomic(self):
        before=copy.deepcopy(self.g.p)
        with self.assertRaises(ValueError):self.g.learn_ability('fireball')
        self.assertEqual(self.g.p,before)
        self.level(4);before=copy.deepcopy(self.g.p)
        with self.assertRaisesRegex(ValueError,'level 5'):self.g.learn_ability('kick')
        self.assertEqual(self.g.p,before)
        self.level(5);self.g.learn_ability('kick');self.g.p['combat']={'turn':'player'}
        before=copy.deepcopy(self.g.p)
        with self.assertRaisesRegex(ValueError,'combat'):self.g.learn_ability('fireball')
        self.assertEqual(self.g.p,before)

    def test_rank_requirements_spending_and_save(self):
        self.level(5)
        with self.assertRaisesRegex(ValueError,'level 6'):self.g.learn_ability('swordplay')
        self.level(6);self.g.learn_ability('swordplay')
        self.level(10);self.g.learn_ability('kick')
        self.assertEqual(self.g.ability_points(),0);self.reload()
        self.assertEqual(self.g.ability_rank('swordplay'),2);self.assertEqual(self.g.ability_rank('kick'),1)
        self.assertEqual(self.g.ability_points(),0)
        self.level(100)
        for _ in range(3):self.g.learn_ability('swordplay')
        before=self.g.ability_points()
        with self.assertRaisesRegex(ValueError,'maximum'):self.g.learn_ability('swordplay')
        self.assertEqual(self.g.ability_points(),before)

    def test_old_save_preserves_known_skills_and_xp(self):
        self.level(10);self.g.p.pop('learned_skills');self.g.p.pop('ability_points_spent')
        self.g.p['spell_xp']={'fireball':250};self.g.state['announced_skills']=['bash','kick','enchanting']
        self.reload()
        self.assertEqual(self.g.p['spell_xp']['fireball'],250)
        self.assertEqual(self.g.ability_rank('bash'),1);self.assertEqual(self.g.ability_rank('fireball'),1)
        self.assertEqual(self.g.ability_rank('enchanting'),0);self.assertEqual(self.g.ability_points(),2)
        known=copy.deepcopy(self.g.p['learned_skills']);self.reload();self.assertEqual(self.g.p['learned_skills'],known)

    def test_unlearned_skill_cannot_cast_or_spend_mana(self):
        self.level(10);self.arena();before=copy.deepcopy(self.g.p)
        with self.assertRaisesRegex(ValueError,'not learned'):self.g.activate_skill('fireball')
        self.assertEqual(self.g.p,before)

    def test_enchanting_is_mage_only_even_for_migrated_skills(self):
        self.level(10)
        for cls in ('warrior','rogue'):
            self.g.p['class']=cls
            with self.assertRaisesRegex(ValueError,'class'):self.g.learn_ability('enchanting')
            self.g.p['learned_skills']['enchanting']=1
            with self.assertRaisesRegex(ValueError,'class'):self.g.activate_skill('enchanting','right')
            self.g.p['learned_skills'].pop('enchanting')
        self.g.p['class']='mage';self.g.learn_ability('enchanting')
        self.g.p['gold']=500;self.g.w['revision']['enchant_base']=100
        self.g.activate_skill('enchanting','right')
        self.assertTrue(self.g.item(self.g.p['equipment']['weapon'])['enchanted'])

    def test_cross_class_spell_power_cost_and_practice(self):
        self.level(5);self.g.learn_ability('fireball');e=self.arena()
        before=self.g.p['mana'];self.g.activate_skill('fireball')
        self.assertEqual(10000-e['hp'],6);self.assertEqual(before-self.g.p['mana'],12)
        self.assertEqual(self.g.p['spell_xp']['fireball'],.5)
        self.assertEqual(self.g.p['mana_xp'],.5)
        self.g.p['class']='mage';self.assertEqual(self.g.skill_power('fireball',0),16)
        self.assertEqual(self.g.mana_cost('fireball'),6)
        for cls,expected in [('mage',300),('warrior',105)]:
            self.g.p['class']=cls;self.g.p['learned_skills']['fireball']=5;self.g.p['spell_xp']['fireball']=252450
            self.assertEqual(self.g.skill_power('fireball',0),expected)

    def test_mage_martial_penalty_affects_actual_damage(self):
        self.level(15);self.g.learn_ability('kick');self.g.learn_ability('bash')
        self.g.w['classes']['warrior']['damage']=[10,10];self.g.w['classes']['mage']['damage']=[10,10]
        self.g.p['equipment']={};e=self.arena()
        self.g.activate_skill('kick');warrior=10000-e['hp']
        self.now+=20;e['hp']=10000;self.g.p['class']='mage';self.g.activate_skill('kick')
        self.assertLess(10000-e['hp'],warrior*.4)

    def test_passive_rank_improves_basic_attacks_and_is_not_castable(self):
        self.level(6);e=self.arena();self.g.w['classes']['warrior']['damage']=[10,10]
        self.g.strike();first=10000-e['hp'];e['hp']=10000
        self.g.p['combat']=None;self.g.learn_ability('swordplay');self.g.strike()
        self.assertGreater(10000-e['hp'],first)
        with self.assertRaisesRegex(ValueError,'automatic'):self.g.activate_skill('swordplay')

    def test_learning_snapshot_and_live_validation(self):
        self.level(5);self.g.learn_ability('kick');data=self.g.snapshot()
        self.assertEqual(data['player']['ability_points'],0)
        self.assertFalse(next(s for s in data['player_skills'] if s['id']=='bash')['unlocked'])
        self.assertFalse(any(s['id']=='enchanting' for s in data['player_skills']))
        w=copy.deepcopy(self.g.w);w['skills'].pop('kick')
        with self.assertRaisesRegex(ValueError,'learned'):self.g.update_world(w)
        w=copy.deepcopy(self.g.w);w['classes']['mage']['starting_ability']='lightning'
        with self.assertRaisesRegex(ValueError,'starting ability|Starting ability'):validate(w)

    def equip(self,iid):
        granted=self.g.grant(iid);self.g.p['inventory'].append(granted);self.g.equip_hand(granted)

    def test_all_body_slots_shield_and_two_hands(self):
        self.g.command('LoOk SeLf')
        text=self.g.state['log'][-1]['text']
        for label in ('Left hand','Helmet','Pants','Arms'):
            self.assertIn(label+': '+('boxers' if label=='Pants' else 'nothing'),text)
        for iid in ('leather_cap','leather_pants','leather_bracers'):self.equip(iid)
        self.assertTrue(set(('helmet','armor','pants','arms','weapon'))<=set(self.g.p['equipment']))
        shield=next(i for i,s in self.g.w['items'].items() if s.get('shield') and not s.get('drop_only'));self.equip(shield)
        self.assertEqual(self.g.p['equipment']['left_hand'],shield)
        equipped=copy.deepcopy(self.g.p['equipment'])
        self.g.command('look self');text=self.g.state['log'][-1]['text']
        for slot,label in [('weapon','Right hand'),('left_hand','Left hand'),('helmet','Helmet'),('armor','Chest'),('pants','Pants'),('arms','Arms')]:
            self.assertIn(label+': '+self.g.item(equipped[slot])['name']+' — ',text)
        self.assertEqual(self.g.p['equipment'],equipped)
        self.g.command('eq');self.assertEqual(self.g.state['log'][-1]['text'],text)
        self.g.p['inventory'].append('greatsword');before=copy.deepcopy(self.g.p)
        with self.assertRaisesRegex(ValueError,'Two-handed'):self.g.equip_hand('greatsword')
        self.assertEqual(self.g.p,before)
        self.g.extra_command('unequip','shield');self.g.equip_hand('greatsword')
        with self.assertRaisesRegex(ValueError,'Two-handed'):self.g.equip_hand(shield)
        self.assertEqual(self.g.item(self.g.p['equipment']['weapon'])['hands'],2)
        self.g.command('look self');text=self.g.state['log'][-1]['text']
        self.assertIn('Left hand: occupied by Iron Greatsword',text)
        self.assertIn('two-handed',text);self.assertNotIn('Left hand: nothing',text)
        self.g.extra_command('unequip','bracers');self.assertNotIn('arms',self.g.p['equipment'])
        self.g.p['equipment']={};self.g.p['inventory']=[]
        self.g.w['rooms'][self.g.p['room']]['dark']=True
        self.g.command('look self');text=self.g.state['log'][-1]['text']
        self.assertEqual(text.count(': nothing'),5)
        self.assertIn('Pants: boxers',text)

    def test_all_worn_armor_and_shield_reduce_hits_held_armor_does_not(self):
        self.g.p['equipment']={};e=self.arena();self.g.w['enemies'][e['type']]['damage']=[20,20]
        self.g.p['hp']=100;self.g.enemy_strike(e);self.assertEqual(self.g.p['hp'],80)
        for iid in ('leather_cap','leather_pants','leather_bracers'):self.equip(iid)
        shield=next(i for i,s in self.g.w['items'].items() if s.get('shield'));self.equip(shield)
        defense=3+self.g.item(shield)['armor'];self.g.p['hp']=100;self.g.enemy_strike(e)
        self.assertEqual(self.g.p['hp'],80+defense);self.assertEqual(self.g.snapshot()['player']['defense'],defense)
        self.g.p['equipment']={'weapon':'chain_vest'};self.g.p['hp']=100;self.g.enemy_strike(e)
        self.assertEqual(self.g.p['hp'],80)

    def test_new_armor_slots_enchant_and_repair_preserve_item(self):
        self.level(10);self.g.p.update(room='shop',gold=1000);self.g.p['class']='mage'
        self.g.learn_ability('enchanting');self.equip('leather_cap');self.g.w['revision']['enchant_base']=100
        self.g.activate_skill('enchanting','helmet');iid=self.g.p['equipment']['helmet']
        self.assertTrue(self.g.item(iid)['enchanted']);self.g.state['instances'][iid]['bonus']=-2
        self.g.repair_item('helmet');self.assertEqual(self.g.state['instances'][iid]['bonus'],0)
        self.assertTrue(self.g.item(iid)['enchanted']);self.reload();self.assertEqual(self.g.p['equipment']['helmet'],iid)

    def legacy_limits(self):
        self.g.w['settings']['bag_capacity']=1
        self.g.w['revision']['weight_enabled']=True
        self.g.w['classes']['warrior'].update(carry_capacity=1,carry_per_level=0)
        self.g.w['items']['greatsword']['weight']=10000

    def test_buy_get_and_unequip_ignore_legacy_limits(self):
        self.legacy_limits();self.g.p.update(room='shop',gold=10000)
        before=self.g.p['gold'];self.g.command('buy greatsword')
        self.assertEqual(self.g.p['gold'],before-self.g.w['items']['greatsword']['price'])
        self.g.state['ground']['shop']=['greatsword'];self.g.command('get greatsword')
        self.assertEqual(self.g.p['inventory'].count('greatsword'),2)
        self.assertEqual(self.g.state['ground']['shop'],[])
        self.g.p['inventory'].append('leather_cap');self.g.equip_hand('leather_cap')
        self.g.extra_command('unequip','helmet');self.assertIn('leather_cap',self.g.p['inventory'])
        self.g.command('unequip weapon');self.assertIn('rusted_sword',self.g.p['inventory'])

    def test_ground_chest_withdrawal_preserves_occupied_cage(self):
        self.legacy_limits();chest=self.g.grant('storage_chest');cage=self.g.grant('iron_cage')
        self.g.state['instances'][cage].update(enemy='beetle',count=2)
        self.g.state['instances'][chest]['contents']=[cage,'iron_sword']
        self.g.p['inventory'].append(chest)
        self.g.extra_command('get',f'iron_sword from {chest}')
        self.g.drop_item(chest)
        self.g.extra_command('get',f'{cage} from {chest}')
        self.assertIn(cage,self.g.p['inventory'])
        self.assertEqual(self.g.state['instances'][cage]['count'],2)
        self.assertEqual(self.g.state['instances'][chest]['contents'],[])

    def test_large_inventory_persists_and_legacy_limits_never_reappear(self):
        self.legacy_limits();self.g.update_world(copy.deepcopy(self.g.w))
        self.g.p['inventory'].extend(['greatsword']*1000);before=self.g.p['inventory'][:];self.reload()
        self.assertEqual(self.g.p['inventory'],before)
        self.g.drop_item('greatsword');self.g.get_item('greatsword')
        self.assertEqual(self.g.p['inventory'],before)
        snapshot=self.g.snapshot()
        for key in ('bag_capacity','carried_weight','carry_capacity','weight_enabled'):
            self.assertNotIn(key,snapshot['player'])
        self.assertNotIn('weight',snapshot['items']['greatsword'])
        self.assertEqual(self.g.w['items']['greatsword']['weight'],10000)  # Snapshot must not mutate authored data.
        self.g.command('weight');self.assertIn('no item limit',self.g.state['log'][-1]['text'])

    def test_ordinary_loot_enters_bag_despite_legacy_limits(self):
        self.legacy_limits();self.g.p.update(room='meadow')
        self.g.w['enemies']['beetle']['loot']=[{'item':'greatsword','weight':1}]
        self.g.victory(self.g.enemy());self.assertIn('greatsword',self.g.p['inventory'])
        self.assertNotIn('greatsword',self.g.state['ground'].get('meadow',[]));self.assertGreater(self.g.p['xp'],0)

    def test_equipment_slots_still_validate(self):
        w=copy.deepcopy(self.g.w);w['items']['leather_cap']['armor_slot']='feet'
        with self.assertRaises(ValueError):validate(w)
        self.equip('leather_cap');w=copy.deepcopy(self.g.w);w['items']['leather_cap']['armor_slot']='arms'
        with self.assertRaisesRegex(ValueError,'slot'):self.g.update_world(w)

    def test_capture_ignores_legacy_limits_without_losing_creature(self):
        self.legacy_limits();e=self.arena();e['unconscious']=True
        before=len(self.g.p['inventory']);self.g.extra_command('get',e['uid'])
        self.assertEqual(len(self.g.p['inventory']),before+1)
        captive=self.g.state['instances'][self.g.p['inventory'][-1]]
        self.assertEqual((captive['kind'],captive['enemy']),('captive',e['type']))
        self.assertEqual(e['hp'],0);self.assertFalse(e['unconscious'])

    def test_harvest_ignores_legacy_limits_and_cannot_duplicate_yields(self):
        self.legacy_limits();self.g.p['room']='meadow'
        self.g.w['enemies']['beetle']['harvest']=[{'item':'iron_sword','count':2}]
        corpse=dict(uid='corpse-test',type='beetle',name='Test beetle',room='meadow',expires=self.now+300)
        self.g.state['corpses'].append(corpse)
        self.g.harvest('corpse-test');self.assertTrue(corpse['harvested'])
        self.assertEqual(self.g.p['inventory'].count('iron_sword'),2)
        with self.assertRaises(ValueError):self.g.harvest('corpse-test')
        self.assertEqual(self.g.p['inventory'].count('iron_sword'),2)

    def test_cooking_ignores_legacy_limits_and_consumes_exact_ingredients(self):
        self.legacy_limits()
        self.g.w['recipes']['test_meal']=dict(name='Test Meal',input='potion',output='greatsword',count=1,output_count=2,fire=False,chance=100)
        self.g.p['inventory'].append('potion');before=self.g.p['inventory'].count('potion')
        self.g.cook('test_meal')
        self.assertEqual(self.g.p['inventory'].count('potion'),before-1)
        self.assertEqual(self.g.p['inventory'].count('greatsword'),2)

    def test_armor_magic_practice_in_each_worn_slot(self):
        e=self.arena()
        for iid in ('leather_cap','leather_pants','leather_bracers'):
            self.g.w['items'][iid].update(magic=True,magic_levels=[dict(xp=0,power=1),dict(xp=100,power=2)])
            self.equip(iid)
        self.g.enemy_strike(e)
        for slot in ('helmet','pants','arms'):
            self.assertEqual(self.g.state['instances'][self.g.p['equipment'][slot]]['magic_xp'],2)

    def test_owner_starting_ability_change_does_not_grant_another_on_reload(self):
        w=copy.deepcopy(self.g.w);w['classes']['warrior']['starting_ability']='backstab';self.g.update_world(w)
        self.reload();self.assertEqual(self.g.p['learned_skills'],{'swordplay':1})

    def test_owner_zero_damage_spell_is_respected(self):
        self.level(5);self.g.learn_ability('fireball');e=self.arena()
        self.g.w['skills']['fireball']['magic_levels'][0]['power']=0
        self.g.activate_skill('fireball');self.assertEqual(e['hp'],10000)
