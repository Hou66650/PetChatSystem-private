const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const THREE=require('../static/js/vendor/three.min.js');
const lib={THREE};vm.runInNewContext(fs.readFileSync('static/js/vendor/three-mesh-bvh-0.5.23.js','utf8'),lib);
let terminated=0,posts=0;
class Worker {
 constructor(){this.dead=false;const self={postMessage:(data,transfer)=>{const copy=structuredClone(data,{transfer});queueMicrotask(()=>{if(!this.dead)this.onmessage?.({data:copy});});}};this.self=self;
 vm.runInNewContext(fs.readFileSync('static/js/den/native-occlusion-worker.js','utf8'),{THREE,MeshBVHLib:lib.MeshBVHLib,self,importScripts(){}});}
 postMessage(data,transfer){posts++;const copy=structuredClone(data,{transfer});queueMicrotask(()=>{if(!this.dead)this.self.onmessage({data:copy});});}
 terminate(){this.dead=true;terminated++;}
}
const ctx={THREE,MeshBVHLib:lib.MeshBVHLib,Float32Array,Worker,setTimeout,clearTimeout};
vm.runInNewContext(fs.readFileSync('static/js/den/native-occlusion.js','utf8'),ctx);
const flush=async()=>{for(let i=0;i<30;i++)await Promise.resolve();};
(async()=>{
 const index=new ctx.NativeOcclusion.Index();
 const geometry=new THREE.BoxGeometry(2,2,2,30,30,30);
 const materials=Array.from({length:6},(_,i)=>new THREE.MeshBasicMaterial({side:i%2?THREE.DoubleSide:THREE.FrontSide,transparent:i===4}));
 const mesh=new THREE.Mesh(geometry,materials);mesh.position.set(.1,.1,0);mesh.scale.set(1.3,.8,1.1);mesh.rotation.y=.2;mesh.updateMatrixWorld(true);
 const indices=geometry.index.array.slice(),positions=geometry.attributes.position.array.slice();
 const ray=new THREE.Raycaster(new THREE.Vector3(0,0,5),new THREE.Vector3(0,0,-1),.1,10);
 index.prepare([mesh]);assert.equal(index.hits(mesh,ray),null,'pending index preserves web rendering');await flush();
 for(let x=-2;x<=2;x+=.2)for(const far of [2,5,10]){
  ray.set(new THREE.Vector3(x,.3,5),new THREE.Vector3(0,0,-1));ray.far=far;
  const original=ray.intersectObject(mesh,false),fast=index.hits(mesh,ray);assert(fast);
  assert.equal(fast.length,original.length);for(let i=0;i<fast.length;i++){assert(Math.abs(fast[i].distance-original[i].distance)<1e-5);assert.equal(fast[i].face.materialIndex,original[i].face.materialIndex);}
 }
 assert.deepEqual(geometry.index.array,indices);assert.deepEqual(geometry.attributes.position.array,positions);assert(geometry.attributes.position.array.byteLength>0,'render buffers are not detached');
 assert.equal(geometry.boundsTree,undefined,'do not mutate rendered geometry');
 const count=posts;index.prepare([mesh]);await flush();assert.equal(posts,count,'reuse cached static geometry');
 geometry.attributes.position.needsUpdate=true;index.prepare([mesh]);assert.equal(index.hits(mesh,ray),null);await flush();assert(posts>count,'rebuild after vertex update');
 index.prepare([]);assert.equal(index.entries.size,0);index.dispose();assert.equal(terminated,1);
 const bad=new ctx.NativeOcclusion.Index();bad.prepare([mesh]);await Promise.resolve();bad.fail();assert.equal(bad.hits(mesh,ray),null);await flush();assert.equal(bad.entries.size,0);bad.dispose();
 const gone=new ctx.NativeOcclusion.Index();gone.prepare([mesh]);gone.dispose();await flush();assert.equal(gone.entries.size,0);
 console.log('PASS native occlusion: real worker/BVH, exact ray distances and material groups, unchanged render buffers, cache invalidation, failure and disposal');
})().catch(e=>{console.error(e);process.exit(1)});
