const assert=require('node:assert/strict'),fs=require('node:fs');
const {Navigation}=require('../static/js/den/scene-navigation');
const {Controller}=require('../static/js/den/pet-locomotion');
const report=require('../art/dog-locomotion-v1/build-report.json');
function read(path){const b=fs.readFileSync(path),n=b.readUInt32LE(12);return {g:JSON.parse(b.subarray(20,20+n)),bin:b.subarray(28+n)};}
function values(asset,id){const a=asset.g.accessors[id],v=asset.g.bufferViews[a.bufferView],size={SCALAR:1,VEC3:3,VEC4:4}[a.type],offset=(v.byteOffset||0)+(a.byteOffset||0);assert.equal(a.componentType,5126);return Array.from({length:a.count*size},(_,i)=>asset.bin.readFloatLE(offset+i*4));}
for(const [pet,old] of [['qiuqiu','petchat-v3/qiuqiu'],['xueqiu','petchat-husky-v2/xueqiu']]){
 const asset=read(`static/models/petchat-motion-v1/${pet}.glb`),previous=read(`static/models/${old}.glb`),g=asset.g;
 assert.equal(g.skins[0].joints.length,45);assert.equal(g.animations.length,35);
 for(const a of previous.g.animations)assert(g.animations.some(n=>n.name===a.name));
 for(const count of Object.values(report[pet].weighted_vertices))assert(count>0);
 const deforming=new Set();
 for(const mesh of g.meshes)for(const p of mesh.primitives){
  if(p.attributes.JOINTS_0===undefined)continue;
  const a=g.accessors[p.attributes.JOINTS_0],view=g.bufferViews[a.bufferView],bytes=a.componentType===5121?1:2,weights=values(asset,p.attributes.WEIGHTS_0);
  for(let i=0;i<a.count*4;i++)if(weights[i]>.001){const at=(view.byteOffset||0)+(a.byteOffset||0)+Math.floor(i/4)*(view.byteStride||4*bytes)+(i%4)*bytes;const id=bytes===1?asset.bin.readUInt8(at):asset.bin.readUInt16LE(at);deforming.add(g.nodes[g.skins[0].joints[id]].name);}
 }
 for(const name of Object.keys(report[pet].weighted_vertices))assert(deforming.has(name),'exported skin actually uses '+name);
 for(const error of Object.values(report[pet].contact_error_m))assert(error<.001,'baked contact accuracy');
 for(const name of ['motion_walk','motion_trot','run']){
  const clip=g.animations.find(a=>a.name===name);assert(clip);
  for(const channel of clip.channels){
   const sample=clip.samplers[channel.sampler],data=values(asset,sample.output),size=g.accessors[sample.output].type==='VEC4'?4:3;
   assert(data.every(Number.isFinite));
   const first=data.slice(0,size),last=data.slice(-size);
   const difference=Math.sqrt(first.reduce((n,x,i)=>n+(x-last[i])**2,0));
   const opposite=Math.sqrt(first.reduce((n,x,i)=>n+(x+last[i])**2,0));
   assert(Math.min(difference,channel.target.path==='rotation'?opposite:Infinity)<.002,`${pet} ${name} loop seam ${g.nodes[channel.target.node].name}`);
  }
 }
}
console.log('PASS 45 weighted joints, 35 retained/new clips, finite seamless gait loops, sub-millimetre authoring contact');
function simulate(gait){
 const navigation=new Navigation({radius:10}),model={position:{x:0,z:0},rotation:{y:0}},seen=[],speeds=[];
 const c=new Controller({navigation,model,speed:.34,gaits:{walk:.32,trot:.63,run:.93,turnLeft:1,turnRight:1},animate(k){seen.push(k)},rest(){}});c.enabled=false;
 assert(c.goTo({x:0,z:4},{gait}));let t=0;
 for(;t<3000&&c.path.length;t++){c.update(.02);speeds.push(c.velocity);assert(navigation.isWalkable(model.position));}
 assert(t<3000);assert.equal(c.velocity,0);assert(Math.hypot(model.position.x,model.position.z-4)<.02);
 return {seen,speeds,t,c,model};
}
const walk=simulate('walk'),run=simulate('run');assert(run.t<walk.t*.65);assert(run.seen.includes('run'));assert(run.seen.includes('trot'));assert(run.seen.includes('walk'));
for(let i=1;i<run.speeds.length-1;i++)assert(Math.abs(run.speeds[i]-run.speeds[i-1])<.035,'bounded acceleration');
run.c.goTo({x:0,z:0},{gait:'run'});const before={...run.model.position};run.c.update(.02);assert(Math.hypot(run.model.position.x-before.x,run.model.position.z-before.z)<.001,'turn before moving backwards');
run.c.update(.02,true);assert.equal(run.c.path.length,0);assert.equal(run.c.velocity,0);
const legacy=new Controller({navigation:new Navigation(),model:{position:{x:0,z:0},rotation:{y:0}},animate(){},rest(){}});legacy.goTo({x:0,z:1},{gait:'run'});assert.equal(legacy.requestedGait,'walk');
console.log('PASS run/trot/walk transitions, faster travel, bounded acceleration, turn-first, interruption and legacy fallback');
const workshop=require('../static/js/den/toy-workshop');
const courtyard=JSON.parse(fs.readFileSync('templates/den.html','utf8').match(/const SAKURA_NAV = (\{[^\n]+\});/)[1]);
for(const theme of ['sakura','snow']){
 const base=theme==='snow'?require('../static/js/den/snow-haven-layout'):{...courtyard,...require('../static/js/den/sakura-river-layout')};
 const navigation=new Navigation({...workshop.navigation(theme,base),bodyRadius:theme==='snow'?.65:.5}),model={position:{x:0,z:0},rotation:{y:0}};
 let seed=19;const random=()=>((seed=seed*1664525+1013904223>>>0)/4294967296);
 const c=new Controller({navigation,model,animate(){},rest(){},speed:.34,gaits:{walk:.32,trot:.63,run:.93}});c.enabled=false;
 for(let trip=0;trip<12;trip++){
  const route=navigation.randomDestination(model.position,random);assert(route);assert(c.goTo(route[route.length-1],{gait:'run'}));
  let frames=0;for(;frames<2500&&c.path.length;frames++){c.update(.03);assert(navigation.isWalkable(model.position));}
  assert(frames<2500,theme+' running route completes');
 }
}
console.log('PASS running routes stay outside water, pond, cabinet and scenery on both islands');
