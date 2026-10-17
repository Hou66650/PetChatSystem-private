const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const THREE=require('../static/js/vendor/three.min.js');
const lib={THREE};vm.runInNewContext(fs.readFileSync('static/js/vendor/three-mesh-bvh-0.5.23.js','utf8'),lib);
class Worker {
 constructor(){const self={postMessage:(data,transfer)=>{const result=structuredClone(data,{transfer});queueMicrotask(()=>{if(!this.dead)this.onmessage?.({data:result});});}};this.self=self;
  vm.runInNewContext(fs.readFileSync('static/js/den/native-occlusion-worker.js','utf8'),{THREE,MeshBVHLib:lib.MeshBVHLib,self,importScripts(){}});}
 postMessage(data,transfer){const copy=structuredClone(data,{transfer});queueMicrotask(()=>{if(!this.dead)this.self.onmessage({data:copy});});}
 terminate(){this.dead=true;}
}
const ctx={THREE,MeshBVHLib:lib.MeshBVHLib,Float32Array,Worker,setTimeout,clearTimeout};
for(const file of ['native-occlusion','scene-picking'])vm.runInNewContext(fs.readFileSync('static/js/den/'+file+'.js','utf8'),ctx);
const flush=async()=>{for(let i=0;i<50;i++)await Promise.resolve();};
const scene=new THREE.Group(),geometry=new THREE.BoxGeometry(2,2,2,30,30,30),positions=geometry.attributes.position.array.slice(),indices=geometry.index.array.slice();
const mesh=new THREE.Mesh(geometry,Array.from({length:6},()=>new THREE.MeshBasicMaterial({side:THREE.DoubleSide})));
mesh.rotation.y=.2;mesh.scale.set(1,.8,1.1);scene.add(mesh);
const small=new THREE.Mesh(new THREE.BoxGeometry(.5,.5,.5),new THREE.MeshBasicMaterial());small.position.set(0,.2,2);scene.add(small);
scene.updateMatrixWorld(true);
const ray=new THREE.Raycaster(new THREE.Vector3(0,0,6),new THREE.Vector3(0,0,-1),.1,20);
const picker=new ctx.ScenePicking.Picker();
function compare(visible=false){
 const original=ray.intersectObject(scene,true).find(h=>!visible||h.object.visible),fast=picker.nearest(scene,ray,visible);
 assert.equal(!!fast,!!original);if(original){assert.equal(fast.object,original.object);assert(Math.abs(fast.distance-original.distance)<1e-5);assert(fast.point.distanceTo(original.point)<1e-5);}
 assert.equal(ray.firstHitOnly,undefined,'restore caller ray settings');
}
(async()=>{
 compare();await flush();assert(picker.index.entries.get(geometry)?.proxy,'worker index is active');
 for(let x=-2;x<=2;x+=.1){ray.set(new THREE.Vector3(x,.2,6),new THREE.Vector3(0,0,-1));compare();}
 small.visible=false;ray.set(new THREE.Vector3(0,.2,6),new THREE.Vector3(0,0,-1));compare();compare(true);
 mesh.layers.set(2);ray.layers.set(2);compare(true);assert(picker.nearest(scene,ray,true),'proxy must preserve mesh layer');
 mesh.position.x=.4;mesh.updateMatrixWorld(true);compare(true);
 geometry.attributes.position.needsUpdate=true;compare(true);await flush();compare(true);
 geometry.groups[0].materialIndex=1;compare(true);await flush();compare(true);
 geometry.setDrawRange(0,60);compare(true);assert.equal(picker.index.entries.size,0,'partial ranges use original geometry');
 geometry.setDrawRange(0,Infinity);compare(true);await flush();
 // A custom raycast sharing an indexed geometry must never use its static BVH.
 const custom=new THREE.Mesh(geometry,new THREE.MeshBasicMaterial());custom.layers.set(2);
 custom.raycast=(_r,hits)=>hits.push({distance:.2,point:new THREE.Vector3(0,0,5.8),object:custom});scene.add(custom);compare();
 scene.remove(custom);picker.index.fail();compare(true);picker.dispose();compare(true);
 assert.deepEqual(geometry.attributes.position.array,positions);assert.deepEqual(geometry.index.array,indices);assert.equal(geometry.boundsTree,undefined);
 const template=fs.readFileSync('templates/den.html','utf8');assert(template.includes('pickScene:ray=>scenePicker.nearest(decorGroup,ray,true)'));
 assert(template.includes('scenePicker.nearest(decorGroup,raycaster)?.point'));
 console.log('PASS scene picking: exact nearest points, original object, visibility, layers/transforms, worker warmup, edits/groups/ranges, custom rays, failure/dispose and untouched render geometry');
})().catch(e=>{console.error(e);process.exitCode=1;});
