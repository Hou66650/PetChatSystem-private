/* Desktop-only sequencing: shared island/visit playback is intentionally unchanged. */
(function(root,factory){if(typeof module==='object')module.exports=factory(require('./actions'));else root.DesktopAnimator=factory(root.DesktopActions);})(globalThis,A=>{
 'use strict';
 class Animator{
  constructor(T,pet){
   this.T=T;this.pet=pet;this.mixer=pet.mixer;this.clips=pet.clips;
   this.supported=A.supported(this.clips);this.ids=new Set(this.supported.map(a=>a.id));
   this.intent='idle';this.serial=-1;this.posture='stand';this.phase='idle';this.rate=1;this.clock=0;this.weights=new Map();
   if(pet.active){pet.active.stopFading();pet.active.setEffectiveWeight(1);this.weights.set(pet.active,1);}
   this.active=pet.active;this.blend=null;this.transition=null;
  }
  request(id,serial){
   if(this.serial===serial)return;
   this.serial=serial;this.intent=this.ids.has(id)?id:'idle';this.completed=false;
   // Finish posture transitions before honoring the newest intent; never restart them.
   if(!this.transition)this.route();
  }
  play(clip,loop,phase){
   if(!clip){this.mixer.stopAllAction();this.active=this.pet.active=null;this.weights.clear();this.blend=null;this.phase=phase;return;}
   const next=this.mixer.clipAction(clip),old=this.active;
   if(next===old&&loop&&this.phase===phase)return;
   const starts=new Map(this.weights);
   next.stopFading();next.reset().setLoop(loop?this.T.LoopRepeat:this.T.LoopOnce,loop?Infinity:1);
   next.clampWhenFinished=!loop;next.setEffectiveTimeScale(1).setEffectiveWeight(starts.get(next)||0).play();
   starts.set(next,starts.get(next)||0);this.weights=starts;
   this.blend={starts:new Map(starts),next,age:0,duration:.26};this.active=next;this.phase=phase;this.clock=0;this.rate=1;
   this.pet.active=next;this.pet.action=this.intent;
  }
  transitionTo(name,done){
   const clip=A.find(this.clips,[name]);
   if(!clip){done();return;}
   this.transition={duration:clip.duration,done};this.play(clip,false,name);
  }
  route(){
   if(this.transition)return;
   const target=this.completed?'idle':this.intent,a=A.byId.get(target)||A.byId.get('idle');
   if(this.posture!=='stand'&&this.posture!==target){
    this.transitionTo('stand_up',()=>{this.posture='stand';this.route();});return;
   }
   if(a.enter&&this.posture!==target){
    this.transitionTo(a.enter,()=>{this.posture=target;this.route();});return;
   }
   if(this.phase==='walk'&&target!=='walk'&&target==='idle'&&A.find(this.clips,['stop'])){
    this.transitionTo('stop',()=>this.route());return;
   }
   this.play(A.find(this.clips,a.clips),!!a.loop,target);
  }
  get locomotionReady(){return this.intent==='walk'&&!this.transition&&this.posture==='stand'&&this.phase==='walk'&&!this.blend;}
  update(dt,targetRate=1){
   dt=Math.max(0,Math.min(.05,dt));this.clock+=dt;
   if(this.active){
    const goal=this.phase==='walk'?Math.max(.12,Math.min(3,targetRate)):1;
    this.rate+=(goal-this.rate)*(1-Math.exp(-dt*12));this.active.setEffectiveTimeScale(this.rate);
   }
   if(this.blend){
    const b=this.blend;b.age+=dt;const t=Math.min(1,b.age/b.duration),s=t*t*(3-2*t);
    for(const [action,w] of b.starts){const weight=w*(1-s)+(action===b.next?s:0);action.setEffectiveWeight(weight);this.weights.set(action,weight);}
    if(t===1){for(const action of this.weights.keys())if(action!==b.next)action.stop();this.weights=new Map([[b.next,1]]);this.blend=null;}
   }
   this.mixer.update(dt);
   if(this.transition&&this.clock>=this.transition.duration){const done=this.transition.done;this.transition=null;done();}
   else if(!this.transition&&this.active&&!A.byId.get(this.phase)?.loop&&this.active.time>=this.active.getClip().duration){this.completed=true;this.route();}
  }
  dispose(){this.mixer.stopAllAction();this.weights.clear();this.transition=null;this.blend=null;}
 }
 return {Animator};
});
