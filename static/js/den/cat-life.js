/* Cat-only autonomous behavior. Navigation owns horizontal movement; poses are additive. */
(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.CatLife=api;})(typeof window!=='undefined'?window:globalThis,function(){
 'use strict';
 const clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
 const smooth=x=>{x=clamp(x,0,1);return x*x*(3-2*x);};
 function idleChoice(r,previous){const pool=['idle','curious','ears','sniff','stretch','yawn','affection'].filter(k=>k!==previous);return pool[Math.min(pool.length-1,Math.floor(r*pool.length))];}
 class Controller{
  constructor(T,model,locomotion,{random=Math.random,animate=()=>{},walls=[]}={}){
   Object.assign(this,{T,model,locomotion,random,animate,walls});this.elapsed=0;this.wait=9;this.active=null;this.approach=null;this.last=null;this.entries=[];
   model.traverse(b=>{if(b.isBone&&!/^SOCKET/.test(b.name))this.entries.push({bone:b,q:b.quaternion.clone(),applied:false});});
   this.byName=Object.fromEntries(this.entries.map(e=>[e.bone.name,e]));this.axis=new T.Vector3();this.q=new T.Quaternion();this.parentQ=new T.Quaternion();this.modelQ=new T.Quaternion();this.target=new T.Vector3();
  }
  beforeFrame(){for(const e of this.entries)if(e.applied){e.bone.quaternion.copy(e.q);e.applied=false;}}
  cancel(preserveCommand=false){this.beforeFrame();if(this.active){this.model.position.y=this.locomotion.navigation.surfaceHeight(this.model.position);}
   if(!preserveCommand&&(this.approach||this.active))this.locomotion.interrupt(3);this.active=null;this.approach=null;this.wait=8+this.random()*6;
  }
  begin(kind){
   const nav=this.locomotion.navigation,p=this.model.position;
   if(!nav.isWalkable(p))return false;
   let end=null;
   if(kind==='jump'){
    const yaw=this.model.rotation.y;end={x:p.x+Math.sin(yaw)*.55,z:p.z+Math.cos(yaw)*.55};
    // Check the entire swept corridor, not merely the landing point. No water/rail jumps.
    if(!nav.segmentClear(p,end)||Math.abs(nav.surfaceHeight(p)-nav.surfaceHeight(end))>.025)return false;
    if(nav.bridges.some(b=>Math.abs(p.x-b.x)<b.w/2+nav.clearance&&Math.abs(p.z-b.z)<b.d/2+nav.clearance))return false;
   }
   this.locomotion.interrupt(3);this.animate('idle');
   this.active={kind,time:0,duration:kind==='jump'?1.65:kind==='rub'?4.2:3.6,start:{x:p.x,z:p.z},end};this.last=kind;return true;
  }
  seekWall(){
   const nav=this.locomotion.navigation;
   for(const wall of this.walls){
    const point={x:wall.x+wall.nx*(nav.clearance+.04),z:wall.z+wall.nz*(nav.clearance+.04)};
    if(this.locomotion.goTo(point,{gait:'walk'})){this.approach={wall,point,time:0,path:this.locomotion.path};return true;}
   }return false;
  }
  step(dt,blocked){
   dt=clamp(dt,0,.05);this.elapsed+=dt;
   if((this.active&&this.locomotion.owner==='command')||(this.approach&&this.locomotion.owner==='command'&&this.locomotion.path!==this.approach.path)){
    this.cancel(true);return false;
   }
   if(blocked||!this.locomotion.enabled){if(this.active||this.approach)this.cancel();return false;}
   if(this.approach){
    this.approach.time+=dt;
    if(this.approach.time>35){this.cancel();return false;}
    if(!this.locomotion.path.length){
     const a=this.approach,p=this.model.position;
     if(Math.hypot(p.x-a.point.x,p.z-a.point.z)>.13){this.cancel();return false;}
     // Face along the wall, bringing the cheek/shoulder side toward its surface.
     const yaw=Math.atan2(-a.wall.nz,a.wall.nx),angle=Math.atan2(Math.sin(yaw-this.model.rotation.y),Math.cos(yaw-this.model.rotation.y));
     this.model.rotation.y+=clamp(angle,-dt*2,dt*2);
     if(Math.abs(angle)<.04){this.approach=null;this.begin('rub');}
     return true;
    }return false;
   }
   if(this.active){
    const a=this.active;a.time+=dt;
    if(a.kind==='jump'){
     const u=smooth((a.time-.35)/.85),next={x:a.start.x+(a.end.x-a.start.x)*u,z:a.start.z+(a.end.z-a.start.z)*u};
     if(!this.locomotion.navigation.segmentClear(this.model.position,next)){this.cancel();return false;}
     this.model.position.x=next.x;this.model.position.z=next.z;
    }
    if(a.time>=a.duration){this.active=null;this.wait=9+this.random()*11;this.locomotion.interrupt(2);this.animate('idle');return false;}
    return true;
   }
   this.wait-=dt;
   if(this.autonomous===false||this.wait>0||this.locomotion.owner==='command'||this.locomotion.velocity>.08||this.locomotion.path.length)return false;
   this.wait=8;const pool=['jump','rub','groom','stretch'].filter(k=>k!==this.last),kind=pool[Math.min(pool.length-1,Math.floor(this.random()*pool.length))];
   if(kind==='rub'){this.seekWall();return false;}
   return this.begin(kind);
  }
  attention(camera,explicit){
   if(explicit)return explicit;
   if(this.active)return null;
   const p=this.model.position,path=this.locomotion.path;
   if(path.length)return this.target.set(path[0].x,p.y+.55,path[0].z);
   // Brief eye contact, then independently scan; avoid permanently staring at the camera.
   if(this.elapsed%10<2.5)return camera;
   const yaw=this.model.rotation.y+Math.sin(this.elapsed*.7)*.65;
   return this.target.set(p.x+Math.sin(yaw)*2,p.y+.6+Math.sin(this.elapsed*.4)*.12,p.z+Math.cos(yaw)*2);
  }
  rotate(name,axis,angle){
   const e=this.byName[name];if(!e||!angle)return;
   if(!e.applied){e.q.copy(e.bone.quaternion);e.applied=true;}
   this.axis.set(...axis).applyQuaternion(this.modelQ);this.q.setFromAxisAngle(this.axis,angle);
   e.bone.parent.getWorldQuaternion(this.parentQ);this.q.premultiply(this.parentQ.clone().invert()).multiply(this.parentQ);
   e.bone.quaternion.premultiply(this.q);e.bone.updateMatrixWorld(true);
  }
  pose(dt,state,expression){
   this.model.updateMatrixWorld(true);this.model.getWorldQuaternion(this.modelQ);
   const a=this.active,t=this.elapsed;
   if(!['sleep','eat'].includes(state)){
    this.rotate('tail_mid',[0,1,0],Math.sin(t*1.35)*.10);this.rotate('tail_tip',[1,0,0],Math.sin(t*1.8)*.12);
    const ear=Math.max(0,Math.sin(t*1.9))**18*.12;
    this.rotate('ear_L',[0,0,1],ear);this.rotate('ear_R',[0,0,1],-(Math.max(0,Math.sin(t*1.9+1))**18)*.10);
   }
   if(!a)return;
   const envelope=Math.sin(Math.PI*clamp(a.time/a.duration,0,1))**2;
   if(a.kind==='jump'){
    const air=clamp((a.time-.35)/.85,0,1),lift=Math.sin(Math.PI*air)*.32;
    this.model.position.y+=lift;
    const tuck=Math.sin(Math.PI*air)*.48;
    for(const leg of ['FL','FR','HL','HR']){this.rotate(leg+'_upper',[1,0,0],(leg[0]==='F'?-.5:.6)*tuck);this.rotate(leg+'_lower',[1,0,0],-tuck);}
    this.rotate('spine',[1,0,0],Math.sin(air*Math.PI*2)*.09*envelope);
    this.rotate('neck',[1,0,0],-.12*envelope);
   }else if(a.kind==='rub'){
    this.rotate('neck',[0,1,0],-.28*envelope);this.rotate('head',[0,0,1],.24*envelope);
    this.rotate('spine_front',[0,1,0],Math.sin(a.time*5)*.065*envelope);
    this.rotate('tail',[1,0,0],-.17*envelope);
    if(expression)expression.update(dt,'affection',a.time/a.duration);
   }else if(a.kind==='groom'){
    this.rotate('head',[1,0,0],(.28+Math.sin(a.time*7)*.06)*envelope);
    this.rotate('FL_upper',[1,0,0],-.55*envelope);this.rotate('FL_lower',[1,0,0],-.45*envelope);
    this.rotate('neck',[0,1,0],.16*envelope);
   }else{
    this.rotate('spine_front',[1,0,0],.13*envelope);this.rotate('spine_rear',[1,0,0],-.10*envelope);
    this.rotate('neck',[1,0,0],.12*envelope);this.rotate('tail',[1,0,0],-.20*envelope);
   }
  }
 }
 return {Controller,idleChoice};
});
