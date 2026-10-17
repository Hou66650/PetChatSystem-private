/* Exact nearest-point queries on the original scene, with isolated worker BVHs. */
(function(root){
 'use strict';
 class Picker {
  constructor(){this.index=null;this.disposed=false;}
  prepare(object){
   if(this.disposed)return;
   if(!this.index)this.index=new root.NativeOcclusion.Index();
   const meshes=[];object.traverse(o=>{if(o.isMesh&&o.geometry?.attributes.position)meshes.push(o);});
   this.index.prepare(meshes);
  }
  nearest(object,ray,visibleOnly=false){
   // Unavailable/building/unsupported geometry keeps the original raycast path.
   if(!this.disposed)this.prepare(object);
   let best=null;
   object.traverse(o=>{
    if((visibleOnly&&!o.visible)||!ray.layers.test(o.layers))return;
    let hits=null;
    if(!this.disposed&&o.isMesh&&o.geometry?.attributes.position){
     const first=ray.firstHitOnly;ray.firstHitOnly=true;
     try{hits=this.index?.hits(o,ray);}finally{if(first===undefined)delete ray.firstHitOnly;else ray.firstHitOnly=first;}
    }
    if(hits==null)hits=ray.intersectObject(o,false);
    const h=hits[0];
    // BVH triangle indices belong to its private geometry. Expose only the
    // point/distance needed by interactions, and preserve the original object.
    if(h&&(!best||h.distance<best.distance))best={distance:h.distance,point:h.point,object:o};
   });
   return best;
  }
  dispose(){this.disposed=true;this.index?.dispose();this.index=null;}
 }
 root.ScenePicking={Picker};
})(globalThis);
