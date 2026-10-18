const assert=require('node:assert/strict'),fs=require('node:fs'),crypto=require('node:crypto');
const THREE=require('../static/js/vendor/three.min.js'),A=require('../desktop/actions'),{Animator}=require('../desktop/animator');
const models=['petchat-cat-v3/cat','petchat-shiba-v4/qiuqiu','petchat-husky-v3/xueqiu','petchat-shepherd-v2/shepherd'];
for(const model of models){
 const b=fs.readFileSync('static/models/'+model+'.glb'),length=b.readUInt32LE(12),g=JSON.parse(b.subarray(20,20+length)),binary=b.subarray(28+length);
 const signatures=new Set(),selected=new Set(A.catalog.map(a=>A.find(g.animations,a.clips)?.name));
 const clips=g.animations.map(a=>{
  const duration=Math.max(...a.samplers.map(s=>g.accessors[s.input].max[0]));
  const hash=crypto.createHash('sha256');
  for(const s of a.samplers){const v=g.bufferViews[g.accessors[s.output].bufferView];hash.update(binary.subarray(v.byteOffset||0,(v.byteOffset||0)+v.byteLength));}
  if(selected.has(a.name))signatures.add(hash.digest('hex'));
  return {name:a.name,duration};
 });
 assert.equal(A.supported(clips).length,25,model);assert(signatures.size>=25,'actions must contain distinct authored motion');
 console.log(model+': 25 supported, '+signatures.size+' distinct animation payloads');
}
assert.equal(A.supported([{name:'sleep_loop',duration:1}]).length,0,'sleep requires enter and exit assets');
assert.deepEqual(A.supported([{name:'Idle',duration:1}]).map(a=>a.id),['idle']);
const scene=new THREE.Group();scene.name='pet';
const names=[...new Set(A.catalog.flatMap(a=>[...a.clips,...(a.enter?[a.enter,a.exit]:[])])),'stop'];
const clips=names.map((name,i)=>new THREE.AnimationClip(name,1,[new THREE.NumberKeyframeTrack('.position[y]',[0,.5,1],[i*.01,i*.01+.02,i*.01])]));
const pet={mixer:new THREE.AnimationMixer(scene),clips},anim=new Animator(THREE,pet);
let serial=0;
function step(seconds){for(let t=0;t<seconds;t+=1/120){anim.update(1/120,1);const sum=[...anim.weights.values()].reduce((a,b)=>a+b,0);assert(Math.abs(sum-1)<1e-6||anim.serial===0,'normalized interrupted crossfade weights');assert(Number.isFinite(scene.position.y));}}
anim.request('idle',serial++);step(.5);
for(const a of A.catalog){anim.request(a.id,serial++);step(2.5);assert.equal(anim.posture,a.enter?a.id:'stand');if(!a.loop)assert.equal(anim.phase,'idle',a.id+' returns to idle');assert(anim.weights.size<=2);}
anim.request('sleep',serial++);step(1.5);assert.equal(anim.posture,'sleep');
anim.request('walk',serial++);assert(!anim.locomotionReady);step(.5);assert(!anim.locomotionReady);step(.8);assert(anim.locomotionReady);
anim.request('idle',serial++);assert.equal(anim.phase,'stop');step(1.5);assert.equal(anim.phase,'idle');
anim.request('sleep',serial++);step(.2);anim.request('sit',serial++);step(.1);anim.request('walk',serial++);step(2.5);assert(anim.locomotionReady,'latest intent wins after entering and leaving posture');
for(let i=0;i<80;i++){anim.request(i%2?'paw':'happy',serial++);step(.04);}step(2);assert.equal(anim.weights.size,1,'interrupted actions released');
const before=anim.active.time;anim.request('happy',serial);step(.2);const active=anim.active;anim.request('happy',serial);assert.equal(anim.active,active);assert(anim.active.time>0,'repeated IPC cannot reset one-shot');
anim.request('not-supported',++serial);step(.5);assert.equal(anim.phase,'idle');
for(const id of A.catalog.map(a=>a.id))assert(['idle','walk','run','sniff','sleep','petting','happy'].includes(A.wire(id)));
const recent=['sniff','sit','sleep','stretch','shake','lick'];assert(!recent.includes(A.choose(A.catalog.map(a=>a.id),recent,()=>0)));
anim.dispose();assert.equal(anim.weights.size,0);
const walkOnly={mixer:new THREE.AnimationMixer(new THREE.Group()),clips:[new THREE.AnimationClip('walk',1,[])]};
const limited=new Animator(THREE,walkOnly);limited.request('walk',0);limited.update(.05);limited.request('idle',1);assert.equal(limited.active,null,'missing idle must not leave a walking clip running');limited.dispose();
console.log('PASS sequencing, repeated messages, posture interruption, movement gating, normalized blends, cleanup, missing assets and wire compatibility');
