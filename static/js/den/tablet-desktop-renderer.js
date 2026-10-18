/* No camera, audio, storage, AI calls or unrestricted native proxy in this window. */
(()=>{'use strict';
 const status=document.querySelector('#status'),canvas=document.querySelector('#pet'),select=document.querySelector('#action');
 let hostSeen=false,hostVisible=false,close=false,started=false,pet=null,animator=null,scene=null,renderer=null,camera=null,frame=0,last=0,serial=0,paused=false,autonomous=false,nextChoice=0,walk=0,dx=0,dy=0,epoch=0,emergingAt=0,arriving=false,lastHost=0;
 const operations=new Set();
 async function fetchBounded(path,options={},limit=262144){
  const controller=new AbortController();operations.add(controller);const timeout=setTimeout(()=>controller.abort(),15000);
  try{const r=await fetch(path,{...options,redirect:'error',cache:'no-store',signal:controller.signal});if(Number(r.headers.get('content-length'))>limit)throw Error('响应超过预算');
   const chunks=[],reader=r.body.getReader();let length=0;try{for(;;){const {done,value}=await reader.read();if(done)break;length+=value.length;if(length>limit)throw Error('响应超过预算');chunks.push(value);}}finally{await reader.cancel().catch(()=>{});reader.releaseLock();}
   const bytes=new Uint8Array(length);let at=0;for(const c of chunks){bytes.set(c,at);at+=c.length;}return{ok:r.ok,status:r.status,bytes};
  }finally{clearTimeout(timeout);operations.delete(controller);}
 }
 async function request(op,body,token){const r=await fetchBounded('/api/portals/desktop/'+op,{method:body?'POST':'GET',headers:{'Content-Type':'application/json',...(token?{Authorization:'Bearer '+token}:{})},...(body?{body:JSON.stringify(body)}:{})});const d=JSON.parse(new TextDecoder().decode(r.bytes));if(!r.ok){const e=Error(d.error||'连接失败');e.ended=d.code==='TRIP_ENDED';throw e;}return d;}
 async function asset(path,hash,token,limit){
  if(!/^[a-f0-9]{64}$/.test(hash||'')||(!/^\/static\/models\/[\w/-]+\.glb$/.test(path)&&path!=='/api/portals/desktop/model'))throw Error('模型路径或校验值无效');
  if(!crypto.subtle)throw Error('当前连接无法校验模型，请使用 HTTPS 或 USB 本机连接');
  const r=await fetchBounded(path,{headers:path.startsWith('/api/')?{Authorization:'Bearer '+token}:{}},limit);if(!r.ok)throw Error('模型下载失败');
  const view=new DataView(r.bytes.buffer);if(r.bytes.length<20||view.getUint32(0,true)!==0x46546c67||view.getUint32(4,true)!==2||view.getUint32(8,true)!==r.bytes.length)throw Error('模型文件不完整');
  const digest=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',r.bytes))).map(b=>b.toString(16).padStart(2,'0')).join('');if(digest!==hash)throw Error('模型校验失败');
  return new Promise((resolve,reject)=>new THREE.GLTFLoader().parse(r.bytes.buffer,'',resolve,reject));
 }
 function dispose(){++epoch;cancelAnimationFrame(frame);frame=0;for(const c of operations)c.abort();animator?.dispose();animator=null;if(pet){SelectedAssets.disposeTree(pet.root);pet=null;}renderer?.dispose();renderer=null;scene=null;walk=0;dx=dy=0;for(const e of document.querySelectorAll('footer button,select'))e.disabled=true;}
 const session=new TabletDesktopSession.Session({request,dispose,show:async()=>{if(!hostSeen||!hostVisible||!renderer)throw Error('桌宠窗口尚未显示');renderer.render(scene,camera);},changed(phase,message){status.textContent=message||({preparing:'准备宠物和穿搭…',entering:'等待宠物走进传送门',emerging:'宠物正在走出传送门',roaming:'正在陪伴你'})[phase]||phase;if(phase==='closed'){close=true;return;}if(phase==='emerging'&&!emergingAt){emergingAt=performance.now();}if(phase==='roaming'){for(const e of document.querySelectorAll('footer button,select'))e.disabled=false;}},
  async load(spec,manifest,token,current){
   const generation=epoch;const gltf=await asset(spec.model,manifest.modelSha256,token,50*1024*1024);if(!current()){SelectedAssets.disposeTree(gltf.scene);return;}
   let candidate=new PortalPets.Pet(THREE,gltf,{...spec,strictActions:true,loadAccessory:async item=>{const g=await asset('/static/models/wardrobe-v1/'+item+'.glb',manifest.accessories[item],token,4*1024*1024);return g.scene;}});
   await candidate.wardrobeReady;if(!current()||generation!==epoch){SelectedAssets.disposeTree(candidate.root);return;}if(candidate.wardrobeError){SelectedAssets.disposeTree(candidate.root);throw candidate.wardrobeError;}
   pet=candidate;scene=new THREE.Scene();camera=new THREE.PerspectiveCamera(35,1,.01,30);camera.position.set(0,spec.height*.9,spec.height*3.4);camera.lookAt(0,spec.height*.5,0);
   renderer=new THREE.WebGLRenderer({canvas,alpha:true,antialias:true});renderer.setPixelRatio(Math.min(devicePixelRatio,1.5));renderer.outputEncoding=THREE.sRGBEncoding;renderer.toneMapping=THREE.ACESFilmicToneMapping;renderer.toneMappingExposure=.9;
   scene.add(new THREE.HemisphereLight(0xffffff,0x8b9c77,1.6));const light=new THREE.DirectionalLight(0xffebc4,1.5);light.position.set(2,4,3);scene.add(light,pet.root);pet.root.visible=false;
   animator=new DesktopAnimator.Animator(THREE,pet);select.replaceChildren();for(const a of DesktopActions.supported(pet.clips)){const o=document.createElement('option');o.value=a.id;o.textContent=a.label;select.append(o);}if(!animator.ids.has('idle'))throw Error('模型缺少基础待机动作');
   last=performance.now();frame=requestAnimationFrame(tick);
  }
 });
 function perform(id){if(session.phase!=='roaming'||paused||!animator?.ids.has(id))return;walk=id==='walk'?160:0;animator.request(id,++serial);nextChoice=performance.now()+8000;}
 function tick(now){frame=requestAnimationFrame(tick);if(!renderer||!hostVisible||paused)return;const dt=Math.min(.05,(now-last)/1000);last=now;
  const width=canvas.clientWidth,height=canvas.clientHeight;if(canvas.width!==Math.round(width*renderer.getPixelRatio())||canvas.height!==Math.round(height*renderer.getPixelRatio())){renderer.setSize(width,height,false);camera.aspect=width/Math.max(1,height);camera.updateProjectionMatrix();}
  if(session.phase==='emerging'){
   pet.root.visible=true;const t=Math.min(1,(now-emergingAt)/1800);pet.root.scale.setScalar(Math.max(.01,t*t*(3-2*t)));pet.update(dt);
   if(t===1&&!arriving){arriving=true;session.arrived().catch(()=>{}).finally(()=>{arriving=false;});}
  }else if(session.phase==='roaming'){
   pet.root.visible=true;pet.root.scale.setScalar(1);
   if(autonomous&&now>=nextChoice&&!walk)perform(DesktopActions.choose([...animator.ids]));
   animator.update(dt,walk?1:0);
   if(walk&&animator.locomotionReady){const step=Math.min(walk,dt*45);walk-=step;dx+=step*devicePixelRatio;pet.root.rotation.y=Math.PI/2;if(!walk){animator.request('idle',++serial);pet.root.rotation.y=0;}}
  }
  renderer.render(scene,camera);
 }
 window.PaitTabletRenderer={exchange(input){lastHost=Date.now();hostSeen=true;hostVisible=input.visible===true;
  if(input.closing||!hostVisible){void session.close(input.closing?'正在召回宠物':'窗口已收起，宠物返回小窝');close=true;}
  else if(!started&&/^[\w-]{20,80}$/.test(input.code||'')){started=true;session.start(input.code).catch(e=>{status.textContent=e.message;});}
  const result=JSON.stringify({close,dx,dy});dx=dy=0;return result;
 }};
 const timer=setInterval(()=>{if(hostSeen&&Date.now()-lastHost>5000){void session.close('桌宠窗口连接中断');close=true;}else if(hostVisible)void session.poll();},1500);
 window.__paitTabletDebug=()=>({phase:session.phase,action:pet?.action,clip:pet?.active?.getClip().name,time:pet?.active?.time,visible:!!pet?.root.visible,accessories:pet?.root.userData.accessories?.length||0,actions:animator?.ids.size||0,paused,closed:session.closed});
 function touchButton(id,activate){const button=document.querySelector(id);let down=null,lastTouch=-Infinity;
  button.onpointerdown=e=>{if(e.pointerType==='touch')down={id:e.pointerId,x:e.clientX,y:e.clientY,moved:false};};
  button.onpointermove=e=>{if(down&&Math.hypot(e.clientX-down.x,e.clientY-down.y)>10)down.moved=true;};
  button.onpointercancel=()=>{down=null;};
  button.onpointerup=e=>{const start=down;down=null;if(!start||start.id!==e.pointerId||start.moved||button.disabled)return;const r=button.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)return;lastTouch=performance.now();activate(button);};
  button.onclick=e=>{if(e.detail===0||performance.now()-lastTouch>750)activate(button);};
 }
 touchButton('#return',()=>{close=true;void session.close();});touchButton('#perform',()=>perform(select.value));
 touchButton('#pause',button=>{paused=!paused;button.textContent=paused?'继续':'暂停';last=performance.now();if(paused){cancelAnimationFrame(frame);frame=0;}else if(renderer&&!frame){frame=requestAnimationFrame(tick);}});
 touchButton('#auto',button=>{autonomous=!autonomous;button.textContent='自主：'+(autonomous?'开':'关');nextChoice=performance.now()+1000;});
 let pointer=null;
 canvas.onpointerdown=e=>{if(session.phase!=='roaming')return;canvas.setPointerCapture(e.pointerId);pointer={id:e.pointerId,x:e.clientX,y:e.clientY,at:performance.now(),distance:0};walk=0;animator.request('idle',++serial);};
 canvas.onpointermove=e=>{if(pointer?.id!==e.pointerId)return;const x=e.clientX-pointer.x,y=e.clientY-pointer.y;pointer.distance+=Math.hypot(x,y);dx+=x*devicePixelRatio;dy+=y*devicePixelRatio;pointer.x=e.clientX;pointer.y=e.clientY;};
 canvas.onpointerup=e=>{if(pointer?.id!==e.pointerId)return;if(pointer.distance<8){if(performance.now()-pointer.at>550){try{select.showPicker();}catch(_){select.focus();}}else perform('petting');}pointer=null;};canvas.onpointercancel=()=>{pointer=null;};
 canvas.addEventListener('webglcontextlost',e=>{e.preventDefault();void session.close('绘制已中断，宠物返回小窝');});
 document.addEventListener('visibilitychange',()=>{if(document.hidden&&started)void session.close('窗口不可见，宠物返回小窝');});
 window.addEventListener('pagehide',()=>{clearInterval(timer);void session.close();});
})();
