const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const THREE=require('../static/js/vendor/three.min.js');
vm.runInNewContext(fs.readFileSync('static/js/vendor/GLTFLoader.js','utf8'),{THREE,console,TextDecoder,URL,Blob,self:{URL},setTimeout,clearTimeout});
THREE.TextureLoader.prototype.load=function(url,onLoad){const t=new THREE.Texture();queueMicrotask(()=>onLoad(t));return t;};
const parse=p=>new Promise((resolve,reject)=>{const b=fs.readFileSync(p);new THREE.GLTFLoader().parse(b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength),'',resolve,reject);});
(async()=>{
 let total=0,triangles=0;const positions=[[-9,0,7],[9,1,7],[-9,-.4,-10],[9,.8,-10]];
 for(const [i,theme] of ['sakura','snow','room','camp'].entries()){
  const path='static/models/home-islands/'+theme+'.glb';total+=fs.statSync(path).size;
  const manifest=JSON.parse(fs.readFileSync(path.replace('.glb','.json')));
  assert.deepEqual(require('node:zlib').gunzipSync(fs.readFileSync(path+'.gz')),fs.readFileSync(path),'lossless compressed delivery');
  let originalTriangles=0,area=0;const a=new THREE.Vector3(),b=new THREE.Vector3(),c=new THREE.Vector3();
  const gltf=await parse(path);gltf.scene.updateMatrixWorld(true);
  gltf.scene.traverse(o=>{if(!o.isMesh)return;const g=o.geometry,p=g.attributes.position,idx=g.index,n=idx?idx.count:p.count;originalTriangles+=n/3;for(let k=0;k<n;k+=3){a.fromBufferAttribute(p,idx?idx.getX(k):k).applyMatrix4(o.matrixWorld);b.fromBufferAttribute(p,idx?idx.getX(k+1):k+1).applyMatrix4(o.matrixWorld);c.fromBufferAttribute(p,idx?idx.getX(k+2):k+2).applyMatrix4(o.matrixWorld);area+=b.sub(a).cross(c.sub(a)).length()/2;}});
  assert.equal(originalTriangles,manifest.triangles,'all original triangles preserved');assert(Math.abs(area-manifest.surfaceArea)/manifest.surfaceArea<.0001,'all original surface area preserved');
  const object=gltf.scene,box=new THREE.Box3().setFromObject(object),size=box.getSize(new THREE.Vector3()),center=box.getCenter(new THREE.Vector3());
  assert(size.x>0&&size.z>0);object.position.sub(center);const scale=9/Math.max(size.x,size.z);object.scale.setScalar(scale);object.position.multiplyScalar(scale);
  const group=new THREE.Group();group.position.set(...positions[i]);group.userData.island=i;group.add(object);group.updateMatrixWorld(true);
  const bounds=new THREE.Box3().setFromObject(group),extent=bounds.getSize(new THREE.Vector3());assert(Math.abs(Math.max(extent.x,extent.z)-9)<.001);
  object.traverse(o=>{if(o.isMesh){triangles+=(o.geometry.index?.count||o.geometry.attributes.position.count)/3;assert([...o.geometry.attributes.position.array].every(Number.isFinite));}});
  // Use actual meshes first, then the generous island hit area for river/foliage gaps.
  const pickArea=new THREE.Mesh(new THREE.CylinderGeometry(4.6,4.6,6,20),new THREE.MeshBasicMaterial({visible:false,side:THREE.DoubleSide}));group.add(pickArea);group.updateMatrixWorld(true);
  for(const angle of [0,Math.PI/2,Math.PI,Math.PI*1.5]){
   const origin=group.position.clone().add(new THREE.Vector3(Math.sin(angle)*20,12,Math.cos(angle)*20));
   const ray=new THREE.Raycaster(origin,group.position.clone().sub(origin).normalize());
   const surfaceHits=ray.intersectObject(object,true);const hits=surfaceHits.length?surfaceHits:ray.intersectObject(pickArea,false);assert(hits.length,theme+' selectable around the island');
   let picked=hits[0].object;while(picked&&picked.userData.island===undefined)picked=picked.parent;assert.equal(picked.userData.island,i);
  }
 }
 assert(total<75*1024*1024,'uncompressed geometry stays bounded; gzip served over network');assert(triangles<1700000,'four islands including the expanded meadow have bounded geometry');
 assert(JSON.parse(fs.readFileSync('static/models/home-islands/room.json')).triangles<750000,'expanded island selector uses its own LOD, not the detailed playable stage');
 console.log('PASS four real previews: finite geometry, normalized spacing, all-direction picking, '+triangles+' triangles / '+(total/1024/1024).toFixed(2)+' MiB');
})().catch(e=>{console.error(e);process.exitCode=1;});
