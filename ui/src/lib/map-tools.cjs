'use strict';
(function(root){
 const directions={north:[0,-1,0],south:[0,1,0],east:[1,0,0],west:[-1,0,0],up:[0,0,1],down:[0,0,-1]};
 const opposite={north:'south',south:'north',east:'west',west:'east',up:'down',down:'up'};
 function prefix(region){return ({Town:'TOWN','Coppergrass Prairie':'PRA','Coppergrass Road':'ROAD','Relic Caverns':'CAVE'})[region]||region.toUpperCase().replace(/[^A-Z0-9]/g,'').slice(0,8)||'AREA';}
 function nextCode(world,region){let pre=prefix(region);if(!/^[A-Z]/.test(pre))pre='AREA'+pre;const used=new Set(Object.values(world.rooms).map(r=>r.code));let n=1;while(used.has(pre+'-'+String(n).padStart(3,'0')))n++;return pre+'-'+String(n).padStart(3,'0');}
 function ensureMetadata(world){
  const used=new Set(Object.values(world.rooms).filter(r=>r.map_position).map(r=>r.map_position.join(',')));
  for(const r of Object.values(world.rooms)){
   r.region=r.region||'Unsorted';if(!r.code)r.code=nextCode(world,r.region);
   if(!r.map_position){let x=0;while(used.has([x,3,0].join(',')))x++;r.map_position=[x,3,0];used.add(r.map_position.join(','));}
  }
 }
 function addConnected(world,sourceId,direction,name,description){
  const source=world.rooms[sourceId];if(!source)throw new Error('Choose an existing room.');
  if(!directions[direction])throw new Error('Choose a direction.');
  if(source.exits[direction])throw new Error('That exit already leads to '+world.rooms[source.exits[direction]].name+'. Open that room instead.');
  name=name.trim();description=description.trim();if(!name||name.length>120||!description)throw new Error('Enter a name (up to 120 characters) and description.');
  const pos=source.map_position.map((v,n)=>v+directions[direction][n]);
  const occupied=Object.values(world.rooms).find(r=>r.map_position&&r.map_position.every((v,n)=>v===pos[n]));
  if(occupied)throw new Error('That position is occupied by '+occupied.code+' — '+occupied.name+'. Use the room exit fields to connect existing rooms.');
  let base=name.normalize('NFKD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[^a-z0-9]+/g,'_').replace(/^_+|_+$/g,'').slice(0,40)||'room';
  if(!/^[a-z]/.test(base)||['constructor','prototype','__proto__'].includes(base))base='room_'+base;
  let id=base,n=2;while(Object.prototype.hasOwnProperty.call(world.rooms,id))id=base+'_'+n++;
  const room={name,description,exits:{[opposite[direction]]:sourceId},objects:{},region:source.region,code:nextCode(world,source.region),map_position:pos};
  world.rooms[id]=room;source.exits[direction]=id;return id;
 }
 const tools={directions,opposite,nextCode,ensureMetadata,addConnected};
 if(typeof module!=='undefined'&&module.exports)module.exports=tools;else root.MapTools=tools;
})(globalThis);
