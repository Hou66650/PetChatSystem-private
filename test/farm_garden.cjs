const assert=require('assert'),fs=require('fs');
const {Navigation}=require('../static/js/den/scene-navigation'),farm=require('../static/js/den/farm-garden'),base=require('../static/js/den/mistwood-layout'),layout=require('../static/data/farm-layout.json');
const nav=new Navigation({...farm.navigation(base,layout),bodyRadius:.36});
for(const p of [{x:-7.4,z:4.5},{x:-9.3,z:4.5},{x:-11.6,z:4.5}]){assert(nav.isWalkable(p),JSON.stringify(p));const route=nav.route({x:0,z:4.4},p);assert(route,'farm path');let prior={x:0,z:4.4};for(const next of route){assert(nav.segmentClear(prior,next));prior=next;}}
for(const bed of layout.beds)assert(!nav.isWalkable(bed));
for(const p of [{x:-15,z:4},{x:0,z:10},{x:-9,z:0},{x:4,z:1.8},{x:-11,z:10}])assert(!nav.isWalkable(p),'off-island or water');
assert(nav.route({x:0,z:-.5},{x:-9.3,z:4.5}),'cross bridge to farm');
assert.equal(farm.modelKey('cosmos',10,false),'cosmos-10');assert.throws(()=>farm.modelKey('../escape',1,false));
for(const species of ['cosmos','pumpkin','birch']){const signatures=new Set();for(let s=1;s<=10;s++)for(const far of [false,true]){const buf=fs.readFileSync('static/models/petchat-farm-v1/'+farm.modelKey(species,s,far)+'.glb');assert.equal(buf.toString('ascii',0,4),'glTF');const json=JSON.parse(buf.toString('utf8',20,20+buf.readUInt32LE(12)));assert(json.meshes.length);for(const a of json.accessors)if(a.type==='VEC3'&&a.min){assert(a.min.every(Number.isFinite));assert(a.max.every(Number.isFinite));}if(!far)signatures.add(JSON.stringify(json.accessors.map(a=>a.count)));}assert.equal(signatures.size,10,species+' must have distinct geometry at every stage');}
console.log('PASS farm: connected terrace, bridge, beds/edge/water avoidance, 30 distinct growth meshes and 30 LODs');
