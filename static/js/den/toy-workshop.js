/* Physical props share the existing navigator and fetch animation controller. */
(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.ToyWorkshop=api;})(typeof window!=='undefined'?window:globalThis,function(){
 'use strict';
 const catalog=[{id:'ball',name:'彩纹球',icon:'●',hint:'抛出，让它叼回来',fetch:true},{id:'disc',name:'爪印飞盘',icon:'◉',hint:'低弧线旋转飞行',fetch:true},{id:'rope',name:'编织绳结',icon:'∞',hint:'拖着逗它，也能抛接',fetch:true},{id:'bone',name:'毛绒骨头',icon:'🦴',hint:'柔软的寻回玩具',fetch:true},{id:'duck',name:'小黄鸭',icon:'🐤',hint:'捏一捏，发出啾啾声',fetch:true},{id:'brush',name:'木梳刷',icon:'▥',hint:'沿宠物背部慢慢梳',fetch:false},{id:'rattle',name:'小摇铃',icon:'♫',hint:'左右摇动，引它跑来（可过桥）',fetch:false}];
 const positions={sakura:{x:.65,z:-1.93,w:1.12,d:.52},snow:{x:-.95,z:-1.2,w:1.12,d:.52},camp:{x:-2.65,z:-.45,w:1.12,d:.52}};
 function navigation(theme,base){const ball=theme==='snow'?{x:1.35,z:1.8}:{x:-1.75,z:.6};return {...base,obstacles:[...base.obstacles.filter(o=>Math.hypot(o.x-ball.x,o.z-ball.z)>.02),{kind:'rect',...positions[theme]}]};}
 class Controller {
  constructor(api){
   this.a=api;this.records=[];this.root=null;this.held=null;this.pointerId=null;this.target=null;this.mode='throw';this.lastUse=0;
   this.dialog=document.getElementById('toy-dialog');this.hud=document.getElementById('toy-held');this.tip=document.getElementById('toy-target');
   this.grid=document.getElementById('toy-grid');
   this.grip=new ToyGrip.Controller({THREE:api.THREE,element:document.getElementById('toy-grip'),camera:api.camera,canvas:api.canvas});
   for(const item of catalog){const b=document.createElement('button');b.type='button';b.dataset.toy=item.id;b.innerHTML='<span aria-hidden="true">'+item.icon+'</span><strong>'+item.name+'</strong><small>'+item.hint+'</small>';b.onclick=()=>this.takeKind(item.id);this.grid.append(b);}
   document.getElementById('btn-toys').onclick=()=>this.open();
   this.quick=document.getElementById('toy-quick-open');this.quick.onclick=()=>this.open();
   this.menuCursor=document.getElementById('toy-menu-cursor');
   this.dialog.addEventListener('close',()=>this.menuHover(null));
   this.fullscreenButton=document.getElementById('scene-fullscreen');
   this.fullscreenButton.onclick=()=>this.toggleFullscreen();
   document.addEventListener('fullscreenchange',()=>{if(this.ownsFullscreen&&!document.fullscreenElement){this.ownsFullscreen=false;this.manualFullscreen=false;if(this.immersive)this.cancel();this.applyFullscreen(false);}});
   document.getElementById('toy-recall').onclick=()=>this.recall();
   document.getElementById('toy-cancel').onclick=()=>this.cancel();
   document.getElementById('toy-use').onclick=()=>this.use();
   for(const b of this.hud.querySelectorAll('[data-toy-mode]'))b.onclick=()=>{this.mode=b.dataset.toyMode;this.render();};
   document.addEventListener('keydown',e=>{if(e.key==='Escape'){if(this.held){this.manualFullscreen=false;this.cancel();e.preventDefault();}else if(this.manualFullscreen){this.manualFullscreen=false;this.applyFullscreen(false);e.preventDefault();}}});
   this.ray=new api.THREE.Raycaster();this.makePreview();
  }
  makePreview(){const T=this.a.THREE;this.preview=new T.Group();this.preview.visible=false;this.preview.renderOrder=90;
   this.line=new T.Line(new T.BufferGeometry().setAttribute('position',new T.BufferAttribute(new Float32Array(33*3),3)),new T.LineBasicMaterial({color:0x65b88a,depthTest:false,transparent:true,opacity:.85}));
   this.ring=new T.Mesh(new T.RingGeometry(.15,.19,36),new T.MeshBasicMaterial({color:0x65b88a,side:T.DoubleSide,depthTest:false,transparent:true,opacity:.85}));this.ring.rotation.x=-Math.PI/2;
   this.preview.add(this.line,this.ring);this.a.scene.add(this.preview);
  }
  attach(root,stage,theme){this.clear();this.root=root;const p=positions[theme];root.position.set(p.x,.035,p.z);this.a.scene.add(root);root.updateMatrixWorld(true);stage.updateMatrixWorld(true);
   for(const tree of [stage,root])tree.traverse(node=>{if(!node.userData.toy_id)return;const spec=catalog.find(i=>i.id===node.userData.toy_id);if(!spec)return;const pos=node.getWorldPosition(new this.a.THREE.Vector3()),box=new this.a.THREE.Box3().setFromObject(node);this.records.push({node,spec,parent:node.parent,position:node.position.clone(),quaternion:node.quaternion.clone(),scale:node.scale.clone(),offset:Math.max(.025,pos.y-box.min.y),state:'available',stored:true});});
   root.traverse(o=>{if(o.isMesh){o.castShadow=true;o.receiveShadow=true;}});this.render();this.note('七种玩具已就位，也可以直接拿起岛上的球。');
  }
  restore(r){r.parent.add(r.node);r.node.position.copy(r.position);r.node.quaternion.copy(r.quaternion);r.node.scale.copy(r.scale);r.state='available';r.stored=true;}
  clear(){this.cancel();for(const r of this.records)this.restore(r);if(this.root){this.a.scene.remove(this.root);this.a.dispose(this.root);}this.root=null;this.records=[];this.dialog.close();this.render();}
  cancel(){if(this.pointerId!=null&&this.a.canvas.hasPointerCapture(this.pointerId))this.a.canvas.releasePointerCapture(this.pointerId);this.a.canvas.style.cursor='';this.a.face()?.reset();if(this.held)this.finish(this.held,false);this.pointerId=null;this.preview.visible=false;this.target=null;this.render();}
  recall(){this.cancel();for(const r of this.records)this.restore(r);this.note('玩具已归位，岛上的球也回到原处。');}
  open(){this.cancel();this.render();this.dialog.showModal();}
  note(text){if(this.tip.textContent===text)return;this.tip.textContent=text;if(this.hud.hidden)this.a.face()?.note(text);document.getElementById('toy-status').textContent=text;}
  animateViewport(){
   const canvas=this.a?.canvas;
   if(!canvas?.animate||typeof matchMedia==='function'&&matchMedia('(prefers-reduced-motion: reduce)').matches)return;
   this.viewportAnimation?.cancel();
   // Composite only: resize projection once, never allocate a new WebGL buffer on each animation frame.
   this.viewportAnimation=canvas.animate([{opacity:.78,transform:'scale(1.018)'},{opacity:1,transform:'scale(1)'}],{duration:360,easing:'cubic-bezier(.2,.75,.25,1)'});
  }
  toggleFullscreen(){this.manualFullscreen=!this.manualFullscreen;this.applyFullscreen(this.manualFullscreen||this.immersive);}
  immersiveMode(active){
   if(this.immersive===active)return;this.immersive=active;
   document.body?.classList.toggle('toy-immersive',active);
   this.applyFullscreen(active||!!this.manualFullscreen);
  }
  applyFullscreen(active){
   if(this.fullWanted===active)return;this.fullWanted=active;
   document.body?.classList.toggle('scene-fullscreen',active);
   if(this.fullscreenButton){this.fullscreenButton.textContent=active?'⤡ 退出全屏':'⤢ 全屏';this.fullscreenButton.setAttribute('aria-pressed',String(active));}
   if(active){
    const wrap=document.getElementById('den-wrap');
    if(!document.fullscreenElement&&document.fullscreenEnabled&&typeof navigator!=='undefined'&&navigator.userActivation?.isActive&&wrap?.requestFullscreen){
     try{Promise.resolve(wrap.requestFullscreen()).then(()=>{
      if(document.fullscreenElement!==wrap)return;
      if(this.fullWanted){this.ownsFullscreen=true;this.animateViewport();}
      else document.exitFullscreen?.().catch(()=>{});
     }).catch(()=>this.animateViewport());}catch(e){this.animateViewport();}
    }else this.animateViewport();
   }else{
    if(this.ownsFullscreen){this.ownsFullscreen=false;if(document.fullscreenElement){Promise.resolve(document.exitFullscreen?.()).catch(()=>{}).then(()=>this.animateViewport());return;}}
    this.animateViewport();
   }
  }
  render(){if(this.held?.state!=='held')this.grip?.clear();this.immersiveMode(this.held?.state==='held');if(!this.hud)return;this.hud.hidden=!this.held;document.getElementById('toy-held-name').textContent=this.held?this.held.spec.name:'';for(const b of this.hud.querySelectorAll('[data-toy-mode]')){b.setAttribute('aria-pressed',String(b.dataset.toyMode===this.mode));b.disabled=b.dataset.toyMode==='throw'&&!this.held?.spec.fetch;}for(const b of this.grid.querySelectorAll('[data-toy]'))b.disabled=!this.records.some(r=>r.spec.id===b.dataset.toy&&r.state==='available');}
  pick(x,y){this.root?.updateMatrixWorld(true);this.ray.setFromCamera(new this.a.THREE.Vector2(x/this.a.canvas.clientWidth*2-1,1-y/this.a.canvas.clientHeight*2),this.a.camera);
   const objects=this.records.filter(r=>r.state==='available').map(r=>r.node);const hits=this.ray.intersectObjects(objects,true),cabinetHit=this.root?this.ray.intersectObject(this.root,true)[0]:null;if(cabinetHit&&(!hits.length||cabinetHit.distance<hits[0].distance-.002))return 'cabinet';if(hits.length){let n=hits[0].object;while(n){const r=this.records.find(r=>r.node===n);if(r)return r;n=n.parent;}}
   if(cabinetHit)return 'cabinet';return null;}
  menuHover(button){
   this.menuSelection=button;
   for(const b of this.grid?.querySelectorAll('[data-toy]')||[])b.classList.toggle('hand-hover',b===button);
   if(this.menuCursor)this.menuCursor.hidden=!button;
  }
  menuPick(p){
   const c=this.a.canvas.getBoundingClientRect(),x=p.x+c.left,y=p.y+c.top;
   let best=null,score=Infinity;
   for(const b of this.grid.querySelectorAll('[data-toy]')){
    if(b.disabled)continue;const r=b.getBoundingClientRect();
    const gap=Math.hypot(Math.max(r.left-x,0,x-r.right),Math.max(r.top-y,0,y-r.bottom));
    if(gap>24)continue;
    const d=Math.hypot(x-(r.left+r.right)/2,y-(r.top+r.bottom)/2);
    if(d<score){score=d;best=b;}
   }
   this.menuHover(best);
   if(this.menuCursor){this.menuCursor.style.left=x+'px';this.menuCursor.style.top=y+'px';}
   return best;
  }
  quickHit(x,y){if(!this.quick||this.quick.hidden)return false;const c=this.a.canvas.getBoundingClientRect(),r=this.quick.getBoundingClientRect();return x+c.left>=r.left-18&&x+c.left<=r.right+18&&y+c.top>=r.top-18&&y+c.top<=r.bottom+18;}
  handPick(x,y){
   if(this.quickHit(x,y))return 'cabinet';
   const direct=this.pick(x,y);if(direct)return direct;
   // Modest screen-space tolerance for camera jitter; mouse picking remains exact.
   for(const [dx,dy] of [[-12,0],[12,0],[0,-12],[0,12],[-8,-8],[8,-8],[-8,8],[8,8]]){
    const hit=this.pick(x+dx,y+dy);if(hit&&hit!=='cabinet')return hit;
   }
   return null;
  }
  handHint(h){
   if(!h.present)return '把手放回镜头，张开手指后再捏合';
   if(h.trackingLost)return '暂时看不到手 · 保持拿取，正在找回';
   if(h.quality===false)return '手靠近镜头一些，让整只手入镜';
   if(this.dialog?.open)return this.menuSelection?this.menuSelection.textContent+' · 捏合拿起':'把手移到大卡片附近，再捏合';
   if(this.held)return h.releasing?'正在确认松手…':this.held.spec.name+(this.held.spec.fetch&&this.mode==='throw'?' · 已拿稳，张开手指抛出':' · 已拿稳，张开手指放下');
   const now=performance.now();
   if(now-(this.hoverAt||0)>100){this.hoverAt=now;this.hoverHit=this.handPick(h.pinchX??h.sx,h.pinchY??h.sy);}
   return this.hoverHit==='cabinet'?'玩具柜 · 捏合打开':this.hoverHit?this.hoverHit.spec.name+' · 拇指食指捏合拿起':'准星对准玩具 · 捏合拿起';
  }
  takeKind(kind){const r=this.records.find(r=>r.spec.id===kind&&r.state==='available');if(!r){this.note('这个玩具还没准备好。');return;}this.dialog.close();if(this.take(r)){this.pointerId=null;this.move(this.a.face().project(this.a.model().position));this.note('已拿起'+r.spec.name+'。在空地按住移动，绿色落点松手生效；Esc 归还。');}}
  take(r){if(this.a.busy())return false;this.cancel();this.point=null;this.lastPoint=null;this.shakeDistance=0;this.shakeAt=0;this.a.cancelCommands();const f=this.a.face();r.before={stored:r.stored,position:r.node.getWorldPosition(new this.a.THREE.Vector3()),quaternion:r.node.getWorldQuaternion(new this.a.THREE.Quaternion())};this.a.scene.attach(r.node);r.state='held';this.held=r;this.mode=r.spec.fetch?'throw':'place';
   f.pointerMode=!f.cameraOn;f.mode=r.spec.id==='brush'?'brush':'touch';f.render();
   if(r.spec.fetch)f.holdBall({mesh:r.node,offset:r.offset,kind:r.spec.id,label:r.spec.name,release:complete=>this.finish(r,complete)});
   this.a.locomotion()?.interrupt();this.render();return true;}
  finish(r,complete){this.stopRattle();if(complete){r.state='available';r.stored=false;r.node.quaternion.copy(r.before?.quaternion||r.quaternion);}else if(r.before?.stored)this.restore(r);else if(r.before){this.a.scene.add(r.node);r.node.position.copy(r.before.position);r.node.quaternion.copy(r.before.quaternion);r.state='available';r.stored=false;}else this.restore(r);
   if(this.held===r)this.held=null;this.preview.visible=false;this.target=null;this.pointerId=null;this.a.canvas.style.cursor='';this.render();}
  coords(e){const rect=this.a.canvas.getBoundingClientRect();return {x:e.clientX-rect.left,y:e.clientY-rect.top};}
  consume(e){e.preventDefault();e.stopImmediatePropagation();}
  startDefault(e){const r=this.records.find(r=>r.spec.id==='ball'&&r.state==='available');if(r&&this.take(r)){this.pointerId=e.pointerId;this.a.canvas.setPointerCapture(e.pointerId);this.move(this.coords(e));}}
  pointerDown(e){if(this.held?.state==='playing')return false;if(!e.isPrimary||e.button!==0)return false;const p=this.coords(e),hit=this.held?this.held:this.pick(p.x,p.y);if(!hit)return false;this.consume(e);if(hit==='cabinet'){this.open();return true;}if(!this.held&&!this.take(hit))return true;this.pointerId=e.pointerId;this.a.canvas.setPointerCapture(e.pointerId);this.move(p);return true;}
  pointerMove(e){const p=this.coords(e);if(this.held&&this.held.state==='held'&&(this.pointerId===e.pointerId||this.pointerId==null)){this.consume(e);this.move(p);return true;}if(!this.held){const hit=this.pick(p.x,p.y);this.a.canvas.style.cursor=hit?'grab':'';}return false;}
  pointerUp(e){if(this.pointerId!==e.pointerId)return false;this.consume(e);this.move(this.coords(e));this.release();if(this.a.canvas.hasPointerCapture(e.pointerId))this.a.canvas.releasePointerCapture(e.pointerId);this.pointerId=null;return true;}
  move(p){this.point=p;this.a.face().input={...p,t:performance.now(),pinching:false};}
  grab(on,pos,reason){
   if(this.dialog?.open){
    if(on&&pos){const p={x:pos.pinchX??pos.sx,y:pos.pinchY??pos.sy},b=this.menuPick(p);if(b){this.takeKind(b.dataset.toy);if(this.held)this.move(p);}}
    return true;
   }
   if(on&&pos&&this.held?.state==='held'){this.move({x:pos.pinchX??pos.sx,y:pos.pinchY??pos.sy});return true;}
   if(!on&&this.held?.state==='held'){if(reason==='lost'||reason==='stop'||!pos)this.cancel();else{this.move({x:pos.pinchX??pos.sx,y:pos.pinchY??pos.sy});this.release();}return true;}if(!on||!pos)return false;const p={x:pos.pinchX??pos.sx,y:pos.pinchY??pos.sy},hit=this.handPick(p.x,p.y);if(!hit)return false;if(hit==='cabinet'){this.open();return true;}if(this.take(hit))this.move(p);return true;}
  hand(h){if(this.dialog?.open){if(!h.present||h.trackingLost||h.releasing)this.menuHover(null);else this.menuPick({x:h.pinchX??h.sx,y:h.pinchY??h.sy});return;}if(h.trackingLost||h.releasing)return;if(this.held?.state==='held'){if(!h.present){this.cancel();return;}if(h.pinching)this.move({x:h.pinchX??h.sx,y:h.pinchY??h.sy});}}
  evaluateTarget(){if(!this.point||!this.held)return null;const f=this.a.face(),p=f.ground(this.point.x,this.point.y),loc=this.a.locomotion();if(!p||!loc)return null;
   const now=performance.now(),key=Math.round(p.x*15)+':'+Math.round(p.z*15);if(this.target?.key===key&&now-this.target.at<250)return this.target;
   const valid=loc.navigation.isWalkable(p)&&!!loc.navigation.route(this.a.model().position,p);p.y=loc.navigation.surfaceHeight(p)+this.held.offset;this.target={point:p,valid,key,at:now};return this.target;}
  release(){const r=this.held;if(!r||r.state!=='held')return;const target=this.evaluateTarget();if(!target?.valid){this.cancel();this.note('这里不能落下，已放回拿起前的位置。请选择绿色落点。');return;}
   if(r.spec.fetch){const f=this.a.face();f.ball.fetch=this.mode==='throw';f.ball.lift=this.mode==='throw'?(r.spec.id==='disc'?.32:.65):0;f.throwBall(target.point);if(!f.ball)return;r.state='playing';this.preview.visible=false;this.render();this.hud.hidden=true;}
   else{r.node.position.copy(target.point);this.finish(r,true);this.note('放好了，可以再次拿起。');}}
  quickToss(target){const r=this.records.find(r=>r.spec.id==='ball'&&r.state==='available');if(!r||!this.take(r))return;this.a.face().throwBall(target);if(!this.a.face().ball)return;r.state='playing';this.render();this.hud.hidden=true;}
  stopRattle(){const loc=this.a.locomotion();if(this.rattlePath&&loc?.path===this.rattlePath){loc.interrupt();this.a.act('idle',0);}this.rattlePath=null;this.rattleTarget=null;}
  followRattle(){const target=this.evaluateTarget(),loc=this.a.locomotion();
   if(!target?.valid||!loc){this.stopRattle();this.note('请把摇铃移到可到达的空地，宠物会沿安全路线跑来。');return false;}
   const p=target.point;
   if(this.rattlePath===loc.path&&this.rattleTarget&&Math.hypot(p.x-this.rattleTarget.x,p.z-this.rattleTarget.z)<.18)return true;
   if(Math.hypot(p.x-this.a.model().position.x,p.z-this.a.model().position.z)<.22)return true;
   this.a.act('idle',0);
   if(!loc.goTo(p,{gait:'run'}))return false;
   this.rattlePath=loc.path;this.rattleTarget={x:p.x,z:p.z};return true;
  }
  use(){if(!this.held||this.a.busy()||performance.now()-this.lastUse<1100)return;this.lastUse=performance.now();const k=this.held.spec.id;
   if(k==='rattle'){if(this.followRattle())this.a.say('听到铃声啦！它会沿路跑来，遇到河流就走桥。');}
   else{this.a.act(k==='rope'?'playBow':k==='brush'?'affection':'curious',1500);this.a.say(k==='duck'?'啾啾！它好奇地看着小鸭。':k==='rope'?'它压低前爪，想和你一起玩绳结。':k==='brush'?'慢慢梳背毛，它会很舒服。':'它认真看着你手里的玩具。');}
   if(k==='duck'||k==='rattle')try{const C=window.AudioContext||window.webkitAudioContext;this.audio ||=new C();this.audio.resume();const o=this.audio.createOscillator(),g=this.audio.createGain();o.frequency.setValueAtTime(k==='duck'?850:1500,this.audio.currentTime);o.frequency.exponentialRampToValueAtTime(k==='duck'?450:900,this.audio.currentTime+.16);g.gain.setValueAtTime(.045,this.audio.currentTime);g.gain.exponentialRampToValueAtTime(.001,this.audio.currentTime+.2);o.connect(g);g.connect(this.audio.destination);o.start();o.stop(this.audio.currentTime+.21);o.onended=()=>{o.disconnect();g.disconnect();};}catch(e){}
  }
  update(dt,now){const r=this.held;if(!r||r.state!=='held')return;if(this.a.busy()){this.cancel();return;}if(!this.point)return;
   const f=this.a.face();f.input={...this.point,t:now,pinching:false};
   if(!r.spec.fetch){const p=f.ground(this.point.x,this.point.y,1.1);if(p)r.node.position.lerp(p,1-Math.exp(-Math.max(0,Math.min(.05,dt))*18));if(r.spec.id==='rattle'&&this.lastPoint){
    if(now-(this.shakeAt||0)>350){this.shakeDistance=0;this.shakeAt=now;}
    this.shakeDistance=(this.shakeDistance||0)+Math.hypot(this.point.x-this.lastPoint.x,this.point.y-this.lastPoint.y);
    if(this.shakeDistance>28){this.use();this.shakeDistance=0;this.shakeAt=now;}
   }}
   this.lastPoint={...this.point};const target=this.evaluateTarget();if(!target){this.preview.visible=false;return;}
   this.preview.visible=true;const color=target.valid?0x4cbd8a:0xe16b62;this.line.material.color.setHex(color);this.ring.material.color.setHex(color);this.ring.position.copy(target.point);this.ring.position.y-=r.offset-.035;
   const attr=this.line.geometry.attributes.position,lift=this.mode==='throw'?(r.spec.id==='disc'?.32:.65):0;
   for(let i=0;i<33;i++){const p=this.a.flightPoint(r.node.position,target.point,i/32,lift);attr.setXYZ(i,p.x,p.y,p.z);}attr.needsUpdate=true;this.line.geometry.computeBoundingSphere();
   this.note(target.valid?(this.mode==='throw'?'绿色落点 · 松手抛出，宠物会叼回':r.spec.id==='rattle'?'左右晃动 · 宠物沿绿色落点跑来，可过桥；松手放下':'绿色落点 · 松手放下'):'红色落点 · 河面、障碍或岛外，松手会归还');
  }
 }
 return {catalog,positions,navigation,Controller};
});
