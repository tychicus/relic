"""Contextual player help, explicit command aliases and cosmetic social actions.

Help reads the same rules as gameplay. Suggestions never execute a command.
Emotes produce narrative only; they do not invoke NPC dialogue or combat.
"""
import difflib
import re


ALIASES = {
    'n': 'north', 's': 'south', 'e': 'east', 'w': 'west', 'u': 'up', 'd': 'down',
    'l': 'look', 'examine': 'look', 'inspect': 'look',
    'i': 'inventory', 'inv': 'inventory', 'eq': 'equipment',
    'a': 'attack', 'kill': 'attack', 'wear': 'equip', 'wield': 'equip',
    'remove': 'unequip', 'take': 'get', 'pickup': 'get', 'drink': 'quaff',
    'h': 'help', '?': 'help', 'commands': 'help', 'usage': 'syntax',
    'abilities': 'skills', 'train': 'learn', 'capacity': 'weight',
    'meditate': 'mana', 'skill': 'cast', 'chat': 'talk',
    'socials': 'emotes', 'social': 'emote',
    'enchanting': 'enchant', 'sharpening': 'sharpen',
    'logout': 'quit', 'exit': 'quit',
}

# Syntax and help use one command index. These are implemented commands, not a
# list of aspirational features. Dynamic skills and emotes are added at runtime.
COMMANDS = {
    'help': ('help', 'HELP [topic | skill | command | emote]', 'HELP FIREBALL'),
    'syntax': ('help', 'SYNTAX <command | skill | emote>', 'SYNTAX CAST'),
    'north': ('movement', 'NORTH (N)', 'N'),
    'south': ('movement', 'SOUTH (S)', 'S'),
    'east': ('movement', 'EAST (E)', 'E'),
    'west': ('movement', 'WEST (W)', 'W'),
    'up': ('movement', 'UP (U)', 'U'),
    'down': ('movement', 'DOWN (D)', 'D'),
    'go': ('movement', 'GO <direction> (also MOVE <direction>)', 'GO NORTH'),
    'move': ('movement', 'MOVE <direction>', 'MOVE N'),
    'show': ('map', 'SHOW MAP', 'SHOW MAP'),
    'display': ('map', 'DISPLAY MAP', 'DISPLAY MAP'),
    'look': ('exploration', 'LOOK [MAP | SELF | direction [distance] | object | item | creature | BODY [number]]', 'LOOK NORTH 2'),
    'attack': ('combat', 'ATTACK [creature name | description | ID]', 'ATTACK BEETLE'),
    'target': ('combat', 'TARGET <creature name | description | ID>', 'TARGET SCARRED COPPER BEETLE'),
    'flee': ('combat', 'FLEE', 'FLEE'),
    'skills': ('skills', 'SKILLS', 'HELP FIREBALL'),
    'learn': ('learning', 'LEARN [ability name | ID]', 'LEARN KICK'),
    'cast': ('skills', 'CAST <skill name | ID> [target]', 'CAST FIREBALL BEETLE'),
    'mana': ('mana', 'MANA', 'MANA'),
    'inventory': ('inventory', 'INVENTORY (I, INV)', 'I'),
    'equipment': ('equipment', 'EQUIPMENT (EQ, LOOK SELF)', 'LOOK SELF'),
    'equip': ('equipment', 'EQUIP <item> [LEFT | RIGHT]', 'EQUIP IRON SWORD'),
    'unequip': ('equipment', 'UNEQUIP <slot>', 'UNEQUIP LEFT'),
    'hold': ('equipment', 'HOLD <armor or weapon> [LEFT | RIGHT]', 'HOLD LEATHER VEST'),
    'weight': ('inventory', 'WEIGHT (CAPACITY)', 'WEIGHT'),
    'get': ('inventory', 'GET <item or unconscious creature>\nGET <item> FROM CHEST <number>\nGET <item | ALL | GOLD> FROM BODY [number]', 'GET ALL FROM BODY'),
    'drop': ('inventory', 'DROP <item>', 'DROP SCRAP'),
    'put': ('storage', 'PUT <item> IN CHEST <number>\nPUT <captured creature> IN CAGE <number>', 'PUT POTION IN CHEST 1'),
    'unlock': ('storage', 'UNLOCK <container>', 'UNLOCK OLD CRYPT BOX'),
    'release': ('capture', 'RELEASE CAGE <number>', 'RELEASE CAGE 1'),
    'buy': ('shops', 'BUY [item]', 'BUY POTION'),
    'sell': ('shops', 'SELL <item>\nSELL [CAGE <number>] at a creature buyer', 'SELL SCRAP'),
    'repair': ('crafting', 'REPAIR [item]', 'REPAIR IRON SWORD'),
    'use': ('items', 'USE <item>', 'USE RECALL SCROLL'),
    'quaff': ('items', 'QUAFF <consumable>', 'QUAFF POTION'),
    'eat': ('cooking', 'EAT <food>', 'EAT ROAST VENISON'),
    'rest': ('rest', 'REST', 'REST'),
    'recall': ('recall', 'RECALL (or USE RECALL SCROLL)', 'RECALL'),
    'harvest': ('cooking', 'HARVEST <remains name | ID>', 'HARVEST BEETLE'),
    'cook': ('cooking', 'COOK <recipe name | ingredient>', 'COOK BEETLE MEAT'),
    'sharpen': ('crafting', 'SHARPEN [right-hand weapon]', 'SHARPEN'),
    'enchant': ('crafting', 'ENCHANT <held weapon or worn/held armor>', 'ENCHANT RIGHT'),
    'balance': ('bank', 'BALANCE (at a bank)', 'BALANCE'),
    'deposit': ('bank', 'DEPOSIT <amount | ALL>', 'DEPOSIT 20'),
    'withdraw': ('bank', 'WITHDRAW <amount | ALL>', 'WITHDRAW 20'),
    'loot': ('death', 'LOOT [BODY [number]]', 'LOOT BODY'),
    'talk': ('talk', 'TALK [TO] <NPC or creature> [ABOUT <phrase>]', 'TALK TAMSIN ABOUT COOKING'),
    'ask': ('talk', 'ASK <NPC or creature> ABOUT <phrase>', 'ASK TAMSIN ABOUT COOKING'),
    'say': ('talk', 'SAY <phrase> TO <NPC | creature | CAGE number>', 'SAY HELLO TO TAMSIN'),
    'tell': ('talk', 'TELL <full player or NPC name> <message>', 'TELL ANTHONY Hi!'),
    'who': ('talk', 'WHO', 'WHO'),
    'emotes': ('emotes', 'EMOTES', 'HELP EMOTES'),
    'emote': ('emotes', 'EMOTE <emote name or command> [target]', 'EMOTE WAVE TAMSIN'),
    'me': ('emotes', 'ME <your character\'s action>', 'ME brushes dust from a weathered coat.'),
    'save': ('saving', 'SAVE', 'SAVE'),
    'quit': ('saving', 'QUIT (also LOGOUT or EXIT)', 'QUIT'),
}

