/* Direct gardening: server-backed care, one-bed inspection and world-space placement. */
(function(){
 'use strict';
 const Base=FarmGarden.View,P=FarmPlacement,TOOLS={water:{key:'watering-can',x:-7.95,z:2.03},fertilize:{key:'fertilizer-tin',x:-8.75,z:2.12}};
 FarmGarden.View=class extends Base{
  constructor(api){
   super(api);this.toolModels=new Map();this.toolSources=[];this.animations=new Map();this.toolTarget=new this.T.Vector3();this.toolEpoch=0;
   this.hud=document.getElementById('farm-direct');this.hint=document.getElementById('farm-direct-hint');this.meter=document.getElementById('farm-care-meter');
   document.getElementById('farm-direct-cancel').onclick=()=>this.cancelDirect();
   document.getElementById('farm-rotate-left').onclick=()=>this.rotate(-Math.PI/12);document.getElementById('farm-rotate-right').onclick=()=>this.rotate(Math.PI/12);
   document.getElementById('farm-detail-back').onclick=()=>this.open();
   this.captureDown=e=>{
    if(!this.a.active()||this.dialog.open||e.button!==0||e.altKey)return;
    if(!this.mode)return;
    e.preventDefault();e.stopImmediatePropagation();this.ignoreClick=performance.now()+500;this.pressed=true;this.pressAt={x:e.clientX,y:e.clientY};this.careTime=0;this.careBed=null;this.point(e,false);
   };
   this.captureUp=e=>{if(!this.pressed)return;e.stopImmediatePropagation();this.pressed=false;this.ignoreClick=performance.now()+500;if(this.mode==='place'&&Math.hypot(e.clientX-this.pressAt.x,e.clientY-this.pressAt.y)<8)void this.confirmPlacement();this.careTime=0;};
   this.cancelPointer=()=>{this.pressed=false;this.careTime=0;};this.leaveHandler=()=>{this.cancelPointer();this.hoverBed=null;};
   this.keyHandler=e=>{if(this.dialog.open||!this.mode)return;if(e.key==='Escape'){e.preventDefault();this.cancelDirect();}if(['q','Q','e','E'].includes(e.key)){e.preventDefault();this.rotate(e.key.toLowerCase()==='q'?-Math.PI/12:Math.PI/12);}};
   api.canvas.addEventListener('pointerdown',this.captureDown,true);api.canvas.addEventListener('pointerleave',this.leaveHandler);window.addEventListener('pointerup',this.captureUp,true);window.addEventListener('pointercancel',this.cancelPointer);window.addEventListener('blur',this.cancelPointer);window.addEventListener('keydown',this.keyHandler);
   this.initTools();
  }
  note(text,error=false){super.note(text,error);if(this.hint&&this.mode)this.hint.textContent=text;}
  open(bed){if(bed)return this.inspect(bed);this.cancelDirect();this.inspectedBed=null;this.inspectedPlacement=null;this.resetGuide();super.open();}
  resetGuide(){this.dialog.classList.remove('is-inspecting');document.getElementById('farm-detail').hidden=true;for(const e of this.dialog.querySelectorAll('[data-guide-only]'))e.hidden=false;}
  switchTab(tab){if((this.inspectedBed||this.inspectedPlacement)&&tab!=='guide'){this.inspectedBed=null;this.inspectedPlacement=null;this.resetGuide();}super.switchTab(tab);}
  inspect(id){
   this.cancelDirect();this.inspectedPlacement=null;this.inspectedBed=id;this.dialog.classList.add('is-inspecting');super.switchTab('guide');this.dialog.showModal();this.renderInspector();
  }
  render(){super.render();if(!this.data)return;this.renderFreeStock();if(this.inspectedBed)this.renderInspector();if(this.inspectedPlacement)this.renderPlaced();}
  inspectPlaced(p){this.cancelDirect();this.inspectedBed=null;this.inspectedPlacement=p.id;this.dialog.classList.add('is-inspecting');super.switchTab('guide');this.dialog.showModal();this.renderPlaced();}
  renderPlaced(){
   const p=this.data.arrangements.find(p=>p.id===this.inspectedPlacement);if(!p){this.open();return;}const spec=this.data.catalog.find(s=>s.id===p.species);
   document.getElementById('farm-detail').hidden=false;for(const e of this.dialog.querySelectorAll('[data-guide-only]'))e.hidden=true;
   document.getElementById('farm-detail-title').textContent=spec.name+' · '+(p.container==='pot'?'花盆':'土栽');document.getElementById('farm-detail-status').textContent='已经在你的岛上安家 · 位置与朝向已存入账号。可以搬动，或完整收回仓库。';document.getElementById('farm-detail-growth').hidden=true;
   document.getElementById('farm-detail-actions').replaceChildren(this.button('移动到新位置',()=>this.beginPlacement(p)),this.button('收回仓库',()=>this.act('recover-arrangement',{id:p.id,revision:p.revision})));
   document.getElementById('farm-preview-species').value=p.species;document.getElementById('farm-preview-stage').value=10;if(this.previewKey!==FarmGarden.modelKey(p.species,10,false))void this.preview();
  }
  renderInspector(){
   if(!this.inspectedBed||!this.data)return;const bed=this.data.beds.find(b=>b.id===this.inspectedBed);if(!bed)return;
   document.getElementById('farm-detail').hidden=false;for(const e of this.dialog.querySelectorAll('[data-guide-only]'))e.hidden=true;
   const plant=bed.plant,spec=this.data.catalog.find(s=>s.id===plant?.species),title=(bed.nursery?'育苗床 ':'种植床 ')+bed.id.split('-')[1];
   document.getElementById('farm-detail-title').textContent=title+(spec?' · '+spec.name:' · 等待播种');
   document.getElementById('farm-detail-status').textContent=plant?`${spec.stages[plant.stage-1]} · ${plant.stage}/10 · ${FarmGarden.remaining(plant.remaining)} · ${plant.watered?'今日已浇水':'今日未浇水'} · ${plant.fertilized?'今日已施肥':'今日未施肥'}`:'这块土地还没有植物。选择种子后，会显示此株植物的真实生长模型。';
   const meter=document.getElementById('farm-detail-growth');meter.value=plant?.progress||0;meter.hidden=!plant;
   const actions=document.getElementById('farm-detail-actions');actions.replaceChildren();
   if(plant){
    actions.append(this.button('拿洒水壶',()=>this.takeTool('water',bed.id),plant.watered||plant.ready),this.button('拿肥料 · '+(this.data.inventory.fertilizer||0)+' 份',()=>this.takeTool('fertilize',bed.id),plant.fertilized||plant.ready||!this.data.inventory.fertilizer));
    if(plant.ready){actions.append(this.button('直接栽入土壤',()=>this.beginPlacement({bed:bed.id,plant:plant.id,species:plant.species,container:'soil'})));
     if(spec.kind==='flower')actions.append(this.button('装盆自由摆放',()=>this.beginPlacement({bed:bed.id,plant:plant.id,species:plant.species,container:'pot'}),!this.data.inventory.pot));
     actions.append(this.button('收进仓库',()=>this.act('harvest',{bed:bed.id,plant:plant.id})));
    }
    document.getElementById('farm-preview-species').value=plant.species;document.getElementById('farm-preview-stage').value=plant.stage;
    if(this.previewKey!==FarmGarden.modelKey(plant.species,plant.stage,false))void this.preview();
   }else{
    this.closePreview();document.getElementById('farm-preview-name').textContent='空种植床';
    if(!this.data.started)actions.append(this.button('领取园艺入门礼',()=>this.act('start')));
    for(const s of this.data.catalog.filter(s=>(s.kind==='tree')===!!bed.nursery))actions.append(this.button('播种'+s.name+' · '+(this.data.inventory['seed:'+s.id]||0),()=>this.act('plant',{bed:bed.id,species:s.id}),!this.data.inventory['seed:'+s.id]));
   }
   document.getElementById('farm-preview-wrap').hidden=!plant;
  }
  async preview(){if(this.inspectedBed&&!this.data?.beds.find(b=>b.id===this.inspectedBed)?.plant)return;document.getElementById('farm-preview-wrap').hidden=false;const progress=window.PaitLoading?.start('正在加载植物模型');try{await super.preview();progress?.done();}catch(e){progress?.fail('模型加载失败');}}
  renderFreeStock(){
   const stock=document.getElementById('farm-stock'),s=this.data;stock.replaceChildren();
   for(const spec of s.catalog){const qty=s.inventory[spec.id]||0,c=this.card(spec.name+' · '+qty+' 株',spec.kind==='food'?'存入补给，或把成熟植株栽进岛屿土壤。':'自由选择落点，位置与朝向随账号保存。');
    c.append(this.button('栽入土壤',()=>this.beginPlacement({species:spec.id,container:'soil'}),!qty));
    if(spec.kind==='flower')c.append(this.button('装盆摆放 · '+(s.inventory.pot||0)+' 个盆',()=>this.beginPlacement({species:spec.id,container:'pot'}),!qty||!s.inventory.pot));
    if(spec.kind==='food')c.append(this.button('制作零食',()=>this.act('cook'),!qty));stock.append(c);
   }
   for(const d of s.arrangements||[]){const c=this.card(s.catalog.find(s=>s.id===d.species).name+' · '+(d.container==='pot'?'花盆':'土栽'),`岛上位置 ${d.x.toFixed(1)}, ${d.z.toFixed(1)} · 已保存在账号`);c.append(this.button('搬到新位置',()=>this.beginPlacement(d)),this.button('收回仓库',()=>this.act('recover-arrangement',{id:d.id,revision:d.revision})));stock.append(c);}
   for(const d of s.decorations){const c=this.card(s.placements.find(p=>p.id===d.slot).name,'此前安放的植物仍保留，可收回后自由摆放。');c.append(this.button('收回仓库',()=>this.act('recover',{slot:d.slot})));stock.append(c);}
  }
  async initTools(){
   const progress=window.PaitLoading?.start('正在准备园艺工具');
   try{for(const [kind,t] of Object.entries(TOOLS)){
    const g=await this.a.loader.glb('/static/models/petchat-garden-tools-v1/'+t.key+'.glb?v='+this.a.version,this.a.ticket);
    if(this.disposed){SelectedAssets.disposeTree(g.scene);progress?.done();return;}this.toolSources.push(g.scene);
    const model=g.scene.clone(true);model.position.set(t.x,.035,t.z);model.traverse(o=>{if(o.isMesh){o.castShadow=true;o.receiveShadow=true;}});this.root.add(model);this.toolModels.set(kind,model);
   }progress?.done();}catch(e){progress?.fail('工具模型未能加载');if(!this.disposed)this.note('园艺工具加载失败，请刷新小岛重试。',true);}
  }
  takeTool(kind,bed){
   if(this.busy||this.scopeLost||!this.data||this.data.guest)return;this.cancelDirect();if(!this.toolModels.has(kind)){this.note('工具还在准备，请稍后再试。');return;}
   this.mode='care';this.toolKind=kind;this.dialog.close();this.hud.hidden=false;this.hud.dataset.mode='care';this.showRotation(false);this.meter.hidden=false;this.meter.value=0;this.hint.textContent=(kind==='water'?'洒水壶':'肥料罐')+'已拿起 · 对准种植床按住鼠标照料 · Esc 放回';
   const b=this.data.beds.find(b=>b.id===bed);if(b){this.hoverBed=b.id;this.toolTarget.set(b.x-.3,.95,b.z);this.a.focus?.();}else this.toolTarget.copy(this.toolModels.get(kind).position).add(new this.T.Vector3(0,.8,0));
   this.makeParticles();
  }
  makeParticles(){
   if(this.particles)return;const T=this.T;this.particles=new T.InstancedMesh(new T.SphereGeometry(.013,5,4),new T.MeshStandardMaterial({color:0xa9e5ec,transparent:true,opacity:.75,roughness:.3}),64);this.particles.instanceMatrix.setUsage(T.DynamicDrawUsage);this.particles.frustumCulled=false;this.particles.visible=false;this.root.add(this.particles);this.particleMatrix=new T.Object3D();
  }
  showRotation(on){for(const id of ['farm-rotate-left','farm-rotate-right'])document.getElementById(id).hidden=!on;}
  async beginPlacement(spec){
   if(this.busy||this.scopeLost||this.data?.guest)return;this.cancelDirect();this.mode='place';this.placement={...spec,yaw:spec.yaw||0,x:spec.x??0,z:spec.z??0};this.placementKey=FarmGarden.modelKey(spec.species,10,false);this.dialog.close();this.hud.hidden=false;this.hud.dataset.mode='place';this.showRotation(true);this.meter.hidden=true;this.hint.textContent='正在准备落点预览…';
   const epoch=++this.toolEpoch,progress=window.PaitLoading?.start('正在准备摆放预览');
   try{
    const model=await this.asset(this.placementKey),pot=spec.container==='pot'?await this.asset('flowerpot'):null;if(this.disposed||epoch!==this.toolEpoch){progress?.done();return;}
    const T=this.T;this.ghost=new T.Group();const plant=model.clone(true);plant.position.y=spec.container==='pot'?.29:0;this.ghost.add(plant);if(pot)this.ghost.add(pot.clone(true));
    this.ghostMaterials=[];this.ghost.traverse(o=>{if(o.isMesh){const clone=m=>{const c=m.clone();c.transparent=true;c.opacity=.48;c.depthWrite=false;this.ghostMaterials.push(c);return c;};o.material=Array.isArray(o.material)?o.material.map(clone):clone(o.material);o.castShadow=false;}});
    this.ring=new T.Mesh(new T.RingGeometry(P.radius(spec.species,spec.container),P.radius(spec.species,spec.container)+.04,64),new T.MeshBasicMaterial({color:0x6bd7ac,transparent:true,opacity:.9,side:T.DoubleSide,depthWrite:false}));this.ring.rotation.x=-Math.PI/2;this.ring.position.y=.012;this.ghost.add(this.ring);this.root.add(this.ghost);this.ghost.visible=false;this.targetPoint=null;
    if(spec.id)this.updatePlacement(spec);progress?.done();this.hint.textContent='移动鼠标预览 · 单击摆放 · Q/E 旋转 · Alt+拖动转视角 · Esc 取消';
   }catch(e){progress?.fail('预览加载失败');if(!this.disposed){this.cancelDirect();this.note('预览未能加载，库存未消耗。',true);}}
  }
  rotate(angle){if(!this.placement||this.busy||this.retryPlacement)return;this.placement.yaw+=angle;if(this.targetPoint)this.updatePlacement(this.targetPoint);}
  updatePlacement(point){
   if(!this.ghost||!this.placement||this.retryPlacement)return;Object.assign(this.placement,{x:point.x,z:point.z});this.targetPoint={x:point.x,z:point.z};
   let problem=P.validate(this.data.placementMap,this.placement,this.data.arrangements||[],this.placement.id);
   const pet=this.a.pet?.();if(!problem&&pet&&Math.hypot(pet.x-point.x,pet.z-point.z)<P.radius(this.placement.species,this.placement.container)+.8)problem='宠物在这里，请换个落点';
   this.placementProblem=problem;this.ghost.visible=true;this.ring.material.color.set(problem?0xe38b78:0x75d6b0);this.hint.textContent=problem||'可以摆放 · 单击确认 · Q/E 旋转 · Alt+拖动转视角 · Esc 取消';
  }
  async confirmPlacement(){
   if(this.busy||!this.targetPoint||!this.ghost)return;this.updatePlacement(this.targetPoint);if(this.placementProblem)return;
   const spec=this.retryPlacement||{...this.placement,token:crypto.randomUUID()},old=new Set((this.data.arrangements||[]).map(a=>a.id));this.pendingLanding=spec;this.retryPlacement=spec;
   this.ghost.position.set(spec.x,.035,spec.z);this.ghost.rotation.y=spec.yaw;
   let ok=await this.act('arrange',spec);if(this.disposed)return;
   if(!ok){await this.refresh();ok=this.data.recentRequests?.includes(spec.token);}
   if(ok){const added=this.data.arrangements.find(a=>spec.id?a.id===spec.id:!old.has(a.id));this.cancelDirect();if(added){const g=this.groups.get(added.id);if(g)this.land(g,added,true);}this.note('已保存到你的账号，下次回来仍会保留。');}
   else{this.pendingLanding=null;if(this.lastFailure?.status){this.retryPlacement=null;this.hint.textContent=this.lastFailure.message;}else this.hint.textContent='保存未确认；单击原落点重试（不会重复扣库存），或取消后刷新查看。';}
  }
  land(g,record,lift=false){
   const y=record.container==='pot'?.325:.035;this.animations.set(record.id,{g,from:g.position.clone().add(new this.T.Vector3(0,lift?.38:0)),to:new this.T.Vector3(record.x,y,record.z),yaw:record.yaw||0,start:performance.now()});
  }
  positionRecord(g,r,newly){
   if(!r.container)return;const changed=g.userData.record&&(g.userData.record.x!==r.x||g.userData.record.z!==r.z||g.userData.record.yaw!==r.yaw);
   if(changed||newly&&this.pendingLanding)this.land(g,r,true);else if(!this.animations?.has(r.id)){g.position.set(r.x,r.y,r.z);g.rotation.y=r.yaw||0;}g.userData.record=r;
  }
  async sync(){await super.sync();if(this.disposed||!this.data)return;this.syncNavigation();}
  syncNavigation(){
   const nav=this.a.navigation?.();if(!nav)return;const items=this.data.arrangements||[],signature=JSON.stringify(items.map(p=>[p.id,p.revision]));if(this.navRef===nav&&signature===this.navSignature)return;this.navRef=nav;this.navSignature=signature;
   nav.obstacles=nav.obstacles.filter(o=>!o.farmOwned).concat(items.map(p=>({x:p.x,z:p.z,r:P.radius(p.species,p.container),farmOwned:true})));
   for(const n of nav.nodes)n.valid=nav.isWalkable(n);nav.edgeClear.clear();this.a.onNavigationChanged?.();
  }
  rayPoint(e,height=.035){const r=this.a.canvas.getBoundingClientRect(),ray=new this.T.Raycaster();ray.setFromCamera(new this.T.Vector2((e.clientX-r.left)/r.width*2-1,-(e.clientY-r.top)/r.height*2+1),this.a.camera);return {ray,point:ray.ray.intersectPlane(new this.T.Plane(new this.T.Vector3(0,1,0),-height),new this.T.Vector3())};}
  point(e,click){
   if(this.disposed||!this.a.active()||this.dialog.open){this.hover.hidden=true;return;}if(e.altKey||click&&performance.now()<(this.ignoreClick||0))return;
   const {ray,point}=this.rayPoint(e,this.mode==='care'?.23:.035);if(!point)return;
   if(this.mode==='place'){this.hover.hidden=true;if(!this.busy)this.updatePlacement(point);if(click){e.stopImmediatePropagation();void this.confirmPlacement();}return;}
   if(this.mode==='care'){this.hover.hidden=true;const bed=this.layout.beds.find(b=>Math.abs(point.x-b.x)<b.w/2+.15&&Math.abs(point.z-b.z)<b.d/2+.15);this.hoverBed=bed?.id;this.toolTarget.set(point.x-.4,.95,point.z);if(click)e.stopImmediatePropagation();return;}
   const tool=[...this.toolModels].find(([,m])=>ray.intersectObject(m,true).length||ray.ray.distanceSqToPoint(m.position.clone().add(new this.T.Vector3(0,.25,0)))<.14);if(tool){this.hover.hidden=false;this.hover.textContent=tool[0]==='water'?'洒水壶 · 点击拿起':'肥料罐 · 点击拿起';this.hover.style.left=e.clientX+12+'px';this.hover.style.top=e.clientY-44+'px';if(click){e.stopImmediatePropagation();this.takeTool(tool[0]);}return;}
   const placed=(this.data?.arrangements||[]).find(p=>{const g=this.groups.get(p.id);return g&&ray.intersectObject(g,true).length;});
   if(placed){this.hover.hidden=false;this.hover.textContent=this.data.catalog.find(s=>s.id===placed.species).name+' · 点击查看或搬动';this.hover.style.left=Math.min(innerWidth-270,e.clientX+12)+'px';this.hover.style.top=Math.max(8,e.clientY-44)+'px';if(click){e.stopImmediatePropagation();this.inspectPlaced(placed);}return;}
   super.point(e,click);
  }
  update(dt){
   super.update(dt);if(this.disposed)return;
   if(this.mode&&!this.a.active()||document.hidden){this.cancelDirect();return;}
   if(this.data)this.syncNavigation();const now=performance.now(),reduced=matchMedia('(prefers-reduced-motion: reduce)').matches;
   for(const [id,a] of this.animations){const t=reduced?1:Math.min(1,(now-a.start)/550),ease=1-(1-t)**3;a.g.position.lerpVectors(a.from,a.to,ease);a.g.rotation.y=a.yaw;if(t===1)this.animations.delete(id);}
   if(this.ghost&&this.targetPoint){const target=new this.T.Vector3(this.targetPoint.x,.035,this.targetPoint.z);this.ghost.position.lerp(target,reduced?1:1-Math.exp(-dt*22));this.ghost.rotation.y=this.placement.yaw;}
   if(this.mode!=='care')return;
   const model=this.toolModels.get(this.toolKind);model.position.lerp(this.toolTarget,1-Math.exp(-dt*18));
   const bed=this.data?.beds.find(b=>b.id===this.hoverBed),p=bed?.plant;
   const eligible=p&&!p.ready&&(this.toolKind==='water'?!p.watered:!p.fertilized&&this.data.inventory.fertilizer>0);
   const active=this.pressed&&eligible&&!this.busy;
   model.rotation.z+=( (active?-.65:0)-model.rotation.z)*(1-Math.exp(-dt*12));
   if(this.careBed!==bed?.id){this.careTime=0;this.careBed=bed?.id;}
   if(active){this.careTime+=Math.min(dt,.05);this.hint.textContent=(this.toolKind==='water'?'正在浇水':'正在施肥')+' · 松开可停止';if(this.careTime>=1){this.pressed=false;this.careTime=0;void this.act(this.toolKind,{bed:bed.id,plant:p.id});}}
   else if(this.pressed){this.careTime=0;this.hint.textContent=!p?'请对准有植物的种植床':p.ready?'植物已成熟':this.toolKind==='fertilize'&&!this.data.inventory.fertilizer?'肥料用完了，可在园艺商店补充':'今天已照料过了';}
   this.meter.value=this.careTime;this.particles.visible=!!active;
   if(active){this.particles.material.color.set(this.toolKind==='water'?0xa9e5ec:0xc7a66e);model.updateMatrixWorld(true);const start=model.localToWorld(new this.T.Vector3(.56,.48,0));for(let i=0;i<64;i++){const t=(now*.0018+i/64)%1,spread=.12*Math.sin(i*18.3);this.particleMatrix.position.set(start.x+(bed.x-start.x)*t+spread*t,start.y+(.23-start.y)*t*t,start.z+(bed.z-start.z)*t+Math.cos(i*13)*.12*t);this.particleMatrix.scale.setScalar(this.toolKind==='water'?.7:1);this.particleMatrix.updateMatrix();this.particles.setMatrixAt(i,this.particleMatrix.matrix);}this.particles.instanceMatrix.needsUpdate=true;}
  }
  cancelDirect(){
   ++this.toolEpoch;this.mode=null;this.pressed=false;this.careTime=0;this.pendingLanding=null;this.retryPlacement=null;this.placement=null;this.placementKey=null;this.targetPoint=null;if(this.hud)this.hud.hidden=true;if(this.particles)this.particles.visible=false;
   if(this.ghost){this.root.remove(this.ghost);this.ghostMaterials.forEach(m=>m.dispose());this.ring.geometry.dispose();this.ring.material.dispose();this.ghost=null;}
   for(const [kind,m] of this.toolModels||[]){const t=TOOLS[kind];m.position.set(t.x,.035,t.z);m.rotation.set(0,0,0);}
  }
  dispose(){
   this.cancelDirect();this.a.canvas.removeEventListener('pointerdown',this.captureDown,true);this.a.canvas.removeEventListener('pointerleave',this.leaveHandler);window.removeEventListener('pointerup',this.captureUp,true);window.removeEventListener('pointercancel',this.cancelPointer);window.removeEventListener('blur',this.cancelPointer);window.removeEventListener('keydown',this.keyHandler);
   if(this.particles){this.particles.geometry.dispose();this.particles.material.dispose();}for(const s of this.toolSources)SelectedAssets.disposeTree(s);this.animations.clear();super.dispose();
  }
 };
})();
