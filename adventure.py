"""Persistent encounters, discoveries and individual portable cages for v0.2."""
import copy
import math
import re


def validate_adventure(w):
    def need(ok, message):
        if not ok: raise ValueError(message)
    def number(x, lo, hi, integer=False):
        return type(x) in (int, float) and math.isfinite(x) and lo <= x <= hi and (not integer or type(x) is int)
    def string(x, blank=False): return isinstance(x, str) and len(x) <= 6000 and (blank or bool(x.strip()))
    for iid, i in w['items'].items():
        need(not iid.startswith('@'), 'Item IDs beginning with @ are reserved for individual objects.')
        if i['kind'] == 'cage': need(number(i.get('capacity', 5), 1, 1000, True), 'Cage capacity must be a positive whole number.')
    for e in w['enemies'].values():
        for key in ('battle_cries', 'defeat_messages', 'captive_actions'):
            need(isinstance(e.get(key, []), list) and all(string(x) for x in e.get(key, [])), f'{key} must be a list of nonempty lines.')
        for key, default in [('battle_cry_chance', 0), ('capture_resistance', 0), ('capture_health', 35)]:
            need(number(e.get(key, default), 0, 100), f'{key} must be 0–100 percent.')
        need(type(e.get('capturable', False)) is bool, 'Capturable must be Yes or No.')
        need(string(e.get('captive_description', ''), True), 'Captive description must be text.')
    if 'knockout' in w['skills']:
        need(number(w['skills']['knockout'].get('chance', 70), 0, 100), 'Knockout chance must be 0–100 percent.')
    for rid, r in w['rooms'].items():
        encounter = r.get('encounter')
        if encounter is not None:
            need(isinstance(encounter, dict), 'Encounter must be an object.')
            need(encounter.get('enemy') in w['enemies'], 'Choose an encounter enemy.')
            need(number(encounter.get('chance'), 0, 100) and number(encounter.get('cooldown'), 1, 86400), 'Encounter chance must be 0–100 and cooldown 1–86400 seconds.')
            need(not r.get('safe') and not r.get('enemy'), 'A random encounter room cannot also be safe or have a resident enemy. Clear its resident enemy first.')
        discoveries=r.get('discoveries', [])
        need(isinstance(discoveries, list), 'Room discoveries must be a list.')
        ids=set()
        for d in discoveries:
            need(isinstance(d, dict), 'Discovery must be an object.')
            ident=d.get('id')
            need(string(ident) and ident not in ids, 'Each room discovery needs a unique ID.'); ids.add(ident)
            need(string(d.get('name')) and d.get('kind') in ('item', 'container'), 'Discovery needs a name and item/container type.')
            for k in ('description', 'message', 'open_message'): need(string(d.get(k, ''), True), f'Discovery {k} must be text.')
            trigger=d.get('trigger','visible')
            need(type(d.get('hide_on_respawn', True)) is bool, 'Hide on respawn must be Yes or No.')
            need(trigger in ('visible', 'inspect', 'defeat'), 'Unknown discovery trigger.')
            if trigger=='inspect': need(d.get('target') in r.get('objects',{}), 'Inspection trigger must name an inspectable object in the same room.')
            if trigger=='defeat':
                possible=[r.get('enemy'), (encounter or {}).get('enemy')]+[x.get('enemy') for x in r.get('spawn_pool',[]) if isinstance(x,dict)]
                for group in r.get('population',[]):
                    if isinstance(group,dict):possible += [group.get('enemy')]+[x.get('enemy') for x in group.get('pool',[]) if isinstance(x,dict)]
                need(d.get('target') in w['enemies'] and d['target'] in possible, 'Defeat trigger must name one of the room’s possible creatures.')
            if d['kind']=='item': need(d.get('item') in w['items'], 'Choose the discoverable item.')
            else:
                need(d.get('key') in w['items'] and w['items'][d['key']]['kind']=='key', 'A locked container requires a key item.')
                need(isinstance(d.get('contents'), list) and len(d['contents'])>0 and all(x in w['items'] for x in d['contents']), 'A locked container needs at least one valid item inside.')
    return w


