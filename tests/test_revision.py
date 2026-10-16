from legacy_fixture import disable_regions
import copy
import json
import random
import sqlite3
import tempfile
import unittest
from pathlib import Path
from engine import Game, validate

ROOT=Path(__file__).resolve().parents[1]

class RevisionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.path=self.root/'world.json'
        world=json.loads((ROOT/'content/world.json').read_bytes())
        world['skills']['enchanting'].update(unlock_level=3,allowed_classes=None)
        self.path.write_text(json.dumps(world),encoding='utf-8')
        self.now=1000.;self.db=self.root/'save.db'
        disable_regions(self.path);self.g=Game(self.path,self.db,random.Random(5),lambda:self.now);self.g.create('Tester')
        self.g.p['inventory'].append('lantern');self.g.w['settings']['hit_chance']=1
    def tearDown(self):self.g.db.close();self.temp.cleanup()
    def advance(self,seconds=2):self.now+=seconds;self.g.tick()
    def log(self):return '\n'.join(x['text'] for x in self.g.state['log'][-5:])
    def crowd(self,aggressive=True):
        self.g.w['enemies']['beetle']['aggressive']=aggressive
        self.g.w['rooms']['meadow']['population']=[dict(id='test',enemy='beetle',count=2,chance=100,respawn=True,delay=10)]
        self.g.p['room']='meadow';return self.g.creatures()
    def test_duplicate_descriptors_and_ambiguous_command(self):
        rows=self.crowd(False);names=[self.g.creature_name(e) for e in rows]
        self.assertEqual(len(set(names)),3);self.assertTrue(all('beetle' in x.lower() for x in names))
        self.g.command('target beetle');self.assertIn('distinct',self.log())
        self.g.command('target '+names[1]);self.assertEqual(self.g.p['target'],rows[1]['uid'])
        self.assertIsNone(self.g.p['combat'])
    def test_all_engaged_enemies_attack_and_retarget(self):
        rows=self.crowd();self.g.p['hp']=1000
        for e in rows:e['hp']=100
        self.g.start_combat();self.g.tick();self.advance()
        self.assertEqual(sum('hits you' in l['text'] for l in self.g.state['log']),3)
        self.g.command('target '+rows[2]['uid']);self.assertEqual(self.g.enemy(),rows[2])
        self.g.victory(rows[2]);self.assertIsNotNone(self.g.p['combat']);self.assertNotEqual(self.g.p['target'],rows[2]['uid'])
    def test_population_independent_respawn_and_disabled(self):
        rows=self.crowd(False);extra=rows[1];self.g.victory(extra)
        self.assertEqual(len(self.g.creatures()),2);self.now+=11
        after=self.g.creatures();self.assertEqual(len(after),3);self.assertNotIn(extra['uid'],[x['uid'] for x in after])
        rule=self.g.w['rooms']['meadow']['population'][0];rule['respawn']=False
        victim=next(e for e in after if e.get('group'));self.g.victory(victim);self.now+=100
        self.assertEqual(len(self.g.creatures()),2)
    def test_nothing_spawn_and_entry_cooldown(self):
        room=self.g.w['rooms']['prairie_0_0'];rule=room['population'][0];rule['chance']=0
        self.g.roll_encounter('prairie_0_0');slot=self.g.state['populations']['prairie_0_0']['wildlife:0']
        self.assertIsNone(slot['creature']);rule['chance']=100
        self.g.roll_encounter('prairie_0_0');self.assertIsNone(slot['creature'])
        self.now+=181;self.g.ensure_groups('prairie_0_0');self.assertIsNone(slot['creature'])
        self.g.roll_encounter('prairie_0_0');self.assertIsNotNone(slot['creature'])
    def test_roam_restrictions_and_no_duplicate_home_spawn(self):
        self.g.p['room']='meadow';room=self.g.w['rooms']['meadow'];room.update(roaming=True,roam_rooms=['road'],roam_seconds=2)
        e=self.g.enemy();e['roam_at']=0;self.g.roam();self.assertEqual(e['location'],'road')
        self.assertIsNone(self.g.enemy());self.assertEqual(self.g.creatures('road')[0]['uid'],e['uid'])
        self.now+=3;self.g.roam();self.assertEqual(e['location'],'road')
    def test_status_refresh_stack_expiry_and_resistance(self):
        self.g.p['room']='meadow';e=self.g.enemy();e['hp']=100
        attachment=[dict(effect='scorched',chance=100,duration=3)]
        self.g.apply_effects(attachment,e);self.g.pulse_effects(e);self.assertEqual(e['hp'],98)
        self.g.apply_effects(attachment,e);self.assertEqual(e['effects'][0]['remaining'],3);self.assertEqual(e['effects'][0]['stacks'],1)
        self.g.w['status_effects']['scorched']['stacking']='stack'
        for _ in range(5):self.g.apply_effects(attachment,e)
        self.assertEqual(e['effects'][0]['stacks'],3)
        for _ in range(3):self.g.pulse_effects(e)
        self.assertEqual(e['effects'],[])
        self.g.w['enemies']['beetle']['resistances']=[dict(effect='scorched',chance=100)]
        self.g.apply_effects(attachment,e);self.assertEqual(e['effects'],[])
    def test_skill_weapon_enemy_attachment_sources(self):
        self.g.p['room']='meadow';e=self.g.enemy();e['hp']=1000
        attach=[dict(effect='scorched',chance=100,duration=3)]
        self.g.w['skills']['bash']['status_effects']=attach;self.g.start_combat();self.g.activate_skill('bash');self.assertEqual(len(e['effects']),1)
        e['effects']=[];self.g.w['items']['rusted_sword']['status_effects']=attach;self.g.strike();self.assertEqual(len(e['effects']),1)
        self.g.w['enemies']['beetle']['status_effects']=attach;self.g.enemy_strike(e);self.assertEqual(len(self.g.p['effects']),1)
    def test_stun_prevents_attack_and_skill_without_cooldown(self):
        self.g.p['room']='meadow';e=self.g.enemy();e['hp']=100
        self.g.apply_effects([dict(effect='stunned',chance=100,duration=2)],self.g.p)
        with self.assertRaises(ValueError):self.g.activate_skill('bash')
        self.assertNotIn('bash',self.g.p['cooldowns']);self.g.start_combat();self.g.tick();self.assertEqual(e['hp'],100)
    def test_sharpen_and_enchant_are_individual_and_persist(self):
        self.g.p.update(level=7,gold=1000);self.g.p['inventory'].append('rusted_sword')
        self.g.activate_skill('sharpening');iid=self.g.p['equipment']['weapon']
        self.assertTrue(iid.startswith('@'));self.assertEqual(self.g.item(iid)['damage'],4);self.assertEqual(self.g.item('rusted_sword')['damage'],2)
        self.g.w['revision']['enchant_base']=100;self.g.activate_skill('enchanting')
        self.assertEqual(self.g.item(iid)['damage'],5);self.assertEqual(self.g.p['proficiencies']['enchanting'],1)
        self.g.save();self.g.db.close();self.g=Game(self.path,self.db,clock=lambda:self.now)
        self.assertEqual(self.g.item(iid)['damage'],5);self.now+=121;self.assertEqual(self.g.item(iid)['damage'],3)
    def test_enchant_failure_destruction_eligibility_and_cost(self):
        with self.assertRaises(ValueError):self.g.activate_skill('enchanting')
        self.g.p.update(level=3,gold=100);self.g.w['revision'].update(enchant_base=0,enchant_destroy=100)
        self.g.activate_skill('enchanting');self.assertNotIn('weapon',self.g.p['equipment']);self.assertEqual(self.g.p['gold'],80)
        self.assertEqual(self.g.p['proficiencies']['enchanting'],1)
    def test_hands_shields_dual_and_two_handed_validation(self):
        self.g.p['inventory']+=['buckler','iron_sword']
        self.g.command('equip buckler');self.assertEqual(self.g.p['equipment']['left_hand'],'buckler')
        self.g.command('equip iron sword left');self.assertIn('requires',self.log());self.assertEqual(self.g.p['equipment']['left_hand'],'buckler')
        self.g.p['level']=3;self.g.command('equip iron sword left');self.assertEqual(self.g.p['equipment']['left_hand'],'iron_sword')
        self.g.command('unequip right');self.assertNotIn('weapon',self.g.p['equipment'])
        self.g.command('unequip left');self.g.w['items']['iron_sword']['hands']=2
        self.g.command('equip iron sword right');self.assertEqual(self.g.p['equipment']['weapon'],'iron_sword')
        self.g.command('equip buckler');self.assertNotIn('left_hand',self.g.p['equipment'])
    def test_recall_blocked_and_success(self):
        self.g.p.update(level=3,room='road');self.g.p['inventory']=['recall_scroll'];self.g.w['rooms']['road']['recall_disabled']=True
        self.g.command('recall');self.assertEqual(self.g.p['room'],'road');self.assertIn('recall_scroll',self.g.p['inventory'])
        self.g.w['rooms']['road']['recall_disabled']=False;self.g.command('recall');self.assertEqual(self.g.p['room'],'square');self.assertNotIn('recall_scroll',self.g.p['inventory'])
    def test_recall_combat_and_optional_consumption(self):
        self.g.p.update(level=3,room='meadow');self.g.p['inventory']=['recall_scroll'];self.g.start_combat();self.g.command('recall');self.assertIn('recall_scroll',self.g.p['inventory'])
        self.g.w['revision']['recall_failure_consumes']=True;self.g.command('recall');self.assertNotIn('recall_scroll',self.g.p['inventory']);self.assertEqual(self.g.p['room'],'meadow')
    def test_perception_limits_fog_and_hidden_intermediate(self):
        self.g.w['revision']['perception_chance']=100;self.g.w['revision']['perception_distance_penalty']=0
        self.g.look('north 2');self.assertIn('Frontier Road',self.log())
        self.g.w['rooms']['gate']['obscured_from_outside']=True;self.g.state['log']=[];self.g.look('north 2');self.assertNotIn('Frontier Road',self.log())
        self.g.w['rooms']['gate']['obscured_from_outside']=False;self.g.w['rooms']['gate']['fog']=100;self.g.look('north 2');self.assertIn('indistinct',self.log())
        with self.assertRaises(ValueError):self.g.look('north 99')
    def test_harvesting_each_creature_once_and_cooking(self):
        for eid,ingredient,recipe,output in [('deer','raw_venison','roast_venison','roast_venison'),('turkey','raw_turkey','roast_turkey','roast_turkey'),('beetle','beetle_meat','toast_beetle','toasted_beetle')]:
            self.g.p['room']='meadow';e=self.g.spawn_creature(eid,'meadow');self.g.victory(e);self.g.harvest(e['uid']);self.assertIn(ingredient,self.g.p['inventory'])
            with self.assertRaises(ValueError):self.g.harvest(e['uid'])
            self.g.p['room']=next(rid for rid,r in self.g.w['rooms'].items() if r.get('cooking_fire'))
            self.g.cook(recipe);self.assertNotIn(ingredient,self.g.p['inventory']);self.assertIn(output,self.g.p['inventory'])
    def test_food_cap_cooldown_and_full_health_preservation(self):
        self.g.p['inventory']+=['apple','apple'];self.g.command('eat apple');self.assertEqual(self.g.p['inventory'].count('apple'),2)
        self.g.p['hp']-=2;self.g.command('eat apple');self.assertEqual(self.g.p['hp'],self.g.max_hp());self.assertEqual(self.g.p['inventory'].count('apple'),1)
        self.g.p['hp']-=10;self.g.command('eat apple');self.assertEqual(self.g.p['inventory'].count('apple'),1)
    def test_npc_placement_dialogue_and_interactions(self):
        self.g.command('say hello to tamsin');self.assertIn('cooking fire',self.log())
        self.g.p['room']='road';self.g.command('say hello to tamsin');self.assertIn('No matching',self.log())
        self.g.p['room']='square';self.g.w['npcs']['tamsin']['interactions']=[];self.g.command('say hello to tamsin');self.assertIn('not available',self.log())
    def test_save_reload_preserves_population_effects_and_no_offline_burst(self):
        rows=self.crowd();self.g.start_combat();self.g.apply_effects([dict(effect='scorched',chance=100,duration=3)],rows[1]);self.g.save()
        self.path.write_text(json.dumps(self.g.w),encoding='utf-8')
        p=copy.deepcopy(self.g.p);state=copy.deepcopy(self.g.state['populations']);self.g.db.close();self.now+=10000
        self.g=Game(self.path,self.db,clock=lambda:self.now);self.g.tick();self.assertEqual(self.g.p['hp'],p['hp']);self.assertEqual(self.g.state['populations']['meadow'],state['meadow'])
    def test_validation_rejects_bad_references_numbers_and_safe_spawns(self):
        for mutate in [lambda w:w['revision'].update(enchant_destroy=101),lambda w:w['items']['buckler'].update(kind='loot'),lambda w:w['npcs']['tamsin'].update(room='missing'),lambda w:w['status_effects']['scorched'].update(duration=float('nan')),lambda w:w['rooms']['square'].update(population=[dict(id='x',enemy='deer')])]:
            w=copy.deepcopy(self.g.w);mutate(w)
            with self.assertRaises(ValueError):validate(w)
    def test_owner_cannot_delete_active_effect_or_modified_weapon(self):
        self.g.p['level']=3;self.g.activate_skill('sharpening');w=copy.deepcopy(self.g.w);del w['items']['rusted_sword']
        with self.assertRaises(ValueError):self.g.check_live_references(w)
        self.g.apply_effects([dict(effect='poisoned',chance=100)],self.g.p);w=copy.deepcopy(self.g.w);del w['status_effects']['poisoned']
        with self.assertRaises(ValueError):self.g.check_live_references(w)

    def test_capture_one_enemy_retains_other_opponents_and_unique_pickup(self):
        rows=self.crowd();self.g.w['enemies']['beetle'].update(capturable=True,capture_resistance=0,capture_health=100)
        self.g.w['skills']['knockout']['chance']=100
        self.g.start_combat();self.g.knockout(rows[1]['uid']);self.assertTrue(rows[1]['unconscious']);self.assertIsNotNone(self.g.p['combat'])
        self.assertNotEqual(self.g.p['target'],rows[1]['uid'])
        self.g.w['enemies']['beetle']['aggressive']=False;self.g.p['combat']=None
        self.g.command('get '+rows[1]['uid']);self.assertEqual(rows[1]['hp'],0)
        self.assertEqual(sum(self.g.item(i)['kind']=='captive' for i in self.g.p['inventory']),1)
    def test_modified_weapon_in_chest_keeps_identity_and_can_reload(self):
        self.g.p['level']=3;self.g.activate_skill('sharpening');weapon=self.g.p['equipment']['weapon']
        chest=self.g.grant('storage_chest');self.g.p['inventory'].append(chest)
        self.g.command('unequip right');self.g.command('put '+weapon+' in '+chest)
        self.assertIn(weapon,self.g.state['instances'][chest]['contents']);self.g.save();self.g.db.close()
        self.g=Game(self.path,self.db,clock=lambda:self.now);self.g.command('get '+weapon+' from '+chest)
        self.g.command('equip '+weapon);self.assertEqual(self.g.p['equipment']['weapon'],weapon)
        self.assertEqual(self.g.item(weapon)['damage'],4)
    def test_destruction_with_offhand_keeps_playable_save(self):
        self.g.p.update(level=3,gold=100);self.g.p['inventory'].append('iron_sword');self.g.equip_hand('iron sword left')
        self.g.w['revision'].update(enchant_base=0,enchant_destroy=100);self.g.activate_skill('enchanting')
        self.assertNotIn('weapon',self.g.p['equipment']);self.g.save();self.g.db.close()
        self.g=Game(self.path,self.db,clock=lambda:self.now);self.assertEqual(self.g.p['equipment']['left_hand'],'iron_sword')
    def test_shield_reduces_enemy_damage(self):
        self.g.p['room']='meadow';e=self.g.enemy();self.g.w['enemies']['beetle']['damage']=[5,5]
        self.g.p['inventory'].append('buckler');self.g.equip_hand('buckler');hp=self.g.p['hp'];self.g.enemy_strike(e)
        self.assertEqual(hp-self.g.p['hp'],3)
    def test_slow_actually_delays_attacks_and_invalid_skill_keeps_schedule(self):
        self.g.p['room']='meadow';e=self.g.enemy();e['hp']=1000;self.g.start_combat();self.g.tick()
        self.g.apply_effects([dict(effect='slowed',chance=100,duration=8)],self.g.p)
        self.advance();self.advance();hp=e['hp'];deadline=self.g.p['combat']['next_at']
        self.g.command('cast missing');self.assertEqual(self.g.p['combat']['next_at'],deadline)
        self.advance();self.advance();self.assertEqual(e['hp'],hp)
    def test_effect_kill_rewards_once_and_retargets(self):
        rows=self.crowd();rows[0]['hp']=1;self.g.start_combat();xp=self.g.p['xp']
        self.g.apply_effects([dict(effect='scorched',chance=100,duration=3)],rows[0]);self.g.tick()
        self.assertEqual(self.g.p['xp'],xp+self.g.w['enemies']['beetle']['xp']);self.assertIsNotNone(self.g.p['combat'])
        self.assertNotEqual(self.g.p['target'],rows[0]['uid']);self.assertEqual(len(self.g.state['corpses']),1)
    def test_arrival_joins_fight_and_departed_target_changes(self):
        rows=self.crowd();self.g.start_combat();self.g.retarget();self.g.p['target']=rows[1]['uid']
        rows[1]['location']='road';self.g.retarget();self.assertNotEqual(self.g.p['target'],rows[1]['uid'])
        e=self.g.spawn_creature('beetle','road');e['location']='meadow';self.g.state['released_enemies']['road']=e
        self.g.retarget();self.assertIn(e['uid'],self.g.p['combat']['engaged'])
    def test_legacy_encounter_respawn_disabled(self):
        rid=next(rid for rid,r in self.g.w['rooms'].items() if r.get('encounter'));r=self.g.w['rooms'][rid]
        r['encounter']['chance']=100;r['respawn_enabled']=False;self.g.p['room']=rid;self.g.roll_encounter(rid)
        e=self.g.enemy();self.assertIsNotNone(e);self.g.victory(e);self.now+=10000;self.g.roll_encounter(rid);self.assertIsNone(self.g.enemy())
    def test_legacy_entry_encounter_and_added_group_have_independent_slots(self):
        rid=next(rid for rid,r in self.g.w['rooms'].items() if r.get('encounter'));r=self.g.w['rooms'][rid]
        r['encounter']['chance']=100;r['population']=[dict(id='wildlife',enemy='turkey',count=1,chance=100,trigger='timer')]
        self.g.p['room']=rid;self.g.creatures();self.g.roll_encounter(rid)
        self.assertEqual(len(self.g.creatures()),2)
    def test_full_bag_harvest_failure_and_cooking_failure_preserve_inputs(self):
        self.g.p['room']='meadow';e=self.g.enemy();self.g.victory(e);self.g.w['settings']['bag_capacity']=len(self.g.p['inventory'])
        with self.assertRaises(ValueError):self.g.harvest(e['uid'])
        self.assertFalse(self.g.state['corpses'][0].get('harvested'))
        self.g.w['settings']['bag_capacity']=15;self.g.harvest(e['uid'])
        self.g.p['room']=next(rid for rid,r in self.g.w['rooms'].items() if r.get('cooking_fire'));self.g.w['recipes']['toast_beetle']['chance']=0
        self.g.cook('toast_beetle');self.assertIn('beetle_meat',self.g.p['inventory'])
    def test_partial_sight_reports_near_room_only(self):
        self.g.w['rooms']['square']['sight_limit']=1;self.g.state['log']=[];self.g.look('north 3')
        self.assertIn('North Gate',self.log());self.assertNotIn('Frontier Road',self.log());self.assertIn('obstruction',self.log())
    def test_owner_updates_retain_extra_creatures_health_and_effects(self):
        rows=self.crowd(False);rows[1]['hp']=7;self.g.apply_effects([dict(effect='scorched',chance=100)],rows[1])
        w=copy.deepcopy(self.g.w);w['revision']['food_cooldown']=9;self.g.update_world(w)
        self.assertEqual(rows[1]['hp'],7);self.assertEqual(len(rows[1]['effects']),1)
        w=copy.deepcopy(self.g.w);w['rooms']['meadow']['population']=[]
        with self.assertRaises(ValueError):self.g.update_world(w)
    def test_many_pulses_and_commands_remain_valid(self):
        self.crowd();self.g.p.update(level=7,hp=137,gold=1000)
        for command in ['attack','bash','cast lightning','target beetle','knockout','flee','look','inventory','equipment','skills','eat potion','recall']*5:
            self.g.command(command);self.advance()
        validate(self.g.w);self.g.check_live_references(self.g.w);self.g.save()

if __name__=='__main__':unittest.main()
