const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const THREE=require('../static/js/vendor/three.min.js'),{Controller}=require('../static/js/den/cat-life');
const {Navigation}=require('../static/js/den/scene-navigation'),{Controller:Move}=require('../static/js/den/pet-locomotion'),{Controller:Look}=require('../static/js/den/head-look');
const layout=require('../static/js/den/mistwood-layout');
vm.runInNewContext(fs.readFileSync('static/js/vendor/GLTFLoader.js','utf8'),{THREE,console,TextDecoder,URL,Blob,self:{URL},setTimeout,clearTimeout});
THREE.TextureLoader.prototype.load=function(url,cb){const t=new THREE.Texture();queueMicrotask(()=>cb(t));return t;};
(async()=>{
 const bytes=fs.readFileSync('static/models/petchat-cat-v2/cat.glb');
 const gltf=await new Promise((r,j)=>new THREE.GLTFLoader().parse(bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength),'',r,j));
 const model=new THREE.Group();model.add(gltf.scene);
 const nav=new Navigation({...layout,bodyRadius:.619}),move=new Move({navigation:nav,model,animate(){},rest(){}});
 const cat=new Controller(THREE,model,move,{walls:[{x:.8,z:-3.4,nx:-1,nz:0}],random:()=>.1});
 for(const name of ['head','neck','spine_front','ear_L','tail_tip','FL_lower'])assert(cat.byName[name],name);
 const frame=(blocked=false)=>{cat.beforeFrame();const owned=cat.step(1/60,blocked);move.update(1/60,blocked||owned);model.position.y=nav.surfaceHeight(model.position);cat.pose(1/60,'idle');assert(nav.isWalkable(model.position));};
 model.position.set(-2,0,-3);assert(cat.begin('jump'));let max=0;for(let i=0;i<105;i++){frame();max=Math.max(max,model.position.y-nav.surfaceHeight(model.position));}
 assert(max>.30);assert.equal(cat.active,null);assert(Math.abs(model.position.z+2.45)<.001);
 model.position.set(0,0,1.8);assert.equal(cat.begin('jump'),false,'no jumping on bridge');model.position.set(0,0,0);
 assert(cat.seekWall());for(let i=0;i<2100&&cat.approach;i++)frame();assert.equal(cat.active?.kind,'rub','navigate and align to actual conservatory wall');
 cat.cancel();assert.equal(cat.active,null);assert.equal(cat.approach,null);
 model.position.set(0,0,0);
 for(const kind of ['groom','stretch','rub']){assert(cat.begin(kind));for(let i=0;i<90;i++)frame();model.traverse(o=>{if(o.isBone)assert(o.quaternion.toArray().every(Number.isFinite));});frame(true);assert.equal(cat.active,null);}
 cat.begin('groom');assert(move.goTo({x:-1,z:-1}));const command=move.path;cat.step(1/60,false);assert.equal(cat.active,null);assert.equal(move.path,command,'external command keeps its route');
 move.enabled=false;cat.wait=0;frame();assert.equal(cat.active,null,'roaming off cancels autonomous actions');
 const look=new Look(THREE,model,{relaxBehind:true});model.rotation.y=0;
 for(let i=0;i<150;i++)look.update(1/60,new THREE.Vector3(-2,1,-3));assert(Math.abs(look.yaw)<.01,'behind camera releases head instead of clamping left');look.beforeFrame();
 cat.elapsed=5;move.path=[];const a=cat.attention(new THREE.Vector3(5,3,5),null).clone();cat.elapsed=8;const b=cat.attention(new THREE.Vector3(5,3,5),null).clone();assert(a.distanceTo(b)>.3);
 const explicit=new THREE.Vector3(1,1,1);assert.equal(cat.attention(null,explicit),explicit);
 // Restore in reverse layering order, without accumulating camera/behavior rotations.
 const head=cat.byName.head.bone,base=head.quaternion.clone();cat.active={kind:'groom',time:1,duration:3.6};
 for(let i=0;i<100;i++){cat.beforeFrame();look.beforeFrame();look.update(1/60,new THREE.Vector3(2,1,3));cat.pose(1/60,'idle');}
 cat.beforeFrame();look.beforeFrame();assert(base.angleTo(head.quaternion)<1e-6);
 console.log('PASS actual cat rig: safe hop, bridge exclusion, wall route and alignment, pose restoration, cancellation, independent gaze and behind-camera relaxation');
})().catch(e=>{console.error(e);process.exitCode=1;});
