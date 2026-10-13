'use strict';
const assert=require('node:assert/strict'),MapTools=require('../ui/src/lib/map-tools.cjs'),Editor=require('../ui/src/lib/editor-helpers.cjs');
function base(){return {rooms:{square:{name:'Square',description:'A square.',region:'Town',code:'TOWN-001',map_position:[0,0,0],exits:{}}}};}
let w=base();let id=MapTools.addConnected(w,'square','north','Silver Tower','A tall tower.');
assert.equal(w.rooms.square.exits.north,id);assert.equal(w.rooms[id].exits.south,'square');assert.equal(w.rooms[id].code,'TOWN-002');assert.deepEqual(w.rooms[id].map_position,[0,-1,0]);
let before=JSON.stringify(w);assert.throws(()=>MapTools.addConnected(w,'square','north','Other','Other.'),/already/);assert.equal(JSON.stringify(w),before);
id=MapTools.addConnected(w,'square','down','Crypt','A crypt.');assert.deepEqual(w.rooms[id].map_position,[0,0,-1]);assert.equal(w.rooms[id].exits.up,'square');
w.rooms.block={name:'Occupied',description:'Block',region:'Town',code:'TOWN-004',map_position:[1,0,0],exits:{}};before=JSON.stringify(w);assert.throws(()=>MapTools.addConnected(w,'square','east','Other','Other.'),/occupied/);assert.equal(JSON.stringify(w),before);
assert.throws(()=>MapTools.addConnected(w,'square','west','','description'),/name/);assert.throws(()=>MapTools.addConnected(w,'square','sideways','Room','description'),/direction/);
const code=w.rooms.square.code;w.rooms.square.name='Renamed';MapTools.ensureMetadata(w);assert.equal(w.rooms.square.code,code);
w.rooms.new={name:'New',description:'New',exits:{}};MapTools.ensureMetadata(w);assert.ok(w.rooms.new.code);assert.deepEqual(w.rooms.new.map_position,[0,3,0]);
const chest=Editor.makeEntry({items:{}},'chest','Oak Chest');assert.equal(chest.entry.capacity,30);assert.equal(chest.entry.kind,'chest');
console.log('Map checks passed: bidirectional exits, elevations, permanent codes, collision refusal, no overwrite, metadata and chest creation.');
