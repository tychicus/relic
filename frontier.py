"""v0.3 storage, expiry, spawn pools, conversation and owner metadata."""
import math
import re
from adventure import Adventure


def validate_frontier(w):
    def need(ok, message):
        if not ok: raise ValueError(message)
    def num(x, lo, hi, integer=False):
        return type(x) in (int,float) and math.isfinite(x) and lo<=x<=hi and (not integer or type(x) is int)
    codes=set();positions=set()
    for item in w['items'].values():
        if item['kind']=='chest':need(num(item.get('capacity',30),1,1000,True),'Chest capacity must be a positive whole number.')
    for e in w['enemies'].values():
        need(num(e.get('captive_value',0),0,100000,True),'Creature sale value must be a nonnegative whole number.')
        need(isinstance(e.get('conversation_default',''),str) and len(e.get('conversation_default',''))<=6000,'Default conversation response must be text.')
        rules=e.get('conversations',[]);need(isinstance(rules,list),'Conversation rules must be a list.')
        phrases=set()
        for rule in rules:
            need(isinstance(rule,dict),'Conversation rule must be an object.')
            phrase=rule.get('phrase');response=rule.get('response')
            need(isinstance(phrase,str) and 0<len(phrase.strip())<=100,'Conversation phrase must contain 1–100 characters.')
            phrase=' '.join(phrase.casefold().split());need(phrase not in phrases,'Conversation phrases must be unique for each creature.');phrases.add(phrase)
            need(isinstance(response,str) and 0<len(response.strip())<=6000,'Conversation response is required.')
            need(type(rule.get('attack',False)) is bool,'Conversation attack must be Yes or No.')
    for rid,r in w['rooms'].items():
        if 'code' in r:
            code=r['code'];need(isinstance(code,str) and re.fullmatch(r'[A-Z][A-Z0-9]*-[0-9]{3,}',code) is not None,'Room codes use a prefix and number, such as TOWN-001.')
            need(code not in codes,'Room reference codes must be unique.');codes.add(code)
        if 'region' in r:need(isinstance(r['region'],str) and 0<len(r['region'].strip())<=120,'Region needs a name.')
        if 'map_position' in r:
            pos=r['map_position'];need(isinstance(pos,list) and len(pos)==3 and all(num(n,-10000,10000,True) for n in pos),'Map position must have three integer coordinates.')
            need(tuple(pos) not in positions,'Two rooms cannot occupy the same map position.');positions.add(tuple(pos))
        need(type(r.get('creature_buyer',False)) is bool,'Creature buyer must be Yes or No.')
        if 'respawn_seconds' in r:need(num(r['respawn_seconds'],1,86400),'Room respawn timer must be 1–86400 seconds.')
        if 'spawn_pool' in r:
            pool=r['spawn_pool'];need(isinstance(pool,list),'Respawn pool must be a list.')
            for entry in pool:
                need(isinstance(entry,dict) and entry.get('enemy') in w['enemies'] and num(entry.get('weight'),.001,100000),'Each respawn outcome needs a creature and positive weight.')
            need(not r.get('encounter'),'Choose a respawn pool or an entry-roll encounter, not both.')
            need(not (r.get('safe') and (pool or r.get('enemy'))),'Safe rooms cannot spawn creatures.')
    return w


