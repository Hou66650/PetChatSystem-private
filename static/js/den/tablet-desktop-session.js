/* Trip credentials stay in this window's memory; never in URLs or localStorage. */
(function(root,factory){const api=factory();if(typeof module==='object')module.exports=api;else root.TabletDesktopSession=api;})(globalThis,()=>{
 class Session{
  constructor({request,load,show,dispose,changed,now=Date.now}){Object.assign(this,{request,load,show,dispose,changed,now});this.epoch=0;this.token='';this.phase='idle';this.lastContact=0;this.busy=false;this.closed=true;}
  async start(code){
   if(!this.closed)throw Error('请先召回当前桌宠');
   const epoch=++this.epoch;this.closed=false;this.phase='preparing';this.changed(this.phase);
   try{
    const paired=await this.request('pair',{code},'');
    if(epoch!==this.epoch){await this.request('return',{},paired.token).catch(()=>{});return;}
    this.token=paired.token;if(paired.protocol!==2||typeof this.token!=='string'||!this.token)throw Error('不兼容的传送协议');
    this.pet=paired.pet;this.lastContact=this.now();
    this.manifest=await this.request('manifest',{},this.token);
    if(epoch!==this.epoch)return;
    await this.load(this.pet,this.manifest,this.token,()=>epoch===this.epoch);
    if(epoch!==this.epoch)return;
    await this.show();if(epoch!==this.epoch)return;
    await this.request('ready',{},this.token);if(epoch!==this.epoch)return;
    this.phase='entering';this.changed(this.phase);
   }catch(error){if(epoch===this.epoch){await this.close(error.message);throw error;}}
  }
  async poll(){
   if(this.closed||!this.token||this.busy)return;const epoch=this.epoch;this.busy=true;
   try{
    const state=await this.request('state',null,this.token);if(epoch!==this.epoch)return;
    if(!['preparing','entering','emerging','roaming'].includes(state.phase))throw Error('传送状态无效');
    const order=['preparing','entering','emerging','roaming'];
    if(order.indexOf(state.phase)>=order.indexOf(this.phase)){this.phase=state.phase;this.changed(this.phase);}
    if(this.phase==='roaming'){
     const m=await this.request('manifest',{},this.token);if(epoch!==this.epoch)return;
     if(m.modelSha256!==this.manifest.modelSha256||JSON.stringify(m.accessories)!==JSON.stringify(this.manifest.accessories))throw Error('模型或穿搭已变化，请重新传送');
    }
    await this.request('ping',{},this.token);if(epoch===this.epoch)this.lastContact=this.now();
   }catch(error){if(epoch===this.epoch&&(error.ended||this.now()-this.lastContact>40000||error.message.includes('变化')||error.message.includes('无效')))await this.close(error.message);}
   finally{if(epoch===this.epoch)this.busy=false;}
  }
  async arrived(){if(this.phase!=='emerging'||this.closed)return;const epoch=this.epoch;await this.request('arrived',{},this.token);if(epoch===this.epoch){this.phase='roaming';this.changed(this.phase);}}
  async close(message='宠物已收起，正在返回小窝'){
   if(this.closed)return;this.closed=true;++this.epoch;this.busy=false;const token=this.token;this.token='';this.phase='closed';this.dispose();this.changed('closed',message);
   if(token)await this.request('return',{},token).catch(()=>{});
  }
 }
 return {Session};
});
