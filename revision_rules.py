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
  'weight_enabled':boolean('Enforce carrying weight limits',True),
  'rare_drops_enabled':boolean('Enable very rare bonus equipment drops',True),
  'rare_drop_chance':number('Special drop chance per eligible kill (%) — 0.1 means 1 in 1000',.1,0,100),
  'rare_drop_min_level':number('Minimum enemy level for special drops',10,1,100,True),
  'rare_drop_pool':rows('Special equipment pool',dict(item=reference('Drop-only weapon or armor','items'),weight=number('Relative selection weight',1,.001,100000),min_level=number('Minimum enemy level for this item',10,1,100,True))),
  'enemy_heal_enabled':boolean('Wounded enemies recover outside combat',True),
  'enemy_heal_delay':number('Enemy recovery delay after combat / injury (seconds)',20,0,86400),
  'enemy_heal_interval':number('Seconds between enemy healing installments',5,1,3600),
  'enemy_heal_percent':number('Enemy maximum HP recovered per installment (%)',2,0,100),
  'learning_enabled':boolean('Choose abilities with learning points',True),
  'learning_points_per_level':number('Learning points earned per award',1,1,10,True),
  'learning_point_interval':number('Character levels between point awards (5 = levels 5, 10, 15; 1 starts at level 2)',5,1,100,True),
  'learning_rank_bonus':number('Power bonus per additional learned rank (fraction)',.1,0,1),
  'learning_rank_level_gap':number('Additional character levels required per ability rank',5,1,25,True),
  'mana_enabled':boolean('Spells consume mana',True),
  'mana_regen':number('Mana recovered per second outside combat',1,0,100),
  'mana_combat_regen':number('Mana recovered per second in combat',0,0,100),
  'mana_level_cap':number('Mana mastery level cap',100,1,100,True),
  'mana_xp_first':number('Mana practice XP to level 2',100,1,100000,True),
  'mana_xp_step':number('Extra mana XP required per later level',50,0,100000,True),
  'mana_xp_per_use':number('Mana practice XP per valid paid cast',1,1,10000,True),
  'mana_per_practice_level':number('Maximum mana gained per mana mastery level',2,0,1000,True),
  'practice_challenge_bonus':number('Extra practice multiplier for an enemy at or above character level',1,0,10,True),
  'practice_harder_bonus':number('Additional practice multiplier for a harder enemy',1,0,10,True),
  'practice_harder_gap':number('Enemy levels above character for harder bonus',3,1,100,True),
  'action_recovery':number('Recovery between manual combat skills (seconds; 0 disables)',2,0,60),
  'potion_recovery':number('Recovery between healing potions (seconds; 0 disables)',10,0,3600),
  'repair_enabled':boolean('Allow equipment repair',True),
  'repair_anywhere':boolean('Allow repair outside repair shops'),
  'repair_base_cost':number('Repair fee per item (gold)',0,0,100000,True),
  'repair_cost_per_point':number('Repair gold per damage / protection point restored',5,0,100000,True),
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
  'player_bodies':boolean('Leave recoverable player bodies instead of immediate death losses',True),
  'player_body_seconds':number('Player body and belongings lifetime (seconds; 900 = 15 minutes)',900,1,86400),
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
SCHEMA['rooms']['repair_service']=boolean('Equipment repairs available here')
SCHEMA['rooms']['bank_service']=boolean('Bank deposits and withdrawals available here')
SCHEMA['classes']=dict(mana=number('Starting maximum mana',0,0,10000,True),mana_per_level=number('Maximum mana gained per character level',0,0,1000,True),dodge=number('Chance to dodge incoming attacks (%)',0,0,75),flee_bonus=number('Added escape chance (fraction)',0,0,1))
SCHEMA['classes']['description']=text('Class description shown at character creation')
SCHEMA['classes']['requires_magic']=boolean('Class requires a race that can use magic')
SCHEMA['races']['description']=text('Race description shown at character creation')
SCHEMA['races']['magic_allowed']=boolean('Race can use magic (spells, enchanting, magical equipment and scrolls)',True)
SCHEMA['items']['requires_magic']=boolean('Requires magic use (also applies to consumables)')
SCHEMA['items']['drop_only']=boolean('Enemy-drop equipment only — cannot be sold by shops')
SCHEMA['classes']['carry_capacity']=number('Carrying capacity at character level 1 (lb)',60,1,10000)
SCHEMA['classes']['carry_per_level']=number('Extra carrying capacity per character level (lb)',2,0,1000)
SCHEMA['items']['weight']=number('Item weight (lb; containers exclude contents)',0,0,10000)
SCHEMA['items']['armor_slot']=choice('Worn slot (armor = chest; shields use a hand)',['helmet','armor','pants','arms'],'armor')
SCHEMA['enemies']['weight']=number('Creature carrying weight (lb)',10,0,10000)
SCHEMA['enemies']['healing_override']=boolean('Use creature-specific recovery settings below')
SCHEMA['enemies']['heal_delay']=number('Creature recovery delay (seconds; requires override)',20,0,86400)
SCHEMA['enemies']['heal_interval']=number('Creature recovery interval (seconds; requires override)',5,1,3600)
SCHEMA['enemies']['heal_percent']=number('Creature recovery HP percent (0 disables; requires override)',2,0,100)
SCHEMA['classes']['starting_ability']=reference('One starting ability','skills',True)
SCHEMA['classes']['mana_recovery_scale']=number('Mana recovery multiplier',1,0,3)
SCHEMA['classes']['affinities']=rows('Ability strengths and disadvantages',dict(category=choice('Ability category',['martial','arcane','subtle','craft'],'martial'),power=number('Power multiplier',1,.05,3),mana=number('Mana cost multiplier',1,.1,5),practice=number('Practice XP multiplier',1,.1,5)))
SCHEMA['skills']['mana_cost']=number('Mana cost per valid use (0 means no cost)',0,0,10000,True)
SCHEMA['skills']['category']=choice('Ability category',['martial','arcane','subtle','craft'],'martial')
SCHEMA['skills']['learn_cost']=number('Learning points per rank',1,1,20,True)
SCHEMA['skills']['max_rank']=number('Maximum chosen rank',5,1,10,True)
SCHEMA['skills']['passive']=boolean('Passive basic-attack training (no CAST command)')
SCHEMA['enemies']['level']=number('Enemy level (sets challenge practice bonus)',1,1,100,True)
SCHEMA['regions']=dict(
    rooms=selections('Squares in this region (weather applies to all)', 'rooms'),
    spawn_rooms=selections('Enemy spawning and wandering squares (overrides their room spawn rules)', 'rooms'),
    pool=rows('Regional enemy bank',dict(enemy=reference('Enemy','enemies'),weight=number('Relative frequency',1,.001,100000))),
    max_population=number('Maximum living regional enemies (0 disables new spawns)',0,0,200,True),
    max_per_room=number('Maximum creatures in one spawn square',3,1,20,True),
    spawn_seconds=number('Seconds between replacements / attempts',60,1,86400),
    spawn_chance=number('Chance per spawn attempt (%)',100,0,100),
    roam=boolean('Enemies wander between neighboring squares',True),
    roam_seconds=number('Seconds between wandering attempts',30,2,86400),
    weather=choice('Weather',['clear','mist','fog','rain','storm','snow'],'clear'),
    fog=number('Fog / weather visibility penalty (%)',0,0,100))
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
    assigned=set()
    for region in w.get('regions',{}).values():
        members=region.get('rooms',[]);spawn_rooms=region.get('spawn_rooms',[])
        if assigned.intersection(members):raise ValueError('A square may belong to only one region.')
        assigned.update(members)
        if any(rid not in members or w['rooms'][rid].get('safe') for rid in spawn_rooms):raise ValueError('Regional spawn squares must be unsafe squares inside the region.')
        if region.get('max_population',0) and (not spawn_rooms or not region.get('pool')):raise ValueError('An active regional population needs spawn squares and an enemy bank.')
    for cid,cls in w['classes'].items():
        categories=[r['category'] for r in cls.get('affinities',[])]
        if len(categories)!=len(set(categories)):raise ValueError('A class may define each ability affinity only once.')
        starter=cls.get('starting_ability')
        if starter:
            skill=w['skills'][starter]
            if skill.get('unlock_level',1)!=1:raise ValueError('A starting ability must unlock at character level 1.')
            if skill.get('allowed_classes') is not None and cid not in skill.get('allowed_classes',[]):raise ValueError('Starting ability must allow its class.')
            if skill.get('allowed_races') is not None:raise ValueError('Starting abilities must allow every playable race.')
    for skill in w['skills'].values():
        if skill.get('passive') and skill.get('effect','damage')!='damage':raise ValueError('Passive training must use the damage effect.')
    for i in w['items'].values():
        if i.get('drop_only') and i['kind'] not in ('weapon','armor'):raise ValueError('Drop-only special equipment must be a weapon or armor.')
        if i.get('shield') and i['kind']!='armor':raise ValueError('Only armor can be a shield.')
        if (i.get('food') or i.get('recall')) and i['kind']!='consumable':raise ValueError('Food and recall scrolls must be consumables.')
        if i.get('food') and i.get('recall'):raise ValueError('An item cannot be both food and a recall scroll.')
    pool=w.get('revision',{}).get('rare_drop_pool',[])
    if len({row['item'] for row in pool})!=len(pool):raise ValueError('Each item may appear only once in the special equipment pool; adjust its weight instead.')
    for row in pool:
        if not w['items'][row['item']].get('drop_only'):raise ValueError('Special equipment pool entries must have enemy-drop equipment only enabled.')
    for room in w['rooms'].values():
        if any(w['items'][iid].get('drop_only') for iid in room.get('shop',[])):
            raise ValueError('Shops cannot stock drop-only special equipment. Remove it from '+room['name']+'.')
    for effect in w.get('status_effects',{}).values():
        if effect.get('kind') not in ('damage','stun','slow'):raise ValueError('A status effect requires a mechanical effect type.')
    for npc in w.get('npcs',{}).values():
        phrases=[' '.join(x.get('phrase','').casefold().split()) for x in npc.get('dialogue',[])]
        if '' in phrases or len(phrases)!=len(set(phrases)):raise ValueError('NPC dialogue phrases must be nonempty and unique.')
    return w
