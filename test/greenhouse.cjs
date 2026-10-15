const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const {Garden,View,lighting}=require('../static/js/den/greenhouse');
const THREE=require('../static/js/vendor/three.min.js');
const {Navigation}=require('../static/js/den/scene-navigation'),layout=require('../static/js/den/mistwood-layout');
const catalog=require('../static/data/cat-world.json');
let now=new Date(2026,9,15,23,59).getTime();const data=new Map(),storage={getItem:k=>data.get(k),setItem:(k,v)=>data.set(k,v)};
const options={scope:'alice',storage,now:()=>now};let garden=new Garden(options);
assert(garden.water('grass'));assert(!garden.water('grass'));assert.equal(garden.state.plants.grass.growth,0);
now+=120000;garden=new Garden(options);assert.equal(garden.state.plants.grass.growth,1);garden.rollover();assert.equal(garden.state.plants.grass.growth,1);
assert(garden.interact('grass','nibble'));assert(!garden.interact('grass','nibble'));assert.equal(garden.state.plants.grass.growth,2);
assert(!garden.interact('catnip','nibble'));assert(garden.interact('catnip','sniff'));
assert.equal(new Garden({...options,scope:'bob'}).state.plants.grass.growth,0);
assert(!garden.water('unknown'));garden.cosmetic('lace',true);assert(new Garden(options).state.cosmetics.lace);
const broken=new Garden({scope:'broken',storage:{getItem:()=>'{',setItem:()=>{throw Error('quota');}}});assert.doesNotThrow(()=>broken.water('grass'));assert.equal(broken.persisted,false);
assert.equal(lighting(12,0).intensity,0);assert(lighting(18,0).intensity>lighting(23,0).intensity);assert(lighting(18,0).warmth>lighting(18,5).warmth);
const nav=new Navigation({...require('../static/js/den/farm-garden').navigation(layout,require('../static/data/farm-layout.json')),bodyRadius:.619});
for(const p of catalog){const target=p.normal?{x:p.x+p.normal.x*(nav.clearance+.04),z:p.z+p.normal.z*(nav.clearance+.04)}:p;assert(nav.route({x:0,z:0},target),p.id+' reachable');}
assert(!nav.isWalkable({x:.9,z:-3.4}));assert(!nav.isWalkable({x:1.4,z:-3.5}));assert(!nav.isWalkable({x:3,z:1.8}));assert(nav.isWalkable({x:3,z:-3.5}));
assert.equal(nav.surfaceHeight({x:3,z:-4.22}),.525);
// All actual routes to and from the retreat have continuous elevation, no side-edge snap.
for(const p of [{x:2.3,z:-2.55},{x:3.7,z:-2.55},{x:0,z:0}]){
 const route=nav.route(p,{x:3,z:-4.22});let a=p,last=nav.surfaceHeight(a);
 for(const b of route){for(let i=1;i<=200;i++){const q={x:a.x+(b.x-a.x)*i/200,z:a.z+(b.z-a.z)*i/200};const h=nav.surfaceHeight(q);assert(Math.abs(h-last)<.03,'continuous ramp');last=h;}a=b;}
}
vm.runInNewContext(fs.readFileSync('static/js/vendor/GLTFLoader.js','utf8'),{THREE,console,TextDecoder,URL,Blob,self:{URL},setTimeout,clearTimeout});
THREE.TextureLoader.prototype.load=function(_url,onLoad){const t=new THREE.Texture();queueMicrotask(()=>onLoad?.(t));return t;};
(async()=>{
 const b=fs.readFileSync('static/models/petchat-mistwood-v1/mistwood.glb');const gltf=await new Promise((res,rej)=>new THREE.GLTFLoader().parse(b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength),'',res,rej));
 const view=new View(THREE,gltf.scene,{...options,scope:'fresh'});assert.equal(view.lamps.length,2);
 for(const id of ['grass','catnip'])for(let layer=0;layer<3;layer++)assert(view.nodes.some(o=>o.userData.garden_plant===id&&o.userData.growth_layer===layer),'modeled growth layers');
 assert(view.nodes.filter(o=>o.userData.garden_plant).every(o=>o.visible===(o.userData.growth_layer===0)));
 view.completed({target:'grass',action:'nibble'});assert(view.nodes.some(o=>o.userData.garden_plant==='grass'&&o.userData.growth_layer===1&&o.visible));
 view.garden.cosmetic('night',true);view.refresh();view.update(1,{x:3,z:-3},'day');assert(view.nodes.filter(o=>o.userData.garden_cosmetic==='night').every(o=>!o.visible));
 view.update(1,{x:3,z:-3},'night');assert(view.nodes.filter(o=>o.userData.garden_cosmetic==='night').every(o=>o.visible));assert(view.lamps[0].intensity>0);
 gltf.scene.updateMatrixWorld(true);
 for(const z of [-3.15,-3.4,-3.65]){
  const ray=new THREE.Raycaster(new THREE.Vector3(3,.7,z),new THREE.Vector3(0,-1,0));const hits=ray.intersectObject(gltf.scene,true);assert(hits.length);assert(Math.abs(hits[0].point.y-nav.surfaceHeight({x:3,z}))<.025,'GLB ramp matches navigation');
 }
 console.log('PASS greenhouse: persisted next-day growth, daily interaction limits, account isolation, cosmetics, lighting, exported layers and accessible ramp/retreat');
})().catch(e=>{console.error(e);process.exitCode=1});
