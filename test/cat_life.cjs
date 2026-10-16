const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const THREE=require('../static/js/vendor/three.min.js'),{Controller}=require('../static/js/den/cat-life');
const {Navigation}=require('../static/js/den/scene-navigation'),{Controller:Move}=require('../static/js/den/pet-locomotion'),{Controller:Look}=require('../static/js/den/head-look');
const layout=require('../static/js/den/mistwood-layout');
vm.runInNewContext(fs.readFileSync('static/js/vendor/GLTFLoader.js','utf8'),{THREE,console,TextDecoder,URL,Blob,self:{URL},setTimeout,clearTimeout});
THREE.TextureLoader.prototype.load=function(url,cb){const t=new THREE.Texture();queueMicrotask(()=>cb(t));return t;};
(async()=>{
 const custom=process.env.PET_LIFE_TEST_GLB;
 const bytes=fs.readFileSync(custom||'static/models/petchat-cat-v3/cat.glb');
 const gltf=await new Promise((r,j)=>new THREE.GLTFLoader().parse(bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength),'',r,j));
 const model=new THREE.Group();model.add(gltf.scene);
 if(custom){const ctx={};vm.runInNewContext(fs.readFileSync('static/js/den/pet-model-bounds.js','utf8'),ctx);const box=ctx.PetModelBounds.measure(THREE,gltf.scene),scale=.85/(box.max.y-box.min.y);gltf.scene.scale.setScalar(scale);gltf.scene.position.set(-(box.min.x+box.max.x)*scale/2,-box.min.y*scale,-(box.min.z+box.max.z)*scale/2);model.userData.height=.85;}
 const nav=new Navigation({...layout,bodyRadius:.619}),move=new Move({navigation:nav,model,animate(){},rest(){}});
 const cat=new Controller(THREE,model,move,{walls:[{x:.8,z:-3.4,nx:-1,nz:0}],random:()=>.1});
 for(const name of ['head','neck','spine','tail_tip','FL_lower',...(!custom?['spine_front','ear_L']:[])])assert(cat.byName[name],name);
 const frame=(blocked=false)=>{cat.beforeFrame();const owned=cat.step(1/60,blocked);move.update(1/60,blocked||owned);model.position.y=nav.surfaceHeight(model.position);cat.pose(1/60,'idle');assert(nav.isWalkable(model.position));};
 model.position.set(-2,0,-3);assert(cat.begin('jump'));let max=0;for(let i=0;i<105;i++){frame();max=Math.max(max,model.position.y-nav.surfaceHeight(model.position));}
 assert(max>.30);assert.equal(cat.active,null);assert(Math.abs(model.position.z+2.45)<.001);
 model.position.set(0,0,1.8);assert.equal(cat.begin('jump'),false,'no jumping on bridge');model.position.set(0,0,0);
 assert(cat.seekWall());for(let i=0;i<2100&&cat.approach;i++)frame();assert.equal(cat.active?.kind,'rub','navigate and align to actual conservatory wall');
 cat.cancel();assert.equal(cat.active,null);assert.equal(cat.approach,null);
 model.position.set(0,0,0);
 for(const kind of ['groom','stretch','rub','mouthClean']){assert(cat.begin(kind));for(let i=0;i<90;i++)frame();model.traverse(o=>{if(o.isBone)assert(o.quaternion.toArray().every(Number.isFinite));});frame(true);assert.equal(cat.active,null);}
 cat.begin('groom');assert(move.goTo({x:-1,z:-1}));const command=move.path;cat.step(1/60,false);assert.equal(cat.active,null);assert.equal(move.path,command,'external command keeps its route');
 move.enabled=false;cat.wait=0;frame();assert.equal(cat.active,null,'roaming off cancels autonomous actions');
 const look=new Look(THREE,model,{relaxBehind:true});model.rotation.y=0;
 for(let i=0;i<150;i++)look.update(1/60,new THREE.Vector3(-2,1,-3));assert(Math.abs(look.yaw)<.01,'behind camera releases head instead of clamping left');look.beforeFrame();
 cat.elapsed=5;cat.lookUntil=0;cat.random=()=>.4;move.path=[];const a=cat.attention(null,null).clone();cat.elapsed=5.5;assert(a.distanceTo(cat.attention(null,null))<.001,'holds gaze instead of constant scanning');cat.elapsed=12;cat.random=()=>.8;const b=cat.attention(null,null).clone();assert(a.distanceTo(b)>.3,'changes focus after dwell');
 const explicit=new THREE.Vector3(1,1,1);assert.equal(cat.attention(null,explicit),explicit);
 // Walking attention wins over persistent face/camera focus and looks beyond close waypoints.
 cat.active=null;move.velocity=.2;model.position.set(0,0,0);model.rotation.y=0;
 move.path=[{x:0,z:.01},{x:0,z:2}];const staleFace=new THREE.Vector3(-8,2,0);
 const forward=cat.attention(new THREE.Vector3(8,4,10),staleFace).clone();assert(Math.abs(forward.x)<1e-6&&forward.z>1.5);assert(cat.lookingAlongRoute);
 move.path=[{x:2,z:0}];const right=cat.attention(null,staleFace).clone();assert(right.x>.8&&right.z>1.5,'bounded anticipation of right turn');
 move.path=[{x:-2,z:0}];const left=cat.attention(null,staleFace).clone();assert(left.x<-.8&&left.z>1.5);
 for(const [target,sign] of [[right,1],[left,-1]]){
  for(let i=0;i<120;i++){cat.beforeFrame();look.beforeFrame();look.update(1/60,target,{state:'walk',locomotionFocus:true});cat.pose(1/60,'walk');}
  assert(look.yaw*sign>.2,'actual rig can anticipate both turn directions');
 }
 cat.beforeFrame();look.beforeFrame();model.rotation.y=Math.PI;move.path=[{x:0,z:-2}];const reversed=cat.attention(null,staleFace).clone();assert(reversed.z< -1.5,'head follows body reversal rather than a fixed world direction');
 move.path=[];move.velocity=0;assert.equal(cat.attention(null,staleFace),staleFace,'idle restores interactive attention');model.rotation.y=0;
 // Restore in reverse layering order, without accumulating camera/behavior rotations.
 const head=cat.byName.head.bone,base=head.quaternion.clone();cat.active={kind:'groom',time:1,duration:3.6};
 for(let i=0;i<100;i++){cat.beforeFrame();look.beforeFrame();look.update(1/60,new THREE.Vector3(2,1,3));cat.pose(1/60,'idle');}
 cat.beforeFrame();look.beforeFrame();assert(base.clone().normalize().angleTo(head.quaternion.clone().normalize())<1e-6,'additive poses restore rotation without drift');
 move.enabled=true;cat.autonomous=false;
 for(const side of [-1,1]){cat.begin('groom');cat.active.side=side;for(let i=0;i<440;i++)frame();assert.equal(cat.active,null,'groom sequence settles for either paw');}
 console.log('PASS actual cat rig: safe hop, bridge exclusion, wall route and alignment, pose restoration, cancellation, independent gaze and behind-camera relaxation');
})().catch(e=>{console.error(e);process.exitCode=1;});
