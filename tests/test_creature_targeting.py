"""Generic creature names select a type; descriptions still select individuals."""
import copy
import json
from pathlib import Path
import random
import tempfile
import unittest

from engine import Game

ROOT=Path(__file__).resolve().parents[1]


class CreatureTargetingTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.path=Path(self.tmp.name)/'world.json'
        world=json.loads((ROOT/'content/world.json').read_text(encoding='utf-8'))
        world.pop('regions',None)
        for enemy in world['enemies'].values():enemy['aggressive']=False
        world['rooms']['meadow']['population']=[dict(id='peers',enemy='beetle',count=1,chance=100)]
        world['skills']['fireball']['status_effects']=[]
        world['settings']['hit_chance']=1
        world['enemies']['beetle']['dodge']=0
        self.path.write_text(json.dumps(world),encoding='utf-8')
        self.db=Path(self.tmp.name)/'save.db'
        self.g=Game(self.path,self.db,random.Random(2),lambda:1000.)
        self.g.create('Tester','human','mage')
        self.g.p.update(room='meadow',attack_ready=2000)
        self.rows=self.g.creatures()
        self.assertEqual(len(self.rows),2)
        for e,descriptor in zip(self.rows,('scarred','watchful')):
            e.update(hp=1000,attack_ready=2000,descriptor=descriptor)

    def tearDown(self):
        self.g.db.close();self.tmp.cleanup()

    def test_generic_kill_attack_alias_and_target_choose_first_same_type(self):
        before=copy.deepcopy(self.g.state)
        for command in ('Kill beetle','ATTACK copper beetle','a the beetle','target beetle'):
            with self.subTest(command=command):
                self.g.state=copy.deepcopy(before);self.g.p=self.g.state['player']
                self.g.command(command)
                self.assertEqual(self.g.p['target'],self.rows[0]['uid'])
                self.assertIn('Target: scarred Copper beetle.',self.g.state['log'][-1]['text'])
                if command.startswith('target'):
                    self.assertIsNone(self.g.p['combat'])
                else:
                    self.assertEqual(self.g.p['combat']['engaged'],[self.rows[0]['uid']])

    def test_descriptions_and_ids_override_current_target_and_generic_keeps_it(self):
        self.g.command('target scarred')
        for target in ('watchful','watchful copper beetle',self.rows[1]['uid']):
            self.g.command('target '+target)
            self.assertEqual(self.g.p['target'],self.rows[1]['uid'])
        self.g.command('kill beetle')
        self.g.command('kill copper beetle')
        self.assertEqual(self.g.p['target'],self.rows[1]['uid'])
        self.assertEqual(self.g.p['combat']['engaged'],[self.rows[1]['uid']])
        self.assertEqual(self.rows[0]['hp'],1000)

    def test_different_types_require_clarification_even_with_matching_current_target(self):
        self.g.w['enemies']['iron_beetle']=dict(self.g.w['enemies']['beetle'],name='Iron beetle')
        self.g.w['rooms']['meadow']['population'].append(dict(id='iron',enemy='iron_beetle',count=1,chance=100))
        iron=next(e for e in self.g.creatures() if e['type']=='iron_beetle')
        self.g.p['target']=self.rows[0]['uid']
        for command in ('kill beetle','attack beetle','target beetle','cast fireball beetle'):
            with self.subTest(command=command):
                before=copy.deepcopy(self.g.p);hp=[e['hp'] for e in self.g.creatures()]
                self.g.command(command)
                self.assertEqual(self.g.p,before)
                self.assertEqual([e['hp'] for e in self.g.creatures()],hp)
                self.assertIn('distinct creature description',self.g.state['log'][-1]['text'])
                self.assertIn('Iron beetle',self.g.state['log'][-1]['text'])
        self.g.command('target copper beetle')
        self.assertEqual(self.g.p['target'],self.rows[0]['uid'])
        self.g.command('kill iron beetle')
        self.assertEqual(self.g.p['target'],iron['uid'])
        self.assertEqual(self.g.p['combat']['engaged'],[iron['uid']])

    def test_generic_spell_hits_only_one_matching_creature(self):
        mana=self.g.p['mana']
        self.g.command('cast fireball beetle')
        self.assertEqual(self.g.p['target'],self.rows[0]['uid'])
        self.assertLess(self.rows[0]['hp'],1000)
        self.assertEqual(self.rows[1]['hp'],1000)
        self.assertLess(self.g.p['mana'],mana)
        self.assertIn('fireball',self.g.p['cooldowns'])
        self.assertEqual(self.g.p['combat']['engaged'],[self.rows[0]['uid']])

    def test_dead_unconscious_absent_and_dark_creatures_are_not_selected(self):
        first,second=self.rows
        first.update(hp=0,respawn_at=2000)
        self.g.p['target']=first['uid']
        self.assertIs(self.g.find_creature('beetle'),second)
        second['unconscious']=True
        with self.assertRaises(ValueError):self.g.find_creature('beetle')
        second['unconscious']=False;second['location']='road'
        with self.assertRaises(ValueError):self.g.find_creature('beetle')
        second['location']='meadow';self.g.w['rooms']['meadow']['dark']=True
        before=copy.deepcopy(self.g.p);self.g.command('kill beetle')
        self.assertEqual(self.g.p,before)
        self.assertIn('dark',self.g.state['log'][-1]['text'])

    def test_matching_target_survives_reload_and_unrelated_target_is_ignored(self):
        self.g.command('target watchful');self.g.save();self.g.db.close()
        self.g=Game(self.path,self.db,random.Random(2),lambda:1000.)
        self.g.command('kill beetle')
        self.assertEqual(self.g.p['target'],self.rows[1]['uid'])
        self.g.p['combat']=None;self.g.p['target']='creature-not-here'
        self.g.command('kill beetle')
        self.assertEqual(self.g.p['target'],self.rows[0]['uid'])


if __name__=='__main__':unittest.main()
