"""Regression coverage for combat-end stun and shared-world notifications."""
import copy
import json
from pathlib import Path
import random
import tempfile
import unittest

from engine import Game
from multiplayer import MultiplayerGame

ROOT = Path(__file__).resolve().parents[1]


class CombatStunTests(unittest.TestCase):
    game_class = Game

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name)/'world.json'
        self.db = Path(self.tmp.name)/'save.db'
        world = json.loads((ROOT/'content/world.json').read_text(encoding='utf-8'))
        world.pop('regions', None)
        for enemy in world['enemies'].values():
            enemy.update(aggressive=False, dodge=0)
        for room in world['rooms'].values():
            room.update(population=[], roaming=False)
        world['settings'].update(hit_chance=1, flee_chance=1)
        world['rooms']['meadow']['exits'] = {'south': 'square'}
        self.path.write_text(json.dumps(world), encoding='utf-8')
        self.now = 1000.
        self.g = self.game_class(self.path, self.db, random.Random(5), lambda: self.now)
        self.context = None
        self.addCleanup(self.close_game)
        if self.game_class is MultiplayerGame:
            self.ident = self.g.create_character('Tester', 'human', 'mage', owner=True)
            self.context = self.g.as_player(self.ident)
            self.context.__enter__()
        else:
            self.g.create('Tester', 'human', 'mage')
        self.g.p.update(level=7, room='meadow')
        self.g.p['learned_skills']['mend'] = 1
        self.g.p['hp'] = self.g.max_hp()-10
        self.g.p['mana'] = self.g.max_mana()

    def close_game(self):
        if self.context:
            self.context.__exit__(None, None, None)
            self.context = None
        self.g.db.close()

    def stun(self):
        self.g.apply_effects([dict(effect='stunned', chance=100, duration=2)], self.g.p)

    def assert_can_heal(self):
        hp = self.g.p['hp']
        self.g.command('cast mend')
        self.assertGreater(self.g.p['hp'], hp)

    def test_flee_clears_stun_and_allows_healing_immediately(self):
        self.g.start_combat()
        self.stun()
        self.g.p['combat']['next_at'] = self.now+4
        self.g.command('flee')
        self.assertIsNone(self.g.p['combat'])
        self.assertEqual(self.g.p['effects'], [])
        self.assert_can_heal()

    def test_last_enemy_dying_clears_stun_and_allows_healing(self):
        enemy = self.g.enemy()
        self.g.start_combat()
        self.stun()
        enemy['effects'] = [dict(id='scorched', remaining=1, stacks=1, damage_override=10000)]
        self.g.tick()
        self.assertIsNone(self.g.p['combat'])
        self.assertEqual(self.g.p['effects'], [])
        self.assert_can_heal()

    def test_active_combat_stun_still_blocks_attacks_and_skills(self):
        enemy = self.g.enemy()
        enemy['hp'] = 1000
        self.g.start_combat()
        self.stun()
        with self.assertRaisesRegex(ValueError, 'stunned'):
            self.g.activate_skill('mend')
        self.g.tick()
        self.assertEqual(enemy['hp'], 1000)
        self.assertEqual(self.g.p['effects'][0]['remaining'], 1)
        self.now += self.g.w['settings']['attack_interval']
        self.g.tick()
        self.assertEqual(enemy['hp'], 1000)
        self.assertEqual(self.g.p['effects'], [])
        self.now += self.g.w['settings']['attack_interval']
        self.g.tick()
        self.assertLess(enemy['hp'], 1000)

    def test_reloaded_idle_stun_clears_without_offline_damage(self):
        self.g.p['room'] = 'square'
        self.stun()
        poison = dict(id='poisoned', remaining=4, stacks=1)
        self.g.p['effects'].append(copy.deepcopy(poison))
        hp = self.g.p['hp']
        self.g.save()
        self.close_game()
        self.now += 10000
        self.g = self.game_class(self.path, self.db, clock=lambda: self.now)
        if self.game_class is MultiplayerGame:
            self.context = self.g.as_player(self.ident)
            self.context.__enter__()
        self.g.tick()
        self.assertEqual(self.g.p['effects'], [poison])
        self.assertEqual(self.g.p['hp'], hp)
        self.assert_can_heal()


class MultiplayerStunTests(CombatStunTests):
    game_class = MultiplayerGame

    def test_flee_does_not_clear_another_players_active_stun(self):
        friend = self.g.create_character('Friend')
        self.g.start_combat()
        self.stun()
        with self.g.as_player(friend):
            self.g.p['room'] = 'meadow'
            self.g.start_combat()
            self.stun()
            partner = self.g.p
        self.g.p['combat']['next_at'] = self.now+4
        self.g.command('flee')
        self.assertIsNone(self.g.p['combat'])
        self.assertEqual(self.g.p['effects'], [])
        self.assertIsNotNone(partner['combat'])
        self.assertEqual(partner['effects'], [dict(id='stunned', remaining=2, stacks=1)])


