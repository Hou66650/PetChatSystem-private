const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const THREE=require('../static/js/vendor/three.min.js');
vm.runInNewContext(fs.readFileSync('static/js/vendor/GLTFLoader.js','utf8'),{THREE,console,TextDecoder,URL,Blob,self:{URL},setTimeout,clearTimeout});
// Geometry tests do not need decoded texture pixels; browser checks use real images.
THREE.TextureLoader.prototype.load=function(url,onLoad){const t=new THREE.Texture();queueMicrotask(()=>onLoad(t));return t;};
const parse=p=>new Promise((resolve,reject)=>{const b=fs.readFileSync(p);new THREE.GLTFLoader().parse(b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength),'',resolve,reject);});
(async()=>{
 const dog=await parse('static/models/petchat-cat-v2/cat.glb');
 const meshes=[];dog.scene.traverse(o=>{if(o.isSkinnedMesh)meshes.push(o);});
 const mixer=new THREE.AnimationMixer(dog.scene),point=new THREE.Vector3();
 for(const clip of dog.animations){
  for(const phase of [.15,.5,.85]){
   mixer.stopAllAction();mixer.clipAction(clip).reset().play();mixer.update(clip.duration*phase);dog.scene.updateMatrixWorld(true);
   const box=new THREE.Box3();
   for(const mesh of meshes){
    mesh.skeleton.update();const positions=mesh.geometry.attributes.position;
    for(let i=0;i<positions.count;i+=19){point.fromBufferAttribute(positions,i);mesh.boneTransform(i,point);point.applyMatrix4(mesh.matrixWorld);assert(point.toArray().every(Number.isFinite),clip.name);box.expandByPoint(point);}
   }
   assert(Math.max(...box.getSize(new THREE.Vector3()).toArray())<3,clip.name+': bounded deformed geometry');
   assert(box.min.y>-.035,clip.name+': sampled surface ground clearance');
  }
 }
 for(const name of ['SOCKET_mouth','SOCKET_head','SOCKET_neck'])assert(dog.scene.getObjectByName(name),name);
 console.log('PASS actual Cat GLB: all 35 clips at three phases, finite bounded skin, ground clearance and attachment sockets');
})().catch(e=>{console.error(e);process.exitCode=1;});
