"""Shared authoring schema and strict validation for the v0.5 additions."""
import math

def number(label, default, low=0, high=10000, integer=False):
    return dict(type='number', label=label, default=default, min=low, max=high, integer=integer)

def text(label, default=''):
    return dict(type='text', label=label, default=default)

def boolean(label, default=False):
    return dict(type='boolean', label=label, default=default)

def choice(label, choices, default):
    return dict(type='choice', label=label, choices=choices, default=default)

def reference(label, group, optional=False):
    return dict(type='ref', label=label, group=group, optional=optional)

def rows(label, fields):
    return dict(type='rows', label=label, fields=fields, default=[])

def selections(label, group):
    return dict(type='refs', label=label, group=group, default=[])

ATTACHMENT = dict(effect=reference('Status effect', 'status_effects'), chance=number('Application chance (%)',100,0,100), duration=number('Duration (pulses; 0 uses effect default)',0,0,100,True))
SPAWN = dict(id=text('Permanent spawn rule ID','group'), enemy=reference('Fixed / initial creature','enemies',True), count=number('Number of spawn slots',1,1,12,True), pool=rows('Weighted random alternatives',dict(enemy=reference('Creature','enemies'),weight=number('Weight',1,.001,100000))), chance=number('Chance per attempt (%; failure spawns nothing)',100,0,100), trigger=choice('Attempt trigger',['timer','entry'],'timer'), respawn=boolean('Respawn after defeat or capture',True), delay=number('Respawn / retry delay (seconds)',60,1,86400), roam=boolean('Allow roaming'), roam_seconds=number('Seconds between moves',30,2,86400), roam_rooms=selections('Permitted roaming destinations (empty stays home)','rooms'))
SCHEMA = {
 'revision': {
  'dual_level':number('Dual wield unlock level',3,1,100,True),
  'dual_classes':selections('Classes allowed to dual wield','classes'),
  'offhand_scale':number('Offhand weapon damage contribution',.35,0,1),
  'dual_hit_penalty':number('Dual wield hit chance penalty (fraction)',.10,0,1),
  'perception_distance':number('Maximum look distance',3,1,20,True),
  'perception_chance':number('Base distant perception chance (%)',85,0,100),
  'perception_per_level':number('Perception chance gained per level',2,0,100),
  'perception_distance_penalty':number('Chance penalty for each extra room',20,0,100),
  'food_cooldown':number('Seconds between meals',8,.25,3600),
  'food_in_combat':boolean('Allow eating during combat'),
  'recall_failure_consumes':boolean('Consume recall scroll on a blocked attempt'),
  'corpse_seconds':number('Harvest remains lifetime (seconds)',300,1,86400),
  'enchant_base':number('Enchant success at enchanting level 1 (%)',50,0,100),
  'enchant_level_gain':number('Success percentage gained per enchanting level',2,0,100),
  'enchant_destroy':number('Weapon destruction chance after failure (%)',10,0,100),
  'enchant_damage':number('Weapon damage lost on non-destructive failure',1,0,100,True),
  'enchant_bonus':number('Temporary damage / armor bonus at enchanting level 1',1,1,100,True),
  'enchant_bonus_levels':number('Enchanting levels per additional bonus point',3,1,100,True),
  'enchant_seconds':number('Enchantment duration at enchanting level 1 (seconds)',300,1,86400),
  'enchant_seconds_per_level':number('Extra duration per enchanting level (seconds)',60,0,86400),
  'enchant_cost':number('Gold per valid enchanting attempt',20,0,100000,True),
  'enchant_xp_per_attempt':number('Enchanting XP per valid attempt (success or failure)',1,.01,100),
  'enchant_xp_first':number('XP required to reach enchanting level 2',100,1,100000,True),
  'enchant_xp_step':number('Additional XP required for each later enchanting level',50,0,100000,True),
  'enchant_level_cap':number('Maximum enchanting level',20,1,100,True),
  'sharpen_bonus':number('Temporary sharpening damage bonus',2,1,100,True),
  'sharpen_seconds':number('Sharpening duration (seconds)',120,1,86400)
 },
 'status_effects':dict(description=text('Description'),kind=choice('Mechanical effect',['damage','stun','slow'],'damage'),damage=number('Damage per pulse',2,0,1000,True),duration=number('Default duration (pulses)',3,1,100,True),slow=number('Attack delay multiplier',1.5,1,5),stacking=choice('Repeated applications',['refresh','stack','ignore'],'refresh'),max_stacks=number('Maximum stacks',3,1,10,True),application=text('Application message','{target} is affected by {effect}.'),ongoing=text('Pulse message','{effect} affects {target}.'),expiration=text('Expiration message','{effect} fades from {target}.'),failure=text('Resistance / failed application message','{target} resists {effect}.')),
 'npcs':dict(room=reference('Location','rooms'),appearance=text('Appearance'),description=text('Description'),interactions=selections('Available interactions','npc_interactions'),dialogue=rows('Dialogue rules',dict(phrase=text('Player phrase','hello'),response=text('Response','Hello, traveler.'))),default_response=text('Fallback dialogue','Safe travels.')),
 'recipes':dict(input=reference('Raw ingredient','items'),output=reference('Cooked result','items'),count=number('Ingredients required',1,1,100,True),output_count=number('Items produced',1,1,100,True),fire=boolean('Requires a cooking fire',True),skill=reference('Required skill (optional)','skills',True),tool=reference('Carried tool (optional)','items',True),chance=number('Cooking success chance (%)',100,0,100),consume_failure=boolean('Consume ingredients on failure'),message=text('Success message','Your meal is ready.')),
 'rooms':dict(recall_disabled=boolean('Recall disabled'),cooking_fire=boolean('Cooking fire available'),fog=number('Fog / weather visibility penalty (%)',0,0,100),sight_limit=number('Maximum sight through this room (0 blocks onward view)',20,0,20,True),respawn_enabled=boolean('Legacy enemy respawns',True),spawn_chance=number('Legacy spawn attempt chance (%)',100,0,100),roaming=boolean('Legacy enemy may roam'),roam_seconds=number('Legacy roaming interval (seconds)',30,2,86400),roam_rooms=selections('Legacy enemy roaming destinations','rooms'),population=rows('Additional independent spawn groups',SPAWN)),
 'enemies':dict(status_effects=rows('Status effects on successful attacks',ATTACHMENT),resistances=rows('Status resistance',dict(effect=reference('Effect','status_effects'),chance=number('Resistance (%)',0,0,100))),harvest=rows('Harvest yields',dict(item=reference('Item','items'),count=number('Quantity',1,1,100,True)))),
 'items':dict(hands=choice('Hands required (weapons only)',[1,2],1),shield=boolean('Use this armor as a shield'),food=boolean('Edible food'),recall=boolean('Recall scroll'),status_effects=rows('Status effects on weapon hits',ATTACHMENT)),
 'skills':dict(status_effects=rows('Status effects on successful damage',ATTACHMENT),initiates=boolean('May initiate combat')),
 'races':dict(perception_bonus=number('Perception chance bonus (%)',0,0,100),resistances=rows('Status resistance',dict(effect=reference('Effect','status_effects'),chance=number('Resistance (%)',0,0,100))))
}

