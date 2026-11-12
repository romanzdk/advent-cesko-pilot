import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
const source=await readFile(new URL('../site/helpers.js',import.meta.url),'utf8');
const {filterEvents}=await import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`);
test('pilot region filter isolates the selected region',()=>{
 const base={title:'Vánoční trhy',town:'Plasy',date:'2026-11-28',startTime:'16:00',endDate:null};
 const events=[{...base,id:'a',region:'Plzeňský kraj'},{...base,id:'b',town:'Kuřim',region:'Jihomoravský kraj'}];
 assert.deepEqual(filterEvents(events,{region:'Plzeňský kraj'}).map(e=>e.id),['a']);
 assert.equal(filterEvents(events,{}).length,2);
});
