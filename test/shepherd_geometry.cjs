const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const THREE=require('../static/js/vendor/three.min.js');
vm.runInNewContext(fs.readFileSync('static/js/vendor/GLTFLoader.js','utf8'),{THREE,console,TextDecoder,URL,Blob,self:{URL},setTimeout,clearTimeout});
// Texture pixels are irrelevant to geometry and animation validation in Node.
THREE.TextureLoader.prototype.load=function(url,onLoad){const texture=new THREE.Texture();queueMicrotask(()=>onLoad(texture));return texture;};
const parse=path=>new Promise((resolve,reject)=>{const b=fs.readFileSync(path);new THREE.GLTFLoader().parse(b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength),'',resolve,reject)});
(async()=>{
 const stage=await parse('static/models/petchat-shepherd-v1/alpine.glb'),dog=await parse('static/models/petchat-shepherd-v2/shepherd.glb');
 stage.scene.updateMatrixWorld(true);dog.scene.updateMatrixWorld(true);
 const bounds=new THREE.Box3().setFromObject(dog.scene),h=bounds.max.y-bounds.min.y;
 const radius=Math.hypot(bounds.max.x-bounds.min.x,bounds.max.z-bounds.min.z)*1.12/h/2+.015;
 const layout=require('../static/js/den/alpine-layout'),{Navigation}=require('../static/js/den/scene-navigation'),T=require('../static/js/den/toy-workshop');
 const nav=new Navigation({...T.navigation('camp',layout),bodyRadius:radius});
 assert(nav.route({x:0,z:0},{x:0,z:3.8}),'actual exported dog fits bridge');
 for(const p of [{x:0,z:0},{x:0,z:1.9},{x:0,z:3.8}]){
  const ray=new THREE.Raycaster(new THREE.Vector3(p.x,1,p.z),new THREE.Vector3(0,-1,0));
  const hits=ray.intersectObject(stage.scene,true);assert(hits.length);
  assert(Math.abs(hits[0].point.y-nav.surfaceHeight(p))<.025,'modeled deck follows navigation surface');
 }
 const mixer=new THREE.AnimationMixer(dog.scene);
 for(const name of ['run','sit_idle','play_bow','stand_up']){
  mixer.stopAllAction();const clip=dog.animations.find(c=>c.name===name),a=mixer.clipAction(clip);a.play();mixer.update(clip.duration*.4);dog.scene.updateMatrixWorld(true);
  dog.scene.traverse(o=>{if(o.isBone)assert(o.matrixWorld.elements.every(Number.isFinite));});
 }
 console.log(JSON.stringify({actualBodyRadius:radius,actualDogHeight:h,bridgeAndGround:'verified',animatedBoneMatrices:'finite'}));
})().catch(e=>{console.error(e);process.exitCode=1});
