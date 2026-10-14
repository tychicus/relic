'use strict';
const assert=require('node:assert/strict');
const {makeEntry,uniqueId}=require('../ui/src/lib/editor-helpers.cjs');
const world={rooms:{},items:{},enemies:{},races:{},classes:{},skills:{}};
for(const [kind,group] of Object.entries({room:'rooms',weapon:'items',armor:'items',consumable:'items',light:'items',loot:'items',enemy:'enemies',race:'races',class:'classes',skill:'skills'})) {
 const result=makeEntry(world,kind,"Nick's Silver Sword!");
 assert.equal(result.group,group);assert.equal(result.entry.name,"Nick's Silver Sword!");assert.match(result.id,/^[a-z][a-z0-9_]*$/);
 if(group==='items')assert.equal(result.entry.kind,kind);
 world[group][result.id]=result.entry;
}
assert.equal(makeEntry(world,'weapon','New Blade').entry.damage,1);
assert.equal(makeEntry(world,'armor','New Armor').entry.armor,1);
assert.equal(makeEntry(world,'consumable','Healing').entry.heal,20);
assert.equal(makeEntry(world,'enemy','Goblin').entry.dodge,0);
const region=makeEntry(world,'region','Misty Forest');
assert.equal(region.group,'regions');assert.equal(region.entry.weather,'clear');
assert.equal(region.entry.max_population,0);assert.equal(region.entry.max_per_room,3);
assert.deepEqual(region.entry.spawn_rooms,[]);assert.deepEqual(region.entry.pool,[]);
const a=makeEntry(world,'room','Misty Forest');world.rooms[a.id]=a.entry;
const b=makeEntry(world,'room','Misty Forest');assert.notEqual(a.id,b.id);assert.equal(world.rooms[a.id],a.entry);
for(const name of ['123 Tower','Étoile','神殿','!!!','constructor','__proto__','A'.repeat(120)]) {
 const result=makeEntry(world,'room',name);assert.match(result.id,/^[a-z][a-z0-9_]*$/);assert.notEqual(result.id,'constructor');assert.equal(result.entry.name,name);
}
assert.throws(()=>makeEntry(world,'room','   '));assert.throws(()=>makeEntry(world,'unknown','Example'));
console.log('Editor creation checks passed: types, stats, normal names, duplicate names, accents, non-Latin names, and reserved keys.');
