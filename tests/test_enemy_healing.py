import copy
import json
from pathlib import Path
import random
import tempfile
import unittest
from engine import Game,validate

ROOT=Path(__file__).resolve().parents[1]


class EnemyHealingTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'world.json';self.db=Path(self.tmp.name)/'save.db'
        self.path.write_bytes((ROOT/'content/world.json').read_bytes());self.now=1000.
        self.g=Game(self.path,self.db,random.Random(3),lambda:self.now);self.g.create('Tester')
        self.e=self.g.creatures('road',True)[0] if self.g.creatures('road',True) else self.g.creatures('meadow',True)[0]
        self.g.w['enemies'][self.e['type']]['hp']=100;self.e['hp']=50

    def tearDown(self):self.g.db.close();self.tmp.cleanup()

    def test_delay_interval_and_cap_on_game_tick(self):
        self.g.tick();self.now+=19;self.g.tick();self.assertEqual(self.e['hp'],50)
        self.now+=1;self.g.tick();self.assertEqual(self.e['hp'],52)
        self.now+=4;self.g.tick();self.assertEqual(self.e['hp'],52)
        self.now+=1;self.g.tick();self.assertEqual(self.e['hp'],54)
        self.e['hp']=99;self.now+=5;self.g.tick();self.assertEqual(self.e['hp'],100)

    def test_all_engaged_enemies_pause_and_delay_after_flee(self):
        rows=[]
        for region in self.g.state['regional_populations'].values():rows+=region['creatures']
        peers=rows[:2]
        for e in peers:e.update(hp=1)
        self.g.p['combat']={'engaged':[e['uid'] for e in peers]}
        self.g.heal_enemies();self.now+=100;self.g.heal_enemies()
        self.assertEqual([e['hp'] for e in peers],[1,1])
        self.g.p['combat']=None;self.now+=19;self.g.heal_enemies();self.assertEqual([e['hp'] for e in peers],[1,1])
        self.now+=1;self.g.heal_enemies();self.assertTrue(all(e['hp']>1 for e in peers))

    def test_unconscious_and_dead_never_heal(self):
        self.e['unconscious']=True;self.g.heal_enemies();self.now+=1000;self.g.heal_enemies()
        self.assertEqual(self.e['hp'],50)
        self.e['unconscious']=False;self.e['hp']=0;self.now+=1000;self.g.heal_enemies();self.assertEqual(self.e['hp'],0)

    def test_reload_preserves_hp_and_does_not_apply_offline_healing(self):
        self.e['hp']=10
        uid=self.e['uid'];self.g.heal_enemies();self.g.save();self.g.db.close();self.now+=100000
        self.g=Game(self.path,self.db,random.Random(3),lambda:self.now)
        self.e=next(e for rid in self.g.w['rooms'] for e in self.g.creatures(rid,True,False) if e['uid']==uid)
        # Current authored maximum clamps saved wounds on load if lower.
        before=self.e['hp'];self.g.heal_enemies();self.assertEqual(self.e['hp'],before)
        self.now+=19;self.g.heal_enemies();self.assertEqual(self.e['hp'],before)

    def test_large_clock_jump_gives_only_one_installment(self):
        self.g.heal_enemies();self.now+=100000;self.g.heal_enemies();self.assertEqual(self.e['hp'],52)

    def test_owner_overrides_and_disable(self):
        self.g.w['enemies'][self.e['type']].update(healing_override=True,heal_delay=2,heal_interval=3,heal_percent=10)
        self.g.heal_enemies();self.now+=2;self.g.heal_enemies();self.assertEqual(self.e['hp'],60)
        self.now+=3;self.g.heal_enemies();self.assertEqual(self.e['hp'],70)
        self.g.w['enemies'][self.e['type']]['heal_percent']=0;self.now+=20;self.g.heal_enemies();self.assertEqual(self.e['hp'],70)
        self.g.w['enemies'][self.e['type']]['heal_percent']=10;self.g.w['revision']['enemy_heal_enabled']=False
        self.now+=20;self.g.heal_enemies();self.assertEqual(self.e['hp'],70)

    def test_fixed_and_released_creatures_also_recover(self):
        fixed=self.g.state['spawns']['vault'];fixed['hp']=1
        released=self.g.spawn_creature('beetle','road');released.update(hp=1,released=True)
        self.g.state['released_enemies']['road']=released
        self.g.heal_enemies();self.now+=20;self.g.heal_enemies()
        self.assertGreater(fixed['hp'],1);self.assertGreater(released['hp'],1)

    def test_healing_owner_validation_and_live_save(self):
        for field,value in [('enemy_heal_interval',0),('enemy_heal_percent',101),('enemy_heal_delay',-1)]:
            w=copy.deepcopy(self.g.w);w['revision'][field]=value
            with self.assertRaises(ValueError):validate(w)
        w=copy.deepcopy(self.g.w);w['revision'].update(enemy_heal_delay=1,enemy_heal_interval=2,enemy_heal_percent=3)
        self.g.update_world(w);self.assertEqual(json.loads(self.path.read_text(encoding='utf-8'))['revision']['enemy_heal_percent'],3)
