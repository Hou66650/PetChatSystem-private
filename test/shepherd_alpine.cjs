const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const {Navigation}=require('../static/js/den/scene-navigation');
const Toys=require('../static/js/den/toy-workshop');
const layout=require('../static/js/den/alpine-layout');
const E=require('../static/js/den/shiba-expression');
const read=p=>{const b=fs.readFileSync(p);return JSON.parse(b.toString('utf8',20,20+b.readUInt32LE(12)));};
const dog=read('static/models/petchat-shepherd-v1/shepherd.glb'),stage=read('static/models/petchat-shepherd-v1/alpine.glb');
const clips=new Set(dog.animations.map(a=>a.name));assert.equal(clips.size,35);assert.equal(dog.skins[0].joints.length,45);
for(const name of ['run','motion_walk','motion_trot','sit_down','stand_up',...Object.values(E.acts).map(a=>a.clip)])assert(clips.has(name),name);
for(const m of dog.meshes)if(m.extras?.targetNames){assert(m.extras.targetNames.includes('Blink_L'));assert(m.weights.every(w=>w===0),'eyes open in exported rest pose');}
assert(dog.meshes.some(m=>m.primitives.some(p=>p.attributes.COLOR_0!==undefined)),'sable coat uses exported color');
assert(stage.nodes.filter(n=>n.extras?.waterfall_role==='curtain').length===2);
assert(stage.meshes.length<=24,'material batches bound scene draw calls');
assert(fs.statSync('static/models/petchat-shepherd-v1/alpine.glb').size<20e6);
assert(fs.statSync('static/models/petchat-shepherd-v1/shepherd.glb').size<15e6);
const nav=new Navigation({...Toys.navigation('camp',layout),bodyRadius:.92});
assert(nav.isWalkable({x:0,z:0}));assert(!nav.isWalkable({x:3,z:1.9}));assert(!nav.isWalkable({x:5.5,z:0}));
assert(!nav.isWalkable({x:1.7,z:-2.9}));assert(!nav.isWalkable({x:-2.65,z:-.45}));
const from={x:0,z:0},to={x:0,z:3.8},route=nav.route(from,to);assert(route,'large shepherd can cross the bridge');
let prev=from;for(const p of route){assert(nav.segmentClear(prev,p));prev=p;}
assert.equal(nav.surfaceHeight({x:0,z:1.9}),.30500000000000005);
const source=fs.readFileSync('templates/den.html','utf8');
const specs=vm.runInNewContext('('+source.match(/const SPECS = (\{[\s\S]*?\n        \});/)[1]+')');
assert(specs[4].expressive&&specs[4].pbr);assert(specs[4].glb.includes('petchat-shepherd-v1'));
assert(source.includes("ToyWorkshop.navigation('camp',AlpineLayout)"));assert(source.includes("currentTheme==='camp'?'/static/textures/alpine-sky-v1'"));
for(const time of ['day','night'])assert(fs.statSync('static/textures/alpine-sky-v1/'+time+'.webp').size<1e6);
console.log('PASS shepherd 35 clips/45 joints, open eyelids, coat colors, bounded GLBs/batches, river/cliff/building/cabinet exclusion, bridge route, selected scene integration');
