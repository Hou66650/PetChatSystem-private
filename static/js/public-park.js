/* Real, opt-in presence: no fake users, no control of another owner's pet. */
(()=>{'use strict';
 const root=document.getElementById('pet-park'),canvas=document.getElementById('park-canvas'),status=document.getElementById('park-status'),join=document.getElementById('park-join'),leave=document.getElementById('park-leave'),select=document.getElementById('park-pet'),buttons=[...root.querySelectorAll('[data-action]')];
 const T=THREE,scene=new T.Scene();scene.background=new T.Color(0xdce7df);scene.fog=new T.Fog(0xdce7df,45,100);
 let renderer;try{renderer=new T.WebGLRenderer({canvas,antialias:true,powerPreference:'low-power'});}catch(e){status.textContent='三维暂不可用，请返回群岛后重试。';if(join)join.disabled=true;return;}
 window.PaitWebCompat?.prepareRenderer(renderer);renderer.outputEncoding=T.sRGBEncoding;renderer.toneMapping=T.ACESFilmicToneMapping;renderer.toneMappingExposure=.85;
 const camera=new T.PerspectiveCamera(42,1,.1,150);camera.position.set(14,20,25);const controls=new T.OrbitControls(camera,canvas);controls.target.set(0,0,0);controls.enableDamping=true;controls.enablePan=false;controls.minDistance=12;controls.maxDistance=48;controls.maxPolarAngle=1.3;
 scene.add(new T.HemisphereLight(0xfffaeb,0x61755d,.85));const sun=new T.DirectionalLight(0xffecd0,1.1);sun.position.set(-15,22,10);scene.add(sun);scene.add(PetParkScene.create(T));
 const actors=new Map(),ray=new T.Raycaster(),pointer=new T.Vector2(),plane=new T.Plane(new T.Vector3(0,1,0),0),hit=new T.Vector3();
 let token=null,mine=null,target=null,state=null,timer=null,epoch=0,disposed=false,raf,last=0,action='idle',actionUntil=0,lastGood=performance.now(),gesture=null;
 const self={x:0,z:0,yaw:0};
 async function request(operation,data){const controller=new AbortController(),timeout=setTimeout(()=>controller.abort(),4500);try{const response=await fetch('/api/park'+(operation?'/'+operation:''),{method:operation?'POST':'GET',headers:{'Content-Type':'application/json','X-Profile-Scope':root.dataset.scope},body:operation?JSON.stringify(data):undefined,signal:controller.signal,cache:'no-store'});const body=await response.json();if(!response.ok)throw Object.assign(new Error(body.error||'连接失败'),{status:response.status});return body;}finally{clearTimeout(timeout);}}
 function approach(p){if(!token)return;const dx=self.x-p.x,dz=self.z-p.z,d=Math.hypot(dx,dz)||1;let x=p.x+dx/d*.95,z=p.z+dz/d*.95;const radius=Math.sqrt((x/8)**2+(z/6)**2);if(radius>1){x/=radius;z/=radius;}target={x,z};status.textContent='走近'+p.spec.name+'，可以打个招呼。';}
 function remove(id){const a=actors.get(id);if(!a)return;a.loader.begin();a.label.remove();if(a.pet){a.pet.mixer.stopAllAction();a.pet.mixer.uncacheRoot(a.pet.model);scene.remove(a.pet.root);SelectedAssets.disposeTree(a.pet.root);}actors.delete(id);}
 async function load(p){
  const loader=new SelectedAssets.Loader(new T.GLTFLoader()),ticket=loader.begin(),label=document.createElement('button');label.type='button';label.textContent=p.spec.name+(p.mine?' · 我':'');label.title='走近这位伙伴';document.getElementById('park-players').append(label);
  const a={loader,label,remote:p,pet:null};actors.set(p.id,a);label.onclick=()=>approach(p);
  try{const gltf=await loader.glb(p.spec.model+'?v='+encodeURIComponent(root.dataset.version),ticket);if(actors.get(p.id)!==a){SelectedAssets.disposeTree(gltf.scene);return;}
   a.pet=new PortalPets.Pet(T,gltf,p.spec);a.pet.root.position.set(p.x,0,p.z);a.pet.root.rotation.y=p.yaw;scene.add(a.pet.root);
   const ball=new T.Mesh(new T.SphereGeometry(.18,12,8),new T.MeshStandardMaterial({color:0xd39b58,roughness:.7}));ball.visible=false;a.pet.root.add(ball);a.ball=ball;
  }catch(e){if(e.name!=='AbortError'&&actors.get(p.id)===a){a.label.textContent=p.spec.name+' · 加载失败';a.label.onclick=()=>{remove(p.id);load(a.remote);};if(p.mine)status.textContent='伙伴模型加载失败，可点右侧名字重试，或结束游玩。';}}
 }
 function apply(next,initial=false){state=next;lastGood=performance.now();document.getElementById('park-count').textContent='在线伙伴 '+next.count+' / '+next.capacity;
  const ids=new Set(next.players.map(p=>p.id));for(const id of actors.keys())if(!ids.has(id))remove(id);
  for(const p of next.players){if(p.mine){mine=p.id;if(initial)Object.assign(self,{x:p.x,z:p.z,yaw:p.yaw});}
   const a=actors.get(p.id);if(a){a.remote=p;a.label.onclick=()=>approach(a.remote);}else load(p);
  }
 }
 function ui(){if(join)join.disabled=!!token;if(select)select.disabled=!!token;if(leave)leave.hidden=!token;buttons.forEach(b=>b.disabled=!token);}
 function stop(message,notify=true){const old=token;token=null;mine=null;target=null;action='idle';epoch++;ui();if(old&&notify)fetch('/api/park/leave',{method:'POST',keepalive:true,headers:{'Content-Type':'application/json','X-Profile-Scope':root.dataset.scope},body:JSON.stringify({token:old})}).catch(()=>{});for(const id of [...actors.keys()])remove(id);if(message)status.textContent=message;}
 async function poll(){if(disposed)return;clearTimeout(timer);if(document.hidden){timer=setTimeout(poll,1000);return;}const generation=epoch;
  try{const data=token?await request('sync',{token,...self,action:performance.now()<actionUntil?action:'idle'}):await request();if(generation!==epoch)return;apply(data);}
  catch(e){if(generation!==epoch)return;if([401,409].includes(e.status))stop(e.message,false);else if(e.status===422){target=null;const data=await request().catch(()=>null);if(data)apply(data,true);status.textContent='移动已重新同步，请再点草坪。';}
   else{target=null;status.textContent='连接暂时中断，正在重连。';if(performance.now()-lastGood>8000)stop('连接中断，已停止游玩；恢复后请重新入园。');}}
  finally{if(!disposed)timer=setTimeout(poll,token?500:3000);}
 }
 if(join)join.onclick=async()=>{join.disabled=true;const generation=++epoch;try{const data=await request('join',{pet:Number(select.value)});if(generation!==epoch){request('leave',{token:data.token}).catch(()=>{});return;}token=data.token;apply(data,true);ui();status.textContent='点草坪散步，拖动旋转；点伙伴名字走近，再打个招呼。';}catch(e){status.textContent=e.message;ui();}};
 if(leave)leave.onclick=()=>stop('已经结束游玩，伙伴会从公共乐园离开。');
 for(const button of buttons)button.onclick=()=>{if(!token)return;const next=button.dataset.action;if(next==='walk'){target={x:0,z:0};action='idle';status.textContent='一起走到草坪中央。';return;}target=null;action=next;actionUntil=performance.now()+4200;status.textContent=button.textContent+' · 同场伙伴也能看到这个动作';};
 canvas.addEventListener('pointerdown',e=>{gesture=e.isPrimary?{id:e.pointerId,x:e.clientX,y:e.clientY}:null;});
 canvas.addEventListener('pointermove',e=>{if(gesture&&Math.hypot(e.clientX-gesture.x,e.clientY-gesture.y)>6)gesture=null;});
 canvas.addEventListener('pointercancel',()=>gesture=null);
 canvas.addEventListener('pointerup',e=>{const g=gesture;gesture=null;if(!g||g.id!==e.pointerId||!token||Math.hypot(e.clientX-g.x,e.clientY-g.y)>6)return;const r=canvas.getBoundingClientRect();pointer.set((e.clientX-r.left)/r.width*2-1,1-(e.clientY-r.top)/r.height*2);ray.setFromCamera(pointer,camera);if(ray.ray.intersectPlane(plane,hit)&&PetParkScene.inside(hit.x,hit.z)){target={x:hit.x,z:hit.z};action='idle';status.textContent='正在草坪上散步。';}});
 function frame(now){raf=requestAnimationFrame(frame);if(document.hidden||now-last<1000/30)return;const dt=last?Math.min((now-last)/1000,.08):0;last=now;
  const w=canvas.clientWidth,h=canvas.clientHeight;if(w&&h&&(canvas.width!==Math.floor(w*renderer.getPixelRatio())||canvas.height!==Math.floor(h*renderer.getPixelRatio()))){renderer.setPixelRatio(Math.min(devicePixelRatio,1.25,Math.sqrt(1800000/(w*h))));renderer.setSize(w,h,false);camera.aspect=w/h;camera.updateProjectionMatrix();}
  let walking=false;if(token&&target&&actors.get(mine)?.pet){const dx=target.x-self.x,dz=target.z-self.z,d=Math.hypot(dx,dz);if(d<.15)target=null;else{const step=Math.min(d,dt*2.5);self.x+=dx/d*step;self.z+=dz/d*step;self.yaw=Math.atan2(dx,dz);walking=true;}}
  for(const [id,a] of actors){if(!a.pet)continue;const p=a.pet.root.position,remote=a.remote,isMine=!!token&&id===mine,tx=isMine?self.x:remote.x,tz=isMine?self.z:remote.z,d=Math.hypot(tx-p.x,tz-p.z),k=isMine?1:1-Math.exp(-dt*10);p.x+=(tx-p.x)*k;p.z+=(tz-p.z)*k;const yaw=isMine?self.yaw:remote.yaw;a.pet.root.rotation.y+=Math.atan2(Math.sin(yaw-a.pet.root.rotation.y),Math.cos(yaw-a.pet.root.rotation.y))*(1-Math.exp(-dt*12));
   const current=isMine?(now<actionUntil?action:'idle'):remote.action,moving=isMine?walking:d>.035;a.pet.play(moving?'walk':current==='ball'?'happy':current);a.pet.update(dt);a.ball.visible=current==='ball';if(a.ball.visible)a.ball.position.set(Math.sin(now*.004)*.6,.2+Math.abs(Math.sin(now*.006))*.35,1.1);
  }controls.update();renderer.render(scene,camera);
 }
 document.addEventListener('visibilitychange',()=>{if(document.hidden)stop('已暂停公开游玩，回来后可以重新入园。');});
 addEventListener('pagehide',()=>{disposed=true;clearTimeout(timer);cancelAnimationFrame(raf);stop(null);});
 addEventListener('pageshow',e=>{if(e.persisted){disposed=false;last=0;poll();raf=requestAnimationFrame(frame);}});
 canvas.addEventListener('webglcontextlost',e=>{e.preventDefault();stop('画面已暂停，请刷新后重新入园。');cancelAnimationFrame(raf);if(join)join.disabled=true;});
 poll();raf=requestAnimationFrame(frame);
})();
