"""One serialized world, independent characters, and recipient-owned logs.

Legacy mechanics run in an explicit player context under the world lock. Only
the selected player's snapshot is returned; other logs never enter that
response. Character selection is open during local/LAN multiplayer testing.
"""
from contextlib import contextmanager
import copy

from engine import Game
from encounters import actor_id, ready_actions, sync_encounter
from social import Social

PRIVATE_KEYS = ('player', 'log', 'announced_skills', 'learning_announced_level')


class MultiplayerGame(Social, Game):
    multiplayer = True

    def __init__(self, *args, **kwargs):
        self._ready = False
        self._selected = None
        self._presence = {}
        self._mana_clocks = {}
        self._encounters = {}
        self._ticking = False
        super().__init__(*args, **kwargs)
        self.state.setdefault('players', {})
        self.state.setdefault('owner_id', self.p['id'] if self.p else None)
        if self.p:
            self.state['players'][self.p['id']] = {key: self.state.get(key) for key in PRIVATE_KEYS}
        self._ready = True
        self._selected = self.p['id'] if self.p else None
        for ident in list(self.state['players']):
            with self.as_player(ident):
                self.init_adventure()
                self.announce_skills(initial=True)
                if self.p.get('combat'):
                    room = self.p['room']
                    old = self.p['combat']
                    encounter = self._encounters.setdefault(room, old)
                    encounter['engaged'] = list(dict.fromkeys(encounter.get('engaged', []) + old.get('engaged', [])))
                    encounter['next_at'] = self.clock() + self.w['settings']['attack_interval']
                    self.p['combat'] = encounter
        self.check_live_references(self.w)
        self.save()

    @property
    def owner_id(self):
        return self.state.get('owner_id')

    def all_players(self):
        players = {ident: row['player'] for ident, row in self.state.get('players', {}).items()}
        if self.p:
            players[self.p['id']] = self.p
        return list(players.values())

    def _flush_player(self):
        if self.p:
            ident = self.p['id']
            self.state['players'][ident] = {key: self.state.get(key) for key in PRIVATE_KEYS}
            self._mana_clocks[ident] = (self._mana_tick, self._mana_in_combat)

    def _select(self, ident):
        row = self.state['players'].get(ident, {})
        self.state.update(player=row.get('player'), log=row.get('log') or [],
                          announced_skills=row.get('announced_skills') or [],
                          learning_announced_level=row.get('learning_announced_level') or 0)
        self.p = self.state['player']
        self._selected = ident
        self._mana_tick, self._mana_in_combat = self._mana_clocks.get(ident, (self.clock(), bool(self.p and self.p.get('combat'))))

    @contextmanager
    def as_player(self, ident):
        with self.lock:
            self._flush_player()
            previous = self._selected
            self._select(ident)
            try:
                yield self
            finally:
                self._flush_player()
                self._select(previous)

    def save(self):
        if not self._ready:
            return super().save()
        self._flush_player()
        # Retain the original owner in the legacy fields for save compatibility.
        payload = dict(self.state)
        owner = self.state['players'].get(self.owner_id, {})
        payload.update({key: owner.get(key) for key in PRIVATE_KEYS})
        payload['log'] = owner.get('log') or []
        import json
        with self.db:
            self.db.execute('INSERT OR REPLACE INTO state VALUES (?, ?)', ('world', json.dumps(payload)))

    def character_choices(self):
        with self.lock:
            return [dict(id=p['id'], name=p['name'], level=p['level'],
                         race=p['race'], **{'class': p['class']}, gender=p.get('gender', 'male'),
                         race_name=self.w['races'][p['race']]['name'],
                         class_name=self.w['classes'][p['class']]['name']) for p in self.all_players()]

    def create_character(self, name, race='human', character_class='warrior', owner=False, gender='male'):
        with self.lock:
            name = ' '.join(str(name).split())
            if any(p['name'].casefold() == name.casefold() for p in self.all_players()):
                raise ValueError('That character already exists. Choose it from the character list to continue.')
            if any(n['name'].casefold() == name.casefold() for n in self.w.get('npcs', {}).values()):
                raise ValueError('That name belongs to a townsfolk NPC. Choose another character name.')
            healing = self._enemy_heal_at
            with self.as_player(None):
                super().create(name, race, character_class, gender=gender)
                ident = self.p['id']
                self._selected = ident
                self._flush_player()
                if owner and not self.owner_id:
                    self.state['owner_id'] = ident
                self._enemy_heal_at = healing
                self.save()
            self.touch(ident)
            return ident

    def touch(self, ident):
        if ident in self.state['players']:
            self._presence[ident] = self.clock()

    def resume_character(self, ident):
        with self.as_player(ident):
            if self.p and self.p.pop('logged_out', False):
                self._mana_tick = self.clock()
                self.save()

    def leave_character(self, ident):
        with self.as_player(ident):
            if self.p.get('combat'):
                raise ValueError('Finish combat or FLEE before quitting.')
            previous = self.p.get('logged_out')
            self.p['logged_out'] = True
            try:
                self.save()
            except Exception:
                if previous is None:
                    self.p.pop('logged_out', None)
                else:
                    self.p['logged_out'] = previous
                raise
        self._presence.pop(ident, None)

    def social_players(self):
        return [p for p in self.all_players() if not p.get('logged_out') and
                (p is self.p or self.clock()-self._presence.get(p['id'], float('-inf')) < 30)]

    def deliver_message(self, player_id, text, kind):
        with self.as_player(player_id):
            self.log(text, kind)

    def player_event(self, player_id, text, kind='info'):
        if not self._ready:
            return super().player_event(player_id, text, kind)
        if player_id in self.state['players']:
            self.deliver_message(player_id, text, kind)

    def room_event(self, room, text, kind='info'):
        if not self._ready:
            return super().room_event(room, text, kind)
        for player in self.all_players():
            if player['room'] == room and not player.get('logged_out'):
                with self.as_player(player['id']):
                    super().room_event(room, text, kind)

    def expire_player_bodies(self):
        # Wait until every saved character has a routable log during startup.
        if self._ready:
            super().expire_player_bodies()

    def guide_command(self, verb, target):
        if verb == 'say':
            self.say(target); return True
        if verb == 'tell':
            self.tell(target); return True
        if verb == 'who':
            names = ', '.join(p['name'] for p in self.social_players())
            self.log('Online: '+(names or 'nobody')+'.'); return True
        return super().guide_command(verb, target)

    def show_help(self, query=''):
        if query.casefold() in ('chat', 'talk', 'say', 'tell', 'who', 'conversation', 'dialogue', 'npc'):
            self.log('SAY <message> speaks to everyone currently in your room. Example: SAY Hello everyone!\n'
                     'TELL <full name> <message> is private between you and one online player, even in another room. Example: TELL Bob Hi!\n'
                     'Use WHO to see online players. Multiword names work: TELL Sam Green Hello!\n'
                     'NPCs must be in your room: TELL Fizzlewick P. Grubbs hi starts a private conversation. SAY hello can receive a public NPC reply.\n'
                     'TALK GRUBBS, ASK GRUBBS ABOUT BUYING, and SAY BUYING TO GRUBBS also work. NPC replies use their authored dialogue.\n'
                     'If a name matches both a player and NPC, specify TELL PLAYER <name> <message> or TELL NPC <name> <message>.')
            return
        return super().show_help(query)

    def show_syntax(self, query):
        if query.casefold() == 'say':
            self.log('SAY <message>\nSAY <phrase> TO <NPC | creature | CAGE number>\nExample: SAY Hello everyone!\nDetails: HELP CHAT')
            return
        return super().show_syntax(query)

    def look(self, target):
        super().look(target)
        if self._ready and not target and self.p and self.visible():
            names = [p['name'] for p in self.social_players() if p['id'] != self.p['id'] and p['room'] == self.p['room']]
            if names:
                self.log('Players here: '+', '.join(names)+'.')

    def snapshot(self):
        result = super().snapshot()
        if self._ready:
            result['multiplayer'] = True
            result['players_here'] = [dict(name=p['name'], level=p['level']) for p in self.social_players()
                                      if self.p and p['id'] != self.p['id'] and p['room'] == self.p['room'] and self.visible()]
            # Return detached data while still holding the world lock.
            return copy.deepcopy(result)
        return result

    def engaged_creature_ids(self):
        return {uid for p in self.all_players() for uid in (p.get('combat') or {}).get('engaged', [])}

    def start_combat(self, initiated=True):
        if not self._ready:
            return super().start_combat(initiated)
        enemy = self.enemy()
        if not enemy or self.w['rooms'][self.p['room']].get('safe'):
            return
        if not self.p.get('combat'):
            room = self.p['room']
            encounter = self._encounters.setdefault(room, dict(room=room, turn='simultaneous', next_at=self.clock(),
                engaged=[], initiator=self.p['id'] if initiated else None))
            self.p['combat'] = encounter
            self.p['target'] = enemy['uid']
            if enemy['uid'] not in encounter['engaged']:
                encounter['engaged'].append(enemy['uid'])
            self.log('Combat begins: '+self.creature_name(enemy)+'. Attacks are automatic.', 'combat')
            self.refresh_encounter(encounter)

    def refresh_encounter(self, encounter):
        room = encounter['room']
        players = [p for p in self.all_players() if p['room'] == room and p.get('combat') is encounter and p['hp'] > 0]
        enemies = self.creatures(room)
        engaged = encounter['engaged']
        for enemy in enemies:
            if self.w['enemies'][enemy['type']]['aggressive'] and enemy['uid'] not in engaged:
                engaged.append(enemy['uid'])
        enemies = [e for e in enemies if e['uid'] in engaged]
        if not players or not enemies:
            for player in players:
                player['combat'] = None
                player.pop('target', None)
            self._encounters.pop(room, None)
            return {}
        for player in players:
            if not any(e['uid'] == player.get('target') for e in enemies):
                player['target'] = enemies[0]['uid']
        return sync_encounter(encounter, players, enemies, self.rng)

    def retarget(self):
        if not self._ready:
            return super().retarget()
        if self.p and self.p.get('combat'):
            self.refresh_encounter(self.p['combat'])

    def apply_effects(self, attachments, actor, damage_override=None):
        super().apply_effects(attachments, actor, damage_override)
        if self.p and actor is not self.p and actor.get('effects'):
            actor['effect_source'] = self.p['id']

    def victory(self, enemy):
        if enemy.get('reward_claimed'):
            return
        enemy['reward_claimed'] = True
        super().victory(enemy)

    def tick(self):
        if not self._ready:
            return super().tick()
        with self.lock:
            if self._ticking or not self.all_players():
                return
            self._ticking = True
            try:
                self._flush_player()
                before = copy.deepcopy(self.state)
                players = self.all_players()
                with self.as_player(players[0]['id']):
                    self.cleanup_drops(); self.expire_player_bodies(); self.roam(); self.expire_enchantments()
                    self.state['corpses'] = [c for c in self.state['corpses'] if c['expires'] > self.clock() and not c.get('harvested')]
                    self.heal_enemies()
                for player in players:
                    if player.get('logged_out'):
                        continue
                    with self.as_player(player['id']):
                        self.retarget()
                        if not player.get('combat'):
                            hostile = next((e for e in self.creatures() if self.w['enemies'][e['type']]['aggressive']), None)
                            if hostile:
                                player['target'] = hostile['uid']; self.start_combat(initiated=False)
                        self.recover_mana()
                for encounter in list(self._encounters.values()):
                    if self.clock() < encounter['next_at']:
                        continue
                    roster = self.refresh_encounter(encounter)
                    if not roster:
                        continue
                    members = encounter['participants']['players'][:]
                    stunned = {ident: any(self.w['status_effects'].get(s['id'], {}).get('kind') == 'stun' for s in actor.get('effects', [])) for ident, actor in roster.items()}
                    for ident, actor in list(roster.items()):
                        current = self.refresh_encounter(encounter)
                        if not current:
                            break
                        if ident not in current:
                            continue
                        members = encounter['participants']['players'][:]
                        source = ident if ident in self.state['players'] else actor.get('effect_source')
                        if source not in members:
                            source = members[0]
                        with self.as_player(source):
                            self.pulse_effects(actor)
                    roster = self.refresh_encounter(encounter)
                    for actor, _ in ready_actions(encounter, roster, None, self.clock()):
                        roster = self.refresh_encounter(encounter)
                        target = roster.get(encounter['targets'].get(actor_id(actor)))
                        if actor_id(actor) not in roster or not target or actor['hp'] <= 0 or target['hp'] <= 0:
                            continue
                        if stunned.get(actor_id(actor)):
                            continue
                        ident = actor['id'] if 'race' in actor else target['id']
                        with self.as_player(ident):
                            if actor is self.p:
                                self.strike()
                            else:
                                self.enemy_strike(actor)
                        actor['attack_ready'] = self.clock()+2*self.w['settings']['attack_interval']*self.slow(actor)
                    encounter['next_at'] = self.clock()+self.w['settings']['attack_interval']
                for player in players:
                    if not player.get('logged_out'):
                        with self.as_player(player['id']):
                            self.clear_idle_stun()
                self._flush_player()
                if before != self.state:
                    self.save()
            finally:
                self._ticking = False

    def check_live_references(self, world):
        if not self._ready:
            return super().check_live_references(world)
        for ident in list(self.state['players']):
            with self.as_player(ident):
                super().check_live_references(world)

    def update_world(self, world):
        with self.lock:
            if any(p.get('combat') for p in self.all_players()):
                raise ValueError('Finish all players\' combat before changing world content.')
            super().update_world(world)
            for ident in list(self.state['players']):
                with self.as_player(ident):
                    self.p['hp'] = min(self.p['hp'], self.max_hp())
                    self.announce_skills()
            self.save()
