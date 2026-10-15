/* Persistent contents of the existing cat-home bowls; inventory is separate. */
(function(){
 class Controller{
  constructor({THREE:T,canvas,camera,decor,scope,enabled,note,invite}){
   Object.assign(this,{T,canvas,camera,decor,scope,enabled,note,invite});this.state=null;this.home=null;this.pending=null;
   this.tip=document.createElement('div');this.tip.className='bowl-tip';this.tip.hidden=true;this.tip.setAttribute('role','status');document.body.append(this.tip);
   this.panel=document.createElement('dialog');this.panel.className='bowl-panel';this.panel.innerHTML='<form method="dialog"><button class="bowl-close" aria-label="关闭">×</button></form><h2></h2><p class="bowl-level"></p><progress max="100"></progress><p class="bowl-stock"></p><p class="bowl-help"></p><button class="bowl-invite">叫它过来</button> <button class="bowl-refill">补充</button> <a href="/supplies" target="_blank" rel="noopener">去补给站 ↗</a>';document.body.append(this.panel);
   this.panel.querySelector('.bowl-invite').onclick=()=>{const kind=this.kind;this.panel.close();this.invite(kind);};
   this.panel.querySelector('.bowl-refill').onclick=()=>this.refill();
   canvas.addEventListener('pointermove',e=>this.hover(e));canvas.addEventListener('pointerleave',()=>this.tip.hidden=true);
   this.timer=setInterval(()=>{if(!document.hidden&&this.enabled())void this.refresh();else this.tip.hidden=true;},15000);void this.refresh();
  }
  bind(home){this.home=home;this.paint();}
  amount(kind){return this.state?(this.state.bowls?.['3']?.[kind]??100):null;}
  async refresh(){try{const r=await fetch('/api/supplies',{cache:'no-store'});if(!r.ok)return;const d=await r.json();if(d.scope!==this.scope){this.state=null;return;}this.state=d;this.paint();}catch{}}
  paint(){
   if(this.home&&this.state)this.home.traverse(o=>{if(!o.isMesh)return;const kind=o.name==='cat_home_kibble'?'food':o.name==='cat_home_water'?'water':null;if(!kind)return;const n=this.amount(kind);o.visible=n>0;if(!o.userData.bowlBase)o.userData.bowlBase={y:o.position.y,scale:o.scale.y};const b=o.userData.bowlBase;o.scale.y=b.scale*(.25+.75*n/100);});
   if(this.panel.open)this.render();
  }
  pick(e){
   if(!this.enabled()||!this.home||this.panel.open)return null;
   const T=this.T,r=this.canvas.getBoundingClientRect(),ray=new T.Raycaster();ray.setFromCamera(new T.Vector2((e.clientX-r.left)/r.width*2-1,-(e.clientY-r.top)/r.height*2+1),this.camera);
   this.home.updateWorldMatrix(true,false);let best=null;
   for(const [kind,x] of [['food',.1],['water',.8]]){
    const center=this.home.localToWorld(new T.Vector3(x,.35,5.38)),hit=ray.ray.intersectSphere(new T.Sphere(center,.30),new T.Vector3());if(!hit)continue;
    const distance=hit.distanceTo(ray.ray.origin);if(!best||distance<best.distance)best={kind,distance};
   }
   if(best){const hit=ray.intersectObject(this.decor,true).find(h=>h.object.visible);if(hit&&hit.distance+.15<best.distance)return null;}
   return best?.kind||null;
  }
  hover(e){const kind=e.buttons?null:this.pick(e);this.tip.hidden=!kind;if(!kind)return;const n=this.amount(kind);this.tip.textContent=(kind==='food'?'食盆':'水盆')+' · '+(n===null?'读取中…':'剩余 '+n+'%')+' · 点击补充';this.tip.style.left=Math.max(8,Math.min(innerWidth-270,e.clientX+16))+'px';this.tip.style.top=Math.max(8,Math.min(innerHeight-55,e.clientY+18))+'px';}
  open(kind){this.kind=this.pending?.kind||kind;this.tip.hidden=true;this.panel.showModal();this.render();void this.refresh();}
  render(){const kind=this.kind,n=this.amount(kind),p=this.panel;p.querySelector('h2').textContent=kind==='food'?'岛上的食盆':'岛上的水盆';p.querySelector('.bowl-level').textContent=n===null?'正在读取剩余量…':'盆内剩余 '+n+'%';p.querySelector('progress').value=n||0;p.querySelector('.bowl-stock').textContent='背包口粮：'+(this.state?.inventory?.kibble??0)+' 份';p.querySelector('.bowl-help').textContent=kind==='food'?'每份口粮补充 25%，最多 100%；首次赠送满盆。':'清水免费加满；首次赠送满盆。';const use=p.querySelector('.bowl-invite');use.textContent=kind==='food'?'叫它吃饭':'叫它喝水';use.disabled=!n||this.busy||this.state?.guest;const b=p.querySelector('.bowl-refill');b.textContent=this.busy?'处理中…':this.pending?'重试上次补充':kind==='food'?'添加 1 份口粮':'免费加满清水';b.disabled=this.busy||!this.state||this.state.guest||(!this.pending&&n>=100);if(this.state?.guest)p.querySelector('.bowl-help').textContent='登录后可保存盆内存量并补充。';}
  async mutate(op,data){const r=await fetch('/api/supplies/'+op,{method:'POST',headers:{'Content-Type':'application/json','X-Profile-Scope':this.scope},body:JSON.stringify(data),signal:AbortSignal.timeout(8000)});const d=await r.json();if(!r.ok){const e=new Error(d.error||'操作失败');e.definite=true;throw e;}if(d.scope!==this.scope)throw new Error('账号已变化，请刷新');this.state=d;this.paint();}
  async refill(){if(this.busy)return;this.pending??={token:crypto.randomUUID(),pet:'3',kind:this.kind};this.busy=true;this.render();try{await this.mutate('bowl-refill',this.pending);this.pending=null;this.note('已补充到岛上的盆里');}catch(e){if(e.definite)this.pending=null;this.note(e.message||'网络暂时不可用，请重试');}finally{this.busy=false;this.render();}}
  consume(kind,event){if(!this.state||this.state.guest)return;const data={pet:'3',kind,token:'bowl-'+event};const run=async(attempt)=>{try{await this.mutate('bowl-consume',data);}catch(e){if(!e.definite&&attempt<2)setTimeout(()=>run(attempt+1),2000);else this.note('盆内存量未同步，请稍后刷新');}};void run(0);}
 }
 window.IslandBowls={Controller};
})();
