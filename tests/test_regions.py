import copy
import json
from pathlib import Path
import random
import tempfile
import unittest
from unittest.mock import Mock

from engine import Game, validate
from encounters import sync_encounter, ready_actions

ROOT = Path(__file__).resolve().parents[1]


class RegionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name)/'world.json'
        self.path.write_bytes((ROOT/'content/world.json').read_bytes())
        self.db = Path(self.temp.name)/'game.db'
        self.now = 1000.
        self.g = Game(self.path, self.db, random.Random(27), lambda: self.now)
        self.g.create('Scout')

    def tearDown(self):
        self.g.db.close()
        self.temp.cleanup()

    def reload(self):
        self.g.save(); self.g.db.close()
        self.path.write_text(json.dumps(self.g.w), encoding='utf-8')
        self.g = Game(self.path, self.db, random.Random(27), lambda: self.now)

    def road(self):
        return self.g.w['regions']['coppergrass_road'], self.g.state['regional_populations']['coppergrass_road']

    def test_default_world_caps_and_fixed_specials(self):
        for ident, region in self.g.w['regions'].items():
            actors=self.g.state['regional_populations'][ident]['creatures']
            self.assertEqual(len(actors),region['max_population'])
            self.assertTrue(all(e['location'] in region['spawn_rooms'] for e in actors))
            for rid in region['spawn_rooms']:
                self.assertLessEqual(len(self.g.creatures(rid,True,False)),region['max_per_room'])
                self.assertNotIn(rid,self.g.state['spawns'])
        self.assertEqual(self.g.state['spawns']['dungeon']['type'],'vampire')
        self.assertIn('vault',self.g.state['spawns'])
        self.assertFalse(self.g.creatures('square',True))

    def test_multiple_same_type_creatures_can_share_square_and_be_targeted(self):
        region,area=self.road()
        for e in area['creatures']: e['location']='meadow'
        self.g.p['room']='meadow'
        rows=self.g.creatures()
        self.assertEqual(len(rows),2)
        names=[self.g.creature_name(e) for e in rows]
        self.assertEqual(len(set(names)),2)
        with self.assertRaisesRegex(ValueError,'distinct'):self.g.find_creature('beetle')
        for e,name in zip(rows,names):
            self.assertIs(self.g.find_creature(name),e)
            self.assertIs(self.g.find_creature(e['uid']),e)

    def test_each_engaged_enemy_attacks_and_next_target_survives_victory(self):
        region,area=self.road(); region['roam']=False
        for e in area['creatures']:e['location']='meadow'
        self.g.w['enemies']['beetle'].update(aggressive=True,damage=[2,2])
        self.g.w['settings']['hit_chance']=1
        self.g.p['equipment']={}
        self.g.p.update(room='meadow',attack_ready=self.now+100)
        self.g.start_combat(); combat=self.g.p['combat']
        self.assertEqual(len(combat['engaged']),2)
        combat.update(turn='enemy',next_at=self.now)
        hp=self.g.p['hp'];self.g.tick()
        self.assertEqual(self.g.p['hp'],hp-4)
        first=self.g.enemy();self.g.victory(first)
        self.assertIsNotNone(self.g.p['combat'])
        self.assertNotEqual(self.g.p['target'],first['uid'])
        self.g.victory(self.g.enemy());self.assertIsNone(self.g.p['combat'])

    def test_neutral_bystander_only_joins_when_provoked(self):
        region,area=self.road();region['roam']=False
        self.g.w['enemies']['beetle']['aggressive']=False
        for e in area['creatures']:e['location']='meadow'
        self.g.p.update(room='meadow',attack_ready=self.now+100)
        self.g.command('attack '+area['creatures'][0]['uid'])
        self.assertEqual(len(self.g.p['combat']['engaged']),1)
        self.g.command('target '+area['creatures'][1]['uid'])
        self.g.tick()
        self.assertEqual(len(self.g.p['combat']['engaged']),2)

    def test_player_and_every_enemy_attack_in_one_pulse_with_independent_recovery(self):
        region,area=self.road();region['roam']=False
        for e in area['creatures']:e.update(location='meadow',hp=1000)
        self.g.w['enemies']['beetle'].update(aggressive=True,damage=[2,2],dodge=0)
        self.g.w['settings']['hit_chance']=1
        self.g.p.update(room='meadow',equipment={},hp=1000)
        self.g.start_combat();target=self.g.enemy()
        self.g.tick()
        self.assertLess(target['hp'],1000);self.assertEqual(self.g.p['hp'],996)
        self.assertEqual(self.g.p['combat']['initiator'],self.g.p['id'])
        deadlines=[a['attack_ready'] for a in [self.g.p]+area['creatures']]
        self.assertEqual(deadlines,[self.now+4]*3)
        hp=target['hp'];self.now+=2;self.g.tick()
        self.assertEqual(target['hp'],hp);self.assertEqual(self.g.p['hp'],996)
        area['creatures'][0]['attack_ready']=self.now+100
        self.now+=2;self.g.tick()
        self.assertLess(target['hp'],hp);self.assertEqual(self.g.p['hp'],994)
        # A delayed clock resolves one attack per ready actor, never catch-up bursts.
        self.now+=1000;self.g.tick();self.assertEqual(self.g.p['hp'],990)
        self.g.tick();self.assertEqual(self.g.p['hp'],990)

    def test_automatic_encounter_has_no_player_initiator(self):
        region,area=self.road();region['roam']=False
        for e in area['creatures']:e.update(location='meadow',hp=1000)
        self.g.w['enemies']['beetle']['aggressive']=True
        self.g.p.update(room='meadow',hp=1000)
        self.g.tick();fight=self.g.p['combat']
        self.assertIsNone(fight['initiator'])
        self.assertTrue(all(fight['targets'][e['uid']]==self.g.p['id'] for e in area['creatures']))
        self.g.command('attack '+area['creatures'][0]['uid'])
        self.assertIsNone(fight['initiator'])

    def test_roaming_uses_edges_boundaries_and_capacity(self):
        region,area=self.road();region['max_per_room']=1
        a,b=area['creatures'];a['location']='road';b['location']='meadow'
        for e in (a,b):e['roam_at']=self.now
        self.g.roam()
        self.assertEqual(a['location'],'road')
        self.assertEqual(b['location'],'meadow')
        b['hp']=0;b['respawn_at']=self.now+60
        a['roam_at']=self.now
        self.g.roam();self.assertEqual(a['location'],'meadow')
        for _ in range(40):
            self.now+=31;old=a['location'];self.g.roam()
            self.assertIn(a['location'],region['spawn_rooms'])
            if a['location']!=old:self.assertIn(a['location'],self.g.w['rooms'][old]['exits'].values())

    def test_engaged_and_unconscious_creatures_stay_put(self):
        region,area=self.road()
        a,b=area['creatures'];a['location']=b['location']='meadow'
        self.g.p.update(room='meadow',attack_ready=self.now+100)
        self.g.start_combat();b['unconscious']=True
        for e in (a,b):e['roam_at']=self.now
        self.g.roam()
        self.assertEqual([e['location'] for e in (a,b)],['meadow','meadow'])

    def test_replacements_delayed_capped_and_not_caused_by_looking(self):
        region,area=self.road();region['roam']=False
        dead=area['creatures'][0];dead['hp']=0;dead['respawn_at']=self.now+60
        self.g.p['room']='road'
        for _ in range(10):self.g.look('north');self.g.snapshot()
        self.assertEqual(len(area['creatures']),2)
        self.now+=59;self.g.tick_regions();self.assertEqual(len(self.g.region_creatures()),21)
        self.now+=1;self.g.tick_regions()
        self.assertEqual(len(area['creatures']),2)
        self.assertTrue(all(e['hp']>0 for e in area['creatures']))
        ids=[e['uid'] for e in area['creatures']]
        for _ in range(20):self.g.tick_regions()
        self.assertEqual(ids,[e['uid'] for e in area['creatures']])

    def test_reload_preserves_identity_health_location_and_deadlines(self):
        region,area=self.road();area['creatures'][0]['hp']=7
        before=copy.deepcopy(self.g.state['regional_populations'])
        self.reload()
        self.assertEqual(self.g.state['regional_populations'],before)
        self.now+=100000;self.reload()
        self.assertEqual(self.g.state['regional_populations'],before)

    def test_fog_changes_scouting_and_survives_owner_save(self):
        self.g.p['room']='road'
        w=copy.deepcopy(self.g.w);w['regions']['coppergrass_road'].update(weather='fog',fog=100)
        self.g.update_world(w)
        self.g.look('north');self.assertIn('indistinct',self.g.state['log'][-1]['text'])
        data=self.g.snapshot();self.assertEqual(data['room']['weather'],'fog');self.assertEqual(data['room']['fog'],100)
        self.reload();self.assertEqual(self.g.fog_at('meadow'),100)
        self.g.w['regions']['coppergrass_road']['fog']=0
        self.g.look('north');self.assertIn('Meadow',self.g.state['log'][-1]['text'])

    def test_owner_can_change_bank_but_cannot_discard_occupied_region(self):
        region,area=self.road();before=copy.deepcopy(area)
        w=copy.deepcopy(self.g.w);w['regions']['coppergrass_road']['pool']=[dict(enemy='deer',weight=1)]
        self.g.update_world(w);self.assertEqual(area,before)
        for change in ('delete','cap','room','capacity'):
            w=copy.deepcopy(self.g.w);r=w['regions']['coppergrass_road']
            if change=='delete':del w['regions']['coppergrass_road']
            elif change=='cap':r['max_population']=1
            elif change=='room':r['spawn_rooms']=[];r['max_population']=0
            else:
                for e in area['creatures']:e['location']='meadow'
                r['max_per_room']=1
            with self.assertRaises(ValueError):self.g.update_world(w)

    def test_region_validation_rejects_bad_bounds_and_memberships(self):
        for field,value in [('max_population',-1),('max_per_room',0),('fog',101),('weather','hail'),('spawn_seconds',0),('pool',[dict(enemy='missing',weight=1)]),('spawn_rooms',['square']),('rooms',['square'])]:
            w=copy.deepcopy(self.g.w);w['regions']['coppergrass_road'][field]=value
            with self.assertRaises(ValueError,msg=field):validate(w)

    def test_old_save_adopts_wounded_and_unconscious_creatures_once(self):
        actual=copy.deepcopy(self.g.w)
        self.g.db.close();self.db.unlink()
        legacy=copy.deepcopy(actual);legacy.pop('regions')
        self.path.write_text(json.dumps(legacy),encoding='utf-8')
        self.g=Game(self.path,self.db,random.Random(3),lambda:self.now);self.g.create('Veteran')
        e=self.g.state['spawns']['meadow'];e.update(hp=3,unconscious=True)
        uid=e['uid'];self.g.save();self.g.db.close()
        self.path.write_text(json.dumps(actual),encoding='utf-8')
        self.g=Game(self.path,self.db,random.Random(3),lambda:self.now)
        adopted=[e for e in self.g.region_creatures() if e['uid']==uid]
        self.assertEqual(len(adopted),1);self.assertEqual(adopted[0]['hp'],3);self.assertTrue(adopted[0]['unconscious'])
        self.reload();self.assertEqual(sum(e['uid']==uid for e in self.g.region_creatures()),1)


