/* Face-to-face interaction: shared camera/pointer behavior and bounded pose overlays. */
(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.FacePlay=api;})(typeof window!=='undefined'?window:globalThis,function(){
  'use strict';
  const defaults={face:true,hands:true,gestures:true,remote:false,lift:false,mirror:true,sensitivity:1.3,centerX:.5,centerY:.5};
  const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
  function settings(value={}){
    const out={...defaults};
    for(const key of ['face','hands','gestures','remote','lift','mirror'])if(typeof value[key]==='boolean')out[key]=value[key];
    for(const key of ['centerX','centerY'])out[key]=clamp(Number(value[key])||.5,.05,.95);
    out.sensitivity=clamp(Number(value.sensitivity)||1.3,.6,2.5);return out;
  }
  function flightPoint(from,to,t,lift=.65){return {x:from.x+(to.x-from.x)*t,y:from.y+(to.y-from.y)*t+Math.sin(Math.PI*t)*lift,z:from.z+(to.z-from.z)*t};}
  function zoneAt(point,zones){
    let best=null,score=1;
    for(const zone of zones){const d=Math.hypot((point.x-zone.x)/zone.rx,(point.y-zone.y)/zone.ry);if(d<score){score=d;best=zone;}}
    return best;
  }
  class Touch {
    constructor(){this.reset();}
    reset(){this.last=null;this.zone=null;this.moving=0;this.stroke=0;this.lastMove=0;this.lastReward=0;this.stopped=false;}
    sample(point,zone,now){
      if(!zone){this.last=null;this.zone=null;this.moving=0;return null;}
      if(zone!==this.zone){this.zone=zone;this.last={...point,t:now};this.moving=0;this.stroke=0;this.lastMove=now;this.stopped=false;return {enter:true,speed:0};}
      const dt=Math.min(150,Math.max(1,now-this.last.t)),dx=point.x-this.last.x,dy=point.y-this.last.y;
      const speed=Math.hypot(dx,dy)/dt*1000;
      if(speed>12&&speed<1200){this.moving+=dt;this.stroke+=dt;this.lastMove=now;this.stopped=false;}
      const nuzzle=!this.stopped&&this.stroke>400&&now-this.lastMove>650;
      if(nuzzle)this.stopped=true;
      const reward=this.moving>=2500&&now-this.lastReward>=5000;
      if(reward){this.lastReward=now;this.moving=0;}
      this.last={...point,t:now};return {speed,dx,dy,nuzzle,reward};
    }
  }
  class Controller {
    constructor(api){
      this.a=api;this.touch=new Touch();this.mode='touch';this.pointerMode=false;this.cameraOn=false;this.input=null;
      this.face=null;this.model=null;this.bones=[];this.look={x:0,y:0,r:0};this.tool=null;this.guiding=false;
      this.ball=null;this.lastReact=0;this.lastGreeting=0;this.poseTouch=null;
      try{this.options=settings(JSON.parse(localStorage.getItem('mpc_faceplay_v1')||'{}'));}catch(e){this.options=settings();}
      this.panel=document.getElementById('faceplay-dialog');
      this.panel.addEventListener('close',()=>api.cancelStarting?.());
      this.hud=document.getElementById('faceplay-hud');
      this.brush=document.getElementById('faceplay-brush');
      this.tip=document.getElementById('faceplay-tip');this.halo=document.getElementById('faceplay-halo');
      for(const element of this.panel.querySelectorAll('[data-vision-option]')){
        const key=element.dataset.visionOption;if(element.type==='checkbox')element.checked=this.options[key];else element.value=this.options[key];
        element.addEventListener('change',()=>{
          this.options=settings({...this.options,[key]:element.type==='checkbox'?element.checked:Number(element.value)});
          this.persist();api.configure(this.options);
          if(['face','hands','remote'].includes(key)&&this.cameraOn){api.stop();this.note('识别模式已更新，点击开启摄像头继续。');}
        });
      }
      document.getElementById('vision-calibrate').onclick=()=>{
        const result=api.calibrate();
        if(result){this.options=settings({...this.options,...result});this.persist();this.note('中心已校准。手保持舒适位置，移动即可触碰宠物。');}
        else this.note('请先开启手势识别，把一只手放在镜头中央。');
      };
      document.getElementById('vision-reset-calibration').onclick=()=>{this.options=settings({...this.options,centerX:.5,centerY:.5,sensitivity:1.3});this.panel.querySelector('[data-vision-option="sensitivity"]').value=1.3;this.persist();api.configure(this.options);this.note('已恢复默认活动范围。');};
      document.getElementById('vision-pointer').onclick=()=>{
        api.stop();this.pointerMode=true;this.reset();this.panel.close();this.render();this.note('按住宠物轻轻移动：摸头、挠下巴或顺背毛。');
      };
      document.getElementById('faceplay-exit').onclick=()=>{api.stop();this.pointerMode=false;this.reset();this.render();};
      document.getElementById('faceplay-settings').onclick=()=>this.panel.showModal();
      for(const button of this.hud.querySelectorAll('[data-play-tool]'))button.onclick=()=>{
        api.toys?.()?.cancel();this.reset();this.mode=button.dataset.playTool;this.render();
        this.note(this.mode==='ball'?'在空地按住并拖动，松手抛球；摄像头模式捏合拿球，松开投出。':this.mode==='brush'?'用刷子沿背部缓缓移动。':'触碰头顶、下巴或背部，试试不同速度。');
      };
      document.getElementById('faceplay-toss').onclick=()=>{
        const loc=api.locomotion(),m=api.model();if(!loc||!m||api.busy())return;
        const path=loc.navigation.randomDestination(m.position);
        if(path?.length){if(api.toys?.()){api.toys().quickToss(path[path.length-1]);}else{this.holdBall();this.throwBall(path[path.length-1]);}}
      };
      const canvas=api.canvas;
      canvas.addEventListener('pointerdown',event=>{
        if(api.toys?.()?.pointerDown(event))return;
        if(!this.pointerMode||!event.isPrimary||event.button!==0)return;
        event.preventDefault();event.stopImmediatePropagation();api.cancelCommands();this.pressed=event.pointerId;canvas.setPointerCapture(event.pointerId);
        this.pointer(event);if(this.mode==='ball'){if(api.toys?.()){api.toys().startDefault(event);}else this.holdBall();}
      },true);
      canvas.addEventListener('pointermove',event=>{if(api.toys?.()?.pointerMove(event))return;if(this.pointerMode&&event.pointerId===this.pressed){event.preventDefault();event.stopImmediatePropagation();this.pointer(event);}},true);
      canvas.addEventListener('pointerup',event=>{
        if(api.toys?.()?.pointerUp(event))return;
        if(!this.pointerMode||event.pointerId!==this.pressed)return;
        event.preventDefault();event.stopImmediatePropagation();this.pointer(event);
        if(this.ball?.phase==='held')this.throwBall(this.ground(this.input.x,this.input.y));
        this.pressed=null;this.input=null;this.touch.reset();this.hideHalo();
        if(canvas.hasPointerCapture(event.pointerId))canvas.releasePointerCapture(event.pointerId);
      },true);
      canvas.addEventListener('pointercancel',()=>{api.toys?.()?.cancel();this.pressed=null;this.reset();},true);
      this.render();
    }
    persist(){try{localStorage.setItem('mpc_faceplay_v1',JSON.stringify(this.options));}catch(e){}}
    note(text){this.tip.textContent=text;document.getElementById('vision-settings-status').textContent=text;}
    render(){
      this.hud.hidden=!(this.cameraOn||this.pointerMode);
      for(const b of this.hud.querySelectorAll('[data-play-tool]'))b.setAttribute('aria-pressed',String(b.dataset.playTool===this.mode));
      document.getElementById('faceplay-toss').hidden=this.mode!=='ball';
      document.getElementById('vision-start').textContent=this.cameraOn?'关闭摄像头':'开启摄像头';
    }
    camera(on){this.cameraOn=on;if(on)this.pointerMode=false;this.reset();this.render();}
    pointer(event){const r=this.a.canvas.getBoundingClientRect();this.input={x:event.clientX-r.left,y:event.clientY-r.top,t:performance.now()};}
    hand(h){
      if(!this.cameraOn)return;
      if(h.trackingLost||h.releasing){this.input=null;this.touch.reset();this.hideHalo();return;}
      if(!h.present||h.quality===false){this.input=null;this.touch.reset();this.hideHalo();return;}
      this.input={x:h.sx,y:h.sy,t:performance.now(),pinching:h.pinching};
    }
    grab(on,pos,reason){
      if(this.a.toys?.()||this.mode!=='ball')return false;
      if(on&&pos)this.holdBall();
      else if(this.ball?.phase==='held'){
        if(reason==='lost'||reason==='stop'||!pos)this.reset();
        else this.throwBall(this.ground(pos.pinchX??pos.sx,pos.pinchY??pos.sy));
      }
      return true;
    }
    faceInput(face){
      this.face=face.present?{...face,t:performance.now()}:null;
      if(!face.present)return;
      const now=performance.now();
      if(Math.abs(face.roll)>.18&&now-this.lastReact>4500&&!this.a.busy()&&!this.tool&&!this.input&&!this.ball){this.lastReact=now;this.a.act('curious',1600);}
    }
    gaze(on){
      if(on&&performance.now()-this.lastGreeting>6500&&!this.a.busy()&&!this.tool&&!this.ball){
        this.lastGreeting=performance.now();this.a.act(this.a.id()===2?'greet':'ears',1500);this.a.say(this.a.id()===2?'嗷呜，看到你啦！':'我在听呢。');
      }
    }
    project(world){const p=world.clone().project(this.a.camera);return {x:(p.x*.5+.5)*this.a.canvas.clientWidth,y:(-.5*p.y+.5)*this.a.canvas.clientHeight};}
    ground(x,y,height=0){
      const T=this.a.THREE,r=new T.Raycaster();r.setFromCamera(new T.Vector2(x/this.a.canvas.clientWidth*2-1,1-y/this.a.canvas.clientHeight*2),this.a.camera);
      return r.ray.intersectPlane(new T.Plane(new T.Vector3(0,1,0),-height),new T.Vector3());
    }
    zones(){
      const m=this.a.model();if(!m)return [];
      const head=this.project(this.a.head()),mouth=this.project(this.a.mouth());
      const h=m.userData.height||1;
      const body=this.project(m.localToWorld(new this.a.THREE.Vector3(0,h*.53,0)));
      const edge=this.project(this.a.head().clone().add(new this.a.THREE.Vector3(0,h*.25,0)));
      const r=clamp(Math.hypot(edge.x-head.x,edge.y-head.y),22,95);
      return [{id:'chin',label:'挠下巴',x:mouth.x,y:mouth.y+r*.22,rx:r*.72,ry:r*.45},
        {id:'head',label:'摸摸头',x:head.x,y:head.y-r*.35,rx:r,ry:r*.7},
        {id:'back',label:'顺背毛',x:body.x,y:body.y,rx:r*1.4,ry:r*.85}];
    }
    hideHalo(){this.halo.hidden=true;if(this.brush)this.brush.hidden=true;this.poseTouch=null;}
    guide(point){this.tool={...point,t:performance.now()};}
    releaseGuide(){if(this.guiding)this.a.locomotion()?.interrupt();this.guiding=false;this.tool=null;}
    beforeFrame(){for(const entry of this.bones)if(entry.base){entry.bone.quaternion.copy(entry.base);entry.base=null;}}
    bind(){
      const model=this.a.model();if(this.model===model)return;
      this.reset();this.model=model;this.bones=[];
      model?.traverse(bone=>{if(bone.isBone&&(bone===model.userData.headBone||/^eye_[LR]$/i.test(bone.name)))this.bones.push({bone,eye:/^eye/i.test(bone.name),base:null});});
    }
    reset(keepPointer=false){
      if(!keepPointer && this.pressed!=null){const c=this.a.canvas;if(c?.hasPointerCapture(this.pressed))c.releasePointerCapture(this.pressed);this.pressed=null;}
      this.beforeFrame();this.releaseGuide();this.touch.reset();this.input=null;this.face=null;this.hideHalo();
      if(this.ball){const b=this.ball;this.ball=null;if(b.item)b.item.release(['drop','placed'].includes(b.phase));else{this.a.scene.remove(b.mesh);b.mesh.geometry.dispose();b.mesh.material.dispose();}this.a.locomotion()?.interrupt();}
      this.look={x:0,y:0,r:0};this.poseTouch=null;
    }
    holdBall(item=null){
      if(this.a.busy()||!this.a.model())return;
      this.reset(true);const T=this.a.THREE;
      const mesh=item?.mesh||new T.Mesh(new T.SphereGeometry(.105,16,12),new T.MeshStandardMaterial({color:0xeaa975,roughness:.65}));
      if(!item){mesh.position.copy(this.a.mouth());this.a.scene.add(mesh);}
      this.ball={mesh,item,phase:'held',home:this.a.model().position.clone(),started:performance.now(),offset:item?.offset||.11,lift:item?.kind==='disc'?.32:.65,duration:item?.kind==='disc'?900:700,fetch:true};
      this.a.locomotion()?.interrupt(2.5);this.note('拿稳啦，向空地松手。');
    }
    throwBall(target){
      const b=this.ball,loc=this.a.locomotion();if(!b||!target||!loc){this.reset();return;}
      if(!loc.navigation.isWalkable(target)||!loc.navigation.route(this.a.model().position,target)){
        this.reset();this.note('这里是河面、障碍物或岛外，换一块可走到的空地吧。');return;
      }
      b.started=performance.now();
      b.from=b.mesh.position.clone();b.target={x:target.x,z:target.z};b.phase='flight';b.at=performance.now();
      this.a.act('idle',0);this.note(b.fetch?'接好'+(b.item?.label||'球')+'！它会绕开河流，把玩具叼回来。':'正在放下，落地后可以再次拿起。');
    }
    updateBall(now,dt=.02){
      const b=this.ball,m=this.a.model(),loc=this.a.locomotion();if(!b||!m||!loc)return;
      b.elapsed=(b.elapsed||0)+Math.min(dt,.05);
      if(b.elapsed>45||this.a.busy()){const timeout=b.elapsed>45;this.reset();if(timeout)this.note('先歇一下，换块近一点的空地再来。');return;}
      const T=this.a.THREE;
      if(b.phase==='held'){
        if(this.input){const p=this.ground(this.input.x,this.input.y,1.1);if(p){b.mesh.position.lerp(p,.25);}}
      } else if(b.phase==='flight'){
        const t=clamp((now-b.at)/(b.duration||700),0,1),y=loc.navigation.surfaceHeight(b.target)+(b.offset||.11);
        const point=flightPoint(b.from,{x:b.target.x,y,z:b.target.z},t,b.lift);b.mesh.position.set(point.x,point.y,point.z);
        if(b.item?.kind==='disc')b.mesh.rotation.y+=dt*9;
        if(t===1&&!b.fetch){b.phase='placed';this.reset();this.note('放好了，随时可以再拿起来。');return;}
        if(t===1){b.phase='chase';this.a.act('idle',0);if(!loc.goTo(b.target,{gait:'run'})){this.reset();this.note('这次没有找到安全路线，再试一块空地吧。');}}
      } else if(b.phase==='chase'&&Math.hypot(m.position.x-b.target.x,m.position.z-b.target.z)<.15){
        b.phase='pickup';b.at=now;this.a.act('noseLick',650);this.note('叼到啦，马上回来。');
      } else if(b.phase==='pickup'){
        b.mesh.position.lerp(this.a.mouth(),1-Math.exp(-12*Math.max(0,Math.min(.05,dt))));
        if(now-b.at>750){b.mesh.position.copy(this.a.mouth());b.phase='return';this.a.act('idle',0);if(!loc.goTo(b.home,{gait:'trot'})){this.reset();this.note('回程暂时被挡住了，这轮先结束，再换块空地吧。');}}
      } else if(b.phase==='return'){
        b.mesh.position.copy(this.a.mouth());
        if(Math.hypot(m.position.x-b.home.x,m.position.z-b.home.z)<.15){b.phase='drop';b.at=now;b.from=b.mesh.position.clone();this.a.act('greet',1700);this.note((this.a.id()===3?'猫咪':this.a.id()===2?'雪球':'球球')+'把'+(b.item?.label||'球')+'还给你：再来一次！');}
      } else if(b.phase==='drop'){
        const t=clamp((now-b.at)/350,0,1);b.mesh.position.y=b.from.y+(loc.navigation.surfaceHeight(m.position)+(b.offset||.11)-b.from.y)*t;
        if(now-b.at>1800){if(!b.autonomous)this.a.onFetch?.(b.item?.kind||'ball');this.reset();}
      }
    }
    update(dt,now){
      this.attention=null;
      this.bind();if(!this.model || (!this.cameraOn&&!this.pointerMode&&!this.tool&&!this.ball))return;
      this.updateBall(now,dt);
      if(this.a.busy()){this.hideHalo();this.touch.reset();this.releaseGuide();this.input=null;this.face=null;}
      const point=this.input&&((this.pointerMode&&this.pressed!=null)||now-this.input.t<600)?this.input:null;
      const tool=this.tool&&(this.a.foodActive?.()||now-this.tool.t<450)?this.tool:null;
      if(!tool&&this.guiding)this.releaseGuide();
      let aim=tool||point;
      if(tool&&!this.a.busy()){
        const head=this.project(this.a.head()),distance=Math.hypot(tool.x-head.x,tool.y-head.y);
        const loc=this.a.locomotion();
        this.guiding=true;
        if(tool.y<head.y-65&&distance<190){if(now-(this.lastGuideAction||0)>1800){this.a.act('sit',1200);this.lastGuideAction=now;}this.note('举高零食，它坐下等你。');}
        else if(distance>110&&now-(this.lastGuideMove||0)>800){
          const p=this.ground(tool.x,tool.y);this.lastGuideMove=now;
          if(p&&loc?.navigation.isWalkable(p)){this.a.act('idle',0);loc.goTo(p);this.note('慢慢移动零食，引它走到你身边。');}
        }
      }
      if(point&&!tool&&!this.ball&&!point.pinching&&!this.a.busy()&&this.a.toys?.()?.held?.spec.id!=='rattle'){
        const zone=zoneAt(point,this.zones());
        if(zone){
          const sample=this.touch.sample(point,zone.id,now);this.poseTouch=zone.id;
          this.halo.hidden=false;this.halo.style.left=zone.x+'px';this.halo.style.top=zone.y+'px';
          this.halo.style.width=zone.rx*2+'px';this.halo.style.height=zone.ry*2+'px';
          this.halo.textContent=this.mode==='brush'?'梳梳毛':zone.label;
          if(this.brush){this.brush.hidden=this.mode!=='brush'||this.a.toys?.()?.held?.spec.id==='brush';this.brush.style.left=point.x+'px';this.brush.style.top=point.y+'px';}
          if(sample.enter){this.a.act(zone.id==='back'?'petting':'affection',2000);this.note(zone.label+' · 缓缓移动，停一停它还会蹭你。');}
          if(sample.nuzzle){this.a.act('affection',2200);this.a.say(this.a.id()===2?'别停嘛，再挠一下！':'它轻轻蹭了蹭你的手。');}
          if(sample.reward)this.a.reward();
          if(sample.speed>800&&now-this.lastReact>3000){this.lastReact=now;this.a.act('curious',1000);this.note('轻一点，慢慢摸更舒服。');}
          if(this.mode==='brush'&&zone.id==='back'&&sample.speed>20&&now-this.lastReact>1400){this.lastReact=now;this.a.act('petting',1200);this.note('顺着背毛慢慢梳，它放松下来了。');}
        }else{this.hideHalo();this.touch.sample(point,null,now);}
      }else{this.hideHalo();this.touch.reset();}
      if(!aim&&this.face&&now-this.face.t<600&&!this.a.busy())aim={x:this.face.x*this.a.canvas.clientWidth,y:this.face.y*this.a.canvas.clientHeight};
      this.attention=aim;
      const head=this.project(this.a.head()),fade=1-Math.exp(-dt*7);
      const tx=aim?clamp((aim.x-head.x)/this.a.canvas.clientWidth*1.5,-.35,.35):0;
      const ty=aim?clamp((aim.y-head.y)/this.a.canvas.clientHeight,-.20,.20):0;
      this.look.x+=(tx-this.look.x)*fade;this.look.y+=(ty-this.look.y)*fade;
      this.look.r+=((this.face?clamp(this.face.roll,-.18,.18):0)-this.look.r)*fade;
      const T=this.a.THREE;
      for(const entry of this.bones){
        if(!entry.eye&&this.a.model()?.userData.headLook)continue;
        entry.base=entry.bone.quaternion.clone();
        const amount=entry.eye?1.15:.5;
        const chin=this.poseTouch==='chin'?-.08:0;
        const turn=new T.Quaternion().setFromEuler(new T.Euler((this.look.y+chin)*amount,this.look.x*amount,entry.eye?0:this.look.r*.45));
        entry.bone.quaternion.multiply(turn);
      }
    }
  }
  return {settings,zoneAt,flightPoint,Touch,Controller};
});
