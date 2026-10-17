/* Shared doorway clipping. Materials and transforms are restored on cancellation. */
(function(root){
 'use strict';
 class Crossing{
  constructor(T,model,{from,to,gateZ,duration=1.8,onComplete=()=>{}}){
   Object.assign(this,{T,model,from:from.clone(),to:to.clone(),duration,onComplete,age:0,done:false});
   this.original={position:model.position.clone(),yaw:model.rotation.y,visible:model.visible};
   this.materials=new Map();const plane=new T.Plane(new T.Vector3(0,0,1),-gateZ);
   model.traverse(o=>{for(const m of o.material?(Array.isArray(o.material)?o.material:[o.material]):[]){if(this.materials.has(m))continue;this.materials.set(m,{planes:m.clippingPlanes,intersection:m.clipIntersection});m.clippingPlanes=[plane];m.clipIntersection=false;m.needsUpdate=true;}});
   model.position.copy(from);model.rotation.y=Math.atan2(to.x-from.x,to.z-from.z);model.visible=true;
  }
  update(dt){if(this.done)return;this.age+=Math.max(0,Math.min(dt,.1));const t=Math.min(1,this.age/this.duration);this.model.position.lerpVectors(this.from,this.to,t);if(t===1){this.done=true;this.onComplete();}}
  dispose(restore=false){for(const [m,s] of this.materials){m.clippingPlanes=s.planes;m.clipIntersection=s.intersection;m.needsUpdate=true;}this.materials.clear();if(restore){this.model.position.copy(this.original.position);this.model.rotation.y=this.original.yaw;this.model.visible=this.original.visible;}this.done=true;}
 }
 root.PortalTransition={Crossing};
})(globalThis);
