(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.SpeakerGate=api;})(typeof window!=='undefined'?window:globalThis,function(){
 'use strict';
 class Gate{
  constructor({onStart,onTurn,onError}){Object.assign(this,{onStart,onTurn,onError});this.reset();}
  reset(){this.parts=[];this.lead=[];this.silence=0;this.samples=0;this.closed=false;this.busy=false;this.epoch=(this.epoch||0)+1;}
  close(){this.reset();this.closed=true;}
  push(buffer){
   if(this.closed||this.busy)return;
   const data=new Int16Array(buffer);let sum=0;for(const n of data)sum+=n*n;
   const voiced=Math.sqrt(sum/Math.max(1,data.length))/32768>.008;
   if(!this.parts.length){this.lead.push(buffer.slice(0));if(this.lead.length>3)this.lead.shift();if(!voiced)return;this.parts=this.lead;this.lead=[];this.onStart();}
   else this.parts.push(buffer.slice(0));
   this.samples+=data.length;this.silence=voiced?0:this.silence+data.length;
   if(this.silence>=11200||this.samples>=240000){
    const bytes=this.parts.reduce((s,p)=>s+p.byteLength,0),pcm=new Uint8Array(bytes);let offset=0;
    for(const p of this.parts){pcm.set(new Uint8Array(p),offset);offset+=p.byteLength;}
    this.parts=[];this.samples=0;this.silence=0;this.busy=true;const epoch=this.epoch;
    Promise.resolve().then(()=>{if(epoch===this.epoch&&!this.closed)return this.onTurn(pcm.buffer);}).catch(e=>{if(epoch===this.epoch)this.onError(e);}).finally(()=>{if(epoch===this.epoch)this.busy=false;});
   }
  }
 }
 return {Gate};
});