class SharedEncounterTests(unittest.TestCase):
    def test_enemies_focus_initiator_and_keep_target_when_other_players_attack(self):
        players=[dict(id='p1',hp=30,room='arena',target='e1'),dict(id='p2',hp=30,room='arena',target='e1')]
        enemies=[dict(uid='e1',hp=20,location='arena'),dict(uid='e2',hp=20,location='arena')]
        fight=dict(room='arena',initiator='p2');rng=Mock()
        roster=sync_encounter(fight,players,enemies,rng)
        self.assertEqual([fight['targets'][e['uid']] for e in enemies],['p2','p2'])
        self.assertEqual(len(ready_actions(fight,roster,None,10)),4)
        players[0]['target']='e2'
        enemies.append(dict(uid='e3',hp=20,location='arena'))
        sync_encounter(fight,players,enemies,rng)
        self.assertEqual([fight['targets'][e['uid']] for e in enemies],['p2']*3)
        rng.choice.assert_not_called()

    def test_automatic_targets_roll_per_enemy_then_stay_until_invalid(self):
        players=[dict(id='p1',hp=30,room='arena'),dict(id='p2',hp=30,room='arena'),dict(id='p3',hp=30,room='arena')]
        enemies=[dict(uid='e1',hp=20,location='arena'),dict(uid='e2',hp=20,location='arena')]
        fight=dict(room='arena');rng=Mock();rng.choice.side_effect=['p2','p1','p3']
        sync_encounter(fight,players,enemies,rng)
        self.assertEqual([fight['targets'][e['uid']] for e in enemies],['p2','p1'])
        self.assertEqual(rng.choice.call_count,2)
        self.assertEqual(rng.choice.call_args.args[0],['p1','p2','p3'])
        sync_encounter(fight,list(reversed(players)),enemies,rng)
        self.assertEqual(rng.choice.call_count,2)
        players[1]['room']='town'
        sync_encounter(fight,players,enemies,rng)
        self.assertEqual(fight['targets']['e1'],'p3')
        self.assertEqual(fight['targets']['e2'],'p1')
        self.assertEqual(rng.choice.call_args.args[0],['p1','p3'])
        players[2]['hp']=0
        sync_encounter(fight,players,enemies,rng)
        self.assertEqual(fight['targets']['e1'],'p1')
        players[0]['hp']=0
        roster=sync_encounter(fight,players,enemies,rng)
        self.assertFalse(ready_actions(fight,roster,None,100))

    def test_multiple_players_have_independent_targets_and_attack_timers(self):
        players=[dict(id='p1',hp=30,room='arena',target='e1'),dict(id='p2',hp=30,room='arena',target='e2',attack_ready=12)]
        enemies=[dict(uid='e1',hp=20,location='arena'),dict(uid='e2',hp=20,location='arena')]
        fight=dict(room='arena',targets={'e1':'p1','e2':'p2'})
        roster=sync_encounter(fight,players,enemies)
        self.assertEqual(fight['targets'],dict(p1='e1',p2='e2',e1='p1',e2='p2'))
        self.assertEqual(len(ready_actions(fight,roster,'players',10)),1)
        self.assertEqual(len(ready_actions(fight,roster,'players',12)),2)
        self.assertEqual(len(ready_actions(fight,roster,'enemies',10)),2)
        players[0]['room']='town';enemies[1]['hp']=0
        roster=sync_encounter(fight,players,enemies)
        self.assertEqual(fight['targets'],dict(p2='e1',e1='p2'))
        enemies[0]['unconscious']=True
        roster=sync_encounter(fight,players,enemies)
        self.assertFalse(ready_actions(fight,roster,'players',12))