TOPICS = ('help', 'movement', 'exploration', 'map', 'combat', 'capture', 'skills',
          'learning', 'mana', 'inventory', 'equipment', 'storage', 'shops',
          'items', 'rest', 'recall', 'crafting', 'cooking', 'bank', 'death',
          'talk', 'emotes', 'saving')
TOPIC_ALIASES = {
    'start': 'help', 'getting started': 'help', 'navigation': 'movement',
    'show map': 'map', 'display map': 'map', 'look map': 'map',
    'explore': 'exploration', 'fight': 'combat', 'fighting': 'combat',
    'capturing': 'capture', 'cage': 'capture', 'cages': 'capture',
    'spells': 'skills', 'progression': 'learning', 'leveling': 'learning',
    'bag': 'inventory', 'chest': 'storage', 'chests': 'storage',
    'shop': 'shops', 'store': 'shops', 'trading': 'shops',
    'potion': 'items', 'potions': 'items', 'food': 'cooking',
    'banking': 'bank', 'body': 'death', 'corpse': 'death',
    'dialogue': 'talk', 'conversation': 'talk', 'npc': 'talk',
    'emote': 'emotes', 'social': 'emotes', 'socials': 'emotes',
    'logout': 'saving', 'quit': 'saving', 'exit': 'saving',
}


def normalized(value):
    return ' '.join(value.casefold().split())


def reserved_words(world):
    words = set(COMMANDS) | set(ALIASES) | set(TOPICS) | set(TOPIC_ALIASES)
    for sid, skill in world['skills'].items():
        words.update((normalized(sid), normalized(skill['name'])))
    return words


