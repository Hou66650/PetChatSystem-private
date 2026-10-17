'use strict';
const api=window.paitDesktop,canvas=document.getElementById('pet'),renderer=new THREE.WebGLRenderer({canvas,alpha:true,antialias:true,powerPreference:'high-performance'});
renderer.setSize(280,300,false);renderer.setPixelRatio(Math.min(devicePixelRatio,1.5));renderer.outputEncoding=THREE.sRGBEncoding;renderer.toneMapping=THREE.ACESFilmicToneMapping;renderer.toneMappingExposure=.9;renderer.localClippingEnabled=true;
const scene=new THREE.Scene(),camera=new THREE.PerspectiveCamera(35,280/300,.01,20);camera.position.set(0,.85,3.15);camera.lookAt(0,.52,0);
scene.add(new THREE.HemisphereLight(0xffffff,0x8b9c77,1.6));const light=new THREE.DirectionalLight(0xffebc4,1.5);light.position.set(2,4,3);scene.add(light);
let pet,trip=null,phase=null,epoch=0,last=performance.now(),crossing=null,settle=0,acknowledging=false,ackAt=0,move={yaw:0,speed:0,action:'idle'};
const gate=new THREE.Group();gate.visible=false;scene.add(gate);
const gold=new THREE.MeshStandardMaterial({color:0xffcc70,emissive:0xd68a28,emissiveIntensity:.65,metalness:.6,roughness:.28,transparent:true});
const ring=new THREE.Mesh(new THREE.TorusGeometry(.48,.035,10,64),gold);ring.scale.y=1.4;ring.position.set(0,.64,-.3);gate.add(ring);
const glow=new THREE.MeshBasicMaterial({color:0xffdca0,transparent:true,opacity:.16,depthWrite:false,side:THREE.DoubleSide});
const pane=new THREE.Mesh(new THREE.CircleGeometry(.47,48),glow);pane.scale.y=1.4;pane.position.copy(ring.position);gate.add(pane);
const dust=new THREE.Group();gate.add(dust);for(let i=0;i<16;i++){const a=i*Math.PI/8,m=new THREE.Mesh(new THREE.SphereGeometry(.012,5,4),gold);m.position.set(Math.sin(a)*.54,.64+Math.cos(a)*.76,-.29);dust.add(m);}
function disposePet(){crossing?.dispose();crossing=null;gate.visible=false;settle=0;ackAt=0;acknowledging=false;if(pet){scene.remove(pet.root);SelectedAssets.disposeTree(pet.root);pet=null;}}
function parse(bytes){return new Promise((resolve,reject)=>new THREE.GLTFLoader().parse(bytes,'',resolve,reject));}
async function load(id,version){
 const progress=window.PaitLoading?.start('正在准备桌宠模型与穿搭');let candidate;
 try{
  const d=await api.command('model',{trip:id});if(d.error)throw Error(d.error);
  const gltf=await parse(d.bytes);if(version!==epoch){SelectedAssets.disposeTree(gltf.scene);progress?.cancel();return;}
  const spec={...d.pet,loadAccessory:async item=>{const a=await api.command('accessory',{trip:id,item});if(a.error)throw Error(a.error);const g=await parse(a.bytes);return g.scene;}};
  candidate=new PortalPets.Pet(THREE,gltf,spec);await candidate.wardrobeReady;
  if(version!==epoch){SelectedAssets.disposeTree(candidate.root);progress?.cancel();return;}
  if(candidate.wardrobeError)throw candidate.wardrobeError;
  if((d.pet.wardrobe||[]).length!==candidate.root.userData.accessories.length)throw Error('饰品挂点不完整，取消此次传送');
  pet=candidate;scene.add(pet.root);renderer.compile(scene,camera);pet.root.visible=false;renderer.render(scene,camera);
  const ready=await api.command('ready',{trip:id});if(ready.error)throw Error(ready.error);
  const latest=await api.command('state');if(version===epoch)state(latest);progress?.done();
 }catch(e){if(candidate&&candidate!==pet)SelectedAssets.disposeTree(candidate.root);if(version===epoch){progress?.fail('模型或饰品未准备好，正在返回小岛');await api.command('return',{trip:id});}else progress?.cancel();console.error('Desktop preparation failed:',e.message);}
}
function state(s){
 if(!s.connected){epoch++;trip=null;phase=null;disposePet();return;}
 if(s.trip!==trip){epoch++;disposePet();trip=s.trip;phase=s.phase;move={yaw:0,speed:0,action:'idle'};void load(trip,epoch);}
 if(['preparing','entering','emerging','roaming'].indexOf(s.phase)>=['preparing','entering','emerging','roaming'].indexOf(phase))phase=s.phase;
 if(phase==='emerging'&&pet&&!crossing){
  gate.visible=true;gold.opacity=1;glow.opacity=.16;pet.play('walk',Math.min(3,1.72/(2.2*.348*pet.model.scale.x)));
  crossing=new PortalTransition.Crossing(THREE,pet.root,{from:new THREE.Vector3(0,0,-1.6),to:new THREE.Vector3(0,0,.12),gateZ:-.3,duration:2.2,onComplete:()=>{pet.play('idle');settle=.5;}});
 }
 if(phase==='roaming'&&pet){crossing?.dispose();crossing=null;gate.visible=false;pet.root.position.y=0;pet.root.visible=true;}
}
async function arrived(){
 if(acknowledging||performance.now()<ackAt||phase!=='emerging')return;const id=trip,version=epoch;acknowledging=true;
 try{const r=await api.command('arrived',{trip:id});if(r.error)throw Error(r.error);}
 catch(_){if(version===epoch)ackAt=performance.now()+1000;}
 finally{if(version===epoch)acknowledging=false;}
}
api.subscribe(state);api.command('state').then(state);
api.subscribeMotion(m=>{if(m.trip===trip)move=m;});
function tick(now){
 requestAnimationFrame(tick);if(now-last<30)return;const dt=Math.min(.05,(now-last)/1000);last=now;
 if(pet){
  if(phase==='emerging'){
   crossing?.update(dt);dust.rotation.y=Math.sin(now*.001)*.08;
   if(crossing?.done){settle=Math.max(0,settle-dt);pet.root.position.y=-Math.sin((.5-settle)*Math.PI*2)*.015*(settle/.5);gold.opacity=settle/.5;glow.opacity=.16*settle/.5;if(!settle){gate.visible=false;void arrived();}}
  }else if(phase==='roaming'){
   pet.root.rotation.y=move.yaw;
   // Authored walking gait travels about .348 model units per second at 1x.
   // Project that distance through the actual camera to match window DIP motion.
   const base=new THREE.Vector3(0,0,.12).project(camera),stride=new THREE.Vector3(.348*pet.model.scale.x,0,.12).project(camera);
   const stridePixels=Math.max(8,Math.abs(stride.x-base.x)*140);
   const turning=move.action==='idle'&&Math.abs(move.turnRate||0)>.2;
   pet.play(turning?(move.turnRate>0?'turnRight':'turnLeft'):move.action,move.action==='walk'?Math.max(.12,Math.min(3,move.speed/stridePixels)):1);
  }
  pet.update(dt);
 }
 renderer.render(scene,camera);
}
requestAnimationFrame(tick);
canvas.onclick=()=>{if(phase==='roaming')api.command('pet');};canvas.oncontextmenu=e=>{e.preventDefault();api.command('menu');};
let ignored=false;const mouseRay=new THREE.Raycaster();
function ignore(value){if(value!==ignored){ignored=value;api.command('ignore',value);}}
canvas.onmousemove=e=>{if(!pet){ignore(true);return;}mouseRay.setFromCamera(new THREE.Vector2(e.offsetX/280*2-1,-e.offsetY/300*2+1),camera);ignore(!mouseRay.intersectObject(pet.root,true).length);};canvas.onmouseleave=()=>ignore(true);
