/* Cat-only autonomous behavior. Navigation owns horizontal movement; poses are additive. */
(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.CatLife=api;})(typeof window!=='undefined'?window:globalThis,function(){
 'use strict';
 const clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
 const smooth=x=>{x=clamp(x,0,1);return x*x*(3-2*x);};
 function idleChoice(r,previous){const pool=['idle','curious','ears','sniff','stretch','yawn','affection'].filter(k=>k!==previous);return pool[Math.min(pool.length-1,Math.floor(r*pool.length))];}
 class Controller{
  constructor(T,model,locomotion,{random=Math.random,animate=()=>{},walls=[]}={}){
   Object.assign(this,{T,model,locomotion,random,animate,walls});this.elapsed=0;this.wait=9;this.active=null;this.approach=null;this.last=null;this.entries=[];this.lookUntil=0;this.lookYaw=0;this.lookHeight=.6;this.lookAtCamera=false;
   model.traverse(b=>{if(b.isBone&&!/^SOCKET/.test(b.name))this.entries.push({bone:b,q:b.quaternion.clone(),p:b.position.clone(),applied:false,shifted:false});});
   this.byName=Object.fromEntries(this.entries.map(e=>[e.bone.name,e]));this.axis=new T.Vector3();this.q=new T.Quaternion();this.parentQ=new T.Quaternion();this.modelQ=new T.Quaternion();this.target=new T.Vector3();
  }
  beforeFrame(){for(const e of this.entries){if(e.applied){e.bone.quaternion.copy(e.q);e.applied=false;}if(e.shifted){e.bone.position.copy(e.p);e.shifted=false;}}}
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
   this.locomotion.interrupt(3);this.animate(kind==='groom'?'sit':'idle');
   this.active={kind,time:0,duration:kind==='jump'?1.65:kind==='rub'?5.4:kind==='groom'?7.2:4.6,side:this.random()<.5?-1:1,start:{x:p.x,z:p.z},end};this.last=kind;return true;
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
   this.lookingAlongRoute=false;
   if(this.active)return null;
   const p=this.model.position,path=this.locomotion.path;
   if(path.length||this.locomotion.velocity>.08){
    // Follow a point ahead along the route, never a near waypoint behind the head.
    // Persistent face/camera attention must not override travel attention.
    this.lookingAlongRoute=true;
    let from=p,remaining=1.2,aim=null;
    for(const point of path){
     const length=Math.hypot(point.x-from.x,point.z-from.z);
     if(length>.001){const u=Math.min(1,remaining/length);aim={x:from.x+(point.x-from.x)*u,z:from.z+(point.z-from.z)*u};remaining-=length;if(remaining<=0)break;}
     from=point;
    }
    const body=this.model.rotation.y;
    const desired=aim&&Math.hypot(aim.x-p.x,aim.z-p.z)>.03?Math.atan2(aim.x-p.x,aim.z-p.z):body;
    const relative=Math.atan2(Math.sin(desired-body),Math.cos(desired-body));
    const yaw=body+clamp(relative,-.65,.65);
    const head=this.byName.head?.bone;this.model.updateMatrixWorld(true);
    const height=head?head.getWorldPosition(this.target).y:p.y+.6;
    return this.target.set(p.x+Math.sin(yaw)*2,height,p.z+Math.cos(yaw)*2);
   }
   if(explicit)return explicit;
   // Hold a focus between occasional changes instead of sweeping like a metronome.
   if(this.elapsed>=this.lookUntil){this.lookUntil=this.elapsed+1.8+this.random()*3.6;this.lookYaw=(this.random()-.5)*1.25;this.lookHeight=.48+this.random()*.22;this.lookAtCamera=this.random()<.22;}
   if(this.lookAtCamera&&camera)return camera;
   const yaw=this.model.rotation.y+this.lookYaw;
   return this.target.set(p.x+Math.sin(yaw)*2,p.y+this.lookHeight,p.z+Math.cos(yaw)*2);
  }
  rotate(name,axis,angle){
   const e=this.byName[name];if(!e||!angle)return;
   if(!e.applied){e.q.copy(e.bone.quaternion);e.applied=true;}
   this.axis.set(...axis).normalize().applyQuaternion(this.modelQ);this.q.setFromAxisAngle(this.axis,angle);
   e.bone.parent.getWorldQuaternion(this.parentQ);this.q.premultiply(this.parentQ.clone().invert()).multiply(this.parentQ);
   e.bone.quaternion.premultiply(this.q);e.bone.updateMatrixWorld(true);
  }
  pose(dt,state,expression){
   this.model.updateMatrixWorld(true);this.model.getWorldQuaternion(this.modelQ);
   const a=this.active,t=this.elapsed;
   if(!['sleep','eat'].includes(state)){
    this.rotate('tail_mid',[0,1,0],Math.sin(t*1.35)*.10);this.rotate('tail_tip',[1,0,0],Math.sin(t*1.8)*.12);
    const ear=Math.max(0,Math.sin(t*1.17)*Math.sin(t*.43+.8))**12*.12;
    this.rotate('ear_L',[0,0,1],ear);this.rotate('ear_R',[0,0,1],-(Math.max(0,Math.sin(t*1.41+1)*Math.sin(t*.37))**18)*.10);
   }
   this.eatBlend=(this.eatBlend||0)+((state==='eat'?1:0)-(this.eatBlend||0))*(1-Math.exp(-dt*6));
   if(this.eatBlend>.001){
    const blend=this.eatBlend,e=this.byName.neck;
    if(e){e.p.copy(e.bone.position);e.shifted=true;e.bone.getWorldPosition(this.target);this.target.y-=.22*blend;e.bone.parent.worldToLocal(this.target);e.bone.position.copy(this.target);e.bone.updateMatrixWorld(true);}
    this.rotate('neck',[1,0,0],.7*blend);this.rotate('head',[1,0,0],(.15+Math.sin(t*9)*.025)*blend);
   }
   if(!a)return;
   const envelope=Math.sin(Math.PI*clamp(a.time/a.duration,0,1))**2;
   if(a.kind==='jump'){
    const air=clamp((a.time-.35)/.85,0,1),lift=Math.sin(Math.PI*air)*.32;
    this.model.position.y+=lift;
    const crouch=smooth(a.time/.16)*(1-smooth((a.time-.18)/.17));
    const landing=smooth((a.time-1.16)/.10)*(1-smooth((a.time-1.3)/.35));
    this.rotate('spine_front',[1,0,0],.10*crouch-.07*landing);
    this.rotate('spine_rear',[1,0,0],-.16*crouch+.09*landing);
    const tuck=Math.sin(Math.PI*air)*.48+crouch*.12+landing*.09;
    for(const leg of ['FL','FR','HL','HR']){this.rotate(leg+'_upper',[1,0,0],(leg[0]==='F'?-.5:.6)*tuck);this.rotate(leg+'_lower',[1,0,0],-tuck);}
    this.rotate('spine',[1,0,0],Math.sin(air*Math.PI*2)*.09*envelope);
    this.rotate('neck',[1,0,0],-.12*envelope);
   }else if(a.kind==='rub'){
    // Cheek first, then shoulder, then release. The root stays inside the safe wall corridor.
    const cheek=smooth(a.time/.7)*(1-smooth((a.time-2.4)/1.0));
    const shoulder=smooth((a.time-1.8)/1.1)*(1-smooth((a.time-4.1)/1.3));
    this.rotate('neck',[0,1,0],-.24*cheek);this.rotate('head',[0,0,1],.18*cheek);
    this.rotate('spine_front',[0,1,0],-.09*shoulder);this.rotate('spine_rear',[0,1,0],.06*shoulder);
    this.rotate('tail_tip',[1,0,0],-.13*envelope);
    if(expression)expression.update(dt,'affection',a.time/a.duration);
   }else if(a.kind==='groom'){
    const side=a.side||1,leg=side<0?'FL':'FR';
    const raised=smooth(a.time/.8)*(1-smooth((a.time-5.8)/1.4));
    const cycle=Math.max(0,a.time-.9)%1.4;
    // Three small licks, a pause, and a slow face wipe; alternate the raised paw.
    const lick=a.time<4.6&&cycle<.85?Math.sin(cycle/.85*Math.PI*3)**2:0;
    const wipe=smooth((a.time-4.6)/.55)*(1-smooth((a.time-5.5)/.7));
    this.rotate('head',[.65,0,-.76],(.32+.055*lick-.12*wipe)*raised);
    this.rotate(leg+'_upper',[1,0,0],(-.42-.16*wipe)*raised);this.rotate(leg+'_lower',[1,0,0],-1.65*raised);
    this.rotate('neck',[.65,0,-.76],(.42-.18*wipe)*raised);
    this.rotate(leg+'_foot',[1,0,0],.45*raised);
    this.rotate('neck',[0,1,0],-.15*side*raised);this.rotate('head',[0,0,1],.07*side*wipe);
    this.rotate('jaw',[1,0,0],.035*lick*raised);
   }else{
    this.rotate('spine_front',[1,0,0],.13*envelope);this.rotate('spine_rear',[1,0,0],-.10*envelope);
    this.rotate('neck',[1,0,0],.12*envelope);this.rotate('tail',[1,0,0],-.20*envelope);
   }
  }
 }
 return {Controller,idleChoice};
});
