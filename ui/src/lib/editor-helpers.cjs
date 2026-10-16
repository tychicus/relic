'use strict';
(function(root){
  function uniqueId(name, entries) {
    let base=name.normalize('NFKD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[^a-z0-9]+/g,'_').replace(/^_+|_+$/g,'').slice(0,40) || 'entry';
    if(!/^[a-z]/.test(base)) base='entry_'+base;
    if(['constructor','prototype','__proto__'].includes(base)) base='entry_'+base;
    let id=base, n=2;
    while(Object.prototype.hasOwnProperty.call(entries,id)) id=base+'_'+n++;
    return id;
  }
  function makeEntry(world, kind, rawName) {
    const name=rawName.trim();
    if(!name || name.length>120) throw new Error('Give it a name between 1 and 120 characters.');
    const groups={region:'regions',room:'rooms',enemy:'enemies',weapon:'items',armor:'items',consumable:'items',light:'items',loot:'items',key:'items',cage:'items',chest:'items',race:'races',class:'classes',skill:'skills',npc:'npcs',status_effect:'status_effects',recipe:'recipes',emote:'emotes'};
    const group=groups[kind]; if(!group) throw new Error('Choose what you want to add.');
    const defaults={room:{name,description:'Describe this place.',exits:{},objects:{}},enemy:{name,description:'Describe this creature.',hp:20,dodge:0,damage:[2,4],xp:10,gold:[1,3],aggressive:false,respawn:30,loot:[{item:null,weight:1}]},race:{name,hp_bonus:0},class:{name,hp:65,damage:[4,7],skills:[]},skill:{name,description:'Describe this skill.',cooldown:10,multiplier:1.5,effect:'damage',unlock_level:1,allowed_classes:null,allowed_races:null}};
    let entry=defaults[kind];
    if(kind==='emote') {
      const taken=Object.fromEntries(Object.values(world.emotes||{}).flatMap(e=>[e.command,...(e.aliases||[])]).map(k=>[k,true]));
      entry={name,command:uniqueId('gesture_'+name.slice(0,24),taken),aliases:[],enabled:true,description:'Describe this action.',message:'{actor} gestures.',target_message:'{actor} gestures toward {target}.'};
    }
    if(kind==='region')entry={name,rooms:[],spawn_rooms:[],pool:[],max_population:0,max_per_room:3,spawn_seconds:60,spawn_chance:100,roam:true,roam_seconds:30,weather:'clear',fog:0};
    if(kind==='npc')entry={name,room:Object.keys(world.rooms)[0],appearance:'Describe their appearance.',description:'Describe this person.',interactions:['look','talk'],dialogue:[],default_response:'Hello, traveler.'};
    if(kind==='status_effect')entry={name,description:'Describe this effect.',kind:'damage',damage:2,duration:3,slow:1.5,stacking:'refresh',max_stacks:3,application:'{target} is affected by {effect}.',ongoing:'{effect} affects {target}.',expiration:'{effect} fades from {target}.',failure:'{target} resists {effect}.'};
    if(kind==='recipe')entry={name,input:Object.keys(world.items)[0],output:Object.keys(world.items)[0],count:1,output_count:1,fire:true,chance:100,consume_failure:false,message:'Your meal is ready.'};
    if(group==='items') {entry={name,description:'Describe this item.',kind,price:5};const stat={weapon:'damage',armor:'armor',consumable:'heal'}[kind];if(stat)entry[stat]=kind==='consumable'?20:1;if(kind==='cage'){entry.capacity=5;entry.price=45;entry.protected=true;}if(kind==='chest'){entry.capacity=30;entry.price=60;entry.protected=true;}if(kind==='key'){entry.price=0;entry.protected=true;}}
    world[group]??={};return {group,id:uniqueId(name,world[group]),entry};
  }
  const helpers={uniqueId,makeEntry};
  if(typeof module!=='undefined' && module.exports) module.exports=helpers;
  else root.EditorHelpers=helpers;
})(globalThis);
