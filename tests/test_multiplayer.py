"""Shared-world, recipient privacy and transport tests with generated saves."""
import copy
from http.cookiejar import CookieJar
import json
from pathlib import Path
import random
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import build_opener, HTTPCookieProcessor, Request
from unittest.mock import patch

from engine import Game
from multiplayer import MultiplayerGame
from server import make_server

ROOT = Path(__file__).resolve().parents[1]


class MultiplayerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name)/'world.json'
        world = json.loads((ROOT/'content/world.json').read_text(encoding='utf-8'))
        world.pop('regions', None)
        for enemy in world['enemies'].values():
            enemy['aggressive'] = False
        for room in world['rooms'].values():
            room['population'] = []
            room['roaming'] = False
        world['settings']['hit_chance'] = 1
        self.path.write_text(json.dumps(world), encoding='utf-8')
        self.db = Path(self.tmp.name)/'save.db'
        self.now = 1000.
        self.g = MultiplayerGame(self.path, self.db, random.Random(5), lambda: self.now)
        self.alice = self.g.create_character('Alice', owner=True)
        self.bob = self.g.create_character('Bob')
        self.clara = self.g.create_character('Clara')

    def tearDown(self):
        self.g.db.close()
        self.tmp.cleanup()

    def player(self, ident):
        return self.g.state['players'][ident]['player']

    def command(self, ident, text):
        self.g.touch(ident)
        with self.g.as_player(ident):
            return self.g.command(text)

    def state(self, ident):
        with self.g.as_player(ident):
            return self.g.snapshot()

    def log(self, ident):
        return '\n'.join(row['text'] for row in self.state(ident)['log'])

    def test_room_speech_is_live_case_preserving_and_room_scoped(self):
        self.player(self.clara)['room'] = 'shop'
        self.command(self.alice, 'say Hello Everyone!')
        for ident in (self.alice, self.bob):
            self.assertIn('Alice says: Hello Everyone!', self.log(ident))
        self.assertNotIn('Hello Everyone!', self.log(self.clara))
        self.assertEqual([p['name'] for p in self.state(self.alice)['players_here']], ['Bob'])
        self.player(self.clara)['room'] = 'square'
        self.assertNotIn('Hello Everyone!', self.log(self.clara))
        self.command(self.clara, 'say I came to visit')
        self.assertIn('Clara says: I came to visit', self.log(self.alice))

    def test_private_tell_never_leaks_even_when_everyone_is_in_one_room(self):
        self.command(self.alice, 'tell Bob Secret Blue Lantern')
        self.assertIn('You tell Bob: Secret Blue Lantern', self.log(self.alice))
        self.assertIn('Alice tells you: Secret Blue Lantern', self.log(self.bob))
        self.assertNotIn('Secret Blue Lantern', json.dumps(self.state(self.clara)))
        self.player(self.bob)['room'] = 'shop'
        self.command(self.alice, 'tell bob Across rooms')
        self.assertIn('Across rooms', self.log(self.bob))
        self.assertNotIn('Across rooms', self.log(self.clara))
        self.assertNotIn('accounts', self.state(self.alice))
        self.assertNotIn('password', json.dumps(self.state(self.alice)))

    def test_npc_public_and_private_conversations_keep_existing_dialogue(self):
        for ident in (self.alice, self.bob):
            self.player(ident)['room'] = 'shop'
        self.command(self.alice, 'tell Anthony hi')
        self.assertIn('Anthony tells you: Welcome to my general store', self.log(self.alice))
        self.assertNotIn('Welcome to my general store', self.log(self.bob))
        self.command(self.alice, 'say hello')
        self.assertIn('Anthony says: Welcome to my general store', self.log(self.bob))
        self.assertNotIn('Anthony says:', self.log(self.clara))
        self.command(self.alice, 'SAY buying TO ANTHONY')
        self.assertIn('Type BUY to browse', self.log(self.bob))
        self.command(self.alice, 'talk anthony about selling')
        self.assertIn('I buy spare equipment', self.log(self.alice))

    def test_multiword_names_offline_recipients_and_invalid_syntax(self):
        sam = self.g.create_character('Sam Green')
        self.command(self.alice, 'tell "Sam Green" Nice to meet you!')
        self.assertIn('Nice to meet you!', self.log(sam))
        self.command(self.alice, 'tell Sam Green Hello Again')
        self.assertIn('Hello Again', self.log(sam))
        self.now += 31
        self.command(self.alice, 'tell Bob hidden-offline-message')
        self.assertNotIn('hidden-offline-message', self.log(self.bob))
        self.assertIn('must be online', self.log(self.alice))
        self.command(self.alice, 'say')
        self.assertIn('Use SAY', self.log(self.alice))

    def test_independent_progress_shared_ground_and_persistence(self):
        self.command(self.alice, 'drop potion')
        self.assertIn('potion', self.state(self.bob)['ground'])
        self.command(self.bob, 'get potion')
        self.assertNotIn('potion', self.state(self.alice)['ground'])
        self.command(self.alice, 'east')
        self.assertEqual(self.player(self.alice)['room'], 'shop')
        self.assertEqual(self.player(self.bob)['room'], 'square')
        self.command(self.alice, 'tell Bob Saved private message')
        expected = {p['id']: copy.deepcopy(p) for p in self.g.all_players()}
        self.g.save(); self.g.db.close()
        self.g = MultiplayerGame(self.path, self.db, clock=lambda: self.now)
        self.assertEqual({p['id']: p for p in self.g.all_players()}, expected)
        self.assertIn(dict(id=self.alice, name='Alice', level=1, race='human',
                           **{'class': 'warrior'}, gender='male', race_name='Human',
                           class_name='Warrior'), self.g.character_choices())
        self.assertIn('Saved private message', self.log(self.bob))
        self.assertNotIn('Saved private message', self.log(self.clara))

    def test_shared_combat_resolves_each_enemy_once_and_rewards_one_kill(self):
        for ident in (self.alice, self.bob):
            self.player(ident)['room'] = 'meadow'
        with self.g.as_player(self.alice):
            enemy = self.g.enemy(); enemy['hp'] = 1000
            self.g.start_combat()
        with self.g.as_player(self.bob):
            self.g.start_combat()
        encounter = self.player(self.alice)['combat']
        self.assertIs(encounter, self.player(self.bob)['combat'])
        self.g.tick()
        hits = sum('hits you for' in line['text'] for ident in (self.alice, self.bob) for line in self.state(ident)['log'])
        self.assertEqual(hits, 1)
        hp = enemy['hp']
        self.g.tick(); self.g.tick()
        self.assertEqual(enemy['hp'], hp)
        enemy['hp'] = 1
        self.now += 4
        self.g.tick()
        self.assertIsNone(self.player(self.alice)['combat'])
        self.assertIsNone(self.player(self.bob)['combat'])
        self.assertEqual(len(self.g.state['corpses']), 1)
        self.assertEqual(self.player(self.alice)['xp'] + self.player(self.bob)['xp'], self.g.w['enemies']['beetle']['xp'])

    def test_character_names_and_world_validation_cover_every_player(self):
        with self.assertRaises(ValueError): self.g.create_character('ALICE')
        with self.assertRaises(ValueError): self.g.create_character('Anthony')
        self.assertNotIn('accounts', self.g.state)
        world = copy.deepcopy(self.g.w)
        self.player(self.bob)['room'] = 'shop'
        del world['rooms']['shop']
        with self.assertRaises(ValueError): self.g.check_live_references(world)

    def test_reloaded_combat_stays_shared_without_offline_attack_burst(self):
        for ident in (self.alice, self.bob):
            self.player(ident)['room'] = 'meadow'
            with self.g.as_player(ident):
                self.g.enemy()['hp'] = 1000
                self.g.start_combat()
        self.g.save(); self.g.db.close()
        self.now += 10000
        self.g = MultiplayerGame(self.path, self.db, clock=lambda: self.now)
        before = [self.player(i)['hp'] for i in (self.alice, self.bob)]
        self.assertIs(self.player(self.alice)['combat'], self.player(self.bob)['combat'])
        self.g.tick()
        self.assertEqual(before, [self.player(i)['hp'] for i in (self.alice, self.bob)])

    def test_other_players_bodies_and_personal_progress_remain_separate(self):
        with self.g.as_player(self.alice):
            self.g.p['gold'] = 123
            self.g.p['room'] = 'meadow'
            self.g.death()
        body = self.g.state['player_bodies'][-1]
        self.player(self.bob)['room'] = 'meadow'
        result = self.command(self.bob, 'get all from '+body['id'])
        self.assertIn('only recover belongings from your own body', json.dumps(result['log']))
        self.assertEqual(body['gold'], 123)
        self.assertEqual(self.player(self.bob)['gold'], 30)
        self.player(self.alice)['room'] = 'meadow'
        self.command(self.alice, 'get all from '+body['id'])
        self.assertEqual(self.player(self.alice)['gold'], 123)
        self.assertNotIn('meadow', self.player(self.clara)['explored_rooms'])

    def test_engaged_enemies_do_not_heal_or_roam_during_another_players_tick(self):
        with self.g.as_player(self.bob):
            self.g.p['room'] = 'meadow'
            enemy = self.g.enemy()
            enemy['hp'] = 10
            self.g.start_combat()
            self.g.w['rooms']['meadow'].update(roaming=True, roam_rooms=['road'], roam_seconds=2)
            self.g.w['revision'].update(enemy_heal_delay=0, enemy_heal_interval=1, enemy_heal_percent=100)
            enemy['roam_at'] = 0
        with self.g.as_player(self.alice):
            self.g.roam()
            self.g.heal_enemies()
        self.assertEqual(enemy['location'], 'meadow')
        self.assertEqual(enemy['hp'], 10)

    def test_simultaneous_commands_are_serialized_without_recipient_mixups(self):
        def send(ident, recipient, prefix):
            for number in range(8):
                self.command(ident, f'tell {recipient} {prefix}-{number}')
        threads = [threading.Thread(target=send, args=(self.alice, 'Bob', 'alice-only')),
                   threading.Thread(target=send, args=(self.clara, 'Bob', 'clara-only'))]
        for thread in threads: thread.start()
        for thread in threads: thread.join()
        self.assertNotIn('clara-only', self.log(self.alice))
        self.assertNotIn('alice-only', self.log(self.clara))
        for prefix in ('alice-only', 'clara-only'):
            for number in range(8): self.assertIn(f'{prefix}-{number}', self.log(self.bob))

    def test_legacy_owner_migration_preserves_generated_character(self):
        old_db = Path(self.tmp.name)/'legacy.db'
        old = Game(self.path, old_db, clock=lambda: self.now)
        old.create('Original')
        old.p.update(gold=739, room='shop')
        old.p['inventory'].append('lantern')
        old.remember_room()
        old.save(); expected = copy.deepcopy(old.p); old.db.close()
        migrated = MultiplayerGame(self.path, old_db, clock=lambda: self.now)
        try:
            self.assertEqual(migrated.owner_id, expected['id'])
            with migrated.as_player(migrated.owner_id): self.assertEqual(migrated.p, expected)
            visitor = migrated.create_character('Visitor')
            self.assertNotEqual(visitor, migrated.owner_id)
            with migrated.as_player(migrated.owner_id): self.assertEqual(migrated.p, expected)
        finally:
            migrated.db.close()

    def test_http_sessions_keep_private_messages_and_editor_isolated(self):
        server = make_server(self.g, 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        base = f'http://127.0.0.1:{server.server_port}'
        def client():
            opener = build_opener(HTTPCookieProcessor(CookieJar()))
            token = json.load(opener.open(base+'/api/state'))['token']
            def call(path, body=None):
                request = Request(base+path, data=json.dumps(body).encode() if body is not None else None,
                                  headers={'X-Game-Token': token, 'Content-Type': 'application/json'})
                return json.load(opener.open(request, timeout=5))
            return call
        try:
            alice, bob, clara, anonymous = [client() for _ in range(4)]
            for call, ident, name in ((alice, self.alice, 'Alice'), (bob, self.bob, 'Bob'), (clara, self.clara, 'Clara')):
                self.assertEqual(call('/api/join', dict(player_id=ident))['player']['name'], name)
            self.assertFalse(alice('/api/state')['session']['owner'])
            alice('/api/command', dict(command='tell Bob transport-private-text'))
            self.assertIn('transport-private-text', json.dumps(bob('/api/state')))
            self.assertNotIn('transport-private-text', json.dumps(clara('/api/state')))
            self.assertNotIn('transport-private-text', json.dumps(anonymous('/api/state')))
            self.assertNotIn(server.owner_key, json.dumps(anonymous('/api/state')))
            forged = clara('/api/command', dict(command='say Identity check', player_id=self.alice))
            self.assertEqual(forged['player']['name'], 'Clara')
            self.assertIn('Clara says: Identity check', json.dumps(bob('/api/state')))
            with self.assertRaises(HTTPError) as error: anonymous('/api/command', dict(command='say forged'))
            self.assertEqual(error.exception.code, 401)
            error.exception.close()
            for path in ('/api/world', '/api/editor-schema'):
                with self.assertRaises(HTTPError) as error: bob(path)
                self.assertEqual(error.exception.code, 403)
                error.exception.close()
            with self.assertRaises(HTTPError) as error: alice('/api/world')
            self.assertEqual(error.exception.code, 403)
            error.exception.close()
            with self.assertRaises(HTTPError) as error: bob('/api/world', self.g.w)
            self.assertEqual(error.exception.code, 403)
            error.exception.close()
            chooser = alice('/api/leave', {})
            self.assertIsNone(chooser['player'])
            self.assertEqual(chooser['log'], [])
            self.assertEqual({p['name'] for p in chooser['characters']}, {'Alice', 'Bob', 'Clara'})
            self.assertNotIn('transport-private-text', json.dumps(chooser))
            # Switching characters replaces the session and the recipient log.
            self.assertNotIn('transport-private-text', json.dumps(alice('/api/join', dict(player_id=self.clara))))
            owner = anonymous('/api/host', dict(code=server.owner_key))
            self.assertEqual(owner['player']['id'], self.alice)
            self.assertTrue(owner['session']['owner'])
            self.assertIn('rooms', anonymous('/api/world'))
            self.assertTrue(anonymous('/api/leave', {})['session']['owner'])
            created = anonymous('/api/create', dict(name='Dara', race='elf', **{'class': 'mage'}))
            self.assertEqual(created['player']['name'], 'Dara')
            self.assertTrue(created['session']['owner'])
            self.assertNotIn('transport-private-text', json.dumps(created))
            self.assertEqual(anonymous('/api/state')['player']['id'], created['player']['id'])
            with self.assertRaises(HTTPError) as error: bob('/api/join', dict(player_id='missing'))
            self.assertEqual(error.exception.code, 400)
            error.exception.close()
        finally:
            server.shutdown(); thread.join(); server.server_close()

    def test_launcher_opens_local_owner_link_when_lan_addresses_are_printed(self):
        import server as transport
        class PreviewServer:
            server_port = 8765
            owner_key = 'test-owner-key'
            stop_requested = threading.Event()
            def serve_forever(self, **kwargs): raise KeyboardInterrupt
            def server_close(self): pass
            def shutdown(self): pass
        root = Path(self.tmp.name)/'launcher'
        (root/'content').mkdir(parents=True)
        (root/'content/world.json').write_bytes(self.path.read_bytes())
        with patch.object(transport, 'ROOT', root), patch.object(transport, 'make_server', return_value=PreviewServer()), \
             patch('sys.argv', ['server.py', '--host', '0.0.0.0']), patch.object(transport.socket, 'getaddrinfo', return_value=[(None, None, None, None, ('192.168.1.20', 0))]), \
             patch.object(transport.webbrowser, 'open') as open_browser, patch('builtins.print'):
            self.assertEqual(transport.main(), 0)
        open_browser.assert_called_once_with('http://127.0.0.1:8765/?owner=test-owner-key')


if __name__ == '__main__': unittest.main()
