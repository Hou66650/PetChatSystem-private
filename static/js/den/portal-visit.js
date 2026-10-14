(()=>{'use strict';const $=id=>document.getElementById(id),config=window.VISIT;let state,scene,camera,renderer,controls,pets=[],moves=[],ready=false,busy=false,events=[],lastSample=0,elapsed=0,ended=false;
 const addEvent=kind=>{if(!pets.length)return;const p=pets[0].root.position;events.push({id:crypto.randomUUID(),kind,x:p.x,z:p.z});events=events.slice(-12);};
 async function api(op,body){const r=await fetch('/api/portals/'+op,{method:'POST',headers:{'Content-Type':'application/json','X-Profile-Scope':config.scope},body:JSON.stringify({trip:config.trip,...body})});const d=await r.json();if(!r.ok)throw Error(d.error||'连接失败');return d;}
 async function load(){
  const r=await fetch('/api/portals/trip/'+config.trip,{cache:'no-store'});state=await r.json();if(!r.ok)throw Error(state.error);if(state.status!=='active'){ended=true;$('visit-status').textContent=state.reason||'行程已结束';return;}
  renderer=new THREE.WebGLRenderer({canvas:$('visit-world'),antialias:true,powerPreference:'high-performance'});renderer.setPixelRatio(Math.min(devicePixelRatio,1.5));renderer.outputEncoding=THREE.sRGBEncoding;renderer.toneMapping=THREE.ACESFilmicToneMapping;
  scene=new THREE.Scene();scene.background=new THREE.Color(0xb8cfd1);scene.fog=new THREE.Fog(0xb8cfd1,25,65);scene.add(new THREE.HemisphereLight(0xe9f6ff,0x69805b,1.3));const sun=new THREE.DirectionalLight(0xffe4be,1.2);sun.position.set(6,12,8);scene.add(sun);
  camera=new THREE.PerspectiveCamera(40,innerWidth/innerHeight,.1,100);camera.position.set(10,9,15);controls=new THREE.OrbitControls(camera,renderer.domElement);controls.target.set(0,.5,0);controls.enableDamping=true;controls.maxDistance=35;controls.minDistance=4;controls.maxPolarAngle=Math.PI*.48;
  const loader=new SelectedAssets.Loader(new THREE.GLTFLoader()),ticket=loader.begin(),stage=await loader.glb(state.hostPet.stage,ticket);scene.add(stage.scene);if(state.hostPet.theme==='room')new PetPortals.Gates(THREE,scene,{desktop:{x:2.3,z:-.75,mountX:1.4,mountZ:-1.65},neighbor:{x:4.6,z:-.75,mountZ:-1.65}});
  let layout={room:MistwoodLayout,camp:AlpineLayout,snow:SnowHavenLayout,sakura:{...SakuraRiverLayout,radius:3.2,obstacles:[{x:-2.1,z:-1.5,r:.55},{x:2.25,z:-1.2,r:.38},{kind:'rect',x:0,z:-2.65,w:3.7,d:.26}]}}[state.hostPet.theme];
  // Only the selected destination and these two pets are requested.
  for(const spec of [state.petSpec,state.hostPet]){const gltf=await loader.glb(spec.model,ticket),pet=new PortalPets.Pet(THREE,gltf,spec);scene.add(pet.root);pets.push(pet);const box=new THREE.Box3().setFromObject(pet.root),radius=Math.hypot(box.max.x-box.min.x,box.max.z-box.min.z)/2+.015;
   pet.radius=radius;const nav=new PetNavigation.Navigation({...layout,bodyRadius:radius}),move=new PetLocomotion.Controller({navigation:nav,model:pet.root,animate:k=>pet.play(k),rest:()=>pet.play('idle')});move.autonomous=false;pet.root.position.copy(new THREE.Vector3(...[0,0,0]));const start=nav.nearest({x:pets.length===1?-1:1,z:0});pet.root.position.set(start.x,nav.surfaceHeight(start),start.z);moves.push(move);
  }
  if(ended)return;ready=true;resize();requestAnimationFrame(tick);$('visit-status').textContent=state.mine?'它们各自探索，靠近时会打招呼。':'正在旁观好友的宠物来访。';
 }
 function resize(){if(!renderer)return;renderer.setSize(innerWidth,innerHeight,false);camera.aspect=innerWidth/innerHeight;camera.updateProjectionMatrix();}addEventListener('resize',resize);
 const minds=[{next:.1,rest:0},{next:.2,rest:0}];let previous=performance.now();
 function tick(now){if(ended)return;requestAnimationFrame(tick);const dt=Math.min(.05,(now-previous)/1000);previous=now;elapsed+=dt;
  if(state.mine){
   for(let i=0;i<2;i++){
    const pet=pets[i],move=moves[i],mind=minds[i],other=pets[1-i];
    if(elapsed>=mind.next&&!move.path.length){
     const near=pet.root.position.distanceTo(other.root.position)<1.7,choice=mind.choice;mind.choice=null;
     if(choice==='rest'){pet.play('sleep');mind.rest=elapsed+6;mind.next=elapsed+9;if(i===0)addEvent('rest');continue;}
     if(near&&(choice==='sniff'||(!choice&&Math.random()<.55))){pet.play('sniff');mind.rest=elapsed+3;mind.next=elapsed+6;if(i===0)addEvent('sniff');}
     else{const route=move.navigation.randomDestination(pet.root.position,Math.random),target=route?.[route.length-1];const chase=choice==='chase'||Math.random()<.3;const follow=move.navigation.nearest({x:other.root.position.x+1.3,z:other.root.position.z});if(target&&move.goTo(chase&&follow?follow:target,{gait:chase?'trot':'walk'})&&i===0)addEvent(chase?'chase':'walk');mind.rest=0;mind.next=elapsed+5+Math.random()*5;}
    }
    // Independent navigators yield before overlapping bodies; neither can cross water.
    const dist=pet.root.position.distanceTo(other.root.position),next=move.path[0],towards=next&&(next.x-pet.root.position.x)*(other.root.position.x-pet.root.position.x)+(next.z-pet.root.position.z)*(other.root.position.z-pet.root.position.z)>0,yielding=towards&&dist<pet.radius+other.radius+.12;
    move.update(dt,elapsed<mind.rest||yielding);pet.root.position.y=move.navigation.surfaceHeight(pet.root.position);
   }
   if(now-lastSample>2000){lastSample=now;addEvent('position');void send();}
  }else if(state.snapshot){for(let i=0;i<2;i++){const s=state.snapshot[i?'host':'visitor'];if(s){pets[i].root.position.lerp(new THREE.Vector3(s.x,moves[i].navigation.surfaceHeight(s),s.z),1-Math.exp(-dt*6));pets[i].root.rotation.y=s.yaw;pets[i].play(s.action);}}}
  for(const p of pets)p.update(dt);controls.update();renderer.render(scene,camera);
 }
 async function send(){if(busy||ended)return;busy=true;const batch=events.splice(0,12);try{await api('sample',{snapshot:{visitor:pets[0].snapshot(),host:pets[1].snapshot()},events:batch});}catch(e){$('visit-status').textContent=e.message;}finally{busy=false;}}
 async function poll(){try{const r=await fetch('/api/portals/trip/'+config.trip,{cache:'no-store'});const d=await r.json();if(!r.ok)throw Error(d.error);state=d;if(state.status!=='active'){ended=true;$('visit-status').textContent=state.reason+' · 已回到本岛';$('visit-return').textContent='打开自己的小岛';}
   $('visit-messages').replaceChildren(...state.messages.map(m=>{const p=document.createElement('p');p.textContent=(m.mine?'你：':'对方：')+m.text;return p;}));
  }catch(e){$('visit-status').textContent=e.message;}}
 $('visit-return').onclick=async()=>{if(ended){location.href='/den?pet='+encodeURIComponent(state.mine?state.pet:'3');return;}try{await api('return',{});await poll();}catch(e){$('visit-status').textContent=e.message;}};
 $('visit-message').onsubmit=async e=>{e.preventDefault();try{await api('message',{text:$('visit-text').value});$('visit-text').value='';await poll();}catch(err){$('visit-status').textContent=err.message;}};
 async function think(){if(!ready||ended||!state.mine)return;try{const d=await api('plan',{});if(ended)return;minds[0].choice=d.visitor;minds[1].choice=d.host;$('visit-status').textContent=(d.source==='model'?'AI 决策':'本地探索')+' · 两只宠物各自选择下一步。';}catch(e){}}
 load().then(()=>think()).catch(e=>$('visit-status').textContent='无法进入：'+e.message);setInterval(poll,2500);setInterval(think,32000);
})();
