"""Starter recall, consumption boundaries, saved progress and owner settings."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from engine import Game, validate

ROOT=Path(__file__).resolve().parents[1]
COMMANDS=('recall','use recall scroll','use recall_scroll','quaff recall_scroll','eat recall_scroll')


class RecallLevelTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.path=Path(self.tmp.name)/'world.json'
        world=json.loads((ROOT/'content/world.json').read_text(encoding='utf-8'))
        world.pop('regions',None)
        for enemy in world['enemies'].values():enemy['aggressive']=False
        self.path.write_text(json.dumps(world),encoding='utf-8')
        self.db=Path(self.tmp.name)/'save.db'
        self.g=Game(self.path,self.db,clock=lambda:1000.)

    def tearDown(self):
        self.g.db.close();self.tmp.cleanup()

    def reload(self):
        self.g.save();self.g.db.close();self.g=Game(self.path,self.db,clock=lambda:1000.)

    def test_every_eligible_race_and_class_starts_with_one_recall(self):
        for race in self.g.w['races']:
            for cls in self.g.w['classes']:
                if not self.g.class_eligible(race,cls):continue
                with self.subTest(race=race,cls=cls):
                    other=Game(self.path,':memory:',clock=lambda:1000.)
                    try:
                        other.create('Starter',race,cls)
                        self.assertEqual(other.p['inventory'].count('recall_scroll'),1)
                        other.p['room']='shop';other.command('recall')
                        self.assertEqual(other.p['room'],'square')
                        self.assertEqual(other.p['inventory'].count('recall_scroll'),1)
                    finally:other.db.close()

    def test_all_commands_reuse_at_levels_one_and_two_across_reload(self):
        self.g.create('Starter')
        for level in (1,2):
            for command in COMMANDS:
                with self.subTest(level=level,command=command):
                    self.g.p.update(level=level,room='shop',hp=10,gold=321)
                    before=copy.deepcopy(self.g.p)
                    self.g.command(command)
                    self.assertEqual(self.g.p['room'],'square')
                    for key in ('inventory','hp','gold','mana','equipment','cooldowns','mana_xp'):
                        self.assertEqual(self.g.p[key],before[key],key)
                    self.reload()
                    self.assertEqual(self.g.p['inventory'].count('recall_scroll'),1)

    def test_single_use_from_three_through_twenty_nine_for_all_commands(self):
        self.g.create('Starter','orc','warrior')
        for level in (3,29):
            for command in COMMANDS:
                with self.subTest(level=level,command=command):
                    self.g.p.update(level=level,room='shop',inventory=['recall_scroll','recall_scroll'])
                    self.g.command(command)
                    self.assertEqual(self.g.p['room'],'square')
                    self.assertEqual(self.g.p['inventory'],['recall_scroll'])

    def test_real_level_gains_switch_recall_rules_immediately_and_persist(self):
        self.g.create('Starter')
        for previous,following,remaining,destination in ((2,3,0,'square'),(29,30,1,'shop')):
            self.g.w['enemies']['beetle'].update(xp=1,loot=[dict(item=None,weight=1)])
            self.g.w['revision']['rare_drops_enabled']=False
            self.g.p.update(level=previous,xp=self.g.w['settings']['level_xp'][previous]-1,room='meadow',inventory=['recall_scroll'])
            self.g.victory(self.g.spawn_creature('beetle','meadow'))
            self.assertEqual(self.g.p['level'],following)
            self.reload();self.g.p['room']='shop';self.g.command('recall')
            self.assertEqual(self.g.p['room'],destination)
            self.assertEqual(self.g.p['inventory'].count('recall_scroll'),remaining)

    def test_level_thirty_and_above_reject_every_command_without_consumption(self):
        self.g.create('Starter','orc','rogue')
        for level in (30,100):
            for command in COMMANDS:
                with self.subTest(level=level,command=command):
                    self.g.p.update(level=level,room='shop')
                    self.g.w['revision']['recall_failure_consumes']=True
                    before=copy.deepcopy(self.g.p)
                    self.g.command(command)
                    self.assertEqual(self.g.p,before)
                    self.assertIn('cannot be used at level 30',self.g.state['log'][-1]['text'])
                    self.reload()

    def test_no_recall_is_granted_on_reload_and_replacements_must_be_obtained(self):
        self.g.create('Starter');self.g.p.update(level=3,room='shop',gold=500)
        self.g.command('recall');self.assertNotIn('recall_scroll',self.g.p['inventory'])
        self.reload();self.assertNotIn('recall_scroll',self.g.p['inventory'])
        self.g.p['room']='shop';self.g.command('recall');self.assertEqual(self.g.p['room'],'shop')
        self.assertIn('need a recall scroll',self.g.state['log'][-1]['text'])
        self.g.command('buy recall_scroll');self.assertEqual(self.g.p['gold'],350)
        self.g.command('use recall_scroll');self.assertEqual(self.g.p['room'],'square')
        self.assertNotIn('recall_scroll',self.g.p['inventory'])
        self.g.state['ground'].setdefault('square',[]).append('recall_scroll')
        self.g.command('get recall_scroll');self.g.p['room']='shop';self.g.command('recall')
        self.assertEqual(self.g.p['room'],'square');self.assertNotIn('recall_scroll',self.g.p['inventory'])

    def test_reusable_scrolls_survive_blocked_attempts_even_with_failure_consumption(self):
        self.g.create('Starter')
        self.g.w['revision']['recall_failure_consumes']=True
        self.g.w['rooms']['shop']['recall_disabled']=True
        self.g.state['spawns']['meadow']=self.g.spawn_creature('beetle','meadow')
        for level in (1,2):
            for reason in ('room','combat'):
                with self.subTest(level=level,reason=reason):
                    self.g.p.update(level=level,room='shop' if reason=='room' else 'meadow',combat=None)
                    if reason=='combat':
                        self.g.start_combat();self.assertIsNotNone(self.g.p['combat'])
                        self.g.p['combat']['next_at']=2000
                    room=self.g.p['room'];before=self.g.p['inventory'][:]
                    self.g.command('recall')
                    self.assertEqual(self.g.p['room'],room);self.assertEqual(self.g.p['inventory'],before)
                    self.assertIn('Recall is blocked',self.g.state['log'][-1]['text'])

    def test_owner_thresholds_apply_to_behavior_and_ui_and_validate(self):
        self.g.create('Starter')
        world=copy.deepcopy(self.g.w)
        world['revision'].update(recall_reusable_below_level=5,recall_disabled_from_level=10)
        self.g.update_world(world)
        for level,remaining,destination in ((4,1,'square'),(5,0,'square'),(9,0,'square'),(10,1,'shop')):
            self.g.p.update(level=level,room='shop',inventory=['recall_scroll'])
            state=self.g.command('recall')
            self.assertEqual(self.g.p['room'],destination)
            self.assertEqual(self.g.p['inventory'].count('recall_scroll'),remaining)
            self.assertEqual(state['recall_rules'],dict(reusable_below=5,disabled_from=10,starting_scroll=True))
        for field in ('recall_reusable_below_level','recall_disabled_from_level'):
            for invalid in (0,102,2.5,True):
                invalid_world=copy.deepcopy(world);invalid_world['revision'][field]=invalid
                with self.assertRaises(ValueError):validate(invalid_world)
        world['revision']['recall_reusable_below_level']=11
        with self.assertRaisesRegex(ValueError,'Recall reusable level'):validate(world)


if __name__=='__main__':unittest.main()