SCHEMA['revision']['dual_classes']['default']=['warrior']
DEFAULT_RULES={k:v['default'] for k,v in SCHEMA['revision'].items()}
DEFAULT_RULES['dual_classes']=['warrior']

def validate_revision(w):
    def check(obj, fields, path):
        if not isinstance(obj,dict):raise ValueError(path+' must be a record.')
        for key,s in fields.items():
            if key not in obj:
                if s['type']=='ref' and not s.get('optional'):raise ValueError(path+': choose '+s['label']+'.')
                continue
            v=obj[key]; label=path+': '+s['label']; t=s['type']; ok=True
            if t=='number':ok=type(v) in (int,float) and math.isfinite(v) and s['min']<=v<=s['max'] and (not s['integer'] or type(v) is int)
            elif t=='text':ok=isinstance(v,str) and len(v)<=6000
            elif t=='boolean':ok=type(v) is bool
            elif t=='choice':ok=v in s['choices'] and type(v) is type(s['default'])
            elif t=='ref':ok=isinstance(v,str) and ((s.get('optional') and not v) or v in w.get(s['group'],{}))
            elif t=='refs':
                group={'look':{},'talk':{}} if s['group']=='npc_interactions' else w.get(s['group'],{})
                ok=isinstance(v,list) and all(isinstance(x,str) and x in group for x in v) and len(v)==len(set(v))
            elif t=='rows':
                ok=isinstance(v,list) and len(v)<=100
                if ok:
                    for row in v:check(row,s['fields'],label)
            if not ok:raise ValueError(label+' has an invalid value.')
    check(w.get('revision',{}),SCHEMA['revision'],'Balance')
    for group,fields in SCHEMA.items():
        if group=='revision':continue
        records=w.get(group,{})
        if not isinstance(records,dict):raise ValueError(group+' must be a collection.')
        for ident,obj in records.items():
            if not isinstance(ident,str) or not ident or not isinstance(obj,dict) or not isinstance(obj.get('name'),str) or not obj['name'].strip():raise ValueError(group+' needs a name.')
            check(obj,fields,obj['name'])
    for r in w['rooms'].values():
        ids=[s.get('id') for s in r.get('population',[])]
        if any(not isinstance(i,str) or not i.strip() for i in ids) or len(ids)!=len(set(ids)):raise ValueError('Spawn rule IDs must be nonempty and unique within a room.')
        if r.get('safe') and r.get('population'):raise ValueError('Safe rooms cannot have additional enemy groups.')
        for s in r.get('population',[]):
            if not s.get('enemy') and not s.get('pool'):raise ValueError('A spawn group needs a fixed creature or a pool.')
    for i in w['items'].values():
        if i.get('shield') and i['kind']!='armor':raise ValueError('Only armor can be a shield.')
        if (i.get('food') or i.get('recall')) and i['kind']!='consumable':raise ValueError('Food and recall scrolls must be consumables.')
        if i.get('food') and i.get('recall'):raise ValueError('An item cannot be both food and a recall scroll.')
    for effect in w.get('status_effects',{}).values():
        if effect.get('kind') not in ('damage','stun','slow'):raise ValueError('A status effect requires a mechanical effect type.')
    for npc in w.get('npcs',{}).values():
        phrases=[' '.join(x.get('phrase','').casefold().split()) for x in npc.get('dialogue',[])]
        if '' in phrases or len(phrases)!=len(set(phrases)):raise ValueError('NPC dialogue phrases must be nonempty and unique.')
    return w
