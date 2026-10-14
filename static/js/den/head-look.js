/* Additive attention after animation, restored before the next mixer update. */
(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.PetHeadLook=api;})(typeof window!=='undefined'?window:globalThis,function(){
 'use strict';
 const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
 // Camera motion takes priority over stale face/pointer attention.
 class ViewAttention{
  constructor(){this.until=-Infinity;}
  moved(now){this.until=now+1200;}
  point(now,interactivePoint){return now<this.until?null:interactivePoint||null;}
 }
 class Controller{
  constructor(T,model){
   this.T=T;this.model=model;this.elapsed=0;this.yaw=0;this.pitch=0;
   const bones=[];model.traverse(o=>{if(o.isBone&&!/^SOCKET_/i.test(o.name))bones.push(o);});
   this.head=bones.find(b=>/^head$/i.test(b.name))||bones.find(b=>/head/i.test(b.name));
   this.neck=bones.find(b=>/^neck$/i.test(b.name))||bones.find(b=>/neck/i.test(b.name)&&!/flex/i.test(b.name));
   this.entries=[this.neck&&{bone:this.neck,share:.30},this.head&&{bone:this.head,share:this.neck?.70:1}].filter(Boolean);
   this.entries.forEach(e=>{e.base=new T.Quaternion();e.applied=false;});
   this.origin=new T.Vector3();this.direction=new T.Vector3();this.up=new T.Vector3();this.right=new T.Vector3();
   this.modelQ=new T.Quaternion();this.parentQ=new T.Quaternion();this.delta=new T.Quaternion();this.tilt=new T.Quaternion();
   this.ray=new T.Raycaster();this.plane=new T.Plane();this.screen=new T.Vector2();this.projected=new T.Vector3();
  }
  beforeFrame(){for(const e of this.entries)if(e.applied){e.bone.quaternion.copy(e.base);e.applied=false;}}
  screenTarget(point,camera,width,height){
   if(!this.head||!point||width<=0||height<=0)return null;
   this.model.updateMatrixWorld(true);this.head.getWorldPosition(this.origin);
   camera.getWorldDirection(this.direction);this.projected.copy(this.origin).addScaledVector(this.direction,-Math.max(.65,this.model.userData.height||1));
   this.plane.setFromNormalAndCoplanarPoint(this.direction,this.projected);
   this.screen.set(point.x/width*2-1,1-point.y/height*2);this.ray.setFromCamera(this.screen,camera);
   return this.ray.ray.intersectPlane(this.plane,this.projected);
  }
  update(dt,target,{state='idle',blocked=false}={}){
   if(!this.head)return;
   this.beforeFrame();dt=clamp(dt,0,.1);this.elapsed+=dt;this.model.updateMatrixWorld(true);
   this.head.getWorldPosition(this.origin);this.model.getWorldQuaternion(this.modelQ);
   let yaw=Math.sin(this.elapsed*.55)*.09,pitch=Math.sin(this.elapsed*.37)*.035;
   if(target){
    this.direction.copy(target).sub(this.origin).applyQuaternion(this.modelQ.clone().invert());
    if(this.direction.lengthSq()>.0001){yaw=Math.atan2(this.direction.x,this.direction.z);pitch=Math.atan2(this.direction.y,Math.hypot(this.direction.x,this.direction.z));}
   }
   const quiet=blocked||['sleep','eat','sniff','yawn','shake','lieDown','sitDown','standUp','playBow','stretch','noseLick'].includes(state);
   const weight=quiet?0:['walk','trot','run','turnLeft','turnRight'].includes(state)?.22:['curious','alert','shy','affection','petting'].includes(state)?.25:1;
   yaw=clamp(yaw,-.96,.96)*weight;pitch=clamp(pitch,-.42,.52)*weight;
   const fade=1-Math.exp(-dt*6);this.yaw+=(yaw-this.yaw)*fade;this.pitch+=(pitch-this.pitch)*fade;
   this.up.set(0,1,0).applyQuaternion(this.modelQ);this.right.set(1,0,0).applyQuaternion(this.modelQ);
   for(const e of this.entries){
    e.base.copy(e.bone.quaternion);e.applied=true;
    this.delta.setFromAxisAngle(this.up,this.yaw*e.share);
    this.tilt.setFromAxisAngle(this.right,-this.pitch*e.share);this.delta.multiply(this.tilt);
    e.bone.parent.getWorldQuaternion(this.parentQ);
    this.delta.premultiply(this.parentQ.clone().invert()).multiply(this.parentQ);
    e.bone.quaternion.copy(this.delta.multiply(e.base));e.bone.updateMatrixWorld(true);
   }
  }
 }
 return {Controller,ViewAttention};
});
