"""Exploration privacy, travel and persistence on disposable character saves."""
import copy
import json
import random
import tempfile
import unittest
from pathlib import Path

from engine import Game

ROOT = Path(__file__).resolve().parents[1]


class PlayerMapTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / 'world.json'
        world = json.loads((ROOT / 'content/world.json').read_bytes())
        world['regions'] = {}
        for enemy in world['enemies'].values():
            enemy['aggressive'] = False
        self.path.write_text(json.dumps(world), encoding='utf-8')
        self.database = Path(self.tmp.name) / 'save.db'
        self.now = 1000.
        self.g = Game(self.path, self.database, random.Random(4), lambda: self.now)
        self.g.create('Explorer')

    def tearDown(self):
        self.g.db.close()
        self.tmp.cleanup()

    def reload(self):
        self.g.save()
        self.g.db.close()
        self.g = Game(self.path, self.database, random.Random(4), lambda: self.now)

    def rooms(self):
        return {room['id']: room for room in self.g.snapshot()['exploration_map']['rooms']}

    def test_new_character_maps_only_start_and_never_exposes_spoilers(self):
        rooms = self.rooms()
        self.assertEqual(set(rooms), {'square'})
        self.assertEqual(rooms['square']['exits'], {})
        self.assertEqual(set(rooms['square']), {'id', 'name', 'region', 'position', 'exits'})
        self.assertNotIn('explored_rooms', self.g.snapshot()['player'])
        self.assertNotIn('ui_action', self.g.snapshot())
        before = copy.deepcopy(self.g.state)
        self.g.player_map()
        self.assertEqual(self.g.state, before)

    def test_distant_look_failed_moves_and_help_do_not_chart_destinations(self):
        for command in ('LOOK NORTH 3', 'LOOK EAST', 'UP', 'HELP MAP', 'SYNTAX SHOW'):
            result = self.g.command(command)
            self.assertNotIn('ui_action', result)
            self.assertEqual(set(self.rooms()), {'square'})

    def test_visit_connect_revisit_and_reload(self):
        self.g.command('east')
        rooms = self.rooms()
        self.assertEqual(set(rooms), {'square', 'shop'})
        self.assertEqual(rooms['square']['exits'], {'east': 'shop'})
        self.assertEqual(rooms['shop']['exits'], {'west': 'square'})
        self.assertEqual(self.g.player_map()['current'], 'shop')
        self.g.command('west'); self.g.command('east')
        self.reload()
        self.assertEqual(self.rooms(), rooms)
        self.assertEqual(self.g.player_map()['current'], 'shop')

    def test_map_action_is_exact_reply_only_and_not_replayed_after_reload(self):
        for command in ('SHOW MAP', ' display   MAP ', 'LOOK MAP', ' look   MaP ', 'L MAP'):
            self.assertEqual(self.g.command(command)['ui_action'], 'show_map')
            self.assertNotIn('ui_action', self.g.snapshot())
        for command in ('MAP', 'SHOW', 'SHOW ENEMIES', 'DISPLAY MAP ALL', 'HELP MAP',
                        'HELP LOOK MAP', 'SYNTAX LOOK', 'LOOK', 'LOOK NORTH', 'LOOK SELF', 'LOOK MAP ALL'):
            self.assertNotIn('ui_action', self.g.command(command))
        self.reload()
        self.assertNotIn('ui_action', self.g.snapshot())

    def test_map_payload_is_unchanged_by_enemy_loot_npc_or_hidden_world_changes(self):
        for command in ('north', 'north', 'north'):
            self.g.command(command)
        before = copy.deepcopy(self.g.player_map())
        self.g.spawn_creature('vampire', 'meadow')
        self.g.w['rooms']['meadow']['objects']['spoiler'] = 'Secret treasure'
        self.g.state['ground']['meadow'] = ['greatsword']
        self.g.w['rooms']['dungeon'].update(name='SECRET ROOM', region='SECRET REGION', map_position=[9999, 9999, 999])
        self.g.w['rooms']['meadow']['exits']['down'] = 'dungeon'
        self.assertEqual(self.g.player_map(), before)
        for room in before['rooms']:
            self.assertEqual(set(room), {'id', 'name', 'region', 'position', 'exits'})

    def test_dark_room_is_charted_but_named_only_after_being_seen(self):
        self.g.w['rooms']['shop']['dark'] = True
        self.g.command('east')
        self.assertEqual(self.rooms()['shop']['name'], 'Unlit room')
        self.assertEqual(self.rooms()['shop']['region'], '')
        self.g.p['inventory'].append('lantern')
        self.g.command('SHOW MAP')
        self.assertEqual(self.rooms()['shop']['name'], self.g.w['rooms']['shop']['name'])
        self.g.p['inventory'].remove('lantern')
        self.g.command('west'); self.g.command('east')
        self.assertEqual(self.rooms()['shop']['name'], self.g.w['rooms']['shop']['name'])

    def test_old_save_starts_from_current_room_without_reconstructing_spoilers(self):
        self.g.p['room'] = 'shop'
        self.g.p.pop('explored_rooms')
        self.reload()
        self.assertEqual(set(self.rooms()), {'shop'})

    def test_recall_and_both_death_modes_preserve_exploration(self):
        self.g.command('east')
        self.g.p['inventory'].append('recall_scroll')
        self.g.command('recall')
        self.assertEqual(self.g.p['room'], 'square')
        expected = self.rooms()
        for bodies in (True, False):
            self.g.w['revision']['player_bodies'] = bodies
            self.g.command('east'); self.g.death()
            self.assertEqual(self.g.player_map()['current'], 'square')
            self.assertEqual(self.rooms(), expected)
        self.reload()
        self.assertEqual(self.rooms(), expected)

    def test_flee_charts_only_the_destination_and_map_works_in_combat(self):
        for command in ('north', 'north', 'north'):
            self.g.command(command)
        e = self.g.enemy(); e['hp'] = 10000
        self.g.p['attack_ready'] = self.now + 1000
        self.g.command('attack')
        self.assertIsNotNone(self.g.p['combat'])
        for command in ('SHOW MAP', 'LOOK MAP'):
            self.assertEqual(self.g.command(command)['ui_action'], 'show_map')
        before = set(self.rooms())
        self.g.w['settings']['flee_chance'] = 1
        # Only one possible escape, to a previously unvisited room.
        self.g.w['rooms']['meadow']['exits'] = {'east': 'shop'}
        self.g.command('flee')
        self.assertEqual(self.g.p['room'], 'shop')
        self.assertEqual(set(self.rooms()), before | {'shop'})

    def test_missing_positions_removed_rooms_and_visited_floors(self):
        self.g.command('east')
        self.g.w['rooms']['square'].pop('map_position', None)
        self.g.w['rooms']['shop'].pop('map_position', None)
        rooms = self.rooms()
        self.assertNotEqual(rooms['square']['position'], rooms['shop']['position'])
        self.g.w['rooms']['shop']['map_position'] = [0, 0, -1]
        self.assertEqual(self.rooms()['shop']['position'], [0, 0, -1])
        self.g.command('west')
        del self.g.w['rooms']['shop']
        self.assertEqual(set(self.rooms()), {'square'})
        self.assertEqual(self.rooms()['square']['exits'], {})

    def test_exploration_belongs_to_each_character(self):
        self.g.command('east')
        other = Game(self.path, ':memory:', clock=lambda: self.now)
        try:
            other.create('Other')
            self.assertEqual([room['id'] for room in other.player_map()['rooms']], ['square'])
            self.assertEqual(set(self.rooms()), {'square', 'shop'})
        finally:
            other.db.close()