class WorldNotificationTests(unittest.TestCase):
    def setUp(self):
        self.fixture = CombatStunTests()
        self.fixture.game_class = MultiplayerGame
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.g = self.fixture.g
        self.alice = self.fixture.ident
        self.g.p['room'] = 'square'
        self.bob = self.g.create_character('Bob')
        self.clara = self.g.create_character('Clara')

    def player(self, ident):
        return self.g.state['players'][ident]['player']

    def messages(self, ident, phrase):
        with self.g.as_player(ident):
            return [x['text'] for x in self.g.snapshot()['log'] if phrase in x['text']]

    def test_roam_notifies_departure_and_arrival_observers_once(self):
        for ident in (self.bob, self.clara):
            self.player(ident)['room'] = 'meadow'
        self.player(self.alice)['room'] = 'road'
        with self.g.as_player(self.bob):
            enemy = self.g.enemy()
            name = self.g.creature_name(enemy)
        self.g.w['rooms']['meadow'].update(exits={'south': 'road'}, roaming=True, roam_rooms=['road'])
        enemy['roam_at'] = 0
        self.g.tick()
        self.g.tick()
        self.assertEqual(enemy['location'], 'road')
        for ident in (self.bob, self.clara):
            self.assertEqual(self.messages(ident, name+' leaves'), [name+' leaves the area.'])
            self.assertEqual(self.messages(ident, name+' arrives'), [])
        self.assertEqual(self.messages(self.alice, name+' arrives'), [name+' arrives.'])
        self.assertEqual(self.messages(self.alice, name+' leaves'), [])

    def test_healing_notifies_visible_players_without_duplicate_healing(self):
        for ident in (self.alice, self.bob, self.clara):
            self.player(ident)['room'] = 'meadow'
        self.player(self.alice)['logged_out'] = True
        self.player(self.bob)['inventory'] = []
        self.player(self.clara)['inventory'].append('lantern')
        self.g.w['rooms']['meadow']['dark'] = True
        with self.g.as_player(self.bob):
            enemy = self.g.enemy()
            enemy['hp'] = 1
            name = self.g.creature_name(enemy)
        self.g.w['enemies']['beetle'].update(healing_override=True, heal_delay=0, heal_interval=10, heal_percent=10)
        self.g.tick()
        self.g.tick()
        self.assertEqual(enemy['hp'], 3)
        self.assertEqual(self.messages(self.clara, name+' recovers'), [name+' recovers 2 HP.'])
        self.assertEqual(self.messages(self.bob, name+' recovers'), [])
        self.assertEqual(self.messages(self.alice, name+' recovers'), [])

    def make_expiring_body(self):
        with self.g.as_player(self.bob):
            self.g.p['room'] = 'meadow'
            self.g.death()
            body = self.g.state['player_bodies'][-1]
            body['expires'] = self.fixture.now+1
        self.player(self.bob)['logged_out'] = True
        return body

    def test_body_expiry_notifies_only_owner_even_logged_out(self):
        body = self.make_expiring_body()
        self.fixture.now += 2
        self.g.tick()
        self.g.tick()
        self.assertNotIn(body, self.g.state['player_bodies'])
        phrase = f'Your old body {body["number"]} fades away.'
        self.assertEqual(len(self.messages(self.bob, phrase)), 1)
        self.assertEqual(self.messages(self.alice, phrase), [])
        self.assertEqual(self.messages(self.clara, phrase), [])

    def test_expired_body_on_reload_still_notifies_nonfirst_owner(self):
        body = self.make_expiring_body()
        self.g.save()
        self.fixture.close_game()
        self.fixture.now += 2
        self.g = MultiplayerGame(self.fixture.path, self.fixture.db, clock=lambda: self.fixture.now)
        self.fixture.g = self.g
        self.g.tick()
        self.assertNotIn(body, self.g.state['player_bodies'])
        phrase = f'Your old body {body["number"]} fades away.'
        self.assertEqual(len(self.messages(self.bob, phrase)), 1)
        self.assertEqual(self.messages(self.alice, phrase), [])

    def test_enchantment_expiry_notifies_carrier_only_once(self):
        with self.g.as_player(self.bob):
            iid = self.g.new_instance(dict(kind='weapon', item='iron_sword', bonus=0,
                enchantment=dict(bonus=2, until=self.fixture.now+1)))
            self.g.p['inventory'].append(iid)
        self.fixture.now += 2
        self.g.tick()
        self.g.tick()
        self.assertNotIn('enchantment', self.g.state['instances'][iid])
        self.assertEqual(len(self.messages(self.bob, 'Its magical glow is gone.')), 1)
        self.assertEqual(self.messages(self.alice, 'Its magical glow is gone.'), [])
        self.assertEqual(self.messages(self.clara, 'Its magical glow is gone.'), [])
