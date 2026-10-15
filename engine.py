"""Authoritative, transport-independent game engine. Standard library only."""
import copy
import json
import math
import random
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from adventure import validate_adventure
from frontier import validate_frontier
from abilities import Abilities, validate_abilities
from revision_rules import validate_revision
from magic_progression import validate_magic

DIRECTIONS = {'n': 'north', 's': 'south', 'e': 'east', 'w': 'west', 'u': 'up', 'd': 'down'}

def validate(w):
    def require(ok, message):
        if not ok:
            raise ValueError(message)
    def number(v, low=0, high=100000, integer=False):
        return type(v) in (int, float) and math.isfinite(v) and low <= v <= high and (not integer or type(v) is int)
    def text(v):
        return isinstance(v, str) and 0 < len(v) <= 6000
    require(isinstance(w, dict), 'World must be an object.')
    for key in ('settings', 'races', 'classes', 'skills', 'items', 'enemies', 'rooms', 'starting'):
        require(isinstance(w.get(key), dict), f'{key} must be an object.')
    require(text(w.get('title')), 'A title is required.')
    s = w['settings']
    for key in ('hit_chance', 'flee_chance', 'gold_loss', 'item_loss_chance'):
        require(number(s.get(key), 0, 1), f'{key} must be between 0 and 1.')
    require(number(s.get('attack_interval'), .25, 30), 'Attack interval must be 0.25–30 seconds.')
    for key in ('bag_capacity', 'hp_per_level', 'damage_per_level'):
        require(number(s.get(key), 1, 1000, True), f'{key} must be a positive integer.')
    xp = s.get('level_xp')
    require(isinstance(xp, list) and 1 <= len(xp) <= 100 and xp[0] == 0 and all(number(x, 0, 10000000, True) for x in xp) and all(a < b for a, b in zip(xp, xp[1:])), 'Level XP must start at 0 and increase strictly.')
    def span(v, label):
        require(isinstance(v, list) and len(v) == 2 and all(number(x, 0, 100000, True) for x in v) and v[0] <= v[1], label + ' must be [minimum, maximum] integers.')
    for key in ('rooms', 'items', 'enemies', 'races', 'classes', 'skills'):
        for ident, obj in w[key].items():
            require(text(ident) and isinstance(obj, dict) and text(obj.get('name')), f'Invalid {key} entry: {ident}.')
    require('human' in w['races'] and 'warrior' in w['classes'] and 'bash' in w['skills'], 'Prototype needs human, warrior, and bash.')
    for r in w['races'].values():
        require(number(r.get('hp_bonus'), 0, 10000, True), 'Race HP bonus must be a nonnegative integer.')
    for c in w['classes'].values():
        require(number(c.get('hp'), 1, 10000, True), 'Class HP must be a positive integer.')
        span(c.get('damage'), 'Class damage')
        require(isinstance(c.get('skills'), list) and all(x in w['skills'] for x in c['skills']), 'Unknown class skill.')
    for k in w['skills'].values():
        require(number(k.get('cooldown'), .25, 3600) and number(k.get('multiplier'), .1, 100), 'Invalid skill cooldown or multiplier.')
    for i in w['items'].values():
        require(i.get('kind') in ('weapon', 'armor', 'consumable', 'light', 'loot', 'key', 'cage', 'chest'), 'Unknown item kind.')
        require(number(i.get('price'), 0, 100000, True), 'Prices must be nonnegative integers.')
        require(text(i.get('description')), 'Item description required.')
        for key in ('damage', 'armor', 'heal'):
            if key in i:
                require(number(i[key], 0, 10000, True), f'Item {key} must be a nonnegative integer.')
        required = {'weapon': 'damage', 'armor': 'armor', 'consumable': 'heal'}.get(i['kind'])
        require(not required or required in i, f'{i["name"]} is missing {required}.')
        if 'protected' in i:
            require(type(i['protected']) is bool, 'protected must be true or false.')
    for e in w['enemies'].values():
        require(number(e.get('hp'), 1, 100000, True), 'Enemy HP must be a positive integer.')
        require(number(e.get('dodge', 0), 0, 100), 'Enemy dodge must be a percentage between 0 and 100.')
        span(e.get('damage'), 'Enemy damage'); span(e.get('gold'), 'Enemy gold')
        require(number(e.get('xp'), 0, 100000, True) and number(e.get('respawn'), 1, 86400), 'Invalid enemy XP or respawn.')
        require(type(e.get('aggressive')) is bool and text(e.get('description')), 'Enemy needs aggression and description.')
        loot = e.get('loot')
        require(isinstance(loot, list) and len(loot) > 0, 'Enemy needs a weighted loot table.')
        for l in loot:
            require(isinstance(l, dict) and (l.get('item') is None or l['item'] in w['items']) and number(l.get('weight'), .001, 100000), 'Invalid loot entry.')
    for r in w['rooms'].values():
        require(text(r.get('description')) and isinstance(r.get('exits'), dict), 'Rooms need descriptions and exits.')
        require(all(d in ('north', 'south', 'east', 'west', 'up', 'down') and dest in w['rooms'] for d, dest in r['exits'].items()), 'Exit points to an unknown room or direction.')
        require('enemy' not in r or r['enemy'] in w['enemies'], 'Unknown room enemy.')
        require('shop' not in r or isinstance(r['shop'], list) and all(i in w['items'] for i in r['shop']), 'Unknown shop item.')
        require(isinstance(r.get('objects', {}), dict) and all(text(k) and text(v) for k, v in r.get('objects', {}).items()), 'Objects must map names to descriptions.')
        for key in ('safe', 'dark', 'rest', 'obscured_from_outside'):
            if key in r:
                require(type(r[key]) is bool, f'{key} must be true or false.')
        require(isinstance(r.get('obscured_message', ''), str) and len(r.get('obscured_message', '')) <= 6000, 'Obscured-view message must be text up to 6000 characters.')
        require(not (r.get('safe') and r.get('enemy')), 'Safe rooms cannot contain enemies.')
    a = w['starting']
    require(a.get('room') in w['rooms'] and w['rooms'][a['room']].get('safe'), 'Starting room must be safe.')
    require(number(a.get('gold'), 0, 100000, True), 'Starting gold must be a nonnegative integer.')
    require(isinstance(a.get('inventory'), list) and all(i in w['items'] for i in a['inventory']), 'Invalid starting inventory.')
    require(len(a['inventory']) <= s['bag_capacity'], 'Starting inventory exceeds bag capacity.')
    from equipment import BODY_SLOTS, SLOT_NAMES
    require(isinstance(a.get('equipment'), dict) and not set(a['equipment'])-set(SLOT_NAMES), 'Starting equipment has an unknown slot.')
    for slot,iid in a['equipment'].items():
        item=w['items'].get(iid,{})
        require(item.get('kind') in ('weapon','armor'), 'Starting equipment must be weapons or armor.')
        if slot in BODY_SLOTS:require(item['kind']=='armor' and not item.get('shield') and item.get('armor_slot','armor')==slot,'Starting armor does not match its slot.')
    right=w['items'].get(a['equipment'].get('weapon'),{});left=w['items'].get(a['equipment'].get('left_hand'),{})
    require(not left or right.get('hands',1)!=2 and left.get('hands',1)!=2,'Starting two-handed weapon requires both hands.')
    require(not (right.get('shield') and left.get('shield')),'Starting equipment can contain only one shield.')
    return validate_magic(validate_abilities(validate_adventure(validate_frontier(validate_revision(w)))))


