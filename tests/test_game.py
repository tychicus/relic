from legacy_fixture import disable_regions
import copy
import json
import random
import re
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from engine import Game, validate
from server import make_server

ROOT = Path(__file__).resolve().parents[1]

class Clock:
    def __init__(self): self.now = 1000.0
    def __call__(self): return self.now
    def advance(self, seconds): self.now += seconds

class GameTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.root = Path(self.temp.name)
        self.path = self.root / 'world.json'; self.path.write_bytes((ROOT / 'content/world.json').read_bytes())
        self.clock = Clock(); self.db = self.root / 'save.sqlite3'
        disable_regions(self.path);self.g = Game(self.path, self.db, random.Random(10), self.clock); self.g.create('Tester'); self.g.p['inventory'].append('lantern')  # Regression fixture: acquired light; new starts are tested separately.
    def tearDown(self):
        self.g.db.close(); self.temp.cleanup()
    def go_meadow(self):
        for c in ('n', 'n', 'n'): self.g.command(c)
        self.assertEqual(self.g.p['room'], 'meadow')
    def test_01_start_movement_directional_look_and_inspect(self):
        self.assertEqual(self.g.p['room'], 'square'); self.g.command('look fountain')
        self.assertIn('humming crystal', self.g.state['log'][-1]['text'])
        self.g.command('look north'); self.assertEqual(self.g.p['room'], 'square')
        self.assertIn('North Gate', self.g.state['log'][-1]['text'])
        self.g.command('east'); self.assertEqual(self.g.p['room'], 'shop')
    def test_02_trade_equipment_potion_and_full_bag(self):
        self.g.command('e'); self.g.p['gold'] = 100
        self.g.command('buy iron sword'); self.g.command('equip iron sword')
        self.assertEqual(self.g.p['equipment']['weapon'], 'iron_sword')
        self.assertIn('rusted_sword', self.g.p['inventory'])
        self.g.command('sell rusted sword'); self.assertEqual(self.g.p['gold'], 69)
        self.g.p['hp'] = 10; self.g.command('use potion'); self.assertEqual(self.g.p['hp'], 45)
        self.g.w['settings']['bag_capacity'] = len(self.g.p['inventory'])
        before = self.g.p['gold']; self.g.command('buy potion'); self.assertEqual(self.g.p['gold'], before)
        self.assertIn('full', self.g.state['log'][-1]['text'])
    def test_03_darkness_and_carried_lantern(self):
        self.go_meadow(); self.g.command('e'); self.g.command('drop lantern'); self.g.command('look north')
        self.assertIn('Darkness blocks', self.g.state['log'][-1]['text'])
        self.g.command('get lantern'); self.g.command('look north')
        self.assertIn('Dark Conduit', self.g.state['log'][-1]['text'])
    def test_04_alternating_combat_and_bash_cooldown(self):
        self.go_meadow(); self.g.w['settings']['hit_chance'] = 1
        e = self.g.enemy(); e['hp'] = 1000
        self.g.command('attack'); self.assertEqual(self.g.p['combat']['turn'], 'player')
        hp = self.g.p['hp']; self.g.tick(); self.assertEqual(self.g.p['hp'], hp)
        self.assertLess(e['hp'], 1000); enemy_hp = e['hp']
        self.clock.advance(1.9); self.g.tick(); self.assertEqual(e['hp'], enemy_hp)
        self.clock.advance(.1); self.g.tick(); self.assertLess(self.g.p['hp'], hp)
        self.g.command('bash'); after = e['hp']; self.g.command('bash'); self.assertEqual(e['hp'], after)
        self.assertIn('ready in', self.g.state['log'][-1]['text'])
    def test_05_victory_loot_level_and_timestamp_respawn(self):
        self.go_meadow(); self.g.w['settings']['hit_chance'] = 1
        spec = self.g.w['enemies']['beetle']; spec['loot'] = [{'item':'relic_blade','weight':1}]; spec['xp'] = 35
        self.g.enemy()['hp'] = 1; self.g.command('attack'); self.g.tick()
        self.assertIsNone(self.g.p['combat']); self.assertIsNone(self.g.enemy()); self.assertEqual(self.g.p['level'], 2)
        self.assertIn('relic_blade', self.g.p['inventory']); self.assertEqual(self.g.p['hp'], self.g.max_hp())
        self.g.save(); self.g.db.close(); self.clock.advance(spec['respawn'] + 1)
        self.g = Game(self.path, self.db, random.Random(2), self.clock)
        self.assertEqual(self.g.enemy()['hp'], 18)
    def test_06_death_penalties_protect_equipment_and_light(self):
        self.g.p['gold'] = 100; self.g.w['settings']['item_loss_chance'] = 1
        old_eq = dict(self.g.p['equipment']); self.g.p['room'] = 'vault'; self.g.death()
        self.assertEqual(self.g.p['gold'], 90); self.assertEqual(self.g.p['room'], 'square')
        self.assertEqual(old_eq, self.g.p['equipment']); self.assertIn('lantern', self.g.p['inventory'])
        self.assertEqual(len(self.g.p['inventory']), 2)
    def test_07_progress_and_combat_resume_without_offline_burst(self):
        self.go_meadow(); self.g.command('attack'); self.g.tick(); self.g.save()
        saved = copy.deepcopy(self.g.p); self.g.db.close(); self.clock.advance(10000)
        self.g = Game(self.path, self.db, random.Random(2), self.clock)
        self.assertEqual(self.g.p['room'], saved['room']); self.assertEqual(self.g.p['hp'], saved['hp'])
        self.g.tick(); self.assertEqual(self.g.p['hp'], saved['hp'])
        self.assertEqual(self.g.p['combat']['turn'], saved['combat']['turn'])
    def test_08_flee_success_and_failed_attempt_rate_limit(self):
        self.go_meadow(); self.g.command('attack'); self.g.w['settings']['flee_chance'] = 0
        self.g.command('flee'); self.g.command('flee'); self.assertIn('again in', self.g.state['log'][-1]['text'])
        self.clock.advance(2); self.g.w['settings']['flee_chance'] = 1; self.g.command('flee')
        self.assertIsNone(self.g.p['combat']); self.assertNotEqual(self.g.p['room'], 'meadow')
    def test_09_full_bag_loot_is_recoverable(self):
        self.go_meadow(); self.g.w['settings']['bag_capacity'] = 3; self.g.w['settings']['hit_chance'] = 1
        self.g.w['enemies']['beetle']['loot'] = [{'item':'scrap','weight':1}]
        self.g.enemy()['hp'] = 1; self.g.command('attack'); self.g.tick()
        self.assertEqual(self.g.state['ground']['meadow'], ['scrap'])
        self.g.command('drop potion'); self.g.command('get scrap'); self.assertIn('scrap', self.g.p['inventory'])
    def test_10_owner_changes_hp_and_adds_room_and_item(self):
        new = copy.deepcopy(self.g.w); new['enemies']['goblin']['hp'] = 35
        new['rooms']['tower'] = {'name':'Watchtower','description':'Above the town.','exits':{'south':'square'}}
        new['rooms']['square']['exits']['north'] = 'tower'
        new['items']['coin'] = {'name':'Old coin','description':'Old.','kind':'loot','price':2}
        self.g.update_world(new); self.g.command('n'); self.assertEqual(self.g.p['room'], 'tower')
        self.assertEqual(self.g.w['enemies']['goblin']['hp'], 35)
        self.assertEqual(len(list((self.root/'history').glob('*.json'))), 1)
        self.assertEqual(json.loads(self.path.read_text())['items']['coin']['price'], 2)
    def test_11_invalid_edits_preserve_content_and_save(self):
        before = self.path.read_bytes(); new = copy.deepcopy(self.g.w)
        new['rooms']['square']['exits']['north'] = 'missing'
        with self.assertRaises(ValueError): self.g.update_world(new)
        self.assertEqual(before, self.path.read_bytes())
        new = copy.deepcopy(self.g.w); del new['items']['potion']; new['rooms']['shop']['shop'].remove('potion')
        with self.assertRaises(ValueError): self.g.update_world(new)
        self.assertEqual(before, self.path.read_bytes())
        new = copy.deepcopy(self.g.w); new['settings']['attack_interval'] = 0
        with self.assertRaises(ValueError): validate(new)
    def test_12_aggression_rest_and_invalid_commands(self):
        self.go_meadow(); self.g.command('e'); self.g.command('n'); self.assertIsNotNone(self.g.p['combat'])
        rid = self.g.p['room']; self.g.command('s'); self.assertEqual(self.g.p['room'],rid)
        self.g.death(); self.g.p['hp']=1; self.g.command('w'); self.g.command('rest'); self.assertEqual(self.g.p['hp'],65)
        self.g.command('invented spell'); self.assertIn('Unknown command',self.g.state['log'][-1]['text'])
    def test_13_complete_playable_route_defeats_boss(self):
        self.g.w['settings']['hit_chance'] = 1; self.g.p['gold'] = 100
        self.g.command('e'); self.g.command('buy iron sword'); self.g.command('equip iron sword')
        self.g.command('buy chain vest'); self.g.command('equip chain vest'); self.g.command('w')
        self.go_meadow()
        for stage in ('beetle','goblin','sentinel'):
            if stage=='beetle': self.g.command('attack')
            elif stage=='goblin': self.g.command('e'); self.g.command('n')
            else: self.g.command('n')
            for _ in range(200):
                if not self.g.p['combat']: break
                if self.g.p['hp'] < 30 and 'potion' in self.g.p['inventory']: self.g.command('use potion')
                if self.g.p['cooldowns'].get('bash',0)<=self.clock(): self.g.command('bash')
                self.clock.advance(2); self.g.tick()
            self.assertIsNone(self.g.p['combat']); self.assertNotEqual(self.g.p['room'],'square')
            self.assertIsNone(self.g.enemy())
        self.assertEqual(self.g.p['room'],'vault'); self.assertEqual(self.g.p['level'], sum(self.g.p['xp'] >= x for x in self.g.w['settings']['level_xp']))
    def test_14_http_game_and_owner_endpoints_and_local_protection(self):
        server=make_server(self.g,0); thread=threading.Thread(target=server.serve_forever,daemon=True); thread.start()
        base=f'http://127.0.0.1:{server.server_port}'
        def request(path,body=None,token=None,origin=None,host=None):
            headers={}
            if token: headers['X-Game-Token']=token
            if origin: headers['Origin']=origin
            if host: headers['Host']=host
            req=Request(base+path,data=json.dumps(body).encode() if body is not None else None,headers=headers)
            return urlopen(req,timeout=3)
        try:
            with request('/api/state') as response: data=json.load(response)
            token=data['token']; self.assertEqual(data['player']['name'],'Tester')
            with request('/api/command',{'command':'e'},token) as response: self.assertEqual(json.load(response)['player']['room'],'shop')
            assets=set()
            for path in ('/','/admin'):
                with request(path) as response: self.assertEqual(response.status,200); page=response.read().decode()
                assets.update(re.findall(r'(?:src|href)="(/assets/[^"]+)"',page))
            self.assertTrue(any(a.endswith('.js') for a in assets)); self.assertTrue(any(a.endswith('.css') for a in assets))
            for path in assets:
                with request(path) as response: self.assertEqual(response.status,200); self.assertGreater(len(response.read()),100)
            for path in ('/assets/../server.py','/assets/%2e%2e/server.py','/assets/missing.js','/app.js'):
                with self.assertRaises(HTTPError) as error: request(path)
                self.assertEqual(error.exception.code,404)
            with self.assertRaises(HTTPError) as error: request('/api/command',{'command':'w'})
            self.assertEqual(error.exception.code,403)
            with self.assertRaises(HTTPError) as error: request('/api/command',{'command':'w'},token,'https://evil.example')
            self.assertEqual(error.exception.code,403)
            with self.assertRaises(HTTPError) as error: request('/api/state',host='evil.example')
            self.assertEqual(error.exception.code,403)
            new=copy.deepcopy(self.g.w);new['enemies']['goblin']['hp']=35
            with request('/api/world',new,token) as response: self.assertTrue(json.load(response)['ok'])
            with request('/api/world') as response: self.assertEqual(json.load(response)['enemies']['goblin']['hp'],35)
        finally: server.shutdown();thread.join();server.server_close()

if __name__=='__main__': unittest.main()
