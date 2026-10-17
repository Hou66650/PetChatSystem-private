// Execute the real per-frame portal UI: no repeated DOM mutations when idle,
// and no delay or weakened guards at arrival, pairing, cancellation or failure.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const ctx={};vm.runInNewContext(fs.readFileSync('static/js/den/portals.js','utf8'),ctx);
const c=Object.create(ctx.PetPortals.Controller.prototype);
let queries=0,writes=0,disabled=false,label='';
const button={get disabled(){return disabled;},set disabled(v){writes++;disabled=v;},
 get textContent(){return label;},set textContent(v){writes++;label=v;}};
const pet={position:{x:0,z:0}};
Object.assign(c,{q(selector){assert.equal(selector,'[data-confirm]');queries++;return button;},
 getPet:()=>({model:pet}),view:{positions:{desktop:{x:2,z:0}}},intent:null});
function check(expectedDisabled,expectedLabel){c.syncConfirm();assert.equal(disabled,expectedDisabled);assert.equal(label,expectedLabel);}
check(true,'确认出发');const idleWrites=writes;
for(let i=0;i<600;i++)check(true,'确认出发');
assert.equal(queries,1);assert.equal(writes,idleWrites,'idle frames must not touch DOM');
c.intent='desktop';c.approaching=true;check(true,'正在走向门口…');
pet.position.x=2;c.approaching=false;check(false,'确认出发');
pet.position.x=1;check(true,'确认出发');pet.position.x=2;check(false,'确认出发');
for(const key of ['scopeLost','approachError','pending']){
 c[key]=true;check(true,key==='pending'?'正在处理…':'确认出发');c[key]=false;check(false,'确认出发');
}
c.trip={status:'pairing'};check(true,'等待桌面配对');
c.trip.status='active';check(true,'宠物已出发');
c.trip=null;c.intent=null;check(true,'确认出发');
c.intent='desktop';c.view=null;check(true,'确认出发');
assert.equal(queries,1,'reuse the stable button across all state changes');
console.log('PASS portal confirmation: idle DOM writes eliminated; arrival, departure, pairing, failure and cancellation remain immediate');