class LegacyGame(Abilities):
    def __init__(self, content_path, database_path, rng=None, clock=None):
        self.path = Path(content_path)
        self.w = validate(json.loads(self.path.read_text(encoding='utf-8')))
        self.rng, self.clock = rng or random.Random(), clock or time.time
        self.lock = threading.RLock()
        self.db = sqlite3.connect(database_path, check_same_thread=False)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('CREATE TABLE IF NOT EXISTS state (id TEXT PRIMARY KEY, body TEXT NOT NULL)')
        saved = self.db.execute("SELECT body FROM state WHERE id='world'").fetchone()
        self.state = json.loads(saved[0]) if saved else {'player': None, 'spawns': {}, 'ground': {}, 'log': [], 'sequence': 0}
        self.p = self.state['player']
        self.init_adventure()
        if self.p and self.p.get('combat'):
            self.p['combat']['next_at'] = self.clock() + self.w['settings']['attack_interval']
        if self.p:
            self.check_live_references(self.w)
            self.announce_skills(initial=True)
        self.save()

    def save(self):
        with self.db:
            self.db.execute('INSERT OR REPLACE INTO state VALUES (?, ?)', ('world', json.dumps(self.state)))

    def log(self, message, kind='info'):
        self.state['sequence'] += 1
        self.state['log'].append({'id': self.state['sequence'], 'text': message, 'kind': kind})
        self.state['log'] = self.state['log'][-180:]

    def create(self, name, race="human", character_class="warrior"):
        with self.lock:
            if self.p:
                raise ValueError('A character already exists. Continue your saved adventure.')
            name = ' '.join(str(name).split())
            if not 1 <= len(name) <= 32 or not all(c.isalnum() or c in " '-" for c in name):
                raise ValueError('Use 1–32 letters, numbers, spaces, apostrophes, or hyphens for your name.')
            if race not in self.w['races'] or character_class not in self.w['classes']:
                raise ValueError('Choose an existing race and class.')
            a = self.w['starting']
            self.p = self.state['player'] = {'id': 'player-'+uuid.uuid4().hex, 'name': name, 'race': race, 'class': character_class, 'level': 1, 'xp': 0, 'hp': self.w['classes'][character_class]['hp'] + self.w['races'][race]['hp_bonus'], 'gold': a['gold'], 'room': a['room'], 'inventory': a['inventory'][:], 'equipment': dict(a['equipment']), 'cooldowns': {}, 'combat': None, 'learned_skills': {}, 'ability_points_spent': 0}
            self.init_adventure()
            self.log(f'Welcome, {name}. Your story begins in Center Square.', 'story')
            self.state['announced_skills']=[]
            self.announce_skills()
            self.look(''); self.save()
            return self.snapshot()

    def max_hp(self):
        return self.w['classes'][self.p['class']]['hp'] + self.w['races'][self.p['race']]['hp_bonus'] + (self.p['level'] - 1) * self.w['settings']['hp_per_level']

    def visible(self, room_id=None):
        return not self.w['rooms'][room_id or self.p['room']].get('dark') or any(self.item(i)['kind'] == 'light' for i in self.p['inventory'])

    def enemy(self, room_id=None):
        return self.resident_enemy(room_id)

    def start_combat(self, initiated=True):
        e = self.enemy()
        if e and not self.p['combat']:
            self.p['combat'] = {'room': self.p['room'], 'turn': 'player', 'next_at': self.clock()}
            self.log(f'Combat begins: {self.w["enemies"][e["type"]]["name"]}. Use SKILLS to check your abilities, QUAFF POTION to heal, or FLEE to escape.', 'combat')

    def tick(self):
        with self.lock:
            if not self.p:
                return
            previous = json.dumps(self.state, sort_keys=True)
            self.cleanup_drops()
            e = self.enemy()
            if e and self.w['enemies'][e['type']]['aggressive'] and not self.p['combat']:
                self.log('A hostile creature spots you.', 'danger'); self.start_combat()
            c = self.p['combat']
            if c and self.clock() >= c['next_at']:
                e = self.enemy()
                if not e:
                    self.p['combat'] = None
                elif c['turn'] == 'player':
                    self.strike(); c['turn'] = 'enemy'
                else:
                    self.enemy_strike(e); c['turn'] = 'player'
                if self.p['combat']:
                    c['next_at'] = self.clock() + self.w['settings']['attack_interval']
            if previous != json.dumps(self.state, sort_keys=True):
                self.save()

    def strike(self, multiplier=1, attack_name=None):
        e = self.enemy()
        if not e:
            return
        name = self.w['enemies'][e['type']]['name']
        if self.rng.random() > self.w['settings']['hit_chance']:
            self.log(f'Your attack misses {name}.', 'combat'); return
        # Legacy enemies default to zero; skip the extra RNG draw at zero so
        # existing combat behavior and seeded outcomes remain unchanged.
        dodge = self.w['enemies'][e['type']].get('dodge', 0)
        if dodge > 0 and self.rng.random() < dodge / 100:
            attack = attack_name or ('Bash' if multiplier != 1 else 'attack')
            self.log(f'{name} dodges your {attack}! No damage dealt.', 'combat')
            return
        cls = self.w['classes'][self.p['class']]
        item = self.w['items'].get(self.p['equipment'].get('weapon'), {})
        dmg = max(1, round((self.rng.randint(*cls['damage']) + item.get('damage', 0) + (self.p['level'] - 1) * self.w['settings']['damage_per_level']) * multiplier))
        e['hp'] = max(0, e['hp'] - dmg)
        self.log((attack_name+"! " if attack_name else "Bash! " if multiplier != 1 else "")+f"You hit {name} for {dmg}.", "combat")
        if e['hp'] == 0:
            self.victory(e)

    def enemy_strike(self, e):
        spec = self.w['enemies'][e['type']]
        if spec.get('battle_cries') and spec.get('battle_cry_chance', 0) > 0 and self.rng.random() < spec['battle_cry_chance'] / 100:
            self.log(self.rng.choice(spec['battle_cries']), 'combat')
        if self.rng.random() > self.w['settings']['hit_chance']:
            self.log(f'{spec["name"]} misses you.', 'combat'); return
        armor = self.w['items'].get(self.p['equipment'].get('armor'), {}).get('armor', 0)
        damage = max(1, self.rng.randint(*spec['damage']) - armor)
        self.p['hp'] = max(0, self.p['hp'] - damage)
        self.log(f'{spec["name"]} hits you for {damage}.', 'danger')
        if self.p['hp'] == 0:
            self.death()

    def victory(self, e):
        spec = self.w['enemies'][e['type']]
        e['hp'] = 0
        if spec.get('defeat_messages'):
            self.log(self.rng.choice(spec['defeat_messages']), 'story')
        if e.get('released'):
            self.p['combat'] = None
            self.log('The released creature falls. No kill rewards are awarded.')
            return
        self.discover('defeat', e['type'])
        gold = self.rng.randint(*spec['gold'])
        self.p['gold'] += gold; self.p['xp'] += spec['xp']; self.p['combat'] = None
        e['respawn_at'] = self.clock() + self.respawn_delay(self.p['room'], e['type'])
        self.log(f'{spec["name"]} falls. +{spec["xp"]} XP · +{gold} gold.', 'reward')
        choice = self.rng.choices(spec['loot'], weights=[x['weight'] for x in spec['loot']], k=1)[0]['item']
        if choice:
            item = self.w['items'][choice]
            choice = self.grant(choice)
            if len(self.p['inventory']) < self.w['settings']['bag_capacity'] and self.can_carry(choice):
                self.p['inventory'].append(choice)
                self.log(f'Loot: {item["name"]}' + (' — uncommon!' if item.get('rarity') else '.'), 'reward')
            else:
                self.state['ground'].setdefault(self.p['room'], []).append(choice)
                self.log(f'You cannot carry more. {item["name"]} remains on the ground. Use GET when you have room and weight capacity.', 'reward')
        level = sum(self.p['xp'] >= x for x in self.w['settings']['level_xp'])
        if level > self.p['level']:
            self.p['level'] = level; self.p['hp'] = self.max_hp()
            self.log(f'Level {level}! Your health is fully restored.', 'reward')
            self.announce_skills()

    def death(self):
        loss = math.ceil(self.p['gold'] * self.w['settings']['gold_loss'])
        self.p['gold'] -= loss
        eligible = [i for i in self.p['inventory'] if not self.item(i).get('protected')]
        lost = None
        if eligible and self.rng.random() < self.w['settings']['item_loss_chance']:
            lost = self.rng.choice(eligible); self.p['inventory'].remove(lost)
        self.log(f'You fall. {loss} gold is lost.' + (f' You also lose {self.item(lost)["name"]}.' if lost else ' Your belongings survive.'), 'danger')
        self.p['combat'] = None; self.p['room'] = self.w['starting']['room']; self.p['hp'] = self.max_hp()
        self.log('You blink awake from death feeling strange and disoriented.', 'story'); self.look('')

    def match(self, target, candidates):
        return self.instance_match(target, candidates)

    def look(self, target):
        if self.extra_look(target): return
        rid = self.p['room']; room = self.w['rooms'][rid]
        target = DIRECTIONS.get(target, target)
        if target in ('north', 'south', 'east', 'west', 'up', 'down'):
            dest = room['exits'].get(target)
            if not dest:
                raise ValueError('There is no exit that way.')
            if not self.visible():
                self.log('Darkness blocks your view. A carried lantern would help.'); return
            adjacent = self.w['rooms'][dest]
            if adjacent.get('obscured_from_outside', False):
                self.log(adjacent.get('obscured_message', '').strip() or 'It is too dark; you cannot see anything.', 'story'); return
            if not self.visible(dest):
                self.log('Darkness blocks your view. A carried lantern would help.'); return
            adjacent = self.w['rooms'][dest]; e = self.enemy(dest)
            self.log(f'To the {target}: {adjacent["name"]}. {adjacent["description"]}' + (f' You see {self.w["enemies"][e["type"]]["name"]}.' if e else ''), 'story'); return
        if not self.visible():
            self.log('You are in darkness. You can feel the exits: ' + ', '.join(room['exits']) + '. Carry a lantern to see.'); return
        if not target:
            self.log(room['name'] + '\n' + room['description'] + '\nExits: ' + ', '.join(room['exits']) + '.', 'story')
            e = self.enemy()
            if e:
                self.log(self.w['enemies'][e['type']]['description'])
            ground = self.visible_ground()
            if ground:
                self.log('On the ground: ' + ', '.join(self.item(i)['name'] for i in ground) + '.')
            self.room_extras()
            return
        for name, desc in room.get('objects', {}).items():
            if target == name.lower():
                self.log(desc, 'story'); return
        e = self.enemy()
        if e and target in self.w['enemies'][e['type']]['name'].lower():
            self.log(self.w['enemies'][e['type']]['description']); return
        candidates = self.p['inventory'] + list(self.p['equipment'].values()) + self.visible_ground() + room.get('shop', [])
        try:
            i = self.match(target, candidates); self.log(self.item(i)['description'])
        except ValueError:
            raise ValueError('You do not see that here.')

    def command(self, raw):
        with self.lock:
            if not self.p:
                raise ValueError('Create your character first.')
            self.tick()
            raw = ' '.join(str(raw).strip().split())[:160]
            if not raw:
                return self.snapshot()
            self.log('> ' + raw, 'command')
            parts = raw.lower().split(' ', 1); verb = DIRECTIONS.get(parts[0], parts[0]); target = parts[1] if len(parts) > 1 else ''
            verb = {'l': 'look', 'i': 'inventory', 'eq': 'equipment', 'a': 'attack', 'kill': 'attack'}.get(verb, verb)
            try:
                room = self.w['rooms'][self.p['room']]
                if self.skill_command(verb, target) or self.extra_command(verb, target):
                    return self.finish()
                if verb in ('north', 'south', 'east', 'west', 'up', 'down'):
                    if self.p['combat']:
                        raise ValueError('You are fighting. Use FLEE to attempt an escape.')
                    if verb not in room['exits']:
                        raise ValueError('There is no exit that way.')
                    self.p['room'] = room['exits'][verb]; self.roll_encounter(self.p['room']); self.look('')
                    e = self.enemy()
                    if e and self.w['enemies'][e['type']]['aggressive']:
                        self.start_combat(initiated=False)
                elif verb == 'look':
                    self.look(target)
                elif verb == 'attack':
                    e = self.enemy()
                    if not self.visible():
                        raise ValueError('It is too dark to choose a target. Carry a lantern.')
                    if not e or target and target not in self.w['enemies'][e['type']]['name'].lower() and target != e['type']:
                        raise ValueError('That enemy is not here.' if target else 'There is nothing here to attack.')
                    if self.p['combat']:
                        raise ValueError('Your basic attacks are already automatic.')
                    self.start_combat()
                elif verb == 'flee':
                    if not self.p['combat']:
                        raise ValueError('You are not in combat.')
                    left = self.p['cooldowns'].get('flee', 0) - self.clock()
                    if left > 0:
                        raise ValueError(f'Try fleeing again in {math.ceil(left)} seconds.')
                    self.p['cooldowns']['flee'] = self.clock() + self.w['settings']['attack_interval']
                    if self.rng.random() < min(1,self.w['settings']['flee_chance']+self.w['classes'][self.p['class']].get('flee_bonus',0)) and room['exits']:
                        self.p['room'] = self.rng.choice(list(room['exits'].values())); self.p['combat'] = None
                        self.log('You break away and escape.', 'story'); self.roll_encounter(self.p['room']); self.look('')
                    else:
                        self.log('You cannot break away!', 'danger')
                elif verb == 'inventory':
                    ids = self.p['inventory']
                    lines = []
                    for i in dict.fromkeys(ids):
                        item = self.item(i)
                        count = ids.count(i)
                        lines.append(self.marked(i, count))
                        if item['kind'] in ('weapon','armor'):
                            lines[-1] += ' — ' + self.gear_stats(item)
                        if item.get('enchantment_description'):
                            lines[-1] += '\n' + item['enchantment_description']
                    self.log(verb.title() + ':\n' + ('\n'.join(lines) or 'empty'))
                    self.log(f'Carrying {self.carried_weight():g}/{self.carry_capacity():g} lb, including worn equipment and container contents.')
                elif verb in ('buy', 'sell', 'equip', 'unequip', 'drop', 'get'):
                    if self.p['combat']:
                        raise ValueError('Finish the fight before trading or rearranging items.')
                    inv = self.p['inventory']; ground = self.state['ground'].setdefault(self.p['room'], [])
                    if verb in ('buy', 'sell') and 'shop' not in room:
                        raise ValueError('You need to be at a shop.')
                    if verb == 'buy' and not target:
                        self.log('For sale:\n' + '\n'.join(f'{self.marked(i, room["shop"].count(i))} — {self.item(i)["price"]} gold each' for i in dict.fromkeys(room['shop']))); return self.finish()
                    if verb == 'unequip':
                        if target not in self.p['equipment']:
                            raise ValueError('Use UNEQUIP WEAPON or UNEQUIP ARMOR.')
                        if len(inv) >= self.w['settings']['bag_capacity']:
                            raise ValueError('Your bag is full.')
                        inv.append(self.p['equipment'].pop(target)); self.log('Equipment returned to your bag.'); return self.finish()
                    candidates = room.get('shop', []) if verb == 'buy' else self.visible_ground() if verb == 'get' else inv
                    i = self.match(target, candidates); item = self.item(i)
                    if verb in ('buy', 'get') and len(inv) >= self.w['settings']['bag_capacity']:
                        raise ValueError('Your bag is full.')
                    if verb in ('buy','get'):self.require_carry(i)
                    if verb == 'get' and not self.visible():
                        raise ValueError('It is too dark to find items on the ground.')
                    if verb == 'buy':
                        if self.p['gold'] < item['price']:
                            raise ValueError('You do not have enough gold.')
                        self.p['gold'] -= item['price']; inv.append(self.grant(i))
                    elif verb == 'sell':
                        if item['kind'] in ('key', 'captive') or item.get('occupied'):
                            raise ValueError('Keys, loose captured creatures, and occupied containers cannot be sold here.')
                        self.state['instances'].pop(i, None)
                        inv.remove(i); price = item['price'] // 2; self.p['gold'] += price
                        self.log(f'Sold {item["name"]} for {price} gold.'); return self.finish()
                    elif verb == 'equip':
                        slot = item['kind']
                        if slot not in ('weapon', 'armor'):
                            raise ValueError('Only weapons and armor are equipped. Lanterns work while carried.')
                        inv.remove(i)
                        if slot in self.p['equipment']:
                            inv.append(self.p['equipment'][slot])
                        self.p['equipment'][slot] = i
                    elif verb == 'drop':
                        self.drop_item(i)
                    elif verb == 'get':
                        self.get_item(i)
                    self.log(f'{verb.title()}: {item["name"]}.')
                elif verb in ('use', 'quaff'):
                    i = self.match(target, self.p['inventory']); item = self.item(i)
                    if verb == 'quaff' and item['kind'] != 'consumable':
                        raise ValueError('You can only quaff a potion or another consumable.')
                    if item['kind'] == 'light':
                        self.log('Your lantern lights the way while carried.'); return self.finish()
                    if not item.get('heal'):
                        raise ValueError('That item cannot be used this way.')
                    if self.p['hp'] >= self.max_hp():
                        raise ValueError('You already have full health. Save your potion.')
                    remaining=self.p.get('potion_ready',0)-self.clock()
                    if remaining>0:
                        raise ValueError(f'You can drink another healing potion in {math.ceil(remaining)} seconds.')
                    restored = min(item['heal'], self.max_hp() - self.p['hp'])
                    self.p['hp'] += restored; self.p['inventory'].remove(i)
                    self.p['potion_ready']=self.clock()+self.rules()['potion_recovery']
                    self.log(f'You recover {restored} HP.', 'reward')
                elif verb == 'rest':
                    if self.p['combat'] or not room.get('rest'):
                        raise ValueError('Rest at The Quiet Coil, west of Center Square.')
                    self.p['hp'] = self.max_hp();self.p['mana']=self.max_mana(); self.log('You rest by the fire. Health and mana fully restored.', 'reward')
                elif verb in ('help', '?'):
                    self.log('LEARN [ability] to choose or improve abilities with earned points. MANA for reserves, WEIGHT for carrying capacity, REPAIR [item] at a repair service. MOVE: N S E W UP DOWN. LOOK [direction/object/item]. INVENTORY (I), EQUIPMENT, EQUIP <item>, UNEQUIP <weapon/armor>. BUY [item], SELL <item>, GET <item>, DROP <item>, QUAFF POTION. ATTACK [enemy], SKILLS, CAST <skill name>, BASH, KNOCKOUT [enemy], FLEE. UNLOCK <box>. GET <unconscious creature>, PUT <creature> IN CAGE <number>, LOOK CAGE <number>, RELEASE CAGE <number>. PUT <item> IN CHEST <number>, GET <item> FROM CHEST <number>, LOOK CHEST <number>. SAY <phrase> TO <creature/cage>. REST at the inn. Progress saves automatically; combat continues while this server is running, even if you close the browser.')
                elif verb == 'save':
                    self.log('Progress saved. Saving is also automatic.')
                else:
                    raise ValueError('Unknown command. Type HELP for commands.')
            except ValueError as error:
                self.log(str(error), 'notice')
            return self.finish()

    def finish(self):
        self.save(); return self.snapshot()

    def snapshot(self):
        with self.lock:
            result = {'title': self.w['title'], 'player': None, 'log': self.state['log'], 'time': self.clock()}
            if not self.p:
                result['creation']={group:[{'id':i,**value} for i,value in sorted(self.w[group].items(),key=lambda x:x[1]['name'].casefold())] for group in ('races','classes')}
                return result
            p = copy.deepcopy(self.p); p['max_hp'] = self.max_hp()
            thresholds = self.w['settings']['level_xp']; p['next_xp'] = thresholds[p['level']] if p['level'] < len(thresholds) else None
            p['level_start_xp'] = thresholds[min(p['level'] - 1, len(thresholds) - 1)]
            p['bag_capacity'] = self.w['settings']['bag_capacity']
            r = self.w['rooms'][p['room']]; light = self.visible(); e = self.enemy()
            result.update(player=p, room={'name': r['name'] if light else 'Darkness', 'description': r['description'] if light else 'You cannot see. Carry a lantern to light the way.', 'exits': list(r['exits']), 'objects': [], 'safe': r.get('safe', False), 'shop': r.get('shop', []), 'rest': r.get('rest', False)}, items=self.w['items'], ground=self.visible_ground() if light else [], enemy=({'name': self.w['enemies'][e['type']]['name'], 'hp': e['hp'], 'max_hp': self.w['enemies'][e['type']]['hp'], 'aggressive': self.w['enemies'][e['type']]['aggressive']} if e and light else None), skills=self.w['skills'])
            return self.extra_snapshot(result)

    def check_live_references(self, w):
        if not self.p:
            return
        self.check_adventure_references(w)
        p = self.p
        if p['room'] not in w['rooms'] or p['race'] not in w['races'] or p['class'] not in w['classes']:
            raise ValueError('Cannot remove the saved character’s room, race, or class.')
        used = p['inventory'] + list(p['equipment'].values()) + [i for pile in self.state['ground'].values() for i in pile]
        if any(i not in w['items'] and i not in self.state['instances'] for i in used):
            raise ValueError('Cannot remove items currently held or on the ground.')
        if any(w['items'].get(self.state['instances'].get(i,{}).get('item',i),{}).get('kind') not in (('armor',) if slot=='armor' else ('weapon','armor')) for slot, i in p['equipment'].items()):
            raise ValueError('Cannot change the kind of an equipped item.')
        if any(r not in w['rooms'] for r, pile in self.state['ground'].items() if pile):
            raise ValueError('Cannot remove a room containing dropped items.')
        if len(w['settings']['level_xp']) < p['level']:
            raise ValueError('Cannot remove the saved character’s level.')
        if len(p['inventory']) > w['settings']['bag_capacity']:
            raise ValueError('Bag capacity is smaller than the saved inventory.')

    def update_world(self, new):
        with self.lock:
            validate(new)
            for rid, room in self.w['rooms'].items():
                if rid in new['rooms'] and room.get('code') and new['rooms'][rid].get('code') != room['code']:
                    raise ValueError('Existing room reference codes are permanent. Rename the room instead.')
            self.check_live_references(new)
            if self.p and self.p['combat']:
                raise ValueError('Finish combat before changing world content.')
            backup = self.path.parent / 'history'; backup.mkdir(exist_ok=True)
            stamp = str(time.time_ns())
            (backup / f'world-{stamp}.json').write_text(self.path.read_text(encoding='utf-8'), encoding='utf-8')
            temp = self.path.with_suffix('.tmp'); temp.write_text(json.dumps(new, indent=2, ensure_ascii=False), encoding='utf-8'); temp.replace(self.path)
            self.w = copy.deepcopy(new)
            for rid, spawn in list(self.state['spawns'].items()):
                room=new['rooms'].get(rid,{})
                allowed={room.get('enemy'),room.get('encounter',{}).get('enemy')} | {x['enemy'] for x in room.get('spawn_pool',[])}
                if rid not in new['rooms'] or spawn['type'] not in allowed:
                    del self.state['spawns'][rid]
                elif spawn['hp'] > 0:
                    spawn['hp'] = min(spawn['hp'], new['enemies'][spawn['type']]['hp'])
            if self.p:
                self.p['hp'] = min(self.p['hp'], self.max_hp())
                self.announce_skills()
                self.log('World settings updated by the owner.', 'notice')
            self.save()


from expedition import Revision

class Game(Revision, LegacyGame):
    """Current game; legacy methods retain unchanged discovery/storage behavior."""
    pass