class Adventure:
    def init_adventure(self):
        for name in ('instances', 'discoveries', 'encounter_rolls', 'released_enemies'):
            self.state.setdefault(name, {})
        self.state.setdefault('instance_sequence', 0)
        # Convert any template cages introduced by an owner into individual cages.
        piles=list(self.state['ground'].values())
        if self.p: piles.append(self.p['inventory'])
        for pile in piles:
            for pos, iid in enumerate(pile):
                if iid in self.w['items'] and self.w['items'][iid]['kind']=='cage': pile[pos]=self.new_cage(iid)

    def new_instance(self, value):
        self.state['instance_sequence'] += 1
        value['number']=self.state['instance_sequence']
        iid='@'+str(value['number'])
        self.state['instances'][iid]=value
        return iid

    def new_cage(self, iid): return self.new_instance({'kind':'cage', 'item':iid, 'enemy':None, 'count':0})
    def grant(self, iid): return self.new_cage(iid) if self.w['items'][iid]['kind']=='cage' else iid

    def item(self, iid):
        instance=self.state.get('instances', {}).get(iid)
        if not instance: return self.w['items'][iid]
        if instance['kind']=='cage':
            spec=dict(self.w['items'][instance['item']]); spec['name']+=f' {instance["number"]}'
            if instance['count']: spec['name']+=' — '+self.w['enemies'][instance['enemy']]['name']+f' (x{instance["count"]})'
            spec['protected']=True; spec['instance']=True; spec['occupied']=bool(instance['count'])
            return spec
        e=self.w['enemies'][instance['enemy']]
        return {'kind':'captive', 'name':f'Unconscious {e["name"]} {instance["number"]}', 'price':0, 'description':e.get('captive_description') or f'{e["name"]} lies unconscious.', 'protected':True, 'instance':True}

    def marked(self, iid, count=1):
        i=self.item(iid); a,b=('[',']') if i['kind'] in ('weapon','armor') else ('(',')')
        return a+i['name']+b+(f' (x{count})' if count>1 else '')

    def instance_match(self, target, candidates):
        ids=list(dict.fromkeys(candidates)); t=target.lower().strip()
        if not t: raise ValueError('Specify an item, creature, or cage by name.')
        aliases={}
        for iid in ids:
            aliases[iid]=[iid.lower(),self.item(iid)['name'].lower()]
            inst=self.state['instances'].get(iid)
            if inst and inst['kind']=='cage': aliases[iid].extend([f'cage {inst["number"]}', self.w['items'][inst['item']]['name'].lower()+f' {inst["number"]}'])
        exact=[i for i in ids if t in aliases[i]]
        found=exact or [i for i in ids if any(t in x for x in aliases[i])]
        if not found: raise ValueError('That item is not available here.')
        if len(found)>1 and all(self.state['instances'].get(i,{}).get('kind')=='captive' for i in found) and len({self.state['instances'][i]['enemy'] for i in found})==1: return found[0]
        if len(found)>1: raise ValueError('Be more specific: '+', '.join(self.item(i)['name'] for i in found))
        return found[0]

    def current_spawn(self, rid=None):
        rid=rid or self.p['room']
        released=self.state['released_enemies'].get(rid)
        if released and released['hp']>0: return released
        return self.state['spawns'].get(rid)

    def roll_encounter(self, rid):
        r=self.w['rooms'][rid]; rule=r.get('encounter')
        if not rule: return
        current=self.current_spawn(rid)
        if current and current['hp']>0: return
        until=max(self.state['encounter_rolls'].get(rid,0), (current or {}).get('respawn_at',0))
        if self.clock()<until: return
        self.state['encounter_rolls'][rid]=self.clock()+rule['cooldown']
        if rule['chance']>0 and self.rng.random()<rule['chance']/100:
            eid=rule['enemy']; self.state['spawns'][rid]={'type':eid,'hp':self.w['enemies'][eid]['hp'],'respawn_at':0,'random':True}
            self.log(f'{self.w["enemies"][eid]["name"]} emerges into your path.', 'danger')

    def discover(self, trigger='visible', target=None):
        rid=self.p['room']; state=self.state['discoveries'].setdefault(rid,{})
        for d in self.w['rooms'][rid].get('discoveries',[]):
            s=state.setdefault(d['id'],{})
            if not s.get('revealed') and d.get('trigger','visible')==trigger and (trigger=='visible' or d.get('target')==target):
                s['revealed']=True
                if self.visible(): self.log(d.get('message') or f'You discover {d["name"]}.','story')
            if s.get('revealed') and d['kind']=='item' and not s.get('materialized'):
                self.state['ground'].setdefault(rid,[]).append(self.grant(d['item']));s['materialized']=True

    def discovery_guarded(self, discovery):
        """Hide defeat discoveries again without resetting their saved progress."""
        if discovery.get('trigger') != 'defeat' or not discovery.get('hide_on_respawn', True):
            return False
        return any(e['type'] == discovery.get('target') and not e.get('released')
                   for e in self.creatures(unconscious=True))

    def visible_ground(self):
        rid = self.p['room']
        hidden = {d['item'] for d in self.w['rooms'][rid].get('discoveries', [])
                  if d['kind'] == 'item' and self.discovery_guarded(d)}
        return [i for i in self.state['ground'].get(rid, [])
                if self.state['instances'].get(i, {}).get('item', i) not in hidden]

    def containers(self):
        if not self.visible(): return []
        rid=self.p['room']; state=self.state['discoveries'].get(rid,{})
        return [(d,state.get(d['id'],{})) for d in self.w['rooms'][rid].get('discoveries',[]) if d['kind']=='container' and state.get(d['id'],{}).get('revealed') and not self.discovery_guarded(d)]

    def find_container(self, target):
        t=target.lower().strip();rows=self.containers()
        exact=[row for row in rows if t in (row[0]['id'].lower(),row[0]['name'].lower())]
        found=exact or [row for row in rows if t and t in row[0]['name'].lower()]
        if len(found)>1 and all(self.state['instances'].get(i,{}).get('kind')=='captive' for i in found) and len({self.state['instances'][i]['enemy'] for i in found})==1: return found[0]
        if len(found)>1: raise ValueError('More than one container matches. Use its full name.')
        return found[0] if found else None

    def show_cage(self, iid):
        instance=self.state['instances'][iid];spec=self.item(iid)
        self.log(spec['name']+'\n'+spec['description'],'story')
        if not instance['count']: self.log(f'Empty cage. Capacity: {spec.get("capacity",5)} creatures of one type.');return
        enemy=self.w['enemies'][instance['enemy']]
        self.log(f'Inside: {enemy["name"]} (x{instance["count"]}) / capacity {spec.get("capacity",5)}.')
        if enemy.get('captive_description'):self.log(enemy['captive_description'],'story')
        if enemy.get('captive_actions'):self.log(self.rng.choice(enemy['captive_actions']),'story')

    def extra_look(self, target):
        if target in ('north','south','east','west','up','down','n','s','e','w','u','d'): return False
        if target:
            available=self.p['inventory']+(self.visible_ground() if self.visible() else [])
            try: iid=self.instance_match(target,available)
            except ValueError: iid=None
            if iid and iid in self.state['instances']:
                if self.state['instances'][iid]['kind']=='cage':self.show_cage(iid)
                else:self.log(self.item(iid)['description'],'story')
                return True
        if not self.visible(): return False
        self.discover()
        for name in self.w['rooms'][self.p['room']].get('objects',{}):
            if target==name.lower():self.discover('inspect',name)
        box=self.find_container(target) if target else None
        if box:
            d,s=box;self.log(d['name']+'\n'+d.get('description','')+'\n'+('Open and empty; any uncollected contents are on the ground.' if s.get('opened') else 'Locked. You need its matching key.'),'story');return True
        return False

    def room_extras(self):
        if not self.visible():return
        for d,s in self.containers():self.log(d['name']+(' (open)' if s.get('opened') else ' (locked)')+'.')
        e=self.current_spawn()
        if e and e['hp']>0 and e.get('unconscious'):self.log(f'Unconscious {self.w["enemies"][e["type"]]["name"]} lies here. GET it to take it with you.')

    def knockout(self, target, skill_id="knockout"):
        e=self.enemy()
        if not self.visible() or not e:raise ValueError('There is no visible, conscious enemy to knock out.')
        spec=self.w['enemies'][e['type']]
        if target and target not in spec['name'].lower() and target!=e['type']:raise ValueError('That enemy is not here.')
        skill=self.require_skill(skill_id)
        if not spec.get('capturable',False):raise ValueError('This creature cannot be captured.')
        if e['hp']>spec['hp']*spec.get('capture_health',35)/100:raise ValueError(f'Weaken it to {spec.get("capture_health",35):g}% health or less first.')
        remaining=self.p['cooldowns'].get(skill_id,0)-self.clock()
        if remaining>0:raise ValueError(f'{skill["name"]} is ready in {math.ceil(remaining)} seconds.')
        self.p['cooldowns'][skill_id]=self.clock()+skill['cooldown']
        chance=self.skill_power(skill_id,skill.get('chance',70))/100*(1-spec.get('capture_resistance',0)/100)
        if self.rng.random()<chance:
            e['unconscious']=True;self.p['combat']=None
            self.log(f'{spec["name"]} collapses unconscious. Combat stops. GET it, then PUT it IN a cage.','reward')
        else:
            self.log(f'{spec["name"]} resists your knockout attempt!','danger');self.start_combat()

    def extra_command(self, verb, target):
        if verb=='knockout':self.knockout(target);return True
        if verb in ('unlock','open'):
            if self.p['combat']:raise ValueError('Finish the fight before opening a container.')
            self.discover();box=self.find_container(target)
            if not box:raise ValueError('You do not see that container here.')
            d,s=box
            if s.get('opened'):raise ValueError('The container is already open. Any remaining treasure is on the ground.')
            if d['key'] not in self.p['inventory']:raise ValueError(f'You need {self.w["items"][d["key"]]["name"]} in your inventory to unlock this.')
            self.p['inventory'].remove(d['key']);s['opened']=True
            self.state['ground'].setdefault(self.p['room'],[]).extend(self.grant(i) for i in d['contents'])
            self.log((d.get('open_message') or f'{d["name"]} opens, revealing its treasure.')+' The key crumbles and is consumed.','reward')
            self.log('Revealed:\n'+'\n'.join(self.marked(i) for i in d['contents']));return True
        if verb=='get' and self.visible():
            self.discover();e=self.current_spawn()
            if e and e['hp']>0 and e.get('unconscious'):
                name=self.w['enemies'][e['type']]['name']
                if target and (target in name.lower() or target==e['type']):
                    if self.p['combat']:raise ValueError('Finish combat before picking up a creature.')
                    if len(self.p['inventory'])>=self.w['settings']['bag_capacity']:raise ValueError('Your bag is full; the unconscious creature remains here.')
                    iid=self.new_instance({'kind':'captive','enemy':e['type']})
                    self.p['inventory'].append(iid);e['hp']=0;e['respawn_at']=self.clock()+self.respawn_delay(self.p['room'], e['type'])
                    e['unconscious']=False;self.log(f'You pick up {name}. No kill rewards are awarded.');return True
        if verb=='put':
            if self.p['combat']:raise ValueError('Finish combat before handling cages.')
            parts=re.split(r'\s+in\s+',target,maxsplit=1)
            if len(parts)!=2:raise ValueError('Use PUT <creature> IN CAGE <number>.')
            captives=[i for i in self.p['inventory'] if self.item(i)['kind']=='captive']
            cid=self.instance_match(parts[0],captives)
            available=self.p['inventory']+(self.visible_ground() if self.visible() else [])
            cages=[i for i in available if self.item(i)['kind']=='cage']
            cage_id=self.instance_match(parts[1],cages);cage=self.state['instances'][cage_id];creature=self.state['instances'][cid]['enemy']
            if cage['count'] and cage['enemy']!=creature:raise ValueError('This cage already contains another creature type. Use a different cage.')
            if cage['count']>=self.item(cage_id).get('capacity',5):raise ValueError('That cage is full.')
            cage['enemy']=creature;cage['count']+=1;self.p['inventory'].remove(cid);del self.state['instances'][cid]
            self.log(f'You place {self.w["enemies"][creature]["name"]} in {self.item(cage_id)["name"]}.');return True
        if verb=='release':
            if self.p['combat'] or self.w['rooms'][self.p['room']].get('safe'):raise ValueError('Release creatures outside town, out of combat.')
            if not self.visible():raise ValueError('Find a well-lit place to release the creature.')
            current=self.current_spawn()
            if self.enemy() or current and current['hp']>0:raise ValueError('This room is already occupied by a creature.')
            available=self.p['inventory']+self.state['ground'].get(self.p['room'],[])
            iid=self.instance_match(target,[i for i in available if self.item(i)['kind']=='cage']);cage=self.state['instances'][iid]
            if not cage['count']:raise ValueError('That cage is empty.')
            eid=cage['enemy'];cage['count']-=1
            if not cage['count']:cage['enemy']=None
            self.state['released_enemies'][self.p['room']]={'type':eid,'hp':self.w['enemies'][eid]['hp'],'respawn_at':0,'released':True}
            self.log(f'You release one {self.w["enemies"][eid]["name"]}. Released creatures give no kill rewards or discovery unlocks.','notice')
            if self.w['enemies'][eid]['aggressive']:self.start_combat()
            return True
        return False

    def extra_snapshot(self, result):
        result['items']=dict(self.w['items'])
        for iid in self.state['instances']:result['items'][iid]=self.item(iid)
        if self.p:
            result['containers']=[{'id':d['id'],'name':d['name'],'opened':bool(s.get('opened'))} for d,s in self.containers()]
            e=self.current_spawn()
            result['unconscious']=self.w['enemies'][e['type']]['name'] if e and e['hp']>0 and e.get('unconscious') and self.visible() else None
            result['enemy_types']={k:v['name'] for k,v in self.w['enemies'].items()}
        return result

    def check_adventure_references(self, w):
        for inst in self.state['instances'].values():
            if inst['kind']=='cage':
                spec=w['items'].get(inst['item'])
                if not spec or spec['kind']!='cage':raise ValueError('Cannot remove or change a purchased cage type.')
                if inst['count']>spec.get('capacity',5):raise ValueError('Cage capacity cannot be smaller than its existing occupants.')
            if inst.get('enemy') and inst['enemy'] not in w['enemies']:raise ValueError('Cannot remove a creature type that has been captured.')
        for rid,state in self.state['discoveries'].items():
            old={d['id']:d for d in self.w['rooms'].get(rid,{}).get('discoveries',[])}
            new={d['id']:d for d in w['rooms'].get(rid,{}).get('discoveries',[])}
            for ident,s in state.items():
                if s.get('revealed') and (ident not in new or old.get(ident,{}).get('kind')!=new[ident]['kind']):raise ValueError('Cannot remove or change the type of an already-discovered placement.')
        for rid,e in self.state['released_enemies'].items():
            if e['hp']>0 and (rid not in w['rooms'] or e['type'] not in w['enemies']):raise ValueError('Cannot remove a room or creature containing a released enemy.')
