"""Rare-drop odds, eligibility, unique gear, carry limits and shop exclusion."""
import copy
import json
from pathlib import Path
import random
import tempfile
import unittest
from unittest.mock import patch
from engine import Game, validate

ROOT=Path(__file__).resolve().parents[1]


class RareDropTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'world.json'
        w=json.loads((ROOT/'content/world.json').read_text(encoding='utf-8'));w.pop('regions',None)
        for enemy in w['enemies'].values():enemy['aggressive']=False
        self.path.write_text(json.dumps(w),encoding='utf-8');self.db=Path(self.tmp.name)/'save.db'
        self.g=Game(self.path,self.db,random.Random(7),lambda:1000.)
        self.g.create('Tester');self.g.p.update(room='meadow',level=20,xp=w['settings']['level_xp'][19],gold=1000)

    def tearDown(self):self.g.db.close();self.tmp.cleanup()

    def reload(self):
        self.g.save();self.g.db.close();self.g=Game(self.path,self.db,random.Random(7),lambda:1000.)

    def corpse(self,kind='vampire'):
        e=self.g.spawn_creature(kind,'meadow');e['hp']=0;return e

    def pool(self,item='kingsfall',chance=100):
        self.g.w['revision'].update(rare_drop_chance=chance,rare_drop_pool=[dict(item=item,weight=1,min_level=10)])

    def test_default_percentage_boundary_and_not_one_percent(self):
        self.assertEqual(self.g.rules()['rare_drop_chance'],.1)
        for roll,success in [(0,True),(.000999,True),(.001,False),(.009,False),(.9999,False)]:
            with self.subTest(roll=roll),patch.object(self.g.rng,'random',return_value=roll):
                self.assertEqual(self.g.award_rare_drop(self.corpse()) is not None,success)

    def test_living_low_level_unconscious_and_released_give_no_drop(self):
        self.pool()
        enemies=[self.corpse('sentinel'),self.corpse(),self.corpse(),self.corpse()]
        enemies[1]['hp']=1;enemies[2]['unconscious']=True;enemies[3]['released']=True
        with patch.object(self.g.rng,'random') as roll:
            for e in enemies:self.assertIsNone(self.g.award_rare_drop(e))
            roll.assert_not_called()

    def test_owner_disable_zero_chance_empty_pool_and_minimum_level(self):
        for change in [dict(rare_drops_enabled=False),dict(rare_drop_chance=0),dict(rare_drop_pool=[]),dict(rare_drop_min_level=11)]:
            saved=copy.deepcopy(self.g.w['revision']);self.g.w['revision'].update(change)
            with patch.object(self.g.rng,'random') as roll:
                self.assertIsNone(self.g.award_rare_drop(self.corpse()));roll.assert_not_called()
            self.g.w['revision']=saved

    def test_item_level_gates_and_weighted_selection(self):
        self.g.w['revision'].update(rare_drop_chance=100,rare_drop_pool=[dict(item='kingsfall',weight=3,min_level=10),dict(item='last_bastion',weight=1,min_level=10),dict(item='starwake',weight=50,min_level=12)])
        with patch.object(self.g.rng,'choices',side_effect=lambda seq,**kw:[seq[-1]]) as choose:
            iid=self.g.award_rare_drop(self.corpse())
            self.assertEqual(self.g.state['instances'][iid]['item'],'last_bastion')
            self.assertEqual(choose.call_args.kwargs['weights'],[3,1])
            iid=self.g.award_rare_drop(self.corpse('cave_troll'))
            self.assertEqual(self.g.state['instances'][iid]['item'],'starwake')
            self.assertEqual(choose.call_args.kwargs['weights'],[3,1,50])

    def test_defeat_awards_normal_loot_and_one_special_item(self):
        self.pool();self.g.w['enemies']['vampire']['loot']=[dict(item='potion',weight=1)]
        e=self.g.spawn_creature('vampire','meadow');before=self.g.p['inventory'].count('potion')
        self.g.victory(e)
        self.assertEqual(self.g.p['inventory'].count('potion'),before+1)
        drops=[i for i in self.g.p['inventory'] if self.g.item(i).get('drop_only')]
        self.assertEqual(len(drops),1);self.assertTrue(e['rare_drop_checked'])
        self.assertTrue(any('RARE FIND!' in line['text'] for line in self.g.state['log']))

    def test_checked_enemy_cannot_reroll_after_reload_and_respawn_can(self):
        self.pool();e=self.corpse();self.g.state['spawns']['meadow']=e
        self.assertIsNotNone(self.g.award_rare_drop(e));self.reload()
        e=self.g.state['spawns']['meadow'];before=len(self.g.p['inventory'])
        with patch.object(self.g.rng,'random') as roll:
            self.assertIsNone(self.g.award_rare_drop(e));roll.assert_not_called()
        self.assertEqual(len(self.g.p['inventory']),before)
        self.pool()  # Restore this test's guaranteed rate after reloading the default world.
        self.assertIsNotNone(self.g.award_rare_drop(self.corpse()))

    def test_failed_roll_is_not_retried(self):
        e=self.corpse()
        with patch.object(self.g.rng,'random',return_value=.9) as roll:
            self.assertIsNone(self.g.award_rare_drop(e));self.assertIsNone(self.g.award_rare_drop(e))
            self.assertEqual(roll.call_count,1)

    def test_large_inventory_collects_rare_drop_and_preserves_it_on_reload(self):
        self.pool();self.g.p['inventory']=['potion']*1000
        self.g.w['settings']['bag_capacity']=1
        iid=self.g.award_rare_drop(self.corpse())
        self.assertIn(iid,self.g.p['inventory']);self.assertNotIn(iid,self.g.state['ground'].get('meadow',[]))
        self.reload();self.assertIn(iid,self.g.p['inventory']);self.assertIn(iid,self.g.state['instances'])

    def test_legacy_weight_limit_does_not_block_rare_drop(self):
        self.pool();self.g.p['inventory']=[]
        self.g.w['classes']['warrior'].update(carry_capacity=1,carry_per_level=0)
        iid=self.g.award_rare_drop(self.corpse())
        self.assertIn(iid,self.g.p['inventory']);self.assertIn(iid,self.g.state['instances'])

    def test_normal_and_rare_loot_are_both_collected(self):
        self.pool();self.g.p['inventory']=['potion']*15;self.g.w['settings']['bag_capacity']=15
        self.g.w['enemies']['vampire']['loot']=[dict(item='potion',weight=1)]
        self.g.victory(self.g.spawn_creature('vampire','meadow'))
        self.assertEqual(len(self.g.p['inventory']),17)
        self.assertEqual(self.g.p['inventory'].count('potion'),16)
        self.assertTrue(self.g.item(self.g.p['inventory'][-1])['drop_only'])
        self.assertFalse(self.g.state['ground'].get('meadow'))

    def test_two_copies_keep_identity_through_repair_death_and_recovery(self):
        self.pool('starwake');first=self.g.award_rare_drop(self.corpse());second=self.g.award_rare_drop(self.corpse())
        self.assertNotEqual(first,second)
        self.g.state['instances'][first].update(magic_xp=350,bonus=-2)
        self.g.p['room']='shop';self.g.repair_item(first)
        self.assertEqual(self.g.state['instances'][first]['magic_xp'],350)
        self.assertEqual(self.g.state['instances'][second]['magic_xp'],0)
        self.g.p['room']='meadow';self.g.death();self.reload()
        self.g.p['room']='meadow';self.g.command('loot body')
        self.assertIn(first,self.g.p['inventory']);self.assertIn(second,self.g.p['inventory'])
        self.assertEqual(self.g.state['instances'][first]['magic_xp'],350)
        self.assertTrue(self.g.item(first)['drop_only'])

    def test_orc_can_equip_nonmagical_rewards_but_not_starwake(self):
        self.g.p['race']='orc'
        for ident in ('kingsfall','ironheart_cuirass','crownguard_helm','pathwarden_greaves','sentinel_vambraces','last_bastion'):
            iid=self.g.grant(ident);self.g.p['inventory'].append(iid);self.g.equip_hand(iid)
        iid=self.g.grant('starwake');self.g.p['inventory'].append(iid)
        with self.assertRaisesRegex(ValueError,'cannot use magic'):self.g.equip_hand(iid)

    def test_shop_validation_and_runtime_purchase_guard(self):
        w=copy.deepcopy(self.g.w);w['rooms']['shop']['shop'].append('kingsfall')
        with self.assertRaisesRegex(ValueError,'Shops cannot stock'):validate(w)
        self.g.p['room']='shop';self.g.w['rooms']['shop']['shop'].append('kingsfall')
        before=copy.deepcopy(self.g.p);self.g.command('buy kingsfall')
        self.assertEqual(self.g.p,before)
        self.assertIn('cannot be purchased',self.g.state['log'][-1]['text'])
        self.g.command('buy');self.assertNotIn('Kingsfall',self.g.state['log'][-1]['text'])
        self.assertNotIn('kingsfall',self.g.snapshot()['room']['shop'])

    def test_selling_a_reward_never_makes_it_shop_stock(self):
        self.pool();iid=self.g.award_rare_drop(self.corpse());self.g.p['room']='shop'
        stock=self.g.w['rooms']['shop']['shop'][:];self.g.command('sell '+iid)
        self.assertNotIn(iid,self.g.p['inventory']);self.assertEqual(self.g.w['rooms']['shop']['shop'],stock)

    def test_owner_pool_validation(self):
        changes=[dict(rare_drop_chance=-.1),dict(rare_drop_chance=100.1),dict(rare_drop_min_level=0),dict(rare_drop_min_level=2.5),dict(rare_drop_pool=[dict(item='potion',weight=1,min_level=10)]),dict(rare_drop_pool=[dict(item='kingsfall',weight=0,min_level=10)])]
        for change in changes:
            w=copy.deepcopy(self.g.w);w['revision'].update(change)
            with self.assertRaises(ValueError):validate(w)
        w=copy.deepcopy(self.g.w);w['revision']['rare_drop_pool'].append(w['revision']['rare_drop_pool'][0])
        with self.assertRaisesRegex(ValueError,'only once'):validate(w)

    def test_default_rewards_exceed_matching_ordinary_equipment(self):
        items=self.g.w['items'];pool=self.g.rules()['rare_drop_pool'];self.assertEqual(len(pool),8)
        for row in pool:
            spec=items[row['item']];self.assertTrue(spec['drop_only'])
            self.assertEqual(spec['rarity'],'legendary')
            peers=[s for s in items.values() if not s.get('drop_only') and s['kind']==spec['kind'] and bool(s.get('shield'))==bool(spec.get('shield')) and (spec['kind']=='weapon' or s.get('armor_slot','armor')==spec.get('armor_slot','armor'))]
            if spec.get('magic'):
                for peer in [s for s in peers if s.get('magic')]:
                    self.assertTrue(all(a['power']>b['power'] for a,b in zip(spec['magic_levels'],peer['magic_levels'])))
            else:
                stat='damage' if spec['kind']=='weapon' else 'armor'
                self.assertGreater(spec[stat],max(s[stat] for s in peers if not s.get('magic')))


if __name__=='__main__':unittest.main()
