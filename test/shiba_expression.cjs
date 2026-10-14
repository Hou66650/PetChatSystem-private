const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const E=require('../static/js/den/shiba-expression.js');
const D=require('../static/js/den/dialogue-actions.js');
const readGLB=path=>{const b=fs.readFileSync(path);assert.equal(b.toString('utf8',0,4),'glTF');return JSON.parse(b.toString('utf8',20,20+b.readUInt32LE(12)));};
const glb=readGLB('static/models/petchat-shiba-v4/qiuqiu.glb');
const old=readGLB('static/models/petchat-v2/qiuqiu.glb');
const clips=new Set(glb.animations.map(a=>a.name));
for(const a of old.animations)assert.ok(clips.has(a.name),`Retained clip ${a.name}`);
for(const a of Object.values(E.acts))assert.ok(clips.has(a.clip),`Exported clip ${a.clip}`);
assert.equal(clips.size,35);assert.equal(glb.skins[0].joints.length,45);
assert.ok(glb.meshes.some(m=>m.extras?.targetNames?.includes('Blink_L')));
for(const mode of ['calm','natural','lively'])for(let i=0;i<100;i++){
    const next=E.idleChoice(i/100,mode,'curious');assert.notEqual(next,'curious');
    if(mode==='calm')assert.ok(!['playBow','greet','shake'].includes(next));
}
assert.equal(E.closure('sleep',.2),1);assert.equal(E.closure('walk',.5),0);
assert.ok(E.closure('yawn',.5)>.9);
function vec(x=0,y=0,z=0){return {x,y,z,clone(){return vec(this.x,this.y,this.z)},copy(v){Object.assign(this,{x:v.x,y:v.y,z:v.z});return this},setScalar(s){this.x=this.y=this.z=s;return this}};}
const eye={isBone:true,name:'eye_L',position:vec(-.116,.077,.168),scale:vec(1,1,1)};
const lid={isBone:true,name:'lid_L',scale:vec(1,1,1)};
const mesh={morphTargetDictionary:{Blink_L:0,Blink_R:1},morphTargetInfluences:[0,0]};
const controller=new E.Controller({traverse(fn){[eye,lid,mesh].forEach(fn)}});
for(let i=0;i<1000;i++)controller.update(1/60,'sleep',.5);
assert.ok(Math.abs(eye.position.z-.126)<.00001,'No accumulating eye displacement');
controller.blink();for(let i=0;i<120;i++)controller.update(1/60,'walk',.2);
assert.ok(Math.abs(eye.position.z-.168)<.00001,'Walking recovers open eyes');assert.ok(mesh.morphTargetInfluences[0]<.00001);
let cancelled=false,resolveStep;const calls=[];
const runner=new D.Runner({status(){},label:a=>a,isHeld:()=>false,begin(){},cancel(){cancelled=true},finish(){},execute(a){calls.push(a);return new Promise(r=>resolveStep=r)}});
(async()=>{const task=runner.run(['curious','play_bow']);runner.cancel();resolveStep();await task;assert.ok(cancelled);assert.deepEqual(calls,['curious']);
const page=await (await fetch('http://127.0.0.1:5002/den')).text();
for(const match of page.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/g))new vm.Script(match[1]);
console.log('PASS: 35 clips, 45 bones, facial morphs, calm behavior, no eye drift, cancellation, rendered page syntax');})();
