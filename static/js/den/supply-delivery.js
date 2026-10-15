(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.SupplyDelivery=api;})(typeof window!=='undefined'?window:globalThis,function(){
 'use strict';
 class Controller{
  constructor(api){this.a=api;this.client=crypto.randomUUID();this.busy=false;this.active=null;this.finished=new Set();this.timer=setInterval(()=>this.poll(),4000);this.lost=false;this.disposed=false;}
  async request(op,data){const abort=new AbortController(),timer=setTimeout(()=>abort.abort(),8000);try{const r=await fetch('/api/supplies/'+op,{method:'POST',headers:{'Content-Type':'application/json','X-Profile-Scope':this.a.scope},body:JSON.stringify({...data,client:this.client}),signal:abort.signal});const d=await r.json();if(d.scope&&d.scope!==this.a.scope||r.status===403||r.status===409&&d.error?.includes('账号')){this.lost=true;throw Error(d.error||'账号已切换');}if(!r.ok)throw Error(d.error||'补给暂时无法领取');return d;}finally{clearTimeout(timer);}}
  async poll(){if(this.disposed||this.busy||this.lost||document.hidden||!this.a.ready())return;this.busy=true;const pet=String(this.a.pet());try{const d=await this.request('claim',{pet});if(!d.delivery||this.disposed)return;const item=d.delivery;
   if(!this.finished.has(item.id)){if(document.hidden||String(this.a.pet())!==pet||!this.a.ready())return;const done=await this.a.use(item);if(!done||this.disposed)return;this.finished.add(item.id);}
   await this.request('complete',{pet,delivery:item.id});this.finished.delete(item.id);this.a.note(item.item.name+'已经用好啦。');
  }catch(e){if(this.lost)this.a.note('补给连接已变化，请刷新小岛。');}finally{this.busy=false;}}
  dispose(){this.disposed=true;clearInterval(this.timer);}
 }
 // Lightweight ceramic serving bowl. Built only while this selected island uses supplies.
 function bowl(T,water){const root=new T.Group(),mat=new T.MeshStandardMaterial({color:water?0xa7c7c5:0x9db49a,roughness:.52}),rim=new T.Mesh(new T.TorusGeometry(.15,.018,8,32),mat);rim.rotation.x=Math.PI/2;rim.position.y=.09;root.add(rim);const shell=new T.Mesh(new T.CylinderGeometry(.15,.115,.08,32,1,true),mat);shell.position.y=.05;root.add(shell);const surface=new T.Mesh(new T.CircleGeometry(.133,32),new T.MeshStandardMaterial({color:water?0x83c1cc:0xb5945e,roughness:water?.18:.9,metalness:0}));surface.rotation.x=-Math.PI/2;surface.position.y=.07;root.add(surface);if(!water){const geo=new T.SphereGeometry(.018,6,4);for(let i=0;i<24;i++){const grain=new T.Mesh(geo,surface.material);const r=.105*Math.sqrt((i+.5)/24),angle=i*2.4;grain.position.set(Math.cos(angle)*r,.077,Math.sin(angle)*r);grain.scale.y=.6;root.add(grain);}}return root;}
 return {Controller,bowl};
});
