const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const T=require('../static/js/vendor/three.min.js'),{Navigation}=require('../static/js/den/scene-navigation'),{Controller}=require('../static/js/den/pet-grounding');
const layout=require('../static/js/den/mistwood-layout');
vm.runInNewContext(fs.readFileSync('static/js/vendor/GLTFLoader.js','utf8'),{THREE:T,console,TextDecoder,URL,Blob,self:{URL},setTimeout,clearTimeout});
const ctx={};vm.runInNewContext(fs.readFileSync('static/js/den/pet-model-bounds.js','utf8'),ctx);
T.TextureLoader.prototype.load=function(url,cb){const t=new T.Texture();queueMicrotask(()=>cb(t));return t;};
const parse=path=>new Promise((r,j)=>{const b=fs.readFileSync(path);new T.GLTFLoader().parse(b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength),'',r,j);});
(async()=>{
 const stage=await parse('static/models/petchat-mistwood-v1/mistwood.glb'),home=await parse('static/models/petchat-cat-home-v1/cat-home.glb');
 stage.scene.updateMatrixWorld(true);home.scene.updateMatrixWorld(true);const nav=new Navigation({...layout,bodyRadius:.3});
 const ray=new T.Raycaster(),down=new T.Vector3(0,-1,0);
 for(const [x,z] of [[-3,4.62],[-3.5,4.62],[-3,4.2],[-2.7,4.9],[-3,5.65]]){
  ray.set(new T.Vector3(x,.4,z),down);const hits=ray.intersectObject(home.scene,true);assert(hits.length);
  assert(Math.abs(nav.surfaceHeight({x,z})-hits[0].point.y)<.008,'home support matches actual GLB cushion/threshold');
 }
 assert.equal(new Navigation({...layout,surfaces:layout.surfaces.filter(s=>s.tag!=='catHome')}).surfaceHeight({x:-3,z:4.62}),.035,'unloaded home has no invisible cushion');
 const gltf=await parse(process.env.PET_GROUNDING_TEST_GLB||'static/models/petchat-cat-v3/cat.glb'),model=gltf.scene,root=new T.Group();
 const growthScale=Number(process.env.PET_GROUNDING_TEST_SCALE||1);
 assert(growthScale>=.72&&growthScale<=1);
 const box=ctx.PetModelBounds.measure(T,model),h=box.max.y-box.min.y,scale=.85*growthScale/h;model.scale.setScalar(scale);
 model.position.set(-(box.min.x+box.max.x)*scale/2,-box.min.y*scale,-(box.min.z+box.max.z)*scale/2);root.add(model);root.userData.height=.85*growthScale;
 const ground=new Controller(T,root,model,nav);assert(ground.samples.length>20);assert(ground.samples.length<=160);
 const dense=[];
 model.traverse(mesh=>{if(!mesh.isSkinnedMesh)return;const a=mesh.geometry.attributes;
  for(let i=0;i<a.position.count;i++){let weight=0;for(let j=0;j<4;j++)if(/^(FL|FR|HL|HR)_(foot|lower)$/.test(mesh.skeleton.bones[a.skinIndex.array[i*4+j]]?.name))weight+=a.skinWeight.array[i*4+j];if(weight>.5)dense.push({mesh,index:i});}
 });
 const original=model.position.clone(),mixer=new T.AnimationMixer(model);
 let oldPenetration=0,maxLift=0,minGap=Infinity;
 for(const name of ['idle_breathe','walk','run','sit_down','sleep_loop']){
  ground.beforeFrame();mixer.stopAllAction();const clip=gltf.animations.find(c=>c.name===name);assert(clip,name);mixer.clipAction(clip).play();
  for(const yaw of [0,Math.PI/2,Math.PI,Math.PI*1.5])for(let step=0;step<=60;step++){
   ground.beforeFrame();mixer.update(1/60);
   const x=name==='sleep_loop'?-3:0,z=name==='sleep_loop'?4.62:-.15+step*.065;root.position.set(x,nav.surfaceHeight({x,z}),z);root.rotation.y=yaw;
   root.updateMatrixWorld(true);for(const mesh of ground.skins)mesh.skeleton.update();
   for(const s of ground.samples){ground.vertex(s.mesh,s.index,ground.point);oldPenetration=Math.max(oldPenetration,nav.surfaceHeight(ground.point)-ground.point.y);}
   ground.update(1/60,{state:name==='walk'?'walk':name==='run'?'run':name==='sit_down'?'sit':name==='sleep_loop'?'sleep':'idle'});
   for(const mesh of ground.skins)mesh.skeleton.update();
   for(const s of ground.samples){ground.vertex(s.mesh,s.index,ground.point);const gap=ground.point.y-nav.surfaceHeight(ground.point);minGap=Math.min(minGap,gap);assert(gap>-.002,`${name} paw penetrates at z=${z}, yaw=${yaw}: ${gap}`);}
   if(step%15===0)for(const s of dense){ground.vertex(s.mesh,s.index,ground.point);const gap=ground.point.y-nav.surfaceHeight(ground.point);assert(gap>-.008,`${name} dense paw geometry penetrates: ${gap}`);}
   maxLift=Math.max(maxLift,ground.lift);assert(model.position.toArray().every(Number.isFinite));
  }
 }
 ground.beforeFrame();assert(model.position.distanceTo(original)<1e-8,'grounding is additive, not cumulative');
 ground.update(.05,{airborne:true});assert.equal(ground.lift,0);assert(model.position.distanceTo(original)<1e-8,'jump/grab preserves authored animation height');
 assert(oldPenetration>.025,'reproduce original bridge paw penetration');
 console.log(JSON.stringify({samples:ground.samples.length,oldPenetration,minGap,maxLift,verified:'real GLB home surfaces; animated cat across bridge in four orientations; sleep on cushion; no cumulative transform or airborne correction'}));
})().catch(e=>{console.error(e);process.exitCode=1;});
