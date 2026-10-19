"""Instance-based encounters and player-owned combat/crafting state.

The old world/save keys remain readable. Extra populations have stable home slots;
roaming changes location, never the slot that owns the respawn timer.
"""
import copy
import math
import re
from revision_rules import DEFAULT_RULES
from enchanting import Enchanting
from magic_progression import MagicProgression
from regions import Regions
from encounters import actor_id, sync_encounter, ready_actions
from mana import Mana
from learning import Learning
from equipment import Equipment, BODY_SLOTS, SLOT_NAMES, SLOT_ALIASES
from enemy_healing import EnemyHealing
from player_bodies import PlayerBodies
from banking import Banking
from rare_drops import RareDrops
from player_map import PlayerMap

DIRECTIONS={'n':'north','s':'south','e':'east','w':'west','u':'up','d':'down'}
TRAITS=['scarred','watchful','lean','broad-shouldered','dust-covered','restless','pale','dark-eyed','weathered','bristling','long-limbed','stout']
MARKS=['notched-eared','gray-marked','white-marked','red-eyed','mud-spattered','amber-eyed','sharp-eyed','mottled','ragged','dark-backed','light-footed','heavy-browed']
CORPSE_DESCRIPTIONS=[
    'The corpse of {name} lies here.',
    'The decaying corpse of {name} lies on the ground.',
    'The lifeless body of {name} lies here.',
    'The remains of {name} lie motionless here.',
]

