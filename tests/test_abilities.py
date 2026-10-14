from legacy_fixture import disable_regions
import copy
import json
import random
import shutil
import tempfile
import unittest
from pathlib import Path
from engine import Game,validate
ROOT=Path(__file__).resolve().parents[1]
class AbilityTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.path=self.root/'world.json'
        shutil.copyfile(ROOT/'content/world.json',self.path);self.now=1000;self.db=self.root/'test.sqlite3';disable_regions(self.path);self.g=Game(self.path,self.db,random.Random(4),lambda:self.now)
    def tearDown(self):self.g.db.close();self.tmp.cleanup()
    def create(self,race='human',cls='warrior'):self.g.create('Tester',race,cls)
    def add_options(self):
        self.g.w['races']['elf']={'name':'Elf','hp_bonus':8}
        self.g.w['classes']['mage']={'name':'Mage','hp':40,'damage':[2,4],'skills':[]}
    def skill(self,id='mend',effect='heal',level=1,classes=None,races=None):
        self.g.w['skills'][id]={'name':id.title(),'description':'Test ability.','cooldown':12,'multiplier':2,'heal':20,'chance':100,'effect':effect,'unlock_level':level,'allowed_classes':classes,'allowed_races':races}
    def log(self):return self.g.state['log'][-1]['text']
    def test_new_starts_without_lantern_and_keeps_equipment(self):
        self.create();self.assertEqual(self.g.p['inventory'],['potion','potion']);self.assertEqual(self.g.p['gold'],30);self.assertEqual(self.g.p['equipment'],self.g.w['starting']['equipment'])
    def test_race_class_selection_and_snapshot(self):
        self.add_options();s=self.g.snapshot();self.assertEqual([r['name'] for r in s['creation']['races']],['Elf','Human'])
        self.create('elf','mage');self.assertEqual(self.g.max_hp(),48);self.assertEqual(self.g.p['hp'],48);self.assertEqual(self.g.snapshot()['player']['class_name'],'Mage')
        self.path.write_text(json.dumps(self.g.w));self.g.save();self.g.db.close();self.g=Game(self.path,self.db,clock=lambda:self.now);self.assertEqual(self.g.p['race'],'elf');self.assertEqual(self.g.p['class'],'mage')
    def test_invalid_selection_creates_no_character(self):
        with self.assertRaises(ValueError):self.g.create('Tester','missing','warrior')
        self.assertIsNone(self.g.p)
    def test_both_class_and_race_must_match(self):
        self.add_options();self.skill(classes=['mage'],races=['elf']);self.create()
        self.g.p['hp']=1
        for race,cls,allowed in [('human','warrior',False),('elf','warrior',False),('human','mage',False),('elf','mage',True)]:
            self.g.p.update(race=race,**{'class':cls});self.assertEqual(self.g.skill_eligible('mend'),allowed)
            if not allowed:self.g.command('cast mend');self.assertEqual(self.g.p['hp'],1);self.assertNotIn('mend',self.g.p['cooldowns'])
        self.g.command('cast mend');self.assertEqual(self.g.p['hp'],21)
    def test_any_includes_future_classes_and_empty_allows_nobody(self):
        self.skill();self.add_options();self.create('elf','mage');self.assertTrue(self.g.skill_eligible('mend'))
        self.g.w['skills']['mend']['allowed_classes']=[];self.assertFalse(self.g.skill_eligible('mend'))
    def test_locked_commands_and_aliases_are_enforced(self):
        self.create();self.g.w['skills']['bash']['unlock_level']=5;self.g.p['room']='meadow';self.g.start_combat();self.g.p['combat']['next_at']=self.now+100
        hp=self.g.enemy()['hp']
        for cmd in ['bash','cast bash','skill Bash']:
            self.g.command(cmd);self.assertIn('level 5',self.log());self.assertEqual(self.g.enemy()['hp'],hp);self.assertNotIn('bash',self.g.p['cooldowns'])
        self.g.w['skills']['knockout']['allowed_races']=[];self.g.command('knockout beetle');self.assertIn('not available',self.log())
    def test_healing_cooldown_full_health_and_reload(self):
        self.skill();self.create();self.g.command('cast mend');self.assertNotIn('mend',self.g.p['cooldowns'])
        self.g.p['hp']=1;self.g.command('cast mend');self.assertEqual(self.g.p['hp'],21);self.g.command('cast mend');self.assertEqual(self.g.p['hp'],21);self.assertIn('ready in',self.log())
        self.path.write_text(json.dumps(self.g.w));self.g.save();self.g.db.close();self.g=Game(self.path,self.db,clock=lambda:self.now)
        self.g.command('cast mend');self.assertEqual(self.g.p['hp'],21);self.now+=12;self.g.command('cast mend');self.assertEqual(self.g.p['hp'],41)
    def test_custom_damage_respects_combat_dodge_and_cooldown(self):
        self.skill('fire_bolt','damage');self.g.w['skills']['fire_bolt']['name']='Fire Bolt';self.create();self.g.command('cast Fire Bolt');self.assertIn('active fight',self.log());self.assertNotIn('fire_bolt',self.g.p['cooldowns'])
        self.g.p['room']='meadow';self.g.start_combat();self.g.p['combat']['next_at']=self.now+100;self.g.w['enemies']['beetle']['dodge']=100;self.g.w['settings']['hit_chance']=1
        hp=self.g.enemy()['hp'];self.g.command('cast fire bolt');self.assertEqual(self.g.enemy()['hp'],hp);self.assertIn('dodges your Fire Bolt',self.log());self.assertIn('fire_bolt',self.g.p['cooldowns'])
        self.now+=12;self.g.w['enemies']['beetle']['dodge']=0;self.g.command('cast fire_bolt');self.assertLess(self.g.state['spawns']['meadow']['hp'],hp)
    def test_custom_knockout_uses_eligibility_and_its_own_cooldown(self):
        self.skill('sleep','knockout');self.create();self.g.p['room']='meadow';e=self.g.enemy();e['hp']=1;self.g.w['enemies']['beetle']['capture_resistance']=0
        self.g.command('cast sleep');self.assertTrue(e['unconscious']);self.assertIn('sleep',self.g.p['cooldowns']);self.assertIsNone(self.g.p['combat'])
    def test_unlock_announced_once_and_available_to_existing_characters(self):
        self.skill(level=2);self.create();self.g.p['room']='meadow';self.g.w['enemies']['beetle']['xp']=35
        self.g.victory(self.g.enemy());self.assertEqual(self.g.p['level'],2);self.assertIn('mend',self.g.available_skill_ids())
        lines=lambda:[l for l in self.g.state['log'] if l['text'].startswith('New skill unlocked: Mend')]
        self.assertEqual(len(lines()),1);self.g.announce_skills();self.assertEqual(len(lines()),1)
        self.g.p['hp']=1;self.g.command('cast mend');self.assertEqual(self.g.p['hp'],21)
    def test_owner_lowering_requirement_unlocks_saved_character(self):
        self.skill(level=5);self.create();w=copy.deepcopy(self.g.w);w['skills']['mend']['unlock_level']=1;self.g.update_world(w);self.assertIn('mend',self.g.available_skill_ids());self.assertTrue(any('New skill unlocked: Mend' in l['text'] for l in self.g.state['log']))
    def test_invalid_skill_configuration_rejected_atomically(self):
        self.skill();self.create();before=self.path.read_bytes()
        for key,value in [('effect','teleport'),('unlock_level',0),('unlock_level',1.5),('allowed_classes',['missing']),('allowed_races','elf'),('heal',0)]:
            w=copy.deepcopy(self.g.w);w['skills']['mend'][key]=value
            with self.assertRaises(ValueError):self.g.update_world(w)
            self.assertEqual(self.path.read_bytes(),before)
    def test_unavailable_skills_not_in_player_list_and_no_object_hints(self):
        self.skill(classes=[]);self.create();s=self.g.snapshot();self.assertNotIn('mend',[k['id'] for k in s['player_skills']]);self.assertEqual(s['room']['objects'],[])
        self.g.command('look nonexistent');self.assertEqual(self.log(),'You do not see that here.')
        self.g.command('look fountain');self.assertNotEqual(self.log(),'You do not see that here.')
    def test_skill_configuration_saves_and_reload(self):
        self.add_options();self.skill('sunburst','damage',3,['mage'],['elf']);self.create();self.g.update_world(copy.deepcopy(self.g.w));self.g.db.close();self.g=Game(self.path,self.db,clock=lambda:self.now)
        self.assertEqual(self.g.w['skills']['sunburst']['allowed_races'],['elf']);self.assertEqual(self.g.w['skills']['sunburst']['unlock_level'],3)
if __name__=='__main__':unittest.main()
