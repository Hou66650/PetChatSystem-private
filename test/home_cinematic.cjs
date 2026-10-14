const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const THREE=require('../static/js/vendor/three.min.js');
const {Environment}=require('../static/js/home-atmosphere');
const {Resident,models}=require('../static/js/home-resident');
const assets=require('../static/js/den/selected-assets');
vm.runInNewContext(fs.readFileSync('static/js/vendor/GLTFLoader.js','utf8'),{THREE,console,TextDecoder,URL,Blob,self:{URL},setTimeout,clearTimeout});
THREE.TextureLoader.prototype.load=function(url,onLoad){const t=new THREE.Texture();queueMicrotask(()=>onLoad(t));return t;};
const requests=[];
class LocalLoader extends assets.Loader{constructor(loader){super(loader,async url=>{requests.push(url);const b=fs.readFileSync('.'+url.split('?')[0]);return {ok:true,arrayBuffer:async()=>b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength)};});}}
(async()=>{
 const scene=new THREE.Scene(),environment=new Environment(THREE,scene);
 const resident=new Resident(THREE,{Loader:LocalLoader,disposeTree:assets.disposeTree},'test');
 assert.equal(requests.length,0,'overview must not preload pets');
 for(const theme of Object.keys(models)){
  const group=new THREE.Group(),object=new THREE.Mesh(new THREE.BoxGeometry(9,1,9),new THREE.MeshBasicMaterial());group.add(object);scene.add(group);environment.addIsland(theme,group);
  await resident.select(theme,{group,object});assert(resident.model,theme+' resident');assert(resident.mixer,theme+' animation');
  const bounds=new THREE.Box3().setFromObject(resident.model);assert(Math.abs(bounds.min.y-.5)<.01,'resident rests on surface');assert(Math.abs(bounds.getSize(new THREE.Vector3()).y-.82)<.01);
  resident.update(1/30);assert(resident.model.parent===group);
 }
 const current=resident.model;resident.clear();assert(!current.parent);assert.equal(resident.model,null);
 await Promise.all([resident.select('snow',{group:new THREE.Group(),object:new THREE.Mesh(new THREE.BoxGeometry(9,1,9),new THREE.MeshBasicMaterial())}),resident.select('camp',{group:new THREE.Group(),object:new THREE.Mesh(new THREE.BoxGeometry(9,1,9),new THREE.MeshBasicMaterial())})]);
 assert(resident.model);resident.clear();
 let triangles=0;
 environment.group.traverse(o=>{if(o.isMesh){assert([...o.geometry.attributes.position.array].every(Number.isFinite));triangles+=(o.geometry.index?.count||o.geometry.attributes.position.count)/3;}});
 assert(triangles<10000,'environment geometry budget');assert.equal(environment.clouds.length,4);
 const before=environment.effects[0].points.geometry.attributes.position.array.slice();environment.update(12,false);assert.notDeepEqual(before,environment.effects[0].points.geometry.attributes.position.array);
 const frozen=environment.effects[0].points.geometry.attributes.position.array.slice();environment.update(13,true);assert.deepEqual(frozen,environment.effects[0].points.geometry.attributes.position.array);
 console.log('PASS procedural atmosphere geometry, four cloud layers, particles/reduced motion, four actual animated residents, grounding, selected-only loading and rapid-switch disposal');
})().catch(e=>{console.error(e);process.exitCode=1;});