class Revision(PlayerMap, RareDrops, Regions, EnemyHealing, Banking, PlayerBodies, Equipment, Learning, Mana, MagicProgression, Enchanting):
    def rules(self):
        return {**DEFAULT_RULES,**self.w.get('revision',{})}

    def all_players(self):
        return [self.p] if self.p else []

    def player_event(self,player_id,text,kind='info'):
        if self.p and self.p['id']==player_id:self.log(text,kind)

    def room_event(self,room,text,kind='info'):
        if self.p and not self.p.get('logged_out') and self.p['room']==room and self.visible():
            self.log(text,kind)

    def engaged_creature_ids(self):
        return set((self.p.get('combat') or {}).get('engaged',[])) if self.p else set()

    def init_adventure(self):
        super().init_adventure()
        self.init_banking()
        self.state.setdefault('populations',{})
        self.state.setdefault('creature_sequence',0)
        self.state.setdefault('corpses',[])
        self.init_player_bodies()
        self.state['schema_version']=5
        self.migrate_enchantments()
        self.init_magic_items()
        self.init_learning()
        self.init_mana()
        if self.p:self.p['hp']=min(self.p['hp'],self.max_hp())
        self.remember_room()
        self.prepare_residents()
        self.prepare_regions()
        self._enemy_heal_at={}

    def prepare_residents(self):
        # Fixed initial residents exist before a player first scouts their room.
        # This consumes no random draws and never rolls entry encounters or pools.
        for rid,room in self.w['rooms'].items():
            if self.region_for(rid, True)[0]:continue
            if room.get('enemy') and not room.get('safe') and not room.get('encounter') and rid not in self.state['spawns']:
                self.state['spawns'][rid]=self.spawn_creature(room['enemy'],rid)

    def tag_creature(self,e,home):
        if 'uid' not in e:
            self.state['creature_sequence']+=1
            e['uid']='creature-'+str(self.state['creature_sequence'])
        e.setdefault('home',home);e.setdefault('location',home);e.setdefault('effects',[])
        e.setdefault('roam_at',self.clock()+30)
        return e

    def spawn_creature(self,eid,home):
        return self.tag_creature({'type':eid,'hp':self.w['enemies'][eid]['hp'],'respawn_at':0},home)

    def ensure_legacy(self,rid):
        if self.region_for(rid, True)[0]:return
        r=self.w['rooms'][rid]
        if r.get('safe'):return
        e=self.state['spawns'].get(rid)
        if e and e['hp']>0:self.tag_creature(e,rid);return
        if r.get('encounter'):return
        initial=r.get('enemy');pool=r.get('spawn_pool')
        if not initial and pool is None:return
        if e is None:
            if initial:
                e=self.spawn_creature(initial,rid);self.state['spawns'][rid]=e
                return
            e={'type':None,'hp':0,'respawn_at':self.clock()+self.respawn_delay(rid)};self.state['spawns'][rid]=e
        if not r.get('respawn_enabled',True) or self.clock()<e.get('respawn_at',0):return
        chance=r.get('spawn_chance',100)
        eid=None
        if chance>=100 or self.rng.random()<chance/100:
            eid=initial if pool is None else self.rng.choices(pool,weights=[x['weight'] for x in pool],k=1)[0]['enemy'] if pool else None
        if eid:self.state['spawns'][rid]=self.spawn_creature(eid,rid)
        else:e['respawn_at']=self.clock()+self.respawn_delay(rid)

    def ensure_groups(self,rid,entry=False):
        if self.region_for(rid, True)[0]:return
        room=self.w['rooms'][rid]
        if room.get('safe'):return
        home=self.state['populations'].setdefault(rid,{})
        for rule in room.get('population',[]):
            for n in range(rule.get('count',1)):
                key=rule['id']+':'+str(n);slot=home.setdefault(key,{'creature':None,'next_at':0,'used':False})
                e=slot['creature']
                if e and e['hp']>0:continue
                if slot['used'] and not rule.get('respawn',True):continue
                if rule.get('trigger','timer')=='entry' and not entry:continue
                deadline=max(slot['next_at'],(e or {}).get('respawn_at',0))
                if self.clock()<deadline:continue
                slot['next_at']=self.clock()+rule.get('delay',60)
                chance=rule.get('chance',100)
                if chance<100 and self.rng.random()>=chance/100:continue
                pool=rule.get('pool',[])
                eid=self.rng.choices(pool,weights=[x['weight'] for x in pool],k=1)[0]['enemy'] if pool else rule.get('enemy')
                if eid:
                    e=slot['creature']=self.spawn_creature(eid,rid);e['group']=rule['id'];slot['used']=True

    def creatures(self,rid=None,unconscious=False,prepare=True):
        rid=rid or self.p['room']
        if prepare:self.ensure_legacy(rid);self.ensure_groups(rid)
        found=[]
        for home,e in list(self.state['spawns'].items())+list(self.state['released_enemies'].items()):
            if e['hp']>0:
                self.tag_creature(e,home)
                if e['location']==rid and (unconscious or not e.get('unconscious')):found.append(e)
        for home,slots in self.state['populations'].items():
            for slot in slots.values():
                e=slot['creature']
                if e and e['hp']>0 and e['location']==rid and (unconscious or not e.get('unconscious')):found.append(e)
        found.extend(e for e in self.region_creatures() if e['location']==rid and (unconscious or not e.get('unconscious')))
        return found

    def creature_name(self,e):
        name=self.w['enemies'][e['type']]['name']
        peers=[x for x in self.creatures(e['location'],True,False) if self.w['enemies'][x['type']]['name'].casefold()==name.casefold()]
        if len(peers)>1 or e.get('descriptor'):
            if not e.get('descriptor'):
                used={x.get('descriptor') for x in peers}
                options=TRAITS+[a+', '+b for a in MARKS for b in TRAITS]
                descriptor=next((x for x in options if x not in used),None)
                if descriptor is None:
                    descriptor='distinctively marked'
                    while descriptor in used:descriptor='heavily '+descriptor
                e['descriptor']=descriptor
            return e['descriptor']+' '+name
        return name

    def find_creature(self,target,rows=None):
        if not self.visible():raise ValueError('It is too dark to choose a creature. Carry a light.')
        rows=self.creatures() if rows is None else rows
        if not target:
            if len(rows)==1:return rows[0]
            if not rows:raise ValueError('There is no matching creature here.')
        target=target.casefold().removeprefix('the ')
        matches=[e for e in rows if target in (e['uid'],self.creature_name(e).casefold())]
        if not matches:matches=[e for e in rows if target and (target==e['type'] or target in self.creature_name(e).casefold())]
        if not matches or len({e['type'] for e in matches})>1:
            raise ValueError('Use a distinct creature description: '+', '.join(self.creature_name(e) for e in (matches or rows))+'.')
        # Descriptors distinguish individuals, not species. Keep a matching target
        # so repeating a generic command does not provoke another bystander.
        return next((e for e in matches if e['uid']==self.p.get('target')),matches[0])

    def enemy(self,room_id=None):
        rows=self.creatures(room_id)
        if not rows:return None
        if room_id is None or room_id==self.p['room']:
            target=self.p.get('target')
            chosen=next((e for e in rows if e['uid']==target),None)
            if chosen:return chosen
        return next((e for e in rows if self.w['enemies'][e['type']]['aggressive']),rows[0])

    def current_spawn(self,rid=None):
        rows=self.creatures(rid,True)
        return next((e for e in rows if e.get('unconscious')),rows[0] if rows else None)

    def roll_encounter(self,rid):
        if self.region_for(rid, True)[0]:return
        room=self.w['rooms'][rid];rule=room.get('encounter');old=self.state['spawns'].get(rid)
        if rule and not (old and old['hp']>0) and (not old or room.get('respawn_enabled',True)):
            until=max(self.state['encounter_rolls'].get(rid,0),(old or {}).get('respawn_at',0))
            if self.clock()>=until:
                self.state['encounter_rolls'][rid]=self.clock()+rule['cooldown']
                if rule['chance']>0 and self.rng.random()<rule['chance']/100:
                    e=self.spawn_creature(rule['enemy'],rid);e['random']=True;self.state['spawns'][rid]=e
                    self.log(self.w['enemies'][e['type']]['name']+' emerges into your path.','danger')
        self.ensure_groups(rid,True)

    def spawn_rule(self,e):
        if e.get('region'):
            region=self.w.get('regions',{}).get(e['region'],{})
            return dict(roam=region.get('roam',True),roam_rooms=region.get('spawn_rooms',[]),roam_seconds=region.get('roam_seconds',30),delay=region.get('spawn_seconds',60))
        r=self.w['rooms'].get(e['home'],{})
        if e.get('group'):return next((g for g in r.get('population',[]) if g['id']==e['group']),{})
        return dict(roam=r.get('roaming',False),roam_rooms=r.get('roam_rooms',[]),roam_seconds=r.get('roam_seconds',30),delay=self.respawn_delay(e['home'],e['type']))

    def roam(self):
        self.tick_regions()
        all_rows=[]
        for rid,r in self.w['rooms'].items():
            if rid==self.p['room'] or rid in self.state['spawns'] or r.get('roaming'):self.ensure_legacy(rid)
            if rid==self.p['room'] or rid in self.state['populations'] or any(g.get('roam') for g in r.get('population',[])):self.ensure_groups(rid)
        for rid in self.w['rooms']:all_rows.extend(self.creatures(rid,True,False))
        engaged=self.engaged_creature_ids()
        for e in all_rows:
            rule=self.spawn_rule(e)
            if e.get('released') or e.get('unconscious') or e['uid'] in engaged or not rule.get('roam') or self.clock()<e['roam_at']:continue
            e['roam_at']=self.clock()+rule.get('roam_seconds',30)
            room=self.w['rooms'][e['location']]
            options=[rid for rid in room['exits'].values() if rid in rule.get('roam_rooms',[]) and not self.w['rooms'][rid].get('safe')]
            if e.get('region'):options=[rid for rid in options if rid in self.regional_destinations(e['region'])]
            if options:
                old=e['location'];e['location']=self.rng.choice(options)
                self.room_event(old,self.creature_name(e)+' leaves the area.')
                self.room_event(e['location'],self.creature_name(e)+' arrives.')

    def start_combat(self,initiated=True):
        e=self.enemy()
        if not e or self.w['rooms'][self.p['room']].get('safe'):return
        if not self.p['combat']:
            self.p['target']=e['uid']
            self.p['combat']={'room':self.p['room'],'turn':'simultaneous','next_at':self.clock(),'engaged':[e['uid']],
                              'initiator':actor_id(self.p) if initiated else None}
            self.log('Combat begins: '+self.creature_name(e)+'. Attacks are automatic. TARGET <description>, CAST <skill>, QUAFF POTION or FLEE.','combat')
            self.retarget()

    def retarget(self):
        c=self.p['combat']
        if not c:return
        rows=self.creatures();engaged=c.setdefault('engaged',[])
        # Legacy in-progress fights acquire an explicit target during migration.
        if not engaged and rows:engaged.append(self.enemy()['uid'])
        for e in rows:
            if self.w['enemies'][e['type']]['aggressive'] and e['uid'] not in engaged:engaged.append(e['uid'])
        candidates=[e for e in rows if e['uid'] in engaged]
        if not candidates:self.p['combat']=None;self.p.pop('target',None);return
        if not any(e['uid']==self.p.get('target') for e in candidates):
            self.p['target']=candidates[0]['uid'];self.log('You turn toward '+self.creature_name(candidates[0])+'.','combat')
        sync_encounter(c,[self.p],candidates,self.rng)

    def tick(self):
        with self.lock:
            if not self.p:return
            before=copy.deepcopy(self.state)
            self.cleanup_drops();self.expire_player_bodies();self.roam();self.expire_enchantments()
            self.state['corpses']=[c for c in self.state['corpses'] if c['expires']>self.clock() and not c.get('harvested')]
            self.retarget()
            if not self.p['combat']:
                hostile=next((e for e in self.creatures() if self.w['enemies'][e['type']]['aggressive']),None)
                if hostile:self.p['target']=hostile['uid'];self.start_combat(initiated=False)
            c=self.p['combat']
            self.recover_mana()
            self.heal_enemies()
            if c and self.clock()>=c['next_at']:
                location=self.p['room']
                stunned={}
                for actor in [self.p]+self.creatures():
                    stunned[id(actor)]=any(self.w.get('status_effects',{}).get(s['id'],{}).get('kind')=='stun' for s in actor.get('effects',[]))
                    self.pulse_effects(actor)
                    if self.p['room']!=location or self.p['hp']<=0:break
                self.retarget();c=self.p['combat']
                if c:
                    c['turn']='simultaneous'
                    opponents=[e for e in self.creatures() if e['uid'] in c['engaged']]
                    roster=sync_encounter(c,[self.p],opponents,self.rng)
                    for actor,_ in ready_actions(c,roster,None,self.clock()):
                        if not self.p['combat'] or self.p['room']!=location:break
                        self.retarget()
                        if not self.p['combat']:break
                        target=roster.get(c['targets'].get(actor_id(actor)))
                        if actor['hp']<=0 or actor.get('unconscious') or not target or target['hp']<=0:continue
                        if stunned.get(id(actor)):
                            if actor is self.p:self.log('You are stunned and cannot attack this pulse.','combat')
                            continue
                        if actor is self.p:
                            self.strike()
                        elif target is self.p:
                            self.enemy_strike(actor)
                        actor['attack_ready']=self.clock()+2*self.w['settings']['attack_interval']*self.slow(actor)
                    if self.p['combat']:c['next_at']=self.clock()+self.w['settings']['attack_interval']
            self.clear_idle_stun()
            # Other effects pause with combat, so offline time never causes a damage burst.
            if before!=self.state:self.save()

    def clear_idle_stun(self):
        # Stun ends with the fight; it must not lock healing/crafting until another fight.
        if not self.p or self.p.get('combat'):return
        for active in list(self.p.get('effects',[])):
            spec=self.w.get('status_effects',{}).get(active['id'],{})
            if spec.get('kind')=='stun':
                self.p['effects'].remove(active)
                self.effect_message('expiration',spec,self.p)

    def finish(self):
        self.clear_idle_stun()
        return super().finish()

    def slow(self,actor):
        return max([1]+[self.w['status_effects'][s['id']].get('slow',1.5) for s in actor.get('effects',[]) if self.w['status_effects'][s['id']]['kind']=='slow'])

    def effect_message(self,key,definition,actor,damage=0):
        name='you' if actor is self.p else self.creature_name(actor)
        msg=definition.get(key,'')
        for token,value in [('target',name),('effect',definition['name']),('damage',str(damage))]:msg=msg.replace('{'+token+'}',value)
        if msg:self.log(msg,'combat')

    def apply_effects(self,attachments,actor,damage_override=None):
        resistance=self.w['races'][self.p['race']].get('resistances',[]) if actor is self.p else self.w['enemies'][actor['type']].get('resistances',[])
        for a in attachments:
            spec=self.w['status_effects'][a['effect']]
            resist=max([0]+[r.get('chance',0) for r in resistance if r['effect']==a['effect']])
            if self.rng.random()>=a.get('chance',100)/100*(1-resist/100):self.effect_message('failure',spec,actor);continue
            active=actor.setdefault('effects',[]);old=next((x for x in active if x['id']==a['effect']),None)
            duration=a.get('duration') or spec.get('duration',3)
            if old:
                mode=spec.get('stacking','refresh')
                if mode=='ignore':continue
                old['remaining']=duration
                if mode=='stack':old['stacks']=min(spec.get('max_stacks',3),old['stacks']+1)
            else:
                old=dict(id=a['effect'],remaining=duration,stacks=1);active.append(old)
            if damage_override is not None and spec['kind']=='damage':old['damage_override']=damage_override
            else:old.pop('damage_override',None)
            self.effect_message('application',spec,actor)

    def pulse_effects(self,actor):
        for active in list(actor.get('effects',[])):
            spec=self.w.get('status_effects',{}).get(active['id'])
            if not spec:actor['effects'].remove(active);continue
            damage=active.get('damage_override',spec.get('damage',0))*active['stacks'] if spec['kind']=='damage' else 0
            actor['hp']=max(0,actor['hp']-damage)
            self.effect_message('ongoing',spec,actor,damage)
            if damage:self.log(('You lose ' if actor is self.p else self.creature_name(actor)+' loses ')+str(damage)+' HP.','combat')
            active['remaining']-=1
            if active['remaining']<=0:actor['effects'].remove(active);self.effect_message('expiration',spec,actor)
            if actor['hp']==0:
                if actor is self.p:self.death()
                else:self.victory(actor)
                return

    def item(self,iid):
        inst=self.state.get('instances',{}).get(iid)
        if inst and inst['kind'] in ('weapon','armor'):
            return self.modified_item(inst)
        return self.magic_template(super().item(iid))

    def strike(self,multiplier=1,attack_name=None):
        if not self.enemy():return
        practice=self.practice_multiplier(self.enemy())
        sid=getattr(self,'_active_skill',None)
        spell=bool(sid and self.w['skills'][sid].get('magic'))
        used=[]
        if not spell:
            for slot in ('weapon','left_hand'):
                iid=self.ensure_magic_slot(slot)
                if iid and self.item(iid)['kind']=='weapon':used.append(iid)
        try:self.resolve_strike(multiplier,attack_name)
        finally:self.train_magic_items(used,practice)

    def resolve_strike(self,multiplier=1,attack_name=None):
        e=self.enemy()
        if not e:return
        name=self.creature_name(e);_,_,dual=self.attack_weapons();rules=self.rules()
        sid=getattr(self,'_active_skill',None)
        progress=self.spell_progress(sid) if sid else None
        hit=self.w['settings']['hit_chance']-(rules['dual_hit_penalty'] if dual and not progress else 0)
        if self.rng.random()>max(0,hit):self.log(f'Your attack misses {name}.','combat');return
        dodge=self.w['enemies'][e['type']].get('dodge',0)
        if dodge and self.rng.random()<dodge/100:self.log(f'{name} dodges your {attack_name or ("Bash" if multiplier!=1 else "attack")}! No damage dealt.','combat');return
        # Keep the original RNG order: spells never roll physical base damage.
        roll=0 if progress else self.rng.randint(*self.w['classes'][self.p['class']]['damage'])
        damage=self.attack_damage(roll,multiplier,sid)
        self.reset_enemy_healing(e)
        e['hp']=max(0,e['hp']-damage);self.log((attack_name+'! ' if attack_name else 'Bash! ' if multiplier!=1 else '')+f'You hit {name} for {damage}.','combat')
        if e['hp']==0:self.victory(e)
        else:
            self.apply_effects(self.attack_effects(sid),e,damage_override=self.skill_effect_damage(sid))

    def enemy_strike(self,e):
        spec=self.w['enemies'][e['type']];name=self.creature_name(e)
        if spec.get('battle_cries') and spec.get('battle_cry_chance',0)>0 and self.rng.random()<spec['battle_cry_chance']/100:self.log(self.rng.choice(spec['battle_cries']),'combat')
        if self.rng.random()>self.w['settings']['hit_chance']:self.log(name+' misses you.','combat');return
        dodge=self.w['classes'][self.p['class']].get('dodge',0)
        if dodge and self.rng.random()<dodge/100:self.log('You dodge '+name+"'s attack.",'combat');return
        protection=[self.ensure_magic_slot(slot) for slot,i in self.p['equipment'].items() if slot in BODY_SLOTS or self.item(i).get('shield')]
        armor=sum(self.item(i).get('armor',0) for i in protection)
        damage=self.warded_damage(max(1,self.rng.randint(*spec['damage'])-armor));self.p['hp']=max(0,self.p['hp']-damage)
        self.log(f'{name} hits you for {damage}.','danger')
        self.train_magic_items(protection,self.practice_multiplier(e))
        if self.p['hp']==0:self.death()
        else:self.apply_effects(spec.get('status_effects',[]),self.p)

    def victory(self,e):
        c=self.p['combat'];name=self.creature_name(e)
        super().victory(e)
        self.award_rare_drop(e)
        e['effects']=[]
        if not e.get('released'):
            e['respawn_at']=self.clock()+self.spawn_rule(e).get('delay',60)
        self.state['corpses'].append(dict(uid=e['uid'],type=e['type'],name=name,room=e['location'],
            description=self.rng.choice(CORPSE_DESCRIPTIONS).format(name=name),released=e.get('released',False),
            expires=self.clock()+self.rules()['corpse_seconds']))
        self.p['combat']=c;self.retarget()

    def enemy_corpses_here(self):
        return [c for c in self.state['corpses'] if c['room']==self.p['room'] and c['expires']>self.clock() and not c.get('harvested')]

    def corpse_description(self,corpse):
        # Old saves have remains without a description; keep LOOK read-only.
        return corpse.get('description') or CORPSE_DESCRIPTIONS[0].format(name=corpse['name'])

    def corpse_harvestable(self,corpse):
        return not corpse.get('released') and bool(self.w['enemies'][corpse['type']].get('harvest'))

    def death(self):
        self.p.pop('ward',None)
        if self.rules()['player_bodies']:
            self.leave_player_body();return
        inventory=set(self.p['inventory']);self.p['effects']=[];self.p.pop('target',None)
        super().death()
        for lost in inventory-set(self.p['inventory']):
            if self.state['instances'].get(lost,{}).get('kind') in ('weapon','armor'):self.state['instances'].pop(lost)

    def knockout(self,target,skill_id='knockout'):
        old_target=self.p.get('target')
        if target:self.p['target']=self.find_creature(target)['uid']
        c=self.p['combat'];e=self.enemy()
        try:super().knockout('',skill_id)
        except ValueError:
            if old_target is None:self.p.pop('target',None)
            else:self.p['target']=old_target
            raise
        if e and e.get('unconscious'):
            e['effects']=[];self.p['combat']=c;self.retarget()
            if self.p['combat']:self.log('Other opponents are still fighting.','danger')

    def activate_skill(self,sid,target=''):
        if any(self.w['status_effects'][s['id']]['kind']=='stun' for s in self.p.get('effects',[])):raise ValueError('You are stunned. Wait for the effect to expire before using a skill.')
        skill=self.require_skill(sid);kind=skill.get('effect','damage')
        cost=self.require_mana(sid)
        if kind in ('enchant','sharpen'):
            self.work_weapon(sid,kind,target);self.spend_mana(cost,self.affinity(sid)['practice']);return
        remaining=self.p['cooldowns'].get(sid,0)-self.clock()
        if remaining>0:raise ValueError(f'{skill["name"]} is ready in {math.ceil(remaining)} seconds.')
        remaining=self.p.get('action_ready',0)-self.clock()
        if remaining>0:raise ValueError(f'Recover before using another combat skill: {math.ceil(remaining)} seconds.')
        if kind=='damage':
            if not self.visible():raise ValueError('It is too dark to choose a target. Carry a light.')
            if not self.p['combat'] and not skill.get('initiates'):
                raise ValueError(skill['name']+' needs an active fight. ATTACK first.')
            e=self.find_creature(target) if target else self.enemy()
            if not e:raise ValueError('There is no visible target here.')
            if self.w['rooms'][self.p['room']].get('safe'):raise ValueError('You cannot attack in this safe place.')
            self.p['target']=e['uid']
            self.start_combat()
            if e['uid'] not in self.p['combat']['engaged']:self.p['combat']['engaged'].append(e['uid'])
        elif kind=='heal' and target:
            raise ValueError('Healing skills affect you. Use CAST '+sid+' without a target.')
        self._active_skill=sid
        practice=self.skill_practice(sid,target)
        try:
            super().activate_skill(sid,target)
            self.spend_mana(cost,practice)
            self.p['action_ready']=self.clock()+self.rules()['action_recovery']
        finally:self._active_skill=None

    def work_weapon(self,sid,kind,target=''):
        if kind=='enchant':self.enchant_item(sid,target);return
        if self.p['combat']:raise ValueError('Finish combat before working on a weapon.')
        iid=self.p['equipment'].get('weapon')
        if not iid or self.item(iid)['kind']!='weapon':raise ValueError('Equip a weapon in your right hand first.')
        skill=self.require_skill(sid);rules=self.rules()
        remaining=self.p['cooldowns'].get(sid,0)-self.clock()
        if remaining>0:raise ValueError(f'{skill["name"]} is ready in {math.ceil(remaining)} seconds.')
        inst=self.state['instances'].get(iid,{})
        if not inst:
            iid=self.new_instance(dict(kind='weapon',item=iid,rank=0,bonus=0));self.p['equipment']['weapon']=iid;inst=self.state['instances'][iid]
        self.p['cooldowns'][sid]=self.clock()+skill['cooldown']
        if kind=='sharpen':
            inst.update(sharpen_bonus=rules['sharpen_bonus'],sharpen_until=self.clock()+rules['sharpen_seconds'])
            self.log(f'Your weapon gains {rules["sharpen_bonus"]} damage for {rules["sharpen_seconds"]:g} seconds.','reward');return

    def equip_hand(self,target):
        if self.p['combat']:raise ValueError('Finish the fight before rearranging equipment.')
        hand='weapon';explicit_hand=False
        for suffix,slot in [(' in left hand','left_hand'),(' left','left_hand'),(' in right hand','weapon'),(' right','weapon')]:
            if target.endswith(suffix):target=target[:-len(suffix)];hand=slot;explicit_hand=True;break
        iid=self.match(target,self.p['inventory']);spec=self.item(iid);eq=self.p['equipment'];proposed=dict(eq)
        self.require_item_use(spec)
        if spec['kind']=='armor' and not explicit_hand:hand='left_hand' if spec.get('shield') else spec.get('armor_slot','armor')
        elif spec['kind'] not in ('weapon','armor'):raise ValueError('Only weapons, armor and shields can be equipped.')
        proposed[hand]=iid
        self.validate_hands(proposed,self.w)
        self.p['inventory'].remove(iid)
        if hand in eq:self.p['inventory'].append(eq[hand])
        eq[hand]=iid;self.ensure_magic_slot(hand);self.log('Equipped '+spec['name']+' in '+SLOT_NAMES[hand]+'.')

    def validate_hands(self,eq,w):
        def spec(i):
            template=self.state['instances'].get(i,{}).get('item',i)
            if template not in w['items']:raise ValueError('Cannot remove an equipped item type.')
            return w['items'][template]
        right=spec(eq['weapon']) if eq.get('weapon') else {};left=spec(eq['left_hand']) if eq.get('left_hand') else {}
        if right and right['kind'] not in ('weapon','armor'):raise ValueError('Right hand requires a weapon or armor.')
        if set(eq)-set(SLOT_NAMES):raise ValueError('Unknown equipment slot.')
        for slot in BODY_SLOTS:
            if eq.get(slot):
                worn=spec(eq[slot])
                if worn['kind']!='armor' or worn.get('shield') or worn.get('armor_slot','armor')!=slot:raise ValueError('That armor does not fit the '+SLOT_NAMES[slot]+' slot.')
        if right.get('shield') and left.get('shield'):raise ValueError('Only one shield can be equipped at a time.')
        if left and left['kind'] not in ('weapon','armor'):raise ValueError('Left hand requires a weapon or armor.')
        if left and (right.get('hands',1)==2 or left.get('hands',1)==2):raise ValueError('Two-handed weapons require an empty left hand and must go in the right hand.')
        rules={**DEFAULT_RULES,**w.get('revision',{})}
        if right.get('kind')=='weapon' and left.get('kind')=='weapon' and (self.p['level']<rules['dual_level'] or self.p['class'] not in rules['dual_classes']):raise ValueError('Dual wielding requires two one-handed weapons, an eligible class and the configured unlock level.')

    def look(self,target):
        if target=='cookbook':
            self.show_cookbook();return
        self.remember_room()
        if target=='self':
            self.show_equipment();return
        if self.is_body_reference(target):
            self.show_player_body(target);return
        parts=target.split();direction=DIRECTIONS.get(parts[0],parts[0]) if parts else ''
        if direction in ('north','south','east','west','up','down'):
            if len(parts)>2 or len(parts)==2 and not parts[1].isdigit():raise ValueError('Use LOOK NORTH 2 (a positive whole distance).')
            distance=int(parts[1]) if len(parts)==2 else 1
            if not 1<=distance<=self.rules()['perception_distance']:raise ValueError('That distance is beyond your perception limit.')
            rid=self.p['room'];penalty=0;sight_budget=distance
            for step in range(1,distance+1):
                r=self.w['rooms'][rid]
                if not self.visible(rid):self.log('Darkness blocks your view. A carried lantern would help.');return
                sight_budget=min(sight_budget,r.get('sight_limit',20))
                if sight_budget<=0:self.log('Terrain or an obstruction blocks the view farther ahead.');return
                dest=r['exits'].get(direction)
                if not dest:self.log('There is no exit that way.' if step==1 else 'The route bends or ends beyond your view.');return
                adjacent=self.w['rooms'][dest]
                if adjacent.get('obscured_from_outside'):self.log(adjacent.get('obscured_message','').strip() or 'It is too dark; you cannot see anything.','story');return
                if not self.visible(dest):self.log('Darkness blocks your view. A carried lantern would help.');return
                penalty=max(penalty,self.fog_at(rid),self.fog_at(dest))
                chance=self.rules()['perception_chance']+(self.p['level']-1)*self.rules()['perception_per_level']+self.w['races'][self.p['race']].get('perception_bonus',0)-(step-1)*self.rules()['perception_distance_penalty']-penalty
                if (step>1 or penalty) and self.rng.random()>=max(0,min(100,chance))/100:self.log('You make out only indistinct shapes farther '+direction+'.');return
                # Observation never creates a spawn or rolls an encounter.
                enemies=self.creatures(dest,False,False)
                self.log(f'To the {direction} ({step}): {adjacent["name"]}. {adjacent["description"]}'+(' You see '+', '.join(self.creature_name(e) for e in enemies)+'.' if enemies else ''),'story');rid=dest;sight_budget-=1
            return
        if target and self.visible():
            npcs=[n for n in self.w.get('npcs',{}).values() if n['room']==self.p['room'] and target==n['name'].casefold()]
            if npcs:
                n=npcs[0]
                if 'look' not in n.get('interactions',['look','talk']):raise ValueError('That person keeps their distance.')
                self.log(n.get('appearance','')+'\n'+n.get('description',''),'story');return
            rows=self.creatures()
            if any(target==e['uid'] or target in self.creature_name(e).casefold() for e in rows):
                e=self.find_creature(target,rows);self.log(self.creature_name(e)+': '+self.w['enemies'][e['type']]['description'],'story');return
        super().look(target)
        if not target:
            for body in self.bodies_here():
                self.log(f'{body["name"]} lies here. Disappears in {math.ceil(body["expires"]-self.clock())} seconds. LOOK BODY {body["number"]}; GET ALL FROM BODY {body["number"]}.')
        if not target:
            region=self.region_for(self.p['room'])[1]
            if region:self.log('Weather: '+region.get('weather','clear')+f'. Visibility penalty: {self.fog_at(self.p["room"]):g}%.')
        if not target and self.visible():
            rows=self.creatures(self.p['room'],True)
            if rows:self.log('Creatures here: '+', '.join(self.creature_name(e)+(' (unconscious)' if e.get('unconscious') else f' ({e["hp"]} HP)') for e in rows)+'.')
            for corpse in self.enemy_corpses_here():self.log(self.corpse_description(corpse),'story')
            for n in self.w.get('npcs',{}).values():
                if n['room']==self.p['room']:self.log(n['name']+' is here. '+n.get('appearance',''))
            if self.w['rooms'][self.p['room']].get('cooking_fire'):self.log('A cooking fire is ready. COOK <recipe or ingredient>.')

    def talk(self,target):
        if ' to ' not in target:return super().talk(target)
        phrase,who=target.rsplit(' to ',1)
        if not self.visible():raise ValueError('You cannot see who is here.')
        people=[n for nid,n in self.w.get('npcs',{}).items() if n['room']==self.p['room'] and who in (nid,n['name'].casefold())]
        if people:
            if len(people)!=1:raise ValueError('Use a unique NPC name.')
            n=people[0]
            if 'talk' not in n.get('interactions',['look','talk']):raise ValueError('They are not available to talk.')
            normalized=' '.join(phrase.strip('"').casefold().split());rule=next((r for r in n.get('dialogue',[]) if ' '.join(r['phrase'].casefold().split())==normalized),None)
            self.log(rule['response'] if rule else n.get('default_response') or n['name']+' gives no reply.','story');return
        # Use descriptors for free creatures while retaining numbered-cage commands.
        rows=self.creatures()
        if any(who==e['uid'] or who==e['type'] or who in self.creature_name(e).casefold() for e in rows):
            e=self.find_creature(who,rows);self.p['target']=e['uid'];who=e['type']
        return super().talk(phrase+' to '+who)

    def harvest(self,target):
        if self.p['combat']:raise ValueError('Finish combat before harvesting.')
        if not self.visible():raise ValueError('It is too dark to harvest.')
        rows=[c for c in self.enemy_corpses_here() if self.corpse_harvestable(c)]
        if target:rows=[c for c in rows if target in (c['uid'],c['type']) or target in c['name'].casefold()]
        if len(rows)!=1:raise ValueError('Specify which remains to harvest: '+(', '.join(c['name'] for c in rows) or 'none here')+'.')
        corpse=rows[0];yields=[x['item'] for x in self.w['enemies'][corpse['type']].get('harvest',[]) for _ in range(x.get('count',1))]
        self.p['inventory'].extend(self.grant(i) for i in yields);corpse['harvested']=True
        self.log('Harvested: '+', '.join(self.w['items'][i]['name'] for i in yields)+'.','reward')

    def show_cookbook(self):
        recipes=self.w.get('recipes',{})
        self.log('COOKBOOK\nUse COOK <recipe name> to prepare a meal. HELP COOKBOOK explains the entries.')
        if not recipes:
            self.log('There are no recipes in your cookbook yet.');return
        inv=self.p['inventory']
        fire=self.w['rooms'][self.p['room']].get('cooking_fire',False)
        for rid,r in recipes.items():
            ingredient=self.w['items'][r['input']];output=self.w['items'][r['output']]
            count=r.get('count',1);have=inv.count(r['input']);missing=[]
            lines=[r['name'],f'Ingredients: {count} × {ingredient["name"]} (carrying {have}).',
                   f'Makes: {r.get("output_count",1)} × {output["name"]}.']
            if output.get('food'):
                lines.append(f'Food: restores up to {output.get("heal",0):g} HP per serving.')
            if have<count:missing.append('not enough ingredients')
            if r.get('fire',True):
                lines.append('Cooking fire: required — '+('available here.' if fire else 'not here.'))
                if not fire:missing.append('a cooking fire')
            else:lines.append('Cooking fire: not required.')
            if r.get('tool'):
                carried=r['tool'] in inv
                lines.append('Tool: '+self.w['items'][r['tool']]['name']+(' (carried).' if carried else ' (not carried).'))
                if not carried:missing.append('the required tool')
            if r.get('skill'):
                try:
                    self.require_skill(r['skill'])
                    lines.append('Skill: '+self.w['skills'][r['skill']]['name']+' (ready).')
                except ValueError as error:
                    lines.append('Skill: '+str(error));missing.append('the required skill')
            chance=r.get('chance',100)
            lines.append(f'Success chance: {chance:g}%.'+(' On failure, ingredients are '+('consumed.' if r.get('consume_failure') else 'kept.') if chance<100 else ''))
            if self.p['combat']:missing.append('finish combat')
            lines.append('Not ready: '+', '.join(missing)+'.' if missing else 'Ready to cook.')
            # Use the display name unless another recipe makes it ambiguous.
            name=r['name'].casefold()
            matches=[other for key,other in recipes.items() if name in (key,other['name'].casefold(),other['input'],self.w['items'][other['input']]['name'].casefold())]
            lines.append('COOK '+(r['name'] if len(matches)==1 else rid).upper())
            self.log('\n'.join(lines))

    def cook(self,target):
        if self.p['combat']:raise ValueError('Finish combat before cooking.')
        recipes=self.w.get('recipes',{});matches=[r for rid,r in recipes.items() if target in (rid,r['name'].casefold(),r['input'],self.w['items'][r['input']]['name'].casefold())]
        if len(matches)!=1:raise ValueError('Use COOK <recipe name>: '+', '.join(r['name'] for r in recipes.values())+'. LOOK COOKBOOK shows ingredients and requirements.')
        r=matches[0];inv=self.p['inventory']
        if r.get('fire',True) and not self.w['rooms'][self.p['room']].get('cooking_fire'):raise ValueError('You need a cooking fire.')
        if r.get('skill'):self.require_skill(r['skill'])
        if r.get('tool') and r['tool'] not in inv:raise ValueError('Carry the required cooking tool.')
        count=r.get('count',1);output_count=r.get('output_count',1)
        if inv.count(r['input'])<count:raise ValueError('You do not have enough ingredients.')
        success=self.rng.random()<r.get('chance',100)/100
        if success or r.get('consume_failure'):
            for _ in range(count):inv.remove(r['input'])
        if success:inv.extend(self.grant(r['output']) for _ in range(output_count));self.log(r.get('message') or 'Your meal is ready.','reward')
        else:self.log('Cooking fails. '+('The ingredients are spoiled.' if r.get('consume_failure') else 'The ingredients are saved.'))

    def extra_command(self,verb,target):
        if verb in ('target','attack'):
            if not self.visible():raise ValueError('It is too dark to choose a target. Carry a light.')
            e=self.find_creature(target) if target else self.enemy()
            if not e:raise ValueError('There is nothing here to attack.')
            self.p['target']=e['uid']
            if verb=='attack':self.start_combat()
            if self.p['combat'] and e['uid'] not in self.p['combat']['engaged']:self.p['combat']['engaged'].append(e['uid'])
            self.log('Target: '+self.creature_name(e)+'.','combat');return True
        if verb=='equip':self.equip_hand(target);return True
        if verb=='hold':
            if not target.endswith((' left',' right',' in left hand',' in right hand')):target+=' left'
            self.equip_hand(target);return True
        if verb=='unequip':
            if self.p['combat']:raise ValueError('Finish the fight before rearranging equipment.')
            slot=SLOT_ALIASES.get(target,target)
            eq=self.p['equipment']
            if slot not in eq:raise ValueError('That equipment slot is empty.')
            proposed=dict(eq);proposed.pop(slot);self.validate_hands(proposed,self.w)
            self.p['inventory'].append(eq.pop(slot));self.log('Equipment returned to your bag.');return True
        if verb in ('enchant','enchanting','sharpen','sharpening','charge','fireball','lightning','mend','backstab','quickstrike','hamstring','kick','frostbolt','power_strike','cutthroat','arcane_lance','shattering_strike','nerve_strike','meteor','executioner','assassinate'):
            sid={'enchant':'enchanting','sharpen':'sharpening'}.get(verb,verb);self.activate_skill(sid,target);return True
        if verb=='harvest':self.harvest(target);return True
        if verb=='cook':self.cook(target);return True
        if verb in ('use','quaff','eat','recall'):
            if verb=='recall':
                candidates=[i for i in self.p['inventory'] if self.item(i).get('recall')]
                if not candidates:raise ValueError('You need a recall scroll.')
                iid=candidates[0]
            else:iid=self.match(target,self.p['inventory'])
            item=self.item(iid)
            self.require_item_use(item)
            if item.get('recall'):
                rules=self.rules();level=self.p['level']
                if level>=rules['recall_disabled_from_level']:
                    raise ValueError(f'Recall scrolls cannot be used at level {rules["recall_disabled_from_level"]} or above. The scroll is preserved.')
                reusable=level<rules['recall_reusable_below_level']
                blocked=self.p['combat'] or self.w['rooms'][self.p['room']].get('recall_disabled')
                if blocked:
                    consumes=rules['recall_failure_consumes'] and not reusable
                    if consumes:self.p['inventory'].remove(iid)
                    raise ValueError('Recall is blocked during combat or in this room. '+('The scroll is consumed.' if consumes else 'The scroll is preserved.'))
                if not reusable:self.p['inventory'].remove(iid)
                self.p['room']=self.w['starting']['room'];self.p.pop('target',None)
                self.log(('The scroll remains ready to use again.' if reusable else 'The scroll dissolves.')+' You return to the center of town.','story')
                self.look('');return True
            if item.get('food'):
                if self.p['combat'] and not self.rules()['food_in_combat']:raise ValueError('Finish combat before eating.')
                if self.p['cooldowns'].get('food',0)>self.clock():raise ValueError('Wait before eating another meal.')
                if self.p['hp']>=self.max_hp():raise ValueError('You already have full health. Save your food.')
                amount=min(item.get('heal',0),self.max_hp()-self.p['hp']);self.p['hp']+=amount;self.p['inventory'].remove(iid);self.p['cooldowns']['food']=self.clock()+self.rules()['food_cooldown'];self.log(f'You eat {item["name"]} and recover {amount} HP.','reward');return True
            if verb=='eat':raise ValueError('That item is not food.')
        if verb=='get' and self.visible():
            rows=[e for e in self.creatures(unconscious=True) if e.get('unconscious')]
            matches=[e for e in rows if target==e['uid'] or target==e['type'] or target and target in self.creature_name(e).casefold()]
            if matches:
                e=self.find_creature(target,rows)
                if self.p['combat']:raise ValueError('Finish combat before picking up a creature.')
                self.p['inventory'].append(self.new_instance(dict(kind='captive',enemy=e['type'])));e['hp']=0;e['unconscious']=False;e['respawn_at']=self.clock()+self.spawn_rule(e).get('delay',60);self.log('You pick up the unconscious creature. No kill rewards are awarded.');return True
        return super().extra_command(verb,target)

    def snapshot(self):
        with self.lock:
            return self.revision_snapshot()

    def revision_snapshot(self):
        result=super().snapshot()
        rules=self.rules()
        result['recall_rules']=dict(reusable_below=rules['recall_reusable_below_level'],disabled_from=rules['recall_disabled_from_level'],starting_scroll=any(self.w['items'][iid].get('recall') for iid in self.w['starting']['inventory']))
        if not self.p:return result
        rows=self.creatures();light=self.visible()
        result['enemies']=[dict(id=e['uid'],name=self.creature_name(e),hp=e['hp'],max_hp=self.w['enemies'][e['type']]['hp'],aggressive=self.w['enemies'][e['type']]['aggressive'],level=self.w['enemies'][e['type']].get('level',1),target=e['uid']==self.p.get('target'),engaged=e['uid'] in (self.p.get('combat') or {}).get('engaged',[]),effects=copy.deepcopy(e['effects'])) for e in rows] if light else []
        chosen=self.enemy()
        if chosen and light:result['enemy']['name']=self.creature_name(chosen)
        result['unconscious_creatures']=[dict(id=e['uid'],name=self.creature_name(e)) for e in self.creatures(unconscious=True) if e.get('unconscious')] if light else []
        result['npcs']=[dict(name=n['name'],appearance=n.get('appearance','')) for n in self.w.get('npcs',{}).values() if n['room']==self.p['room']] if light else []
        result['corpses']=[dict(id=c['uid'],name=c['name'],description=self.corpse_description(c),harvestable=self.corpse_harvestable(c)) for c in self.enemy_corpses_here()] if light else []
        result['player_bodies']=[dict(id=b['id'],name=b['name'],expires=b['expires'],items=len(b['items']),gold=b['gold'],owned=b['owner']==self.p['id']) for b in self.bodies_here()]
        result['status_effects']=self.w.get('status_effects',{})
        region=self.region_for(self.p['room'])[1]
        result['room']['weather']=region.get('weather','clear')
        result['room']['fog']=self.fog_at(self.p['room'])
        if region:result['room']['region']=region['name']
        result['player']['hands']={'right':self.p['equipment'].get('weapon'),'left':self.p['equipment'].get('left_hand')}
        result['player']['enchanting']={sid:self.enchant_progress(sid) for sid,s in self.w['skills'].items() if s.get('effect')=='enchant'}
        return result

    def check_live_references(self,w):
        super().check_live_references(w)
        self.check_body_references(w)
        self.check_region_references(w)
        if self.p:self.validate_hands(self.p['equipment'],w)
        for inst in self.state.get('instances',{}).values():
            if inst['kind'] in ('weapon','armor') and w['items'].get(inst['item'],{}).get('kind')!=inst['kind']:raise ValueError('Cannot remove or change an individually modified equipment type.')
        actors=([self.p] if self.p else [])
        for rid in self.w['rooms']:actors+=self.creatures(rid,True,False)
        for actor in actors:
            if actor is not self.p and (actor['type'] not in w['enemies'] or actor['location'] not in w['rooms'] or actor['home'] not in w['rooms']):raise ValueError('Cannot remove a living creature type or its current/home room.')
            if actor is not self.p and w['rooms'][actor['location']].get('safe'):raise ValueError('Cannot mark an occupied enemy location safe.')
            for effect in actor.get('effects',[]):
                if effect['id'] not in w.get('status_effects',{}):raise ValueError('Cannot remove an active status effect.')
        for home,slots in self.state.get('populations',{}).items():
            new_rules={r['id']:r for r in w['rooms'].get(home,{}).get('population',[])}
            for key,slot in slots.items():
                e=slot['creature'];group,index=key.rsplit(':',1)
                if e and e['hp']>0 and (group not in new_rules or int(index)>=new_rules[group].get('count',1)):raise ValueError('Cannot remove an occupied spawn slot. Defeat or capture its creature first.')
        for c in self.state.get('corpses',[]):
            if c['expires']>self.clock() and not c.get('harvested') and (c['type'] not in w['enemies'] or c['room'] not in w['rooms']):raise ValueError('Cannot remove creature types or rooms with enemy corpses.')