def validate_emotes(world):
    records = world.get('emotes', {})
    if not isinstance(records, dict) or len(records) > 100:
        raise ValueError('Emotes must be a collection of at most 100 entries.')
    reserved, claimed = reserved_words(world), set()
    for ident, row in records.items():
        if not isinstance(ident, str) or not ident or not isinstance(row, dict):
            raise ValueError('Each emote needs an ID and a record.')
        name = row.get('name')
        if not isinstance(name, str) or not 1 <= len(name.strip()) <= 120:
            raise ValueError('Each emote needs a display name of 1–120 characters.')
        if type(row.get('enabled', True)) is not bool:
            raise ValueError(name + ': Enabled must be true or false.')
        description = row.get('description', '')
        if not isinstance(description, str) or len(description) > 600:
            raise ValueError(name + ': description must be at most 600 characters.')
        aliases = row.get('aliases', [])
        if not isinstance(aliases, list) or len(aliases) > 10:
            raise ValueError(name + ': use at most 10 aliases.')
        commands = [row.get('command')] + aliases
        for word in commands:
            if not isinstance(word, str) or not re.fullmatch(r'[a-z][a-z0-9_]{0,39}', word):
                raise ValueError(name + ': commands and aliases must be one lowercase word (letters, numbers or underscores; up to 40 characters).')
        # Names work after EMOTE and HELP, too. They must remain unambiguous.
        keys = set(commands) | {normalized(name)}
        if len(commands) != len(set(commands)) or keys & claimed:
            raise ValueError(name + ': emote names, commands and aliases must be unique.')
        if keys & reserved:
            raise ValueError(name + ': an emote cannot reuse a game command, help topic or skill name.')
        claimed.update(keys)
        for field in ('message', 'target_message'):
            message = row.get(field, '')
            if not isinstance(message, str) or len(message) > 600 or (field == 'message' and not message.strip()):
                raise ValueError(name + ': supply a message of 1–600 characters; the targeted message may be blank.')
            stripped = message.replace('{actor}', '').replace('{target}', '')
            if '{' in stripped or '}' in stripped or (field == 'message' and '{target}' in message):
                raise ValueError(name + ': use only {actor}, and {target} in the targeted message.')
    return world


