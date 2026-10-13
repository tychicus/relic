import copy
import tempfile
import unittest
from pathlib import Path
from engine import Game, validate

ROOT=Path(__file__).resolve().parents[1]

class VisibilityTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)/'world.json'
  self.path.write_bytes((ROOT/'content/world.json').read_bytes())
  self.g=Game(self.path,Path(self.temp.name)/'test.sqlite3');self.g.create('Scout'); self.g.p['inventory'].append('lantern')  # Regression fixture: acquired light; new starts are tested separately.
  self.target=self.g.w['rooms']['gate'];self.target['obscured_from_outside']=True
  self.target['obscured_message']='Heavy fog blocks the way ahead.'
 def tearDown(self):self.g.db.close();self.temp.cleanup()
 def test_hidden_preview_with_lantern_and_visible_exit(self):
  self.assertIn('lantern',self.g.p['inventory'])
  self.target['enemy']='goblin';self.target['safe']=False
  self.g.command('look north')
  self.assertEqual(self.g.state['log'][-1]['text'],'Heavy fog blocks the way ahead.')
  self.assertNotIn('gate',self.g.state['spawns'])
  self.assertIn('north',self.g.snapshot()['room']['exits'])
  self.g.command('north');self.assertEqual(self.g.p['room'],'gate')
  self.assertEqual(self.g.snapshot()['room']['name'],self.target['name'])
  self.assertIsNotNone(self.g.p['combat'])
 def test_default_message_and_direction_alias(self):
  self.target['obscured_message']='   '
  self.g.command('look n')
  self.assertEqual(self.g.state['log'][-1]['text'],'It is too dark; you cannot see anything.')
 def test_room_darkness_still_applies_after_entry(self):
  self.target['dark']=True;self.g.p['inventory'].remove('lantern')
  self.g.command('n');self.assertEqual(self.g.snapshot()['room']['name'],'Darkness')
  self.g.p['inventory'].append('lantern');start=len(self.g.state['log']);self.g.command('look')
  self.assertTrue(any(self.target['description'] in line['text'] for line in self.g.state['log'][start:]))
 def test_clear_room_defaults_and_turn_off(self):
  del self.target['obscured_from_outside'];self.g.command('look north')
  self.assertIn(self.target['name'],self.g.state['log'][-1]['text'])
  self.target['obscured_from_outside']=False;self.g.command('look north')
  self.assertIn(self.target['description'],self.g.state['log'][-1]['text'])
 def test_save_and_reload_and_validation(self):
  self.g.update_world(copy.deepcopy(self.g.w));self.g.db.close()
  self.g=Game(self.path,Path(self.temp.name)/'test.sqlite3')
  self.g.command('look north');self.assertEqual(self.g.state['log'][-1]['text'],'Heavy fog blocks the way ahead.')
  for key,value in [('obscured_from_outside','yes'),('obscured_message',123),('obscured_message','x'*6001)]:
   w=copy.deepcopy(self.g.w);w['rooms']['gate'][key]=value
   with self.assertRaises(ValueError):validate(w)
