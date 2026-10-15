/* One autonomous body per account across same-origin browser tabs. */
(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.CatPresence=api;})(typeof window!=='undefined'?window:globalThis,function(){
 class Lease{
  constructor({scope,active,locks=globalThis.navigator?.locks}){Object.assign(this,{scope,active,locks});this.leader=!locks;this.closed=false;this.timer=setInterval(()=>this.poll(),1500);this.poll();globalThis.addEventListener?.('pagehide',()=>this.dispose());}
  poll(){if(this.closed)return;if(!this.active()){this.release?.();return;}if(!this.locks||this.pending)return;this.pending=true;this.locks.request('pait-cat-body:'+this.scope,{ifAvailable:true},async lock=>{if(!lock||this.closed||!this.active())return;this.leader=true;await new Promise(r=>this.release=r);this.leader=false;this.release=null;}).catch(()=>{this.leader=false;}).finally(()=>{this.pending=false;});}
  dispose(){this.closed=true;clearInterval(this.timer);this.release?.();this.leader=false;}
 }
 return {Lease};
});
