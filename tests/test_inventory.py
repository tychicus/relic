import tempfile
import unittest
from pathlib import Path
from engine import Game

ROOT=Path(__file__).resolve().parents[1]
class InventoryTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();p=Path(self.temp.name)
  (p/'world.json').write_bytes((ROOT/'content/world.json').read_bytes())
  self.g=Game(p/'world.json',p/'test.sqlite3');self.g.create('Quaffer'); self.g.p['inventory'].append('lantern')  # Regression fixture: acquired light; new starts are tested separately.
 def tearDown(self):self.g.db.close();self.temp.cleanup()
 def test_quaff_heals_and_consumes_one(self):
  self.g.p['hp']=1;before=self.g.p['inventory'].count('potion')
  self.g.command('quaff potion')
  self.assertEqual(self.g.p['hp'],36);self.assertEqual(self.g.p['inventory'].count('potion'),before-1)
 def test_quaff_full_health_or_nonconsumable_keeps_items(self):
  before=self.g.p['inventory'][:];self.g.command('quaff potion');self.g.command('quaff lantern')
  self.assertEqual(self.g.p['inventory'],before)
  self.assertIn('only quaff',self.g.state['log'][-1]['text'])
 def test_vertical_stacked_marked_inventory(self):
  self.g.p['inventory']=['potion','iron_sword','potion','chain_vest','potion','lantern','iron_sword']
  before=self.g.p['inventory'][:];self.g.command('inventory')
  self.assertEqual(self.g.state['log'][-1]['text'],'Inventory:\n(Healing potion) (x3)\n[Iron sword] (x2) — Damage 5\n[Chain vest] — Armor 3\n(Lumen lantern)')
  self.assertEqual(self.g.p['inventory'],before)
 def test_use_alias_and_quaff_during_combat(self):
  self.g.p['hp']=1;self.g.command('use potion');self.assertEqual(self.g.p['hp'],36)
  self.g.p['room']='meadow';self.g.start_combat();self.g.command('quaff potion')
  self.assertEqual(self.g.p['hp'],self.g.max_hp());self.assertIsNotNone(self.g.p['combat'])
