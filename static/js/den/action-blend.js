/* Body-only blends; facial layers and the existing den behavior remain independent. */
(function(root,factory){const api=factory();if(typeof module==='object')module.exports=api;else root.PetActionBlend=api;})(globalThis,()=>{
 class Controller {
  constructor(T){this.T=T;this.active=null;this.weights=new Map();this.blend=null;this.rate=1;this.targetRate=1;}
  play(action,{once=false,speed=1,phase=0}={}){
   this.targetRate=Number.isFinite(speed)?speed:1;
   if(this.active===action&&!once&&action.loop===this.T.LoopRepeat)return;
   const weights=new Map(this.weights),first=!weights.size;
   action.stopFading();action.reset();action.setLoop(once?this.T.LoopOnce:this.T.LoopRepeat,once?1:Infinity);
   action.clampWhenFinished=once;action.time=Math.max(0,phase%1)*action.getClip().duration;
   this.rate=this.targetRate;action.setEffectiveTimeScale(this.rate);
   weights.set(action,weights.get(action)||(first?1:0));action.setEffectiveWeight(weights.get(action));action.play();
   this.weights=weights;this.blend={from:new Map(weights),next:action,time:0};this.active=action;
  }
  update(dt){
   dt=Math.max(0,Math.min(.1,dt));this.rate+=(this.targetRate-this.rate)*(1-Math.exp(-12*dt));this.active?.setEffectiveTimeScale(this.rate);
   if(!this.blend)return;
   const b=this.blend;b.time+=dt;const t=Math.min(1,b.time/.26),smooth=t*t*(3-2*t);
   for(const [a,weight] of b.from){const w=weight*(1-smooth)+(a===b.next?smooth:0);a.setEffectiveWeight(w);this.weights.set(a,w);}
   if(t===1){for(const a of this.weights.keys())if(a!==b.next)a.stop();this.weights=new Map([[b.next,1]]);this.blend=null;}
  }
 }
 return {Controller};
});
