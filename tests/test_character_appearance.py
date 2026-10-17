"""Appearance selection, compatibility and persistence using generated saves only."""
import copy
from http.cookiejar import CookieJar
import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import build_opener, HTTPCookieProcessor, Request

from engine import Game
from multiplayer import MultiplayerGame
from server import make_server

ROOT = Path(__file__).resolve().parents[1]


class CharacterAppearanceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / 'world.json'
        self.path.write_bytes((ROOT / 'content/world.json').read_bytes())
        self.db = Path(self.tmp.name) / 'characters.sqlite3'
        self.g = MultiplayerGame(self.path, self.db, clock=lambda: 1000.)

    def tearDown(self):
        self.g.db.close()
        self.tmp.cleanup()

    def test_all_twenty_choices_persist_with_equal_stats_for_both_genders(self):
        expected = {}
        for race in ('human', 'elf', 'orc'):
            for cls in ('warrior', 'rogue', 'mage', 'cleric'):
                if not self.g.class_eligible(race, cls):
                    continue
                stats = []
                for gender in ('male', 'female'):
                    ident = self.g.create_character(f'{gender} {race} {cls}', race, cls, gender=gender)
                    with self.g.as_player(ident):
                        p = self.g.snapshot()['player']
                        stats.append({key: p[key] for key in ('max_hp', 'max_mana', 'learned_skills', 'ability_points', 'gold')})
                        self.assertEqual((p['race'], p['class'], p['gender']), (race, cls, gender))
                    expected[ident] = (race, cls, gender)
                self.assertEqual(*stats)
        self.assertEqual(len(expected), 20)
        self.g.save()
        self.g.db.close()
        self.g = MultiplayerGame(self.path, self.db, clock=lambda: 1000.)
        for choice in self.g.character_choices():
            self.assertEqual((choice['race'], choice['class'], choice['gender']), expected[choice['id']])
            with self.g.as_player(choice['id']):
                self.assertEqual(self.g.snapshot()['player']['gender'], choice['gender'])

    def test_invalid_appearance_and_orc_magic_do_not_create_characters(self):
        for gender in ('', 'other', 'Female', None, [], {}):
            with self.subTest(gender=gender), self.assertRaisesRegex(ValueError, 'Male or Female'):
                self.g.create_character('Invalid', gender=gender)
        for cls in ('mage', 'cleric'):
            with self.assertRaisesRegex(ValueError, 'requires magic'):
                self.g.create_character('Invalid', 'orc', cls, gender='female')
        self.assertEqual(self.g.character_choices(), [])

    def test_legacy_character_gets_display_default_without_changing_progress(self):
        ident = self.g.create_character('Original', 'elf', 'mage', owner=True)
        with self.g.as_player(ident):
            self.g.p.pop('gender')
            self.g.p['gold'] = 739
            self.g.p['inventory'].append('lantern')
            expected = copy.deepcopy(self.g.p)
        self.g.save()
        self.g.db.close()
        self.g = MultiplayerGame(self.path, self.db, clock=lambda: 1000.)
        with self.g.as_player(ident):
            self.assertEqual(self.g.p, expected)
            self.assertEqual(self.g.snapshot()['player']['gender'], 'male')
            self.assertEqual(self.g.p, expected)
        self.assertEqual(self.g.character_choices()[0]['gender'], 'male')

    def test_http_creation_validation_and_selection_in_both_server_modes(self):
        for game_type in (Game, MultiplayerGame):
            with self.subTest(game_type=game_type.__name__):
                game = game_type(self.path, Path(self.tmp.name) / f'{game_type.__name__}.db')
                server = make_server(game, 0)
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                try:
                    base = f'http://127.0.0.1:{server.server_port}'
                    opener = build_opener(HTTPCookieProcessor(CookieJar()))
                    with opener.open(base + '/api/state') as response:
                        token = json.load(response)['token']
                    def call(path, body):
                        request = Request(base + path, data=json.dumps(body).encode(),
                                          headers={'X-Game-Token': token, 'Content-Type': 'application/json'})
                        with opener.open(request, timeout=5) as response:
                            return json.load(response)
                    with self.assertRaises(HTTPError) as error:
                        call('/api/create', dict(name='Wrong', gender='invalid'))
                    self.assertEqual(error.exception.code, 400)
                    error.exception.close()
                    created = call('/api/create', dict(name='Aria', race='elf', **{'class': 'mage'}, gender='female'))
                    self.assertEqual(created['player']['gender'], 'female')
                    if game_type is MultiplayerGame:
                        chooser = call('/api/leave', {})
                        self.assertEqual(chooser['characters'][0]['gender'], 'female')
                        joined = call('/api/join', dict(player_id=created['player']['id']))
                        self.assertEqual(joined['player']['gender'], 'female')
                finally:
                    server.shutdown()
                    thread.join()
                    server.server_close()
                    game.db.close()


if __name__ == '__main__':
    unittest.main()
