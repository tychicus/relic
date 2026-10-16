"""Point milestones, saved progress, and race-wide magic restrictions."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from engine import Game, validate

ROOT=Path(__file__).resolve().parents[1]


class OrcsPointsTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.path=Path(self.tmp.name)/'world.json'
        self.path.write_bytes((ROOT/'content/world.json').read_bytes())
        self.db=Path(self.tmp.name)/'save.db'
        self.g=Game(self.path,self.db,clock=lambda:1000.)

    def tearDown(self):
        self.g.db.close();self.tmp.cleanup()

    def reload(self):
        self.g.save();self.g.db.close();self.g=Game(self.path,self.db,clock=lambda:1000.)

    def test_milestones_spending_and_reload(self):
        self.g.create('Tester')
        for level,points in [(1,0),(2,0),(4,0),(5,1),(9,1),(10,2),(14,2),(15,3),(99,19),(100,20)]:
            self.g.p['level']=level;self.assertEqual(self.g.ability_points(),points)
        self.g.p['level']=5;self.g.learn_ability('kick')
        self.assertEqual(self.g.ability_points(),0);self.reload()
        self.assertEqual(self.g.ability_rank('kick'),1);self.assertEqual(self.g.ability_points(),0)
        self.g.p['level']=10;self.assertEqual(self.g.ability_points(),1)
        self.g.command('learn')
        self.assertTrue(any('every 5 character levels, starting at level 5' in l['text'] for l in self.g.state['log']))
        self.assertIn('every 5',self.g.snapshot()['learning_schedule'])

    def test_old_spending_is_preserved_without_negative_or_duplicate_points(self):
        self.g.create('Tester');self.g.p.update(level=5,ability_points_spent=4)
        self.g.p['learned_skills'].update(kick=1,fireball=1,backstab=1,sharpening=1)
        known=copy.deepcopy(self.g.p['learned_skills'])
        for level,points in [(5,0),(20,0),(25,1)]:
            self.g.p['level']=level;self.reload()
            self.assertEqual(self.g.ability_points(),points)
            self.assertEqual(self.g.p['learned_skills'],known)
            self.assertEqual(self.g.p['ability_points_spent'],4)

    def test_owner_can_adjust_schedule_and_reject_invalid_intervals(self):
        self.g.create('Tester');w=copy.deepcopy(self.g.w)
        w['revision'].update(learning_point_interval=3,learning_points_per_level=2)
        self.g.update_world(w);self.g.p['level']=6;self.assertEqual(self.g.ability_points(),4)
        w['revision']['learning_point_interval']=1;self.g.update_world(w)
        self.g.p['level']=1;self.assertEqual(self.g.ability_points(),0)
        self.g.p['level']=2;self.assertEqual(self.g.ability_points(),2)
        for invalid in (0,1.5,101,True):
            w['revision']['learning_point_interval']=invalid
            with self.assertRaises(ValueError):validate(w)

    def test_orc_creation_hp_classes_and_mana_persist(self):
        orc=next(r for r in self.g.snapshot()['creation']['races'] if r['id']=='orc')
        self.assertEqual(set(orc['available_classes']),{'warrior','rogue'})
        with self.assertRaisesRegex(ValueError,'magic'):self.g.create('Tester','orc','mage')
        self.assertIsNone(self.g.p)
        self.g.create('Tester','orc','warrior')
        self.assertEqual(self.g.p['hp'],77);self.assertEqual(self.g.max_hp(),77)
        self.assertEqual(self.g.available_skill_ids(),['swordplay'])
        self.g.p.update(level=100,mana_xp=1000000);self.reload()
        self.assertEqual(self.g.max_hp(),round((70+99*12)*1.1))
        self.assertEqual(self.g.max_mana(),0);self.assertEqual(self.g.p['mana'],0)

    def test_orc_rogue_and_nonmagical_learning(self):
        self.g.create('Tester','orc','rogue')
        self.assertEqual(self.g.max_hp(),round((self.g.w['classes']['rogue']['hp']+5)*1.1))
        self.assertEqual(self.g.available_skill_ids(),['backstab'])
        self.g.p['level']=5;self.g.learn_ability('quickstrike')
        self.assertEqual(self.g.ability_rank('quickstrike'),1)

    def test_orc_magic_commands_rejected_before_spending_or_effects(self):
        self.g.create('Tester','orc','warrior');self.g.p.update(level=100,hp=10)
        for sid in ('fireball','mend','enchanting','frostbolt'):
            before=copy.deepcopy(self.g.p)
            with self.assertRaises(ValueError):self.g.learn_ability(sid)
            self.assertEqual(self.g.p,before)
            self.g.p['learned_skills'][sid]=1  # Even a migrated learned spell cannot bypass the race.
        for learning in (True,False):
            self.g.w['revision'].update(learning_enabled=learning,mana_enabled=False)
            for cmd in ('cast fireball','skill fireball','fireball','mend','enchant right','cast enchanting right'):
                before=copy.deepcopy(self.g.p);self.g.command(cmd)
                self.assertEqual(self.g.p,before,cmd)
                self.assertIn('not available to your class and race',self.g.state['log'][-1]['text'],cmd)
            self.assertFalse(any(self.g.magical_skill(s) for s in self.g.snapshot()['player_skills']))

    def test_orc_magic_gear_rejected_without_losing_items(self):
        self.g.create('Tester','orc','warrior')
        magic=next(i for i,s in self.g.w['items'].items() if s.get('magic') and s['kind'] in ('weapon','armor'))
        iid=self.g.grant(magic);self.g.p['inventory'].append(iid)
        for cmd in ('use '+iid,'quaff '+iid,'equip '+iid,'hold '+iid):
            before=copy.deepcopy(self.g.p);instances=copy.deepcopy(self.g.state['instances'])
            self.g.command(cmd)
            self.assertEqual(self.g.p,before,cmd);self.assertEqual(self.g.state['instances'],instances,cmd)
            self.assertIn('cannot use magic',self.g.state['log'][-1]['text'])
        inst=self.g.new_instance(dict(kind='weapon',item='iron_sword',bonus=0,enchantment=dict(bonus=2,until=2000)))
        self.g.p['inventory'].append(inst)
        with self.assertRaisesRegex(ValueError,'cannot use magic'):self.g.equip_hand(inst)

    def assert_level_one_recall(self,cls):
        self.g.create('Tester','orc',cls)
        self.reload()
        self.assertEqual(self.g.p['level'],1)
        self.assertFalse(self.g.can_use_magic())
        self.assertTrue(self.g.magical_item(self.g.item('recall_scroll')))
        for cmd in ('recall','use recall scroll','use recall_scroll','quaff recall_scroll','eat recall_scroll'):
            with self.subTest(cls=cls,command=cmd):
                self.g.p.update(room='shop',hp=10,gold=123)
                before=copy.deepcopy(self.g.p)
                self.g.command(cmd)
                self.assertEqual(self.g.p['room'],self.g.w['starting']['room'])
                self.assertEqual(self.g.p['inventory'],before['inventory'])
                for key in ('hp','mana','gold','equipment','learned_skills','cooldowns','mana_xp'):
                    self.assertEqual(self.g.p[key],before[key],key)

    def test_level_one_orc_warrior_reusable_recall_and_unchanged_stats(self):
        self.assert_level_one_recall('warrior')

    def test_level_one_orc_rogue_reusable_recall_and_unchanged_stats(self):
        self.assert_level_one_recall('rogue')

    def test_orc_recall_still_obeys_room_combat_and_failure_consumption(self):
        self.g.create('Tester','orc','warrior')
        self.g.p['level']=3
        self.g.w.pop('regions',None)
        self.g.state['spawns']['meadow']=self.g.spawn_creature('beetle','meadow')
        for reason in ('room','combat'):
            for consumes in (False,True):
                with self.subTest(reason=reason,consumes=consumes):
                    self.g.p.update(room='shop',combat=None)
                    self.g.w['rooms']['shop']['recall_disabled']=reason=='room'
                    if reason=='combat':
                        self.g.p['room']='meadow';self.g.start_combat()
                        self.assertIsNotNone(self.g.p['combat'])
                        self.g.p['combat']['next_at']=2000
                    self.g.w['revision']['recall_failure_consumes']=consumes
                    self.g.p['inventory'].append('recall_scroll')
                    count=self.g.p['inventory'].count('recall_scroll');room=self.g.p['room']
                    self.g.command('recall')
                    self.assertEqual(self.g.p['room'],room)
                    self.assertEqual(self.g.p['inventory'].count('recall_scroll'),count-int(consumes))
                    self.assertIn('Recall is blocked',self.g.state['log'][-1]['text'])

    def test_recall_exception_is_owner_configurable_and_not_inherited_by_other_races(self):
        self.g.create('Tester','orc','warrior')
        self.g.p.update(room='shop');self.g.p['inventory'].append('recall_scroll')
        world=copy.deepcopy(self.g.w);world['races']['orc']['recall_without_magic']=False
        self.g.update_world(world);before=copy.deepcopy(self.g.p);self.g.command('recall')
        self.assertEqual(self.g.p,before)
        self.assertIn('cannot use magic',self.g.state['log'][-1]['text'])
        world['races']['orc']['recall_without_magic']=True;self.g.update_world(world)
        self.g.command('recall');self.assertEqual(self.g.p['room'],self.g.w['starting']['room'])
        self.assertEqual(self.g.p['inventory'],before['inventory'])
        world['races']['human']['magic_allowed']=False;self.g.update_world(world)
        other=Game(self.path,':memory:',clock=lambda:1000.)
        try:
            other.create('Tester','human','warrior');other.p['inventory'].append('recall_scroll')
            before=copy.deepcopy(other.p);other.command('recall');self.assertEqual(other.p,before)
            self.assertIn('cannot use magic',other.state['log'][-1]['text'])
        finally:other.db.close()
        world['races']['orc']['recall_without_magic']='yes'
        with self.assertRaises(ValueError):validate(world)

    def test_ordinary_items_work_and_magic_consumables_are_configurable(self):
        self.g.create('Tester','orc','warrior')
        self.g.p['inventory'].append('iron_sword');self.g.equip_hand('iron_sword')
        self.g.p['hp']=10;self.g.p['inventory'].append('potion');self.g.command('quaff potion')
        self.assertEqual(self.g.p['hp'],45)
        self.g.w['items']['potion']['requires_magic']=True
        self.g.p['inventory'].append('potion');before=copy.deepcopy(self.g.p)
        self.g.command('use potion');self.assertEqual(self.g.p,before)
        self.assertIn('cannot use magic',self.g.state['log'][-1]['text'])

    def test_owner_can_enable_orc_magic_and_adjust_hp(self):
        w=copy.deepcopy(self.g.w);w['races']['orc'].update(magic_allowed=True,hp_bonus=7)
        self.g.update_world(w);self.g.create('Tester','orc','mage')
        self.assertEqual(self.g.max_hp(),63);self.assertGreater(self.g.max_mana(),0)
        self.assertEqual(self.g.available_skill_ids(),['fireball'])

    def test_owner_cannot_disable_magic_under_equipped_magical_gear(self):
        self.g.create('Tester')
        magic=next(i for i,s in self.g.w['items'].items() if s.get('magic') and s['kind']=='weapon')
        iid=self.g.grant(magic);self.g.p['inventory'].append(iid);self.g.equip_hand(iid)
        w=copy.deepcopy(self.g.w);w['races']['human']['magic_allowed']=False
        with self.assertRaisesRegex(ValueError,'Unequip magical'):self.g.update_world(w)
        self.assertTrue(self.g.can_use_magic())


if __name__=='__main__':unittest.main()
