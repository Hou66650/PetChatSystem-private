const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const THREE=require('../static/js/vendor/three.min.js'),{Controller,ViewAttention}=require('../static/js/den/head-look');
vm.runInNewContext(fs.readFileSync('static/js/vendor/GLTFLoader.js','utf8'),{THREE,console,TextDecoder,URL,Blob,self:{URL},setTimeout,clearTimeout});
THREE.TextureLoader.prototype.load=function(url,onLoad){const t=new THREE.Texture();queueMicrotask(()=>onLoad(t));return t;};
const parse=p=>new Promise((resolve,reject)=>{const b=fs.readFileSync(p);new THREE.GLTFLoader().parse(b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength),'',resolve,reject);});
(async()=>{
 const attention=new ViewAttention(), interactive={x:20,y:30};
 assert.equal(attention.point(0,null),null,'resting pets look toward camera');
 attention.moved(100);
 assert.equal(attention.point(200,interactive),null,'orbit wins over face/pointer attention');
 attention.moved(1100);
 assert.equal(attention.point(1500,interactive),null,'damping extends camera attention');
 assert.equal(attention.point(2400,interactive),interactive,'explicit interaction resumes');
 for(const [breed,path] of [['cat','petchat-cat-v2/cat'],['shiba','petchat-shiba-v4/qiuqiu'],['husky','petchat-husky-v3/xueqiu'],['shepherd','petchat-shepherd-v2/shepherd']]){
  const gltf=await parse('static/models/'+path+'.glb'),model=new THREE.Group();model.add(gltf.scene);model.userData.height=1;
  const look=new Controller(THREE,model),base=look.head.quaternion.clone();assert(look.head&&look.neck,breed);
  const meshes=[];model.traverse(o=>{if(o.isSkinnedMesh)meshes.push(o);});
  const mesh=meshes.find(m=>m.morphTargetDictionary?.Blink_L!==undefined),index=mesh.skeleton.bones.indexOf(look.head);
  let vertex=-1;const joints=mesh.geometry.attributes.skinIndex,weights=mesh.geometry.attributes.skinWeight;
  for(let i=0;i<joints.count&&vertex<0;i++)for(let j=0;j<4;j++)if(joints.array[i*4+j]===index&&weights.array[i*4+j]>.8)vertex=i;
  assert(vertex>=0,'actual head is skinned '+breed);
  const sample=()=>{model.updateMatrixWorld(true);mesh.skeleton.update();const p=new THREE.Vector3().fromBufferAttribute(mesh.geometry.attributes.position,vertex);mesh.boneTransform(vertex,p);return p.applyMatrix4(mesh.matrixWorld);};
  const initial=sample();model.updateMatrixWorld(true);const origin=look.head.getWorldPosition(new THREE.Vector3()),target=origin.clone().add(new THREE.Vector3(3,1,2));
  for(let i=0;i<120;i++)look.update(1/60,target);
  assert(look.yaw>.7&&look.yaw<.97);assert(look.pitch>.15);assert(sample().distanceTo(initial)>.025,'head surface visibly follows '+breed);
  const rightPose=sample();
  for(let i=0;i<120;i++)look.update(1/60,origin.clone().add(new THREE.Vector3(-3,-1,2)));
  assert(look.yaw<-.7&&look.pitch<-.15,'camera orbit tracks left and down '+breed);
  assert(sample().distanceTo(rightPose)>.025,'actual skin follows both view directions '+breed);
  for(let i=0;i<120;i++)look.update(1/60,target);
  const fixed=look.head.quaternion.clone();for(let i=0;i<600;i++)look.update(1/60,target);
  assert(fixed.angleTo(look.head.quaternion)<.001,'no cumulative twist');
  look.beforeFrame();assert(base.toArray().every((v,i)=>Math.abs(v-look.head.quaternion.toArray()[i])<1e-7),'restore animation baseline');
  for(let i=0;i<120;i++)look.update(1/60,target,{state:'sleep'});
  assert(Math.abs(look.yaw)<.001&&Math.abs(look.pitch)<.001,'sleep yields to authored pose');look.beforeFrame();
  const mixer=new THREE.AnimationMixer(gltf.scene);mixer.clipAction(gltf.animations.find(a=>a.name==='run')).play();
  for(let i=0;i<120;i++){look.beforeFrame();mixer.update(1/60);look.update(1/60,target,{state:'run'});}
  assert(Math.abs(look.yaw)<.22,'running keeps head near travel direction');assert(sample().toArray().every(Number.isFinite));look.beforeFrame();
  const camera=new THREE.PerspectiveCamera(42,1,0.1,100);camera.position.copy(origin).add(new THREE.Vector3(0,0,3));camera.lookAt(origin);camera.updateMatrixWorld(true);
  const left=look.screenTarget({x:100,y:300},camera,600,600).clone(),right=look.screenTarget({x:500,y:300},camera,600,600).clone();assert(left.x<right.x,'screen attention projects across camera plane');
 }
 const page=fs.readFileSync('templates/den.html','utf8');
 const tick=page.slice(page.indexOf('function tick()'));
 assert(tick.indexOf('controls.update();')<tick.indexOf('headLook.update(poseDt'),'camera damping runs before head tracking');
 assert(!page.includes('pointerAttention'),'passive hovering must not steal view tracking');
 assert(page.indexOf('headLook?.beforeFrame();',page.indexOf('function tick()'))<page.indexOf('mixer.update(actionTransition'));
 assert(page.indexOf('headLook.update(poseDt')>page.indexOf('mixer.update(actionTransition'));
 console.log('PASS four actual rigs: visible head skin motion, directional limits, no drift, restoration, sleep/run priorities, pointer projection and frame ordering');
})().catch(e=>{console.error(e);process.exitCode=1;});
