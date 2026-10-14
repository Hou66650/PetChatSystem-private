const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const THREE=require('../static/js/vendor/three.min.js');
vm.runInNewContext(fs.readFileSync('static/js/vendor/GLTFLoader.js','utf8'),{THREE,console,TextDecoder,URL,Blob,self:{URL},setTimeout,clearTimeout});
// Texture pixels are irrelevant to geometry and animation validation in Node.
THREE.TextureLoader.prototype.load=function(url,onLoad){const texture=new THREE.Texture();queueMicrotask(()=>onLoad(texture));return texture;};
const parse=path=>new Promise((resolve,reject)=>{const b=fs.readFileSync(path);new THREE.GLTFLoader().parse(b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength),'',resolve,reject)});
(async()=>{
 const stage=await parse('static/models/petchat-mistwood-v1/mistwood.glb'),dog=await parse('static/models/petchat-cat-v2/cat.glb');
 const curtains=[];stage.scene.traverse(o=>{if(o.userData.waterfall_role==='curtain')curtains.push(o);});assert.equal(curtains.length,2);for(const o of curtains){assert(o.material.transparent&&o.material.opacity<1,'waterfall fades through transparent material');assert(o.geometry.attributes.uv);}
 stage.scene.updateMatrixWorld(true);dog.scene.updateMatrixWorld(true);
 const bounds=new THREE.Box3().setFromObject(dog.scene),h=bounds.max.y-bounds.min.y;
 const radius=Math.hypot(bounds.max.x-bounds.min.x,bounds.max.z-bounds.min.z)*.85/h/2+.015;
 const layout=require('../static/js/den/mistwood-layout'),{Navigation}=require('../static/js/den/scene-navigation'),T=require('../static/js/den/toy-workshop');
 const nav=new Navigation({...T.navigation('room',layout),bodyRadius:radius});
 assert(nav.route({x:0,z:0},{x:0,z:4.2}),'actual exported dog fits bridge');
 for(const p of [{x:0,z:0},{x:0,z:1.8},{x:0,z:4.2}]){
  const ray=new THREE.Raycaster(new THREE.Vector3(p.x,1,p.z),new THREE.Vector3(0,-1,0));
  const hits=ray.intersectObject(stage.scene,true);assert(hits.length);
  assert(Math.abs(hits[0].point.y-nav.surfaceHeight(p))<.025,'modeled deck follows navigation surface');
 }
 for(const p of [{x:3,z:1.8},{x:-3,z:1.8},{x:.9,z:-3.4},{x:-4.7,z:-2.8},{x:8,z:0},{x:-2.4,z:-1.2}])assert(!nav.isWalkable(p),'water, building, trunks, edge and cabinet are blocked');
 for(const t of layout.trees)assert(!nav.isWalkable({x:t.x,z:t.z}),'every modeled trunk is excluded');
 let from={x:0,z:0};let seed=81;const random=()=>((seed=(1664525*seed+1013904223)>>>0)/2**32);
 for(let i=0;i<20;i++){
  const path=nav.randomDestination(from,random);assert(path);let a=from;
  for(const b of path){assert(nav.segmentClear(a,b));for(let j=0;j<=40;j++)assert(nav.isWalkable({x:a.x+(b.x-a.x)*j/40,z:a.z+(b.z-a.z)*j/40}));a=b;}from=path.at(-1);
 }
 const report=JSON.parse(fs.readFileSync('art/mistwood-v1/stage-report.json'));assert(report.triangles<620000);assert(report.mesh_batches<=56);assert(report.bytes<40*1024*1024);
 const mixer=new THREE.AnimationMixer(dog.scene);
 for(const name of ['run','sit_idle','play_bow','stand_up']){
  mixer.stopAllAction();const clip=dog.animations.find(c=>c.name===name),a=mixer.clipAction(clip);a.play();mixer.update(clip.duration*.4);dog.scene.updateMatrixWorld(true);
  dog.scene.traverse(o=>{if(o.isBone)assert(o.matrixWorld.elements.every(Number.isFinite));});
 }
 console.log(JSON.stringify({actualBodyRadius:radius,actualDogHeight:h,bridgeAndGround:'verified',animatedBoneMatrices:'finite'}));
})().catch(e=>{console.error(e);process.exitCode=1});
