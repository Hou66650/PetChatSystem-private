/* Isolated CPU ray-query geometry; never changes scene meshes or their indices. */
(function(root){
 'use strict';
 let library;
 function loadLibrary(){
  if(root.MeshBVHLib)return Promise.resolve();
  if(!library)library=new Promise((resolve,reject)=>{const script=document.createElement('script');script.src='/static/js/vendor/three-mesh-bvh-0.5.23.js';script.onload=resolve;script.onerror=()=>reject(Error('BVH unavailable'));document.head.appendChild(script);});
  return library;
 }
 class Index {
  constructor(){this.entries=new Map();this.queue=[];this.worker=null;this.current=null;this.serial=0;this.failed=false;this.disposed=false;
   loadLibrary().then(()=>{if(this.disposed)return;try{this.worker=new Worker('/static/js/den/native-occlusion-worker.js');this.worker.onmessage=e=>this.receive(e.data);this.worker.onerror=()=>this.fail();this.pump();}catch(_){this.fail();}}).catch(()=>this.fail());
  }
  eligible(o){const g=o.geometry,p=g.attributes.position;return !o.isSkinnedMesh&&!o.isInstancedMesh&&!g.morphAttributes.position?.length&&p?.array instanceof Float32Array&&!p.isInterleavedBufferAttribute&&!p.normalized&&p.itemSize===3&&g.drawRange.start===0&&(g.drawRange.count===Infinity||g.drawRange.count>=(g.index?.count||p.count));}
  prepare(objects){
   if(this.failed||this.disposed)return;
   const live=new Set();
   for(const o of objects){const g=o.geometry;if((g.index?.count||g.attributes.position.count)<15000||!this.eligible(o))continue;
    live.add(g);let entry=this.entries.get(g);
    if(entry&&(entry.position!==g.attributes.position||entry.index!==g.index||entry.pv!==g.attributes.position.version||entry.iv!==(g.index?.version||0))){entry.proxy?.geometry.dispose();this.entries.delete(g);entry=null;}
    if(!entry){entry={id:++this.serial,source:g,position:g.attributes.position,index:g.index,pv:g.attributes.position.version,iv:g.index?.version||0,proxy:null};this.entries.set(g,entry);this.queue.push(entry);}
   }
   for(const [g,e]of this.entries)if(!live.has(g)){e.proxy?.geometry.dispose();this.entries.delete(g);}
   this.queue=this.queue.filter(e=>this.entries.get(e.source)===e);this.pump();
  }
  pump(){
   if(!this.worker||this.current||this.failed||this.disposed)return;
   const e=this.queue.shift();if(!e)return;this.current=e;
   try{const position=e.position.array.slice(),index=e.index?.array.slice()||null;
    this.worker.postMessage({id:e.id,position,index,groups:e.source.groups},index?[position.buffer,index.buffer]:[position.buffer]);
    this.timeout=setTimeout(()=>this.fail(),30000);
   }catch(_){this.fail();}
  }
  receive(data){
   const e=this.current;if(!e||e.id!==data.id||this.disposed)return;
   clearTimeout(this.timeout);this.current=null;
   if(data.error){this.fail();return;}
   if(this.entries.get(e.source)===e){try{const g=new root.THREE.BufferGeometry();g.setAttribute('position',e.position);g.setIndex(new root.THREE.BufferAttribute(data.tree.index,1));g.groups=e.source.groups.map(x=>({...x}));g.boundsTree=root.MeshBVHLib.MeshBVH.deserialize(data.tree,g,{setIndex:false});e.proxy=new root.THREE.Mesh(g);e.proxy.raycast=root.MeshBVHLib.acceleratedRaycast;}catch(_){this.fail();return;}}
   this.pump();
  }
  hits(object,ray){
   const count=object.geometry.index?.count||object.geometry.attributes.position.count;
   if(count<15000)return ray.intersectObject(object,false);
   const e=this.entries.get(object.geometry);if(!e?.proxy||this.failed||this.disposed)return null;
   e.proxy.matrixWorld.copy(object.matrixWorld);e.proxy.material=object.material;
   return ray.intersectObject(e.proxy,false);
  }
  fail(){this.failed=true;this.release();}
  release(){clearTimeout(this.timeout);this.worker?.terminate();this.worker=null;this.current=null;this.queue=[];for(const e of this.entries.values())e.proxy?.geometry.dispose();this.entries.clear();}
  dispose(){this.disposed=true;this.release();}
 }
 root.NativeOcclusion={Index};
})(globalThis);
