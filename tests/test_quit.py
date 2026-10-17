"""Save-and-quit lifecycle checks using disposable characters and HTTP sessions."""
from contextlib import contextmanager, redirect_stderr
from http.cookiejar import CookieJar
import io
import json
from pathlib import Path
import random
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import build_opener, HTTPCookieProcessor, Request

from multiplayer import MultiplayerGame
from server import make_server

ROOT = Path(__file__).resolve().parents[1]


class QuitTests(unittest.TestCase):
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
        self.path.write_text(json.dumps(world), encoding='utf-8')
        self.database = Path(self.tmp.name)/'game.sqlite3'
        self.now = 1000.
        self.g = MultiplayerGame(self.path, self.database, random.Random(5), lambda: self.now)
        self.alice = self.g.create_character('Alice', owner=True)
        self.bob = self.g.create_character('Bob')
        self.g._presence.clear()

    def tearDown(self):
        self.g.db.close()
        self.tmp.cleanup()

    @contextmanager
    def server(self):
        server = make_server(self.g, 0)
        thread = threading.Thread(target=server.serve_forever, kwargs={'poll_interval': .01}, daemon=True)
        thread.start()
        try:
            yield server, thread
        finally:
            server.shutdown()
            thread.join(timeout=2)
            server.server_close()

    def client(self, server):
        base = f'http://127.0.0.1:{server.server_port}'
        opener = build_opener(HTTPCookieProcessor(CookieJar()))
        with opener.open(base+'/api/state', timeout=3) as response:
            token = json.load(response)['token']
        def call(path, body=None):
            request = Request(base+path, data=json.dumps(body).encode() if body is not None else None,
                              headers={'X-Game-Token': token, 'Content-Type': 'application/json'})
            with opener.open(request, timeout=3) as response:
                return json.load(response)
        return call

    def player(self, ident):
        return self.g.state['players'][ident]['player']

    def saved(self):
        return json.loads(self.g.db.execute("SELECT body FROM state WHERE id='world'").fetchone()[0])

    def test_save_stays_in_game_and_quit_alone_stops_after_persisting(self):
        with self.server() as (server, thread):
            host = self.client(server)
            host('/api/host', {'code': server.owner_key})
            host('/api/command', {'command': 'east'})
            host('/api/command', {'command': 'buy potion'})
            saved = host('/api/command', {'command': 'save'})
            self.assertEqual(saved['player']['id'], self.alice)
            self.assertNotIn('quit', saved)
            self.assertFalse(server.stop_requested.is_set())
            result = host('/api/command', {'command': '  QUIT  '})
            self.assertTrue(result['quit']['server_stopped'])
            self.assertIsNone(result['player'])
            self.assertTrue(server.stop_requested.is_set())
            thread.join(timeout=2)
            self.assertFalse(thread.is_alive())
            player = self.saved()['players'][self.alice]['player']
            self.assertEqual(player['room'], 'shop')
            self.assertEqual(player['gold'], saved['player']['gold'])
            self.assertEqual(player['inventory'], saved['player']['inventory'])
            self.assertTrue(player['logged_out'])

    def test_host_leaves_others_running_and_can_stop_after_they_leave(self):
        with self.server() as (server, thread):
            host, visitor = self.client(server), self.client(server)
            host('/api/host', {'code': server.owner_key})
            visitor('/api/join', {'player_id': self.bob})
            result = host('/api/quit', {})
            self.assertFalse(result['quit']['server_stopped'])
            self.assertTrue(thread.is_alive())
            self.assertFalse(server.stop_requested.is_set())
            bob = visitor('/api/command', {'command': 'who'})
            self.assertEqual(bob['log'][-1]['text'], 'Online: Bob.')
            self.assertFalse(visitor('/api/command', {'command': 'quit'})['quit']['server_stopped'])
            self.assertTrue(thread.is_alive())  # A visiting player cannot stop the host.
            self.assertTrue(host('/api/quit', {})['quit']['server_stopped'])

    def test_logged_out_character_is_safe_persists_and_resumes_at_same_location(self):
        with self.server() as (server, _):
            visitor = self.client(server)
            visitor('/api/join', {'player_id': self.bob})
            self.player(self.bob)['room'] = 'meadow'
            result = visitor('/api/command', {'command': 'logout'})
            self.assertFalse(result['quit']['server_stopped'])
            self.g.w['enemies']['beetle']['aggressive'] = True
            before = (self.player(self.bob)['hp'], self.player(self.bob)['mana'])
            self.now += 60
            self.g.tick()
            self.assertEqual((self.player(self.bob)['hp'], self.player(self.bob)['mana']), before)
            self.assertIsNone(self.player(self.bob)['combat'])
            self.assertIsNone(visitor('/api/state')['player'])
        self.g.save()
        self.g.db.close()
        self.g = MultiplayerGame(self.path, self.database, clock=lambda: self.now)
        self.assertTrue(self.player(self.bob)['logged_out'])
        with self.server() as (server, _):
            visitor = self.client(server)
            result = visitor('/api/join', {'player_id': self.bob})
            self.assertEqual(result['player']['room'], 'meadow')
            self.assertEqual(result['player']['hp'], before[0])
            self.assertFalse(result['player'].get('logged_out'))

    def test_quit_in_combat_and_extra_arguments_do_not_leave_or_stop(self):
        with self.server() as (server, _):
            host = self.client(server)
            host('/api/host', {'code': server.owner_key})
            wrong = host('/api/command', {'command': 'quit now'})
            self.assertNotIn('quit', wrong)
            with self.g.as_player(self.alice):
                self.g.p['room'] = 'meadow'
                self.g.enemy()['hp'] = 1000
                self.g.start_combat()
            result = host('/api/command', {'command': 'quit'})
            self.assertNotIn('quit', result)
            self.assertIn('Finish combat or FLEE', result['log'][-1]['text'])
            self.assertIsNotNone(result['player']['combat'])
            self.assertFalse(self.player(self.alice).get('logged_out'))
            self.assertFalse(server.stop_requested.is_set())
            self.assertEqual(host('/api/command', {'command': 'save'})['player']['id'], self.alice)

    def test_failed_save_keeps_session_and_server_active(self):
        with self.server() as (server, _):
            host = self.client(server)
            host('/api/host', {'code': server.owner_key})
            with patch.object(self.g, 'save', side_effect=OSError('test disk failure')), redirect_stderr(io.StringIO()):
                with self.assertRaises(HTTPError) as error:
                    host('/api/quit', {})
                self.assertEqual(error.exception.code, 500)
                error.exception.close()
            self.assertFalse(server.stop_requested.is_set())
            self.assertFalse(self.player(self.alice).get('logged_out'))
            self.assertEqual(host('/api/state')['player']['id'], self.alice)

    def test_quit_clears_other_character_views_and_aliases_are_reply_only(self):
        with self.server() as (server, _):
            first, second = self.client(server), self.client(server)
            for alias in ('quit', 'LOGOUT', 'exit'):
                first('/api/join', {'player_id': self.bob})
                second('/api/join', {'player_id': self.bob})
                self.assertEqual(first('/api/command', {'command': alias})['ui_action'], 'quit')
                self.assertIsNone(second('/api/state')['player'])
                with self.g.as_player(self.bob):
                    self.assertNotIn('ui_action', self.g.snapshot())
                    self.assertNotIn('quit', self.g.snapshot())

    def test_late_mutations_are_rejected_after_shutdown_save(self):
        with self.server() as (server, _):
            host, visitor = self.client(server), self.client(server)
            host('/api/host', {'code': server.owner_key})
            with patch.object(server, 'shutdown'):
                host('/api/quit', {})
                before = self.saved()
                with self.assertRaises(HTTPError) as error:
                    visitor('/api/create', {'name': 'TooLate'})
                self.assertEqual(error.exception.code, 503)
                error.exception.close()
                self.assertEqual(self.saved(), before)
                self.assertTrue(visitor('/api/state')['quit']['server_stopped'])


if __name__ == '__main__':
    unittest.main()
