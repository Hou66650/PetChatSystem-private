const fs = require('node:fs'), vm = require('node:vm'), assert = require('node:assert/strict');
const { stripTypeScriptTypes } = require('node:module');
let source = fs.readFileSync('harmony/entry/src/main/ets/model/NativePetController.ets', 'utf8');
source = source.replace(/^import .*;\r?\n/gm, '').replace(/export /g, '');
const context = {};
vm.runInNewContext(stripTypeScriptTypes(source, {mode:'transform'}) +
  '\nglobalThis.Controller = NativePetController; globalThis.readSnapshot = readPetSnapshot;', context);
function clip(name) {
  return {name, enabled:false, starts:0, stops:0, pauses:0, callback:null,
    progress:0,stop(){this.stops++;},pause(){this.pauses++;},restart(){this.starts++;},seek(v){this.progress=v;},onFinished(fn){this.callback=fn;}};
}
function make(names = ['idle_breathe','motion_walk','run','touch_head','sleep_loop','stand_up','happy']) {
  const clips = names.map(clip), root = {}, messages = [];
  const pet = new context.Controller('cat', root, clips, m=>messages.push(m));
  pet.restore(null);
  return {pet, root, clips, messages, get:name=>clips.find(a=>a.name===name)};
}
const a = make();
assert.equal(a.pet.action,'idle');
a.pet.perform('petting'); const stale = a.get('touch_head').callback;
a.pet.perform('sleep'); stale(); assert.equal(a.pet.action,'sleep','stale one-shot completion cannot wake a sleeping pet');
a.get('sleep_loop').callback(); assert.equal(a.get('sleep_loop').starts,2);
a.pet.perform('wake'); a.get('stand_up').callback(); assert.equal(a.pet.action,'idle');
a.pet.perform('petting'); a.get('touch_head').callback(); assert.equal(a.pet.action,'idle');

a.pet.perform('walk'); const before = a.pet.snapshot();
a.pet.step(100); const after = a.pet.snapshot();
assert(Math.hypot(after.x-before.x, after.z-before.z)<=.45*.05+1e-10,'long frames must not teleport');
for(let i=0;i<10000;i++) a.pet.step(1/30);
assert(Math.abs(a.root.position.x)<=1.2 && Math.abs(a.root.position.z)<=.6,'roaming stays in bounds');
assert.equal(a.pet.snapshot().action,'idle','persisting movement restores safely at idle');
const pausedPosition = JSON.stringify(a.root.position);
a.pet.suspend(); a.pet.step(1); assert.equal(JSON.stringify(a.root.position),pausedPosition);
const starts = a.get('motion_walk').starts; a.get('motion_walk').callback();
assert.equal(a.get('motion_walk').starts,starts,'background animation cannot restart');
a.pet.resume(); assert.equal(a.get('motion_walk').starts,starts+1);
a.pet.come(); for(let i=0;i<300;i++) a.pet.step(1/30);
assert.equal(a.pet.action,'happy'); assert.equal(a.pet.moving,false);
assert.equal(a.root.position.x,0); assert.equal(a.root.position.z,.55);
a.get('happy').callback(); assert.equal(a.pet.action,'idle');
a.pet.perform('run'); a.pet.perform('petting');
const stopped = JSON.stringify(a.root.position); a.pet.step(.03);
assert.equal(JSON.stringify(a.root.position),stopped,'touch interrupts locomotion');
const completion = a.get('touch_head').callback;
a.pet.dispose(); completion(); a.pet.perform('walk'); a.pet.step(.03);
assert.equal(JSON.stringify(a.root.position),stopped,'disposed controllers cannot move or restart');

const missing = make(['idle_breathe']); missing.pet.perform('run');
assert.equal(missing.pet.moving,false);assert.equal(missing.pet.action,'idle');
assert.match(missing.messages.at(-1),/不支持/);
const prefixed = make(['Armature|idle_breathe','Armature|motion_walk']);
assert(prefixed.pet.supports('walk')); prefixed.pet.perform('walk'); assert(prefixed.pet.moving);

for (const raw of ['null','{}','bad JSON',JSON.stringify({version:1,petId:'cat',x:'1',z:0,yaw:0,action:'idle'}),
  JSON.stringify({version:1,petId:'other',x:0,z:0,yaw:0,action:'idle'}),
  JSON.stringify({version:1,petId:'cat',x:0,z:0,yaw:0,action:'run'})]) {
  assert.equal(context.readSnapshot(raw,'cat'),null);
}
const snapshot=context.readSnapshot(JSON.stringify({version:1,petId:'cat',x:99,z:-99,yaw:100,action:'sleep'}),'cat');
assert.equal(snapshot.x,1.2); assert.equal(snapshot.z,-.6);
const restored=make();restored.pet.restore(snapshot);assert.equal(restored.pet.action,'sleep');
assert.equal(restored.root.position.x,1.2);
const follower=make();
assert(follower.pet.follow('touch_head',.4,1,false));assert.equal(follower.get('touch_head').progress,.4);
const finished=follower.get('touch_head').callback, count=follower.get('touch_head').starts;
finished();assert.equal(follower.get('touch_head').starts,count,'web one-shot completion must not start a second native business action');
assert(follower.pet.follow('motion_walk',.2,.8,true));finished();assert.equal(follower.get('touch_head').starts,count);
follower.get('motion_walk').callback();assert.equal(follower.get('motion_walk').starts,2);
assert.equal(follower.pet.moving,false,'web following cannot start autonomous standalone roaming');
assert.equal(follower.pet.follow('unknown',0,1,true),false);

// Check semantic aliases against actual shipped GLB animation names, not mock names only.
for(const path of ['petchat-cat-v3/cat.glb','petchat-shiba-v4/qiuqiu.glb','petchat-husky-v3/xueqiu.glb','petchat-shepherd-v2/shepherd.glb']) {
  const bytes=fs.readFileSync('static/models/'+path);
  const gltf=JSON.parse(bytes.subarray(20,20+bytes.readUInt32LE(12)).toString());
  const actual=make(gltf.animations.map(a=>a.name));
  for(const action of ['idle','walk','run','petting','sleep','wake','happy']) assert(actual.pet.supports(action),path+': '+action);
}
console.log('PASS native behavior: interruptions, one-shots, movement bounds, call/return, suspension, persistence and four original GLBs');