class PlayerHelp:
    def active_emotes(self):
        return [row for row in self.w.get('emotes', {}).values() if row.get('enabled', True)]

    def emote_names(self, row):
        return [row['command'], normalized(row['name']), *row.get('aliases', [])]

    def skill_names(self):
        return {normalized(alias) for sid, row in self.w['skills'].items()
                for alias in (sid, row['name'])}

    def match_skill(self, name):
        try:
            return super().match_skill(name)
        except ValueError as error:
            if not name.strip(): raise
            # Suggestions are advice only: never cast or spend learning points
            # based on a fuzzy match. The existing parser resolves real matches.
            raise ValueError(str(error) + self.suggestion(normalized(name), self.skill_names())) from None

    def normalize_command(self, raw):
        verb, _, target = raw.partition(' ')
        verb = ALIASES.get(verb.casefold(), verb.casefold())
        if verb in ('me', 'say', 'tell') and (verb == 'me' or getattr(self, 'multiplayer', False)):
            return verb, target  # Keep the player's capitalization in free-form actions.
        target = target.casefold()
        if verb == 'look' and target == 'map':
            return 'show', 'map'
        if verb in ('go', 'move') and ALIASES.get(target, target) in ('north', 'south', 'east', 'west', 'up', 'down'):
            return ALIASES.get(target, target), ''
        # Owner-created skills also work by their full name or ID. Core commands
        # have precedence, so adding a skill can never replace LOOK or SELL.
        if verb not in COMMANDS:
            text = normalized(raw)
            names = self.skill_names()
            matches = [n for n in names if text == n or text.startswith(n + ' ')]
            if matches:
                return 'cast', text
        return verb, target

    def suggestion(self, value, choices):
        matches = difflib.get_close_matches(value, sorted(set(choices)), n=3, cutoff=.65)
        return ' Did you mean ' + ', '.join(m.upper() for m in matches) + '?' if matches else ''

    def unknown_command(self, verb):
        choices = set(COMMANDS) | set(ALIASES) | set(self.skill_names())
        choices.update(n for row in self.active_emotes() for n in self.emote_names(row))
        return f'Unknown command "{verb.upper()}".' + self.suggestion(verb, choices) + ' Use HELP for topics or SYNTAX <command>.'

    def command_error(self, verb, message):
        # Keep gameplay rejections brief. Add a format hint to parsing/selection
        # mistakes; do not replace the specific original error.
        parsing = ('Specify ', 'Use ', 'Include ', 'That item is not available',
                   'You do not see', 'Be more specific', 'Unknown equipment')
        if verb in COMMANDS and message.startswith(parsing) and 'SYNTAX ' not in message:
            return message + f' See SYNTAX {verb.upper()} or HELP {COMMANDS[verb][0].upper()}.'
        return message

    def guide_command(self, verb, target):
        if verb == 'quit':
            if target: raise ValueError('Use QUIT by itself to save and leave the game.')
            if self.p.get('combat'): raise ValueError('Finish combat or FLEE before quitting. SAVE still works during combat.')
            self.log('Progress saved. Leaving the game.', 'notice')
            return True
        if verb in ('show', 'display'):
            if target != 'map': raise ValueError('Use SHOW MAP or DISPLAY MAP to open your explored map.')
            self.remember_room()
            self.log('Explored map opened. Only visited rooms are charted; enemies are never shown. Close the map or press Escape to return to play.')
            return True
        if verb == 'help':
            self.show_help(target); return True
        if verb == 'syntax':
            self.show_syntax(target); return True
        if verb in ('go', 'move'):
            raise ValueError('Use GO <direction>: north, south, east, west, up or down. Example: GO N.')
        if verb in ('talk', 'ask'):
            self.converse(target, ask=verb == 'ask'); return True
        if verb == 'emotes':
            self.show_help('emotes'); return True
        if verb == 'me':
            if not target: raise ValueError('Use ME <action>. Example: ME brushes dust from a weathered coat.')
            self.log(self.p['name'] + ' ' + target, 'emote'); return True
        if verb == 'emote':
            if not target:
                self.show_help('emotes'); return True
            entries = [(name, row) for row in self.active_emotes() for name in self.emote_names(row)]
            for name, row in sorted(entries, key=lambda pair: len(pair[0]), reverse=True):
                if target == name or target.startswith(name + ' '):
                    self.perform_emote(row, target[len(name):].strip()); return True
            names = [n for row in self.active_emotes() for n in self.emote_names(row)]
            raise ValueError('Unknown emote.' + self.suggestion(target.split()[0], names) + ' Use EMOTES to list them, or ME <action> for your own text.')
        for row in self.active_emotes():
            if verb in [row['command'], *row.get('aliases', [])]:
                self.perform_emote(row, target); return True
        return False

    def converse(self, text, ask=False):
        text = text.removeprefix('to ')
        who, separator, phrase = text.partition(' about ')
        if not who or (ask and not separator) or (separator and not phrase) or text.endswith(' about'):
            raise ValueError('Use TALK <person> or ASK <person> ABOUT <phrase>. Example: TALK TAMSIN ABOUT COOKING.')
        if not self.visible(): raise ValueError('You cannot see who is here.')
        # Resolve NPC names without exposing their private dialogue triggers.
        people = [(nid, n) for nid, n in self.w.get('npcs', {}).items() if n['room'] == self.p['room']]
        exact = [(nid, n) for nid, n in people if who in (nid.casefold(), normalized(n['name']))]
        matches = exact or [(nid, n) for nid, n in people if who in normalized(n['name'])]
        if len(matches) > 1: raise ValueError('Be more specific: ' + ', '.join(n['name'] for _, n in matches) + '.')
        if matches: who = matches[0][0]
        try:
            self.talk((phrase if separator else 'hello') + ' to ' + who)
        except ValueError as error:
            hint = self.suggestion(who, [normalized(n['name']) for _, n in people]) if not matches else ''
            raise ValueError(str(error) + hint) from None

    def perform_emote(self, row, target):
        message = row['message']
        name = ''
        if target:
            if not row.get('target_message', '').strip():
                raise ValueError(row['name'] + ' does not take a target. Use ' + row['command'].upper() + '.')
            if target in ('self', 'me', normalized(self.p['name'])):
                name = self.p['name']
            else:
                if not self.visible(): raise ValueError('It is too dark to see an emote target.')
                choices = [(nid.casefold(), n['name']) for nid, n in self.w.get('npcs', {}).items() if n['room'] == self.p['room']]
                choices += [(e['uid'].casefold(), self.creature_name(e)) for e in self.creatures()]
                exact = [(ident, label) for ident, label in choices if target in (ident, normalized(label))]
                matches = exact or [(ident, label) for ident, label in choices if target in normalized(label)]
                if not matches:
                    raise ValueError('You do not see that emote target here.' + self.suggestion(target, [normalized(label) for _, label in choices]))
                if len(matches) != 1: raise ValueError('Be more specific: ' + ', '.join(label for _, label in matches) + '.')
                name = matches[0][1]
            message = row['target_message']
        # Only literal placeholders are supported. This is narrative, never code.
        message = re.sub(r'\{(actor|target)\}', lambda m: self.p['name'] if m[1] == 'actor' else name, message)
        self.log(message, 'emote')

    def help_match(self, query):
        query = normalized(query)
        if query in self.skill_names(): return 'skill', self.match_skill(query)
        for row in self.active_emotes():
            if query in self.emote_names(row): return 'emote', row
        query = TOPIC_ALIASES.get(query, ALIASES.get(query, query))
        if query in TOPICS: return 'topic', query
        if query in COMMANDS: return 'command', query
        return None, query

    def show_syntax(self, query):
        if not query:
            self.log('SYNTAX <command> shows its format and an example.\nTry SYNTAX CAST, SYNTAX TALK, SYNTAX GET, or SYNTAX WAVE.\n<angle brackets> are required; [square brackets] are optional; | means a choice. Do not type the brackets.'); return
        kind, value = self.help_match(query)
        if kind == 'skill':
            self.log(self.skill_syntax(value) + '\nDetails: HELP ' + value.upper()); return
        if kind == 'emote':
            self.log(self.emote_syntax(value) + '\nDetails: HELP ' + value['command'].upper()); return
        canonical = ALIASES.get(normalized(query), normalized(query))
        if canonical in COMMANDS:
            topic, usage, example = COMMANDS[canonical]
            aliases = [a.upper() for a, command in ALIASES.items() if command == canonical]
            self.log(usage + '\nExample: ' + example + ('\nAliases: ' + ', '.join(aliases) if aliases else '') + '\nDetails: HELP ' + topic.upper()); return
        if kind == 'topic':
            rows = [usage for topic, usage, _ in COMMANDS.values() if topic == value]
            if value == 'capture': rows += ['CAST KNOCKOUT <creature>', 'GET <unconscious creature>', 'PUT <creature> IN CAGE <number>']
            self.log('Syntax — ' + value.upper() + '\n' + '\n'.join(dict.fromkeys(rows)) + '\nDetails: HELP ' + value.upper()); return
        self.unknown_help(query)

    def unknown_help(self, query):
        choices = set(TOPICS) | set(COMMANDS) | set(self.skill_names())
        choices.update(n for row in self.active_emotes() for n in self.emote_names(row))
        self.log('No help found for "' + query + '".' + self.suggestion(normalized(query), choices) + ' Use HELP for topics.', 'notice')

    def skill_syntax(self, sid):
        skill = self.w['skills'][sid]
        if skill.get('passive') and self.rules()['learning_enabled']: return 'ATTACK [creature] — ' + skill['name'] + ' is passive; it cannot be cast.'
        effect = skill.get('effect', 'damage')
        suffix = ' <item>' if effect == 'enchant' else ' [right-hand weapon]' if effect == 'sharpen' else '' if effect in ('heal', 'ward') else ' [creature]'
        text = 'CAST ' + skill['name'].upper() + suffix
        if normalized(skill['name']) != normalized(sid): text += '\nAlso: CAST ' + sid.upper() + suffix
        return text

    def skill_help(self, sid):
        skill, rules = self.w['skills'][sid], self.rules()
        rank, cap = self.ability_rank(sid), skill.get('max_rank', 5)
        eligible = self.skill_eligible(sid)
        available = eligible and (rank > 0 if rules['learning_enabled'] else self.p['level'] >= skill.get('unlock_level', 1))
        rows = [skill['name'].upper(), self.skill_syntax(sid)]
        rows.append('Available now.' if available else 'Unavailable to your class or race.' if not eligible else 'Not learned yet.' if rules['learning_enabled'] else 'Locked by character level.')
        if rules['learning_enabled']:
            rows.append(f'Learned rank: {rank}/{cap}. Points available: {self.ability_points()}.')
        rows += self.skill_facts(sid)['lines'] + self.skill_recovery_lines(sid)
        progress = self.spell_progress(sid)
        if progress:
            xp = 'maximum level' if progress['next_xp'] is None else f'{progress["level_xp"]:g}/{progress["next_xp"]:g} XP toward next level'
            rows.append(f'Spell mastery: {progress["level"]}/{progress["max_level"]}; {xp}. Valid uses train it; suitable challenges give extra practice.')
        if skill.get('effect') == 'enchant':
            progress = self.enchant_progress(sid)
            xp = 'maximum level' if progress['next_xp'] is None else f'{progress["level_xp"]:g}/{progress["next_xp"]:g} XP toward next level'
            rows.append(f'Crafting mastery: {progress["level"]}/{progress["max_level"]}; {xp}. Practice improves success, bonus and duration.')
        preview = self.next_skill_rank(sid)
        if preview:
            rows.append(f'Next rank: {preview["rank"]}; {preview["cost"]} point(s), character level {preview["required_level"]}.')
            rows += preview['lines']
            rows.append(f'LEARN {sid.upper()} to buy this rank.')
        elif rules['learning_enabled'] and eligible:
            rows.append('Maximum learned rank reached.')
        self.log('\n'.join(rows))

    def emote_syntax(self, row):
        suffix = ' [target]' if row.get('target_message', '').strip() else ''
        aliases = ', '.join(a.upper() for a in row.get('aliases', []))
        return row['command'].upper() + suffix + '\nEMOTE ' + row['command'].upper() + suffix + ('\nAliases: ' + aliases if aliases else '')

    def show_help(self, query=''):
        if not query: query = 'help'
        kind, topic = self.help_match(query)
        if kind == 'skill': self.skill_help(topic); return
        if kind == 'emote':
            self.log(topic['name'].upper() + '\n' + topic.get('description', '') + '\n' + self.emote_syntax(topic) + '\nCosmetic only; does not trigger dialogue, combat or rewards.'); return
        prefix = ''
        if kind == 'command':
            topic, usage, example = COMMANDS[topic]
            prefix = usage + '\nExample: ' + example + '\n\n'
        elif kind != 'topic': self.unknown_help(query); return
        r = self.rules()
        text = {
            'help': 'HELP — choose a topic\nGetting around: HELP MOVEMENT · HELP EXPLORATION\nFighting: HELP COMBAT · HELP CAPTURE · HELP DEATH\nYour character: HELP SKILLS · HELP LEARNING · HELP MANA\nBelongings: HELP INVENTORY · HELP EQUIPMENT · HELP STORAGE\nTown & supplies: HELP SHOPS · HELP BANK · HELP ITEMS · HELP REST · HELP RECALL\nMaking things: HELP CRAFTING · HELP COOKING\nConversation: HELP TALK · HELP EMOTES\nLeaving & progress: HELP SAVING\nDetails: HELP <skill or command>, such as HELP FIREBALL. Formats: SYNTAX <command>.',
            'map': 'LOOK MAP, SHOW MAP or DISPLAY MAP opens your exploration map in a pop-up. It stays closed until you ask for it.\nOnly rooms you have entered and connections between those rooms appear. Enemy locations, NPCs, loot and hidden discoveries are never shown. Looking into the distance does not chart a room.\nYour current room is highlighted. Choose a visited elevation, zoom, or center on yourself. Click a room to read its known connections; this does not move you. Close or press Escape to return to the command box. Combat continues while the map is open.\nExploration saves with your character and survives death. Older saves start mapping from their current room; past travel cannot be reconstructed. Rooms entered in darkness remain unnamed until you see them.',
            'movement': 'MOVE: N, S, E, W, UP, DOWN (or GO NORTH / MOVE N).\nLOOK shows the room and its exits; LOOK NORTH scouts an exit.\nMovement is blocked during combat; use FLEE. HELP EXPLORATION explains visibility.',
            'exploration': f'LOOK [object | item | creature] examines something. LOOK SELF shows equipment.\nLOOK NORTH 2 scouts farther along a straight route, up to {r["perception_distance"]} rooms. Darkness, terrain and fog may block the view. Carry a lantern for dark rooms.\nRoom descriptions and inspectable objects contain clues. Discoveries may require a defeat, an inspection or a key; help does not reveal puzzle answers.',
            'combat': f'ATTACK [creature] starts automatic attacks. KILL is an alias.\nShared pulses occur every {self.w["settings"]["attack_interval"]:g}s; a basic attack recovers for {2 * self.w["settings"]["attack_interval"]:g}s, longer when slowed.\nCAST <skill> [creature] uses an ability. HELP <skill> shows its requirements. Manual combat skills share {r["action_recovery"]:g}s recovery; each also has its own cooldown.\nTARGET <description> changes opponents; targeting another creature during combat engages it. Aggressive creatures in the room join the fight.\nGeneric creature names retain a matching current target or choose a matching creature of the same type. Different matching types need clarification.\nQUAFF POTION heals, with {r["potion_recovery"]:g}s recovery between potions. FLEE attempts escape through a random exit.\nCombat continues while the server runs, even with the browser closed. HELP DEATH · HELP SAVING.',
            'capture': 'LEARN KNOCKOUT when eligible, then HELP KNOCKOUT for your chance and requirements.\n1. Weaken a capturable creature to its capture-health threshold. KNOCKOUT explains the threshold if it is too healthy.\n2. CAST KNOCKOUT <creature>. Capture resistance reduces success. Failed attempts can start combat.\n3. After success, finish any other opponents, then GET <unconscious creature>.\n4. PUT <creature> IN CAGE <number>. LOOK CAGE <number> inspects it. Cages retain their creature capacity; your bag has no carrying limit.\nSELL CAGE <number> at a creature buyer sells the cage and every occupant. RELEASE CAGE <number> frees them.\nCapturing gives no kill XP, kill gold or rare equipment; released creatures give no kill rewards. Automatic attacks can kill a weakened creature before you capture it.',
            'skills': 'SKILLS lists your learned abilities. LEARN lists choices and their costs.\nHELP <skill name or ID> shows current power, mana, cooldown, targets and learning requirements—even for locked skills. Example: HELP FIREBALL.\nCAST <skill> [target] uses an active ability; passive abilities modify automatic attacks. Full skill names and IDs also work directly.\nCharacter level, learned rank, spell mastery and mana mastery are separate. HELP LEARNING · HELP MANA.',
            'learning': ('Ability selection is enabled. Earn ' + self.learning_schedule() if r['learning_enabled'] else 'Ability selection is disabled; eligible skills unlock at their character level.') + '\nLEARN lists abilities; LEARN <ability> spends points to learn it or improve its rank. Finish combat first.\nHELP <ability> shows the next rank\'s level requirement, cost and your available points. Spell mastery grows separately through valid practice.\nThere is currently no refund command; inspect the ability before spending points.',
            'mana': f'MANA shows your current reserve and mastery. Spells spend the class-adjusted amount shown in HELP <spell>.\nBase recovery is {r["mana_regen"]:g}/second outside combat and {r["mana_combat_regen"]:g}/second in combat, multiplied by your class recovery rate. REST at an inn refills health and mana.\nValid paid casts train mana mastery. Races that cannot use magic have no mana reserve.' + ('\nMana costs are currently disabled by the owner.' if not r['mana_enabled'] else ''),
            'inventory': 'INVENTORY (I / INV) lists your bag. Your bag has no item limit, and items have no carrying weight.\nGET <item> picks it up; DROP <item> leaves it here. Trading and rearranging items require finishing combat.\nDropped ordinary items disappear after 10 minutes. Keys, cages and chests are exempt. There is no undo for dropping or selling.\nPUT <item> IN CHEST <number> stores it. HELP STORAGE · HELP EQUIPMENT.',
            'equipment': f'EQUIPMENT, EQ or LOOK SELF shows every slot. EQUIP <item> wears armor in its slot or holds a weapon.\nEQUIP <weapon> LEFT / RIGHT chooses a hand. HOLD <armor> holds it in the left hand for enchanting; held ordinary armor is not worn protection.\nUNEQUIP <slot> returns gear to your bag. Slots: RIGHT, LEFT, HELMET, CHEST, PANTS, ARMS.\nTwo-handed weapons need both hands. Eligible classes can dual wield from level {r["dual_level"]}; a shield uses a hand.\nLOOK <item> shows its details. Worn armor and held shields add protection. Finish combat before changing equipment; removing gear needs bag space.',
            'storage': 'LOOK CHEST <number> shows its contents.\nPUT <item> IN CHEST <number> stores an item; GET <item> FROM CHEST <number> retrieves one. The chest must be carried or visible here.\nChests retain their own item capacity. Occupied chests cannot be sold, and chests cannot nest inside chests.\nUNLOCK <container> uses its matching key. Keys can be consumed by the lock. HELP CAPTURE for creature cages.',
            'shops': 'At a shop, BUY lists stock; BUY <item> purchases one; SELL <item> sells one for half its shop price, rounded down. LOOK <item> inspects it first.\nUse one item per command; quantity purchases and buyback are not implemented. Finish combat before trading. You must have enough gold for purchases.\nKeys, loose captives and occupied containers cannot be sold at ordinary shops. Rare drop-only equipment cannot be bought.\nAt a creature buyer, SELL lists occupied-cage offers. SELL CAGE <number> sells all occupants and the cage. HELP BANK.',
            'items': f'QUAFF POTION (or DRINK POTION) restores health. Healing potion recovery: {r["potion_recovery"]:g}s. Full health does not consume one.\nUSE <item> uses a compatible consumable; lanterns work simply by carrying them.\nEAT <food> eats a meal; HELP COOKING. RECALL uses a recall scroll; HELP RECALL. Race restrictions still apply to magical items.',
            'rest': 'REST at a rest location, such as The Quiet Coil, restores health and mana without a fee. It cannot be used during combat.\nUse HELP ITEMS for potions or HELP COOKING for food away from the inn.',
            'recall': f'RECALL or USE RECALL SCROLL returns you to the starting room. Carry a recall scroll.\nReusable below level {r["recall_reusable_below_level"]}; single-use from there until level {r["recall_disabled_from_level"]}. At level {r["recall_disabled_from_level"]} and above it cannot be used.\nCombat and recall-blocked rooms prevent recall. A blocked single-use attempt ' + ('consumes its scroll.' if r['recall_failure_consumes'] else 'preserves its scroll.') + '\nReusable scrolls and attempts above the level limit preserve the scroll. Race magic restrictions and the race\'s recall exception still apply.',
            'crafting': 'SHARPEN [weapon] temporarily improves your right-hand weapon outside combat; learn Sharpening first.\nENCHANT <item> temporarily enchants a held weapon or worn/held armor; learn Enchanting first. HOLD <armor> places it in your left hand.\nHELP SHARPENING and HELP ENCHANTING show current requirements, bonuses, costs and risks. Enchanting can damage or destroy weapons.\nREPAIR lists damaged equipment and prices at a repair service; REPAIR <item> repairs it. Individual magical-item mastery is separate from temporary enchantments. HELP COOKING.',
            'cooking': f'HARVEST <remains> collects configured ingredients after combat; not every creature yields food. Remains last {r["corpse_seconds"]:g}s.\nCOOK <recipe or ingredient> uses ingredients and any required fire, tool or skill. COOK by itself lists recipe names.\nEAT <food> restores some health, with {r["food_cooldown"]:g}s between meals. Eating in combat is ' + ('allowed.' if r['food_in_combat'] else 'blocked.') + '\nA full-health attempt preserves food. The inn has a cooking fire.',
            'bank': 'At a bank: BALANCE shows your account; DEPOSIT <amount or ALL> moves carried gold into it; WITHDRAW <amount or ALL> returns gold to your purse.\nExample: DEPOSIT 20. Use positive whole amounts. Finish combat first.\nBanked gold belongs to your character and survives death. Carried gold remains at risk. Banking does not store equipment.',
            'death': (f'Death leaves all carried gold, inventory and worn gear in your body for {r["player_body_seconds"] / 60:g} real minutes, including time with the game closed. Banked gold stays safe.\nReturn and LOOK BODY, then GET ALL FROM BODY or LOOT BODY. GET GOLD FROM BODY or GET <item> FROM BODY recovers specific contents.\nUse BODY <number> if several remain. Recovered equipment goes into the bag and must be equipped again. Anything left when the body expires is lost.' if r['player_bodies'] else f'Recoverable bodies are disabled. Death loses {self.w["settings"]["gold_loss"] * 100:g}% of carried gold and has a {self.w["settings"]["item_loss_chance"] * 100:g}% chance to lose an unprotected bag item. You return to the starting room.'),
            'talk': 'TALK TAMSIN or TALK TO TAMSIN says hello.\nTALK TAMSIN ABOUT COOKING and ASK TAMSIN ABOUT COOKING say "cooking" to her.\nSAY <phrase> TO <NPC | creature | CAGE number> still works. Example: SAY HELLO TO TAMSIN.\nConversation phrases ignore capitalization and repeated spaces but otherwise need the complete phrase. Hidden creature phrases are not revealed in help.\nEmotes are separate cosmetic actions; HELP EMOTES.',
            'saving': 'Progress saves automatically after commands and world updates. SAVE saves immediately and keeps you playing.\nQUIT (also LOGOUT or EXIT) saves and leaves the game. Finish combat or FLEE first. In multiplayer, your character stays out of play until you choose it again; your location and belongings are preserved.\nIf you are the host and no other players are online, QUIT also stops the server and closes the Windows launcher. Otherwise the shared game keeps running. Wait for the saved message; you can then close the browser tab.\nClosing the browser without QUIT leaves your character in the running world, including combat. Ctrl+C remains a fallback for stopping the server. Body deadlines still pass while you are away. HELP DEATH.',
        }
        if topic == 'emotes':
            rows = ['EMOTES — cosmetic expressions', 'Use a command directly, such as WAVE TAMSIN, or EMOTE WAVE TAMSIN.',
                    'ME <action> writes a custom action with your character\'s name. Emotes do not trigger NPC dialogue, deal damage, spend resources or grant rewards.']
            rows += [row['command'].upper() + (' [target]' if row.get('target_message', '').strip() else '') + ' — ' + row.get('description', row['name']) for row in sorted(self.active_emotes(), key=lambda row: row['name'].casefold())]
            if not self.active_emotes(): rows.append('No preset emotes are enabled in this world. ME <action> still works.')
            rows.append('HELP <emote> or SYNTAX <emote> shows details. Targets must be visible here, or SELF.')
            self.log(prefix + '\n'.join(rows)); return
        self.log(prefix + text[topic])
