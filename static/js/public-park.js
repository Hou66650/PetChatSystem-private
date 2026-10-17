/* Real, opt-in presence: no fake users, no control of another owner's pet. */
(()=>{'use strict';
 const root=document.getElementById('pet-park'),canvas=document.getElementById('park-canvas'),status=document.getElementById('park-status'),join=document.getElementById('park-join'),leave=document.getElementById('park-leave'),select=document.getElementById('park-pet'),buttons=[...root.querySelectorAll('[data-action]')];
 const T=THREE,scene=new T.Scene();scene.background=new T.Color(0xdce7df);scene.fog=new T.Fog(0xdce7df,45,100);
 let renderer;try{renderer=new T.WebGLRenderer({canvas,antialias:true,powerPreference:'low-power'});}catch(e){status.textContent='三维暂不可用，请返回群岛后重试。';if(join)join.disabled=true;return;}
 window.PaitWebCompat?.prepareRenderer(renderer);renderer.outputEncoding=T.sRGBEncoding;renderer.toneMapping=T.ACESFilmicToneMapping;renderer.toneMappingExposure=.85;
 const camera=new T.PerspectiveCamera(42,1,.1,150);camera.position.set(14,20,25);const controls=new T.OrbitControls(camera,canvas);controls.target.set(0,0,0);controls.enableDamping=true;controls.enablePan=false;controls.minDistance=12;controls.maxDistance=48;controls.maxPolarAngle=1.3;
 scene.add(new T.HemisphereLight(0xfffaeb,0x61755d,.85));const sun=new T.DirectionalLight(0xffecd0,1.1);sun.position.set(-15,22,10);scene.add(sun);
 const navigation=ParkNavigation.create(JSON.parse(document.getElementById('park-navigation').textContent)),sceneLoader=new SelectedAssets.Loader(new T.GLTFLoader()),retry=document.getElementById('park-retry');
 const actors=new Map(),ray=new T.Raycaster(),pointer=new T.Vector2(),plane=new T.Plane(new T.Vector3(0,1,0),0),hit=new T.Vector3();
 let token=null,mine=null,target=null,path=[],state=null,timer=null,epoch=0,disposed=false,raf,last=0,action='idle',actionUntil=0,lastGood=performance.now(),gesture=null,sceneReady=false,parkModel=null,dirty=true;
 const self={x:0,z:0,yaw:0};
 const autoButton=document.getElementById('park-auto'),intent=document.getElementById('park-intent');
 let facility=null,pauseAfterFacility=false;
 const facilitySpecs=new Map((navigation.config.facilities||[]).map(f=>[f.id,f]));
 let agent=null,aiGoal=null,moveSpeed=1,nextDecision=0,lastDecision=0,blockedAt=0;
 function manual(seconds=12){agent?.interrupt(performance.now()/1000,seconds);aiGoal=null;moveSpeed=1.1;if(intent)intent.textContent='先陪主人玩，稍后继续自主探索。';}
 function behavior(){const activity=agent&&performance.now()/1000>=agent.until?agent.activity:'manual';return {autonomous:!!agent?.enabled,activity:facility?'facility':activity==='facility'?'explore':activity,goal:aiGoal,facility:facility?{id:facility.id,progress:facility.progress}:null};}
 function facilityBusy(){if(!facility)return false;if(intent)intent.textContent='先安全回到草坪，再陪主人玩。';return true;}
 function cancelMove(){target=null;path=[];action='idle';actionUntil=0;aiGoal=null;}
 function think(now){if(facility||!agent||!token||!actors.get(mine)?.pet||now<nextDecision)return;nextDecision=now+.25;
  const peers=(state?.players||[]).filter(p=>!p.mine),command=agent.tick({now,dt:lastDecision?now-lastDecision:.25,pos:self,peers,moving:!!target});lastDecision=now;
  root.dataset.agent=agent.enabled?'auto':'paused';root.dataset.activity=behavior().activity;
  if(!command)return;if(command.cancel){cancelMove();if(intent)intent.textContent=command.message;return;}
  if(command.facility){cancelMove();facility={id:command.facility,progress:0,confirmed:false};ui();if(intent)intent.textContent='正在等候设施入口…';return;}
  if(command.destination){destination(command.destination,command.message,false);if(!target){agent.failed(now);return;}}
  else{target=null;path=[];}
  moveSpeed=command.speed;action=command.action;actionUntil=(now+command.duration)*1000;aiGoal=command.goal;
  if(command.face)self.yaw=Math.atan2(command.face.x-self.x,command.face.z-self.z);
  if(intent)intent.textContent=command.message;
 }
 if(autoButton)autoButton.onclick=()=>{if(!agent||!token)return;if(facility){pauseAfterFacility=!pauseAfterFacility;ui();if(intent)intent.textContent=pauseAfterFacility?'回到草坪后暂停自主游玩。':'完成设施后继续自主游玩。';return;}agent.enable(!agent.enabled,performance.now()/1000);cancelMove();ui();if(intent)intent.textContent=agent.enabled?'让它自己决定接下来玩什么。':'自主游玩已暂停，可以陪它玩。';};
 async function request(operation,data){const controller=new AbortController(),timeout=setTimeout(()=>controller.abort(),4500);try{const response=await fetch('/api/park'+(operation?'/'+operation:''),{method:operation?'POST':'GET',headers:{'Content-Type':'application/json','X-Profile-Scope':root.dataset.scope},body:operation?JSON.stringify(data):undefined,signal:controller.signal,cache:'no-store'});const body=await response.json();if(!response.ok)throw Object.assign(new Error(body.error||'连接失败'),{status:response.status});return body;}finally{clearTimeout(timeout);}}
 function destination(p,message,fromOwner=true){if(fromOwner&&facilityBusy())return;if(fromOwner)manual(25);path=navigation.route(self,p);target=path.shift()||null;action='idle';status.textContent=target?message:'这里暂时不能到达，请选择开阔草坪。';}
 function approach(p){if(!token)return;const dx=self.x-p.x,dz=self.z-p.z,d=Math.hypot(dx,dz)||1;destination({x:p.x+dx/d*1.5,z:p.z+dz/d*1.5},'走近'+p.spec.name+'，可以打个招呼。');}
 async function loadPark(){sceneReady=false;root.dataset.scene='loading';retry.hidden=true;ui();status.textContent='正在展开爪心乐园…';const ticket=sceneLoader.begin();
  try{const gltf=await PetParkScene.load(T,{tier:'play',loader:sceneLoader,ticket,version:root.dataset.version});if(disposed){SelectedAssets.disposeTree(gltf.scene);return;}parkModel=gltf.scene;scene.add(parkModel);sceneReady=true;dirty=true;root.dataset.scene='ready';status.textContent='乐园已就绪，可以带伙伴入园。';ui();poll();}
  catch(error){if(error.name==='AbortError'||disposed)return;root.dataset.scene='failed';retry.hidden=false;status.textContent='乐园未能加载，请检查连接后重试。';ui();}
 }
 retry.onclick=loadPark;
 function remove(id){const a=actors.get(id);if(!a)return;a.loader.begin();a.label.remove();if(a.ball){scene.remove(a.ball);SelectedAssets.disposeTree(a.ball);}if(a.pet){a.pet.mixer.stopAllAction();a.pet.mixer.uncacheRoot(a.pet.model);scene.remove(a.pet.root);SelectedAssets.disposeTree(a.pet.root);}actors.delete(id);dirty=true;}
 async function load(p){
  const loader=new SelectedAssets.Loader(new T.GLTFLoader()),ticket=loader.begin(),label=document.createElement('button');label.type='button';label.textContent=p.spec.name+(p.mine?' · 我':'');label.title='走近这位伙伴';document.getElementById('park-players').append(label);
  const a={loader,label,remote:p,pet:null};actors.set(p.id,a);label.onclick=()=>approach(p);
  try{const gltf=await loader.glb(p.spec.model+'?v='+encodeURIComponent(root.dataset.version),ticket);if(actors.get(p.id)!==a){SelectedAssets.disposeTree(gltf.scene);return;}
   a.pet=new PortalPets.Pet(T,gltf,p.spec);a.pet.root.position.set(p.x,0,p.z);a.pet.root.rotation.y=p.yaw;scene.add(a.pet.root);a.motion=new ParkMotion.Motion(a.pet);a.label.dataset.ready="true";
   const ball=new T.Mesh(new T.SphereGeometry(.18,12,8),new T.MeshStandardMaterial({color:0xd39b58,roughness:.7}));ball.visible=false;scene.add(ball);a.ball=ball;
  }catch(e){if(e.name!=='AbortError'&&actors.get(p.id)===a){a.label.textContent=p.spec.name+' · 加载失败';a.label.onclick=()=>{remove(p.id);load(a.remote);};if(p.mine)status.textContent='伙伴模型加载失败，可点右侧名字重试，或结束游玩。';}}
 }
 function apply(next,initial=false){if(next.layoutVersion&&next.layoutVersion!==navigation.config.version){stop('乐园已更新，请刷新页面后重新入园。');sceneReady=false;ui();return;}state=next;lastGood=performance.now();document.getElementById('park-count').textContent='在线伙伴 '+next.count+' / '+next.capacity;
  const ids=new Set(next.players.map(p=>p.id));for(const id of actors.keys())if(!ids.has(id))remove(id);
  for(const p of next.players){if(p.mine){mine=p.id;if(initial)Object.assign(self,{x:p.x,z:p.z,yaw:p.yaw});}
   if(p.mine&&facility&&p.behavior?.facility?.id===facility.id){facility.confirmed=true;const f=facilitySpecs.get(facility.id);if(p.behavior.facility.progress>=ParkFacilities.length(f)-1e-5){Object.assign(self,ParkFacilities.sample(f,ParkFacilities.length(f)));facility=null;agent.energy=Math.max(.1,agent.energy-.12);agent.playfulness=.15;agent.interrupt(performance.now()/1000,2);if(pauseAfterFacility)agent.enable(false,performance.now()/1000);pauseAfterFacility=false;ui();if(intent)intent.textContent=agent.enabled?'玩好了，回草坪歇一下。':'已回到草坪，暂停自主游玩。';}}
   const a=actors.get(p.id);if(a){a.remote=p;a.label.onclick=()=>approach(a.remote);}else load(p);
  }
 }
 function ui(){if(join)join.disabled=!!token||!sceneReady;if(select)select.disabled=!!token;if(leave)leave.hidden=!token;buttons.forEach(b=>b.disabled=!token||!sceneReady||!!facility);if(autoButton){autoButton.disabled=!token;autoButton.textContent=pauseAfterFacility?'回草坪后暂停':'自主游玩：'+(agent?.enabled?'开':'关');autoButton.setAttribute('aria-pressed',String(!!agent?.enabled));}}
 function stop(message,notify=true){const old=token;facility=null;pauseAfterFacility=false;agent=null;aiGoal=null;lastDecision=0;token=null;mine=null;target=null;path=[];action='idle';epoch++;ui();if(old&&notify)fetch('/api/park/leave',{method:'POST',keepalive:true,headers:{'Content-Type':'application/json','X-Profile-Scope':root.dataset.scope},body:JSON.stringify({token:old})}).catch(()=>{});for(const id of [...actors.keys()])remove(id);dirty=true;if(message)status.textContent=message;}
 async function poll(){if(disposed||!sceneReady)return;clearTimeout(timer);if(document.hidden){timer=setTimeout(poll,1000);return;}const generation=epoch;
  try{const data=token?await request('sync',{token,...self,action:performance.now()<actionUntil?action:'idle',behavior:behavior()}):await request();if(generation!==epoch)return;apply(data);}
  catch(e){if(generation!==epoch)return;if([401,409].includes(e.status))stop(e.message,false);else if(e.status===423){facility=null;ui();cancelMove();agent?.failed(performance.now()/1000);if(intent)intent.textContent='设施有伙伴在玩，先去草坪转转。';}
   else if(e.status===422){cancelMove();const data=await request().catch(()=>null);const saved=data?.players.find(p=>p.mine)?.behavior?.facility;if(facility&&saved){facility.progress=saved.progress;facility.confirmed=true;}else{facility=null;ui();agent?.failed(performance.now()/1000);}if(data)apply(data,true);status.textContent='位置已同步，伙伴会重新选择路线。';}
   else{if(facility)facility.confirmed=false;cancelMove();agent?.interrupt(performance.now()/1000,5);status.textContent='连接暂时中断，正在重连。';if(performance.now()-lastGood>8000)stop('连接中断，已停止游玩；恢复后请重新入园。');}}
  finally{if(!disposed)timer=setTimeout(poll,token?500:3000);}
 }
 if(join)join.onclick=async()=>{if(!sceneReady||token)return;join.disabled=true;const generation=++epoch;try{const data=await request('join',{pet:Number(select.value)});if(generation!==epoch){request('leave',{token:data.token}).catch(()=>{});return;}token=data.token;agent=new ParkAgent.Agent({navigation,personality:data.personality});agent.facilities=navigation.config.facilities;agent.height=data.players.find(p=>p.mine).spec.height;nextDecision=0;lastDecision=0;apply(data,true);ui();status.textContent='伙伴会自己探索和游玩；拖动旋转，也可以随时陪它玩。';}catch(e){status.textContent=e.message;ui();}};
 if(leave)leave.onclick=()=>stop('已经结束游玩，伙伴会从公共乐园离开。');
 for(const button of buttons)button.onclick=()=>{if(!token||facilityBusy())return;manual();const next=button.dataset.action;if(next==='walk'){destination(navigation.config.restPoint,'一起去开阔草坪。');return;}target=null;path=[];action=next;actionUntil=performance.now()+4200;status.textContent=button.textContent+' · 同场伙伴也能看到这个动作';};
 // OrbitControls calls focus() on pointerdown. Focus first without scrolling so
 // the canvas does not shift under the pointer and change the picked destination.
 canvas.addEventListener('pointerdown',()=>canvas.focus({preventScroll:true}),true);
 canvas.addEventListener('pointerdown',e=>{gesture=e.isPrimary?{id:e.pointerId,x:e.clientX,y:e.clientY}:null;});
 canvas.addEventListener('pointermove',e=>{if(gesture&&Math.hypot(e.clientX-gesture.x,e.clientY-gesture.y)>6)gesture=null;});
 canvas.addEventListener('pointercancel',()=>gesture=null);
 canvas.addEventListener('pointerup',e=>{const g=gesture;gesture=null;if(!g||g.id!==e.pointerId||!token||Math.hypot(e.clientX-g.x,e.clientY-g.y)>6)return;const r=canvas.getBoundingClientRect();pointer.set((e.clientX-r.left)/r.width*2-1,1-(e.clientY-r.top)/r.height*2);ray.setFromCamera(pointer,camera);if(ray.ray.intersectPlane(plane,hit)&&(hit.x/8)**2+(hit.z/6)**2<=1){destination({x:hit.x,z:hit.z},'正在草坪上散步。');}});
 function frame(now){raf=requestAnimationFrame(frame);if(document.hidden||now-last<1000/30)return;const dt=last?Math.min((now-last)/1000,.08):0;last=now;
  const w=canvas.clientWidth,h=canvas.clientHeight;if(w&&h&&(canvas.width!==Math.floor(w*renderer.getPixelRatio())||canvas.height!==Math.floor(h*renderer.getPixelRatio()))){renderer.setPixelRatio(Math.min(devicePixelRatio,1.25,Math.sqrt(1800000/(w*h))));renderer.setSize(w,h,false);camera.aspect=w/h;camera.updateProjectionMatrix();dirty=true;}
  think(now/1000);
  let walking=false,budget=dt*moveSpeed;
  if(facility&&facility.confirmed){const f=facilitySpecs.get(facility.id),next=Math.min(ParkFacilities.length(f),facility.progress+dt*f.speed),point=ParkFacilities.sample(f,next);const occupied=(state?.players||[]).some(p=>!p.mine&&Math.hypot(point.x-p.x,point.z-p.z)<1&&Math.hypot(point.x-p.x,point.z-p.z)<Math.hypot(self.x-p.x,self.z-p.z));if(!occupied){walking=next>facility.progress;facility.progress=next;Object.assign(self,point);}if(intent)intent.textContent=occupied?'前面有伙伴，等它走开再继续。':pauseAfterFacility?'回到草坪后暂停自主游玩。':f.message;root.dataset.facility=facility.id;root.dataset.facilityProgress=facility.progress.toFixed(3);}
  else if(!facility){delete root.dataset.facility;delete root.dataset.facilityProgress;}if(token&&actors.get(mine)?.pet)while(target&&budget>0){const dx=target.x-self.x,dz=target.z-self.z,d=Math.hypot(dx,dz);if(d<.001){self.x=target.x;self.z=target.z;target=path.shift()||null;continue;}const step=Math.min(d,budget),nx=self.x+dx/d*step,nz=self.z+dz/d*step;
   const occupied=(state?.players||[]).some(p=>!p.mine&&Math.hypot(nx-p.x,nz-p.z)<1&&Math.hypot(nx-p.x,nz-p.z)<Math.hypot(self.x-p.x,self.z-p.z));
   if(occupied){if(!blockedAt)blockedAt=now;if(now-blockedAt>1800){cancelMove();agent?.failed(now/1000);status.textContent='前面有伙伴，稍等一下再换个位置。';blockedAt=0;}break;}blockedAt=0;self.x+=dx/d*step;self.z+=dz/d*step;self.yaw=Math.atan2(dx,dz);walking=true;budget-=step;}
  for(const [id,a] of actors){if(!a.pet)continue;const p=a.pet.root.position,remote=a.remote,isMine=!!token&&id===mine,tx=isMine?self.x:remote.x,tz=isMine?self.z:remote.z,d=Math.hypot(tx-p.x,tz-p.z),k=isMine?1:1-Math.exp(-dt*10);p.x+=(tx-p.x)*k;p.z+=(tz-p.z)*k;let renderYaw=isMine?self.yaw:remote.yaw;
   const fs=isMine?facility:remote.behavior?.facility;
   if(fs){const f=facilitySpecs.get(fs.id);if(f){a.facilityProgress=a.facilityId===fs.id&&!isMine?Math.min(fs.progress,a.facilityProgress+dt*f.speed):fs.progress;a.facilityId=fs.id;const pose=ParkFacilities.sample(f,a.facilityProgress);p.set(pose.x,pose.y,pose.z);renderYaw=pose.yaw;a.pet.root.rotation.x=pose.pitch;}}else{a.facilityId=null;p.y=0;a.pet.root.rotation.x=0;}
   a.pet.root.rotation.order='YXZ';a.pet.root.rotation.y+=Math.atan2(Math.sin(renderYaw-a.pet.root.rotation.y),Math.cos(renderYaw-a.pet.root.rotation.y))*(1-Math.exp(-dt*12));
   const current=isMine?(now<actionUntil?action:'idle'):remote.action,moving=isMine?walking:d>.035;a.motion.update(moving?((isMine?moveSpeed>1.4:remote.action==='ball')?'run':'walk'):current==='ball'?'sniff':current,dt,moving?.9:1);
   const goal=isMine?aiGoal:remote.behavior?.goal;a.ball.visible=!!goal||current==='ball';if(a.ball.visible){if(goal)a.ball.position.set(goal.x,.18,goal.z);else a.ball.position.set(p.x+Math.sin(now*.004)*.6,.2+Math.abs(Math.sin(now*.006))*.35,p.z+1.1);}
   const activity=isMine?behavior().activity:remote.behavior?.activity,label=fs?facilitySpecs.get(fs.id)?.message:ParkAgent.labels[activity];const caption=remote.spec.name+(isMine?' · 我':'')+(label?' · '+label:'');if(a.label.textContent!==caption)a.label.textContent=caption;
  }const changed=controls.update();if(dirty||changed||actors.size){renderer.render(scene,camera);dirty=false;}
 }
 document.addEventListener('visibilitychange',()=>{if(document.hidden)stop('已暂停公开游玩，回来后可以重新入园。');});
 addEventListener('pagehide',e=>{disposed=true;sceneLoader.begin();clearTimeout(timer);cancelAnimationFrame(raf);stop(null);if(!e.persisted){if(parkModel)SelectedAssets.disposeTree(parkModel);controls.dispose();renderer.dispose();}});
 addEventListener('pageshow',e=>{if(e.persisted){disposed=false;last=0;dirty=true;if(!sceneReady)loadPark();else poll();raf=requestAnimationFrame(frame);}});
 canvas.addEventListener('webglcontextlost',e=>{e.preventDefault();stop('画面已暂停，请刷新后重新入园。');cancelAnimationFrame(raf);if(join)join.disabled=true;});
 loadPark();raf=requestAnimationFrame(frame);
})();