class Frontier(Adventure):
    def init_adventure(self):
        super().init_adventure()
        self.state.setdefault('drop_timers',{})
        piles=list(self.state['ground'].values())
        if self.p:piles.append(self.p['inventory'])
        for pile in piles:
            for n,i in enumerate(pile):
                if i in self.w['items'] and self.w['items'][i]['kind']=='chest':pile[n]=self.new_chest(i)
        self.cleanup_drops()

    def new_chest(self,iid):return self.new_instance({'kind':'chest','item':iid,'contents':[]})
    def grant(self,iid):return self.new_chest(iid) if self.w['items'][iid]['kind']=='chest' else super().grant(iid)
    def item(self,iid):
        inst=self.state.get('instances',{}).get(iid)
        if inst and inst['kind']=='chest':
            spec=dict(self.w['items'][inst['item']]);spec.update(name=spec['name']+f' {inst["number"]}',protected=True,instance=True,occupied=bool(inst['contents']),stored_count=len(inst['contents']))
            return spec
        return super().item(iid)

    def instance_match(self,target,candidates):
        t=target.strip().lower();ids=list(dict.fromkeys(candidates))
        for i in ids:
            inst=self.state['instances'].get(i)
            if inst and inst['kind']=='chest' and t==f'chest {inst["number"]}':return i
        return super().instance_match(target,ids)

    def cleanup_drops(self):
        changed=False
        for rid,timers in list(self.state.get('drop_timers',{}).items()):
            remaining=[];pile=self.state['ground'].get(rid,[])
            for record in timers:
                iid=record['item']
                if iid not in pile:changed=True;continue
                if self.item(iid)['kind'] in ('key','cage','chest'):changed=True;continue
                if self.clock()>=record['expires']:
                    pile.remove(iid);self.state['instances'].pop(iid,None);changed=True
                else:remaining.append(record)
            if remaining:self.state['drop_timers'][rid]=remaining
            else:self.state['drop_timers'].pop(rid,None)
        return changed

    def drop_item(self,iid):
        rid=self.p['room'];self.p['inventory'].remove(iid);self.state['ground'].setdefault(rid,[]).append(iid)
        if self.item(iid)['kind'] not in ('key','cage','chest'):
            self.state['drop_timers'].setdefault(rid,[]).append({'item':iid,'expires':self.clock()+600})

    def get_item(self,iid):
        rid=self.p['room'];self.state['ground'][rid].remove(iid);self.p['inventory'].append(iid)
        timers=self.state['drop_timers'].get(rid,[])
        for n,row in enumerate(timers):
            if row['item']==iid:timers.pop(n);break

    def respawn_delay(self,rid,eid=None):
        r=self.w['rooms'][rid]
        return r.get('respawn_seconds',self.w['enemies'].get(eid,{}).get('respawn',60))

    def resident_enemy(self,room_id=None):
        rid=room_id or self.p['room'];r=self.w['rooms'][rid]
        released=self.state['released_enemies'].get(rid)
        if released and released['hp']>0:return None if released.get('unconscious') else released
        current=self.state['spawns'].get(rid)
        if r.get('encounter'):return current if current and current['hp']>0 and not current.get('unconscious') else None
        pool=r.get('spawn_pool');initial=r.get('enemy')
        if not initial and pool is None:return None
        if current is None:
            current={'type':initial,'hp':self.w['enemies'][initial]['hp'] if initial else 0,'respawn_at':0 if initial else self.clock()+self.respawn_delay(rid)}
            self.state['spawns'][rid]=current
        if current['hp']<=0 and self.clock()>=current.get('respawn_at',0):
            eid=initial if pool is None else (self.rng.choices(pool,weights=[x['weight'] for x in pool],k=1)[0]['enemy'] if pool else None)
            if eid:
                current={'type':eid,'hp':self.w['enemies'][eid]['hp'],'respawn_at':0};self.state['spawns'][rid]=current
        return current if current['hp']>0 and not current.get('unconscious') else None

    def available_chests(self):
        ids=self.p['inventory']+(self.visible_ground() if self.visible() else [])
        return [i for i in ids if self.item(i)['kind']=='chest']

    def show_chest(self,iid):
        spec=self.item(iid);contents=self.state['instances'][iid]['contents']
        self.log(spec['name']+'\n'+spec['description']+f'\nStorage: {len(contents)} / {spec.get("capacity",30)} slots.','story')
        self.log('\n'.join(self.marked(i,contents.count(i)) for i in dict.fromkeys(contents)) or 'Empty.')

    def extra_look(self,target):
        target=re.sub(r'^(inside|in)\s+','',target)
        if target:
            try:iid=self.instance_match(target,self.available_chests())
            except ValueError:iid=None
            if iid:self.show_chest(iid);return True
        return super().extra_look(target)

    def talk(self,target):
        parts=re.split(r'\s+to\s+',target,maxsplit=0)
        if len(parts)<2:raise ValueError('Use SAY <phrase> TO <creature or cage number>.')
        phrase=' to '.join(parts[:-1]).strip().strip('"');who=parts[-1].strip()
        if not phrase or not who:raise ValueError('Include both a phrase and a creature.')
        e=self.enemy();caged=False;eid=None
        if self.visible() and e and (who==e['type'] or who in self.w['enemies'][e['type']]['name'].lower()):eid=e['type']
        else:
            ids=self.p['inventory']+(self.visible_ground() if self.visible() else [])
            cages=[i for i in ids if self.item(i)['kind']=='cage' and self.state['instances'][i]['count']]
            try:iid=self.instance_match(who,cages)
            except ValueError as error:raise ValueError('No matching conscious creature here. For a captive, specify CAGE <number>. '+str(error))
            eid=self.state['instances'][iid]['enemy'];caged=True
        spec=self.w['enemies'][eid];normalized=' '.join(phrase.casefold().split())
        rule=next((r for r in spec.get('conversations',[]) if ' '.join(r['phrase'].casefold().split())==normalized),None)
        self.log(rule['response'] if rule else spec.get('conversation_default') or spec['name']+' gives no reply.','story')
        if rule and rule.get('attack'):
            if caged:self.log('The cage holds firm; the creature cannot attack you.')
            elif self.w['rooms'][self.p['room']].get('safe'):self.log('The creature cannot attack in this safe place.')
            else:self.start_combat()

    def extra_command(self,verb,target):
        if verb=='say':self.talk(target);return True
        if verb=='get' and ' from ' in target:
            if self.p['combat']:raise ValueError('Finish combat before using storage.')
            item_name,chest_name=target.rsplit(' from ',1)
            chest_id=self.instance_match(chest_name,self.available_chests());contents=self.state['instances'][chest_id]['contents']
            iid=self.instance_match(item_name,contents)
            if len(self.p['inventory'])>=self.w['settings']['bag_capacity']:raise ValueError('Your bag is full. The item stays in the chest.')
            contents.remove(iid);self.p['inventory'].append(iid);self.log('Retrieved: '+self.item(iid)['name']+'.');return True
        if verb=='put' and ' in ' in target:
            item_name,destination=target.rsplit(' in ',1)
            available=self.p['inventory']+(self.visible_ground() if self.visible() else [])
            containers=[i for i in available if self.item(i)['kind'] in ('chest','cage')]
            destination_id=self.instance_match(destination,containers)
            if self.item(destination_id)['kind']=='chest':
                if self.p['combat']:raise ValueError('Finish combat before using storage.')
                iid=self.instance_match(item_name,self.p['inventory'])
                if self.item(iid)['kind']=='chest':raise ValueError('Chests cannot be stored inside chests.')
                contents=self.state['instances'][destination_id]['contents']
                if len(contents)>=self.item(destination_id).get('capacity',30):raise ValueError('That chest is full.')
                self.p['inventory'].remove(iid);contents.append(iid);self.log('Stored: '+self.item(iid)['name']+'.');return True
        room=self.w['rooms'][self.p['room']]
        if room.get('creature_buyer') and verb in ('sell','buy'):
            if self.p['combat']:raise ValueError('Finish combat before trading.')
            if verb=='buy' or not target:
                self.log("Jake buys occupied cages. Payment is creature value × count; the cage is included without extra payment. Use SELL CAGE <number>.")
                for i in self.p['inventory']:
                    if self.item(i)['kind']=='cage':
                        inst=self.state['instances'][i]
                        if inst['count']:self.log(f'{self.marked(i)} — {self.w["enemies"][inst["enemy"]].get("captive_value",0)*inst["count"]} gold')
                return True
            iid=self.instance_match(target,self.p['inventory']);inst=self.state['instances'].get(iid,{})
            if inst.get('kind')!='cage' or not inst.get('count'):raise ValueError('Jake buys occupied cages only.')
            value=self.w['enemies'][inst['enemy']].get('captive_value',0)*inst['count']
            if value<=0:raise ValueError('Jake is not buying this creature yet. Set its creature sale value in the owner editor.')
            name=self.item(iid)['name'];self.p['gold']+=value;self.p['inventory'].remove(iid);del self.state['instances'][iid]
            self.log(f'Jake pays {value} gold for {name}. The cage and all occupants are sold.','reward');return True
        return super().extra_command(verb,target)

    def extra_snapshot(self,result):
        result=super().extra_snapshot(result)
        if self.p:
            room=self.w['rooms'][self.p['room']]
            result['room']['creature_buyer']=room.get('creature_buyer',False)
            result['room']['code']=room.get('code','');result['room']['region']=room.get('region','')
            for iid,spec in result['items'].items():
                inst=self.state['instances'].get(iid)
                if inst and inst['kind']=='cage' and inst['count']:
                    spec['creature_sale_value']=self.w['enemies'][inst['enemy']].get('captive_value',0)*inst['count']
        return result

    def check_adventure_references(self,w):
        super().check_adventure_references(w)
        for rid,r in self.w['rooms'].items():
            if rid in w['rooms'] and r.get('code') and w['rooms'][rid].get('code')!=r['code']:raise ValueError('Existing room reference codes are permanent. Rename the room instead.')
        for inst in self.state['instances'].values():
            if inst['kind']!='chest':continue
            spec=w['items'].get(inst['item'])
            if not spec or spec['kind']!='chest':raise ValueError('Cannot remove or change a purchased chest type.')
            if len(inst['contents'])>spec.get('capacity',30):raise ValueError('Chest capacity is smaller than its stored items.')
            for iid in inst['contents']:
                if iid not in w['items'] and iid not in self.state['instances']:raise ValueError('Cannot remove an item stored inside a chest.')
                if iid in w['items'] and w['items'][iid]['kind']=='chest':raise ValueError('An item stored in a chest cannot become another chest.')
