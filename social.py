"""Room speech and private messages; audiences are resolved on the server."""
import re


class Social:
    def social_players(self):
        return [self.p] if self.p else []

    def deliver_message(self, player_id, text, kind):
        if self.p and self.p['id'] == player_id:
            self.log(text, kind)

    def room_message(self, text, kind='say'):
        for player in self.social_players():
            if player['room'] == self.p['room']:
                self.deliver_message(player['id'], text, kind)

    def npc_reply(self, npc, phrase, fallback=True):
        if 'talk' not in npc.get('interactions', ['look', 'talk']):
            raise ValueError('They are not available to talk.')
        phrase = ' '.join(phrase.strip('"').casefold().split())
        dialogue = npc.get('dialogue', [])
        rule = next((r for r in dialogue if ' '.join(r['phrase'].casefold().split()) == phrase), None)
        if not rule and phrase in ('hi', 'hey'):
            rule = next((r for r in dialogue if r['phrase'].casefold() == 'hello'), None)
        return rule['response'] if rule else (npc.get('default_response') or npc['name']+' gives no reply.') if fallback else None

    def message_recipient(self, text):
        """Match a complete name/ID before the message, including multiword names."""
        kind = None
        for prefix in ('player ', 'npc '):
            if text.casefold().startswith(prefix):
                kind, text = prefix.strip(), text[len(prefix):]
                break
        choices = []
        if kind != 'npc':
            choices += [('player', p, [p['name']]) for p in self.social_players()]
        if kind != 'player':
            choices += [('npc', n, [nid, n['name']]) for nid, n in self.w.get('npcs', {}).items() if n['room'] == self.p['room']]
        quoted = re.match(r'^"([^"]+)"\s+(.+)$', text)
        matches = []
        for category, person, names in choices:
            for name in set(names):
                if quoted:
                    if quoted[1].casefold() == name.casefold():
                        matches.append((len(name), category, person, quoted[2]))
                elif text.casefold().startswith(name.casefold()+' ') and text[len(name):].strip():
                    matches.append((len(name), category, person, text[len(name):].strip()))
        if not matches:
            raise ValueError('Use TELL <full player or NPC name> <message>. The player must be online; NPCs must be in your room.')
        longest = max(m[0] for m in matches)
        matches = [m for m in matches if m[0] == longest]
        # An NPC ID and its identical display name refer to the same recipient.
        unique = {(m[1], id(m[2])): m for m in matches}
        if len(unique) != 1:
            raise ValueError('That name matches a player and an NPC. Use TELL PLAYER <name> <message> or TELL NPC <name> <message>.')
        _, category, person, message = next(iter(unique.values()))
        return category, person, message

    def say(self, message):
        if not message:
            raise ValueError('Use SAY <message>. Example: SAY Hello everyone!')
        # Retain authored SAY <phrase> TO <creature/cage/NPC> conversations.
        addressed = re.match(r'^(.*?)\s+to\s+(.+)$', message, re.IGNORECASE)
        if addressed:
            phrase, who = addressed.groups()
            npcs = [n for nid, n in self.w.get('npcs', {}).items() if n['room'] == self.p['room'] and who.casefold() in (nid.casefold(), n['name'].casefold())]
            if npcs:
                reply = self.npc_reply(npcs[0], phrase)
                self.room_message(f'{self.p["name"]} says to {npcs[0]["name"]}: {phrase}')
                self.room_message(f'{npcs[0]["name"]} says: {reply}')
                return
            # Ordinary sentences containing "to" are speech unless the target is
            # an actual creature or cage. Never silently swallow the message.
            creatures = self.creatures(unconscious=True)
            creature = any(who.casefold() in (e['uid'], e['type'], self.creature_name(e).casefold()) for e in creatures)
            if creature or re.fullmatch(r'cage(?:[ -]\d+)?', who, re.IGNORECASE):
                self.talk(message.casefold())
                self.room_message(f'{self.p["name"]} says: {message}')
                return
        self.room_message(f'{self.p["name"]} says: {message}')
        for npc in self.w.get('npcs', {}).values():
            if npc['room'] == self.p['room'] and 'talk' in npc.get('interactions', ['look', 'talk']):
                reply = self.npc_reply(npc, message, fallback=False)
                if reply:
                    self.room_message(f'{npc["name"]} says: {reply}')

    def tell(self, text):
        category, person, message = self.message_recipient(text)
        if category == 'npc':
            reply = self.npc_reply(person, message)
            self.log(f'You tell {person["name"]}: {message}', 'tell')
            self.log(f'{person["name"]} tells you: {reply}', 'tell')
        else:
            self.log(f'You tell {person["name"]}: {message}', 'tell')
            if person['id'] != self.p['id']:
                self.deliver_message(person['id'], f'{self.p["name"]} tells you: {message}', 'tell')
