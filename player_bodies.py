"""Recoverable player belongings with a persistent, real-time decay deadline."""
import math
import re


class PlayerBodies:
    def init_player_bodies(self):
        self.state.setdefault('player_bodies', [])
        self.state.setdefault('body_sequence', 0)
        self.expire_player_bodies()

    def leave_player_body(self):
        self.state['body_sequence'] += 1
        number = self.state['body_sequence']
        body = dict(id=f'body-{number}', number=number, owner=self.p['id'],
                    name=f'{self.p["name"]}\'s body {number}', room=self.p['room'],
                    items=list(self.p['equipment'].values()) + self.p['inventory'][:],
                    gold=self.p['gold'], expires=self.clock()+self.rules()['player_body_seconds'])
        self.state['player_bodies'].append(body)
        self.p.update(inventory=[], equipment={}, gold=0, combat=None, effects=[],
                      room=self.w['starting']['room'], hp=self.max_hp(), mana=self.max_mana())
        self.p.pop('target', None)
        self.log(f'You die. Your belongings and gold remain in body {number} at {self.w["rooms"][body["room"]]["name"]}. '
                 f'Return within {self.rules()["player_body_seconds"]/60:g} minutes and GET ALL FROM BODY {number}.', 'danger')
        self.log('You blink awake from death feeling strange and disoriented.', 'story')
        self.look('')

    def expire_player_bodies(self):
        bodies = self.state.get('player_bodies', [])
        expired = [b for b in bodies if b['expires'] <= self.clock()]
        if not expired:
            return
        self.state['player_bodies'] = [b for b in bodies if b['expires'] > self.clock()]
        # Delete expired instances and nested contents, while preserving anything
        # already recovered or referenced elsewhere in an older save.
        def descendants(ids):
            result = set()
            pending = list(ids)
            while pending:
                iid = pending.pop()
                if iid in result:
                    continue
                result.add(iid)
                pending.extend(self.state['instances'].get(iid, {}).get('contents', []))
            return result
        kept = [i for p in self.all_players() for i in p['inventory'] + list(p['equipment'].values())]
        kept += [i for pile in self.state.get('ground', {}).values() for i in pile]
        kept += [i for body in self.state['player_bodies'] for i in body['items']]
        retained = descendants(kept)
        for body in expired:
            for iid in descendants(body['items']) - retained:
                self.state['instances'].pop(iid, None)
            self.player_event(body['owner'], f'Your old body {body["number"]} fades away. Anything left inside is gone.', 'notice')

    def bodies_here(self):
        return [b for b in self.state.get('player_bodies', [])
                if b['room'] == self.p['room'] and b['expires'] > self.clock()
                and (self.visible() or b['owner'] == self.p['id'])]

    def is_body_reference(self, target):
        return bool(re.fullmatch(r'(?:my )?(?:body|corpse)(?:[ -]\d+)?', target)
                    or any(target == b['name'].lower() for b in self.state.get('player_bodies', [])))

    def find_player_body(self, target):
        self.expire_player_bodies()
        rows = self.bodies_here()
        generic = target in ('body', 'corpse', 'my body', 'my corpse')
        found = [b for b in rows if (generic and b['owner'] == self.p['id'])
                 or target in (b['id'], f'body {b["number"]}', f'corpse {b["number"]}', b['name'].lower())]
        if not found:
            raise ValueError('That body is not here, or it has already faded away.')
        if len(found) > 1:
            raise ValueError('More than one body is here. Specify ' + ' or '.join(f'BODY {b["number"]}' for b in found) + '.')
        return found[0]

    def show_player_body(self, target):
        body = self.find_player_body(target)
        contents = '\n'.join(self.marked(i, body['items'].count(i)) for i in dict.fromkeys(body['items'])) or 'No items remain.'
        self.log(f'{body["name"]}\nDisappears in {math.ceil(body["expires"]-self.clock())} seconds.\n'
                 f'{contents}\nGold: {body["gold"]}.\nGET ALL FROM BODY {body["number"]}, or GET <item> FROM BODY {body["number"]}.')

    def loot_player_body(self, target, item_name='all'):
        body = self.find_player_body(target)
        if body['owner'] != self.p['id']:
            raise ValueError('You can only recover belongings from your own body.')
        items = body['items'][:]
        if item_name not in ('all', 'gold'):
            items = [self.match(item_name, items)]
        recovered = 0
        gold = body['gold'] if item_name in ('all', 'gold') else 0
        if gold:
            self.p['gold'] += gold
            body['gold'] = 0
        for iid in items if item_name != 'gold' else []:
            body['items'].remove(iid)
            self.p['inventory'].append(iid)
            recovered += 1
        self.log(f'Recovered {recovered} item(s) and {gold} gold from body {body["number"]}.')
        if body['items']:
            self.log('Items remain in your body. GET ALL FROM BODY '+str(body['number'])+'.')
        else:
            self.log('No items remain in the body.')

    def extra_command(self, verb, target):
        if verb == 'loot' and (not target or self.is_body_reference(target)):
            self.loot_player_body(target or 'body'); return True
        if verb == 'get' and ' from ' in target:
            item, source = target.rsplit(' from ', 1)
            if self.is_body_reference(source):
                self.loot_player_body(source, item); return True
        return super().extra_command(verb, target)

    def check_body_references(self, world):
        for body in self.state.get('player_bodies', []):
            if body['expires'] <= self.clock():
                continue
            if body['room'] not in world['rooms']:
                raise ValueError('Cannot remove a room containing a recoverable player body.')
            if any(i not in world['items'] and i not in self.state['instances'] for i in body['items']):
                raise ValueError('Cannot remove an item inside a recoverable player body.')
