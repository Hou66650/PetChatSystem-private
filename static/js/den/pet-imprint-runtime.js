/* Confirmed memories map to existing actions; no new motion or imagined events. */
(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.PetImprintRuntime=api;})(typeof window!=='undefined'?window:globalThis,function(){
 'use strict';
 class Controller{
  constructor(a){this.a=a;this.epoch=0;this.last={};this.pending=null;this.running=false;this.disposed=false;this.fetcher=a.fetcher||fetch;this.now=a.now||Date.now;this.pet=a.pet();}
  invalidate(){this.epoch++;this.pending=null;this.a.cancel();}
  queue(kind){if(!['greeting','comfort','play'].includes(kind))return;this.pending={kind,pet:this.a.pet(),until:this.now()+8000};}
  tick(){if(this.disposed)return;if(this.pet!==this.a.pet()){this.pet=this.a.pet();this.invalidate();this.last={};}if(!this.pending)return;if(this.pending.pet!==this.a.pet()||this.now()>this.pending.until||this.a.hidden()){this.pending=null;return;}if(!this.running&&this.a.available()){const kind=this.pending.kind;this.pending=null;void this.trigger(kind);}}
  async trigger(kind,explicit=false){if(this.disposed||this.a.hidden())return false;if(this.running||!this.a.available()){if(explicit)this.a.status('它正在忙，等当前互动结束后再试一次。');return false;}if(!explicit&&this.now()-(this.last[kind]||0)<90000)return false;
   const token=this.epoch,pet=this.a.pet();this.running=true;
   try{const r=await this.fetcher('/api/pet-imprint/'+pet,{cache:'no-store',paitQuiet:true,signal:AbortSignal.timeout(5000)}),d=await r.json();
    if(!r.ok||d.scope!==this.a.scope||d.petId!==pet)throw Error('回忆暂不可用或账号已变化');
    if(token!==this.epoch||pet!==this.a.pet()||this.a.hidden()||!this.a.available()||this.disposed)return false;
    const response=d.enabled&&d.policy.responses[kind],call=d.enabled&&d.policy.calls[kind];
    if(!response&&!call){if(explicit)this.a.status('还没有确认这类习惯或原声，请先在回忆页设置。');return false;}
    const plan=response?(kind==='greeting'||kind==='comfort'?['come',response.action]:[response.action]):[];
    if(plan.some(key=>!this.a.supports(key))){this.a.status('当前模型没有对应动作，保留回忆，等待动作适配。');return false;}
    this.last[kind]=this.now();this.a.status(response?'依据：'+response.evidence.quote+' · 使用现有动作表达':'播放主人确认的原声');
    if(plan.length&&!await this.a.play(plan))return false;
    if(token!==this.epoch||pet!==this.a.pet()||this.a.hidden()||this.disposed)return false;
    if(call)await this.a.call(kind,{explicit,imprint:d});return true;
   }catch(e){if(token===this.epoch&&!this.disposed)this.a.status(e.message||'暂时无法读取回忆');return false;}
   finally{this.running=false;}
  }
  dispose(){this.disposed=true;this.invalidate();}
 }
 return {Controller};
});
