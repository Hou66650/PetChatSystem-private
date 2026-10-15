const api=window.paitDesktop,canvas=document.getElementById('pet'),renderer=new THREE.WebGLRenderer({canvas,alpha:true,antialias:true,powerPreference:'high-performance'});
renderer.setSize(280,300,false);renderer.setPixelRatio(Math.min(devicePixelRatio,1.5));renderer.outputEncoding=THREE.sRGBEncoding;const scene=new THREE.Scene(),camera=new THREE.PerspectiveCamera(35,280/300,.01,20);camera.position.set(1.3,.8,2.5);camera.lookAt(0,.5,0);scene.add(new THREE.HemisphereLight(0xffffff,0x8b9c77,1.6));const light=new THREE.DirectionalLight(0xffebc4,1.5);light.position.set(2,4,3);scene.add(light);let pet,loading=false,last=performance.now(),connected=false;
async function state(s){
 connected=s.connected;
 if(!connected){if(pet){scene.remove(pet.root);SelectedAssets.disposeTree(pet.root);pet=null;}return;}
 if(!pet&&!loading){
  loading=true;const progress=window.PaitLoading?.start('正在准备桌宠模型');
  try{
   const d=await api.command('model');if(d.error)throw Error(d.error);
   if(!connected){progress?.cancel();return;}
   progress?.update('正在解析桌宠模型与动作');
   const gltf=await new Promise((resolve,reject)=>new THREE.GLTFLoader().parse(d.bytes,'',resolve,reject));
   if(!connected){SelectedAssets.disposeTree(gltf.scene);progress?.cancel();return;}
   pet=new PortalPets.Pet(THREE,gltf,d.pet);scene.add(pet.root);renderer.render(scene,camera);
   await api.command('ready');progress?.done();
  }catch(e){progress?.fail('桌宠模型加载失败，正在返回小岛');console.error('Pet model render failed',e.message);if(connected)await api.command('return');}
  finally{loading=false;}
 }
 pet?.play(s.action);
}
api.subscribe(state);api.command('state').then(state);function tick(now){requestAnimationFrame(tick);if(now-last<32)return;const dt=(now-last)/1000;last=now;if(!connected)return;pet?.update(dt);renderer.render(scene,camera);}requestAnimationFrame(tick);
canvas.onclick=()=>api.command('pet');canvas.oncontextmenu=e=>{e.preventDefault();api.command('menu');};
let ignored=false;const mouseRay=new THREE.Raycaster();
function ignore(value){if(value!==ignored){ignored=value;api.command('ignore',value);}}
canvas.onmousemove=e=>{if(!pet){ignore(true);return;}mouseRay.setFromCamera(new THREE.Vector2(e.offsetX/280*2-1,-e.offsetY/300*2+1),camera);ignore(!mouseRay.intersectObject(pet.root,true).length);};canvas.onmouseleave=()=>ignore(true);
