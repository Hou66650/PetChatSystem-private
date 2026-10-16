const fs=require('fs'),vm=require('vm'),assert=require('assert/strict'),T=require('../static/js/vendor/three.min.js');
const {Navigation}=require('../static/js/den/scene-navigation'),{Controller:Move}=require('../static/js/den/pet-locomotion'),{Controller:Life}=require('../static/js/den/cat-life'),{Controller:Agent}=require('../static/js/den/cat-agent'),{Controller:Ground}=require('../static/js/den/pet-grounding');
const layout=require('../static/js/den/mistwood-layout'),catalog=require('../static/data/cat-world.json');
vm.runInNewContext(fs.readFileSync('static/js/vendor/GLTFLoader.js','utf8'),{THREE:T,console,TextDecoder,URL,Blob,self:{URL},setTimeout,clearTimeout});const ctx={};vm.runInNewContext(fs.readFileSync('static/js/den/pet-model-bounds.js','utf8'),ctx);
T.TextureLoader.prototype.load=function(u,cb){const t=new T.Texture();queueMicrotask(()=>cb(t));return t;};
const load=p=>new Promise((r,j)=>{const b=fs.readFileSync(p);new T.GLTFLoader().parse(b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength),'',r,j);});
(async()=>{
 const home=await load('static/models/petchat-cat-home-v1/cat-home.glb');home.scene.updateMatrixWorld(true);const stand=layout.obstacles.find(o=>o.id==='feedingStation');const hit=new T.Raycaster(new T.Vector3(stand.x,1,stand.z),new T.Vector3(0,-1,0)).intersectObject(home.scene,true)[0];assert(hit&&Math.abs(hit.point.y-.29)<.005,'navigation stand matches exported Blender tabletop');
 for(const file of ['static/models/petchat-cat-v3/cat.glb',...(process.env.PET_FEEDING_TEST_GLB?[process.env.PET_FEEDING_TEST_GLB]:[])]){
 const g=await load(file),m=g.scene,box=ctx.PetModelBounds.measure(T,m),s=.85/(box.max.y-box.min.y);m.scale.setScalar(s);m.position.set(-(box.min.x+box.max.x)*s/2,-box.min.y*s,-(box.min.z+box.max.z)*s/2);
 const root=new T.Group();root.userData.height=.85;root.add(m);root.position.set(0,.035,0);
 const nav=new Navigation({...layout,bodyRadius:Math.hypot(box.max.x-box.min.x,box.max.z-box.min.z)*s/2+.015});
 assert(!nav.isWalkable({x:1.5,z:6.28}));assert(!nav.segmentClear({x:1.5,z:4},{x:1.5,z:7.5}));
 const detour=new Navigation({radius:12,bodyRadius:.8,obstacles:layout.obstacles.filter(o=>o.id==='feedingStation')});const around=detour.route({x:1.5,z:3.9},{x:2.7,z:7.5});assert(around&&around.length>1,'walking detours around the whole stand');
 let state='idle',action,time=0;const mixer=new T.AnimationMixer(m);
 function animate(name,speed=1){state=name;const key=({idle:'idle_breathe',mouthClean:'idle_breathe',curious:'idle_breathe'})[name]||name,clip=g.animations.find(c=>c.name===key)||g.animations.find(c=>c.name==='idle_breathe');const next=mixer.clipAction(clip);if(next!==action){action?.stop();next.reset().play();action=next;}action.timeScale=speed;}
 const move=new Move({model:root,navigation:nav,animate,rest(){animate('idle');},speed:.5}),life=new Life(T,root,move,{animate}),ground=new Ground(T,root,m,nav);
 const agent=new Agent({model:root,locomotion:move,life,scope:'fixture',animate,storage:null,now:()=>time,fetcher:async url=>({ok:true,json:async()=>url==='/api/cat-agent'?{scope:'fixture',catalog,memory:[]}:{scope:'fixture',memory:[]}})});await agent.ready;agent.socialAfter=Infinity;agent.networkAfter=Infinity;agent.nextScene=Infinity;
 // Uploaded skins can distribute paw weights mostly to the spine. Include
 // minor foreleg influences too, rather than silently testing no low vertices.
 const legs=[];m.traverse(mesh=>{if(!mesh.isSkinnedMesh)return;const a=mesh.geometry.attributes;for(let i=0;i<a.position.count;i++){let w=0;for(let j=0;j<4;j++)if(/^(FL|FR)_/.test(mesh.skeleton.bones[a.skinIndex.array[i*4+j]]?.name))w+=a.skinWeight.array[i*4+j];if(w>.05)legs.push({mesh,i});}});
 assert(legs.length>0,'front-leg mesh samples must exist');
 let nearest=Infinity,docked=false,ate=false;
 function tick(){time+=1000/60;ground.beforeFrame();life.beforeFrame();agent.step(1/60,false);const active=life.step(1/60,false);move.update(1/60,active);mixer.update(1/60);root.position.y=nav.surfaceHeight(root.position);life.pose(1/60,state);ground.update(1/60,{state});root.updateMatrixWorld(true);m.traverse(o=>{if(o.isSkinnedMesh)o.skeleton.update();});if(time%100<17)for(const {mesh,i} of legs){const p=new T.Vector3().fromBufferAttribute(mesh.geometry.attributes.position,i);mesh.boneTransform(i,p).applyMatrix4(mesh.matrixWorld);if(p.y<.42&&p.y>0){const dx=Math.abs(p.x-stand.x)-stand.w/2,dz=Math.abs(p.z-stand.z)-stand.d/2,gap=Math.hypot(Math.max(dx,0),Math.max(dz,0))+Math.min(Math.max(dx,dz),0);nearest=Math.min(nearest,gap);assert(gap>-.003,`${file} front leg penetrates stand: ${gap}, ${agent.phase}/${state}`);}}if(agent.goal?.docked)docked=true;if(state==='eat')ate=true;}
 for(const kind of ['eat','drink']){assert(agent.requestCare(kind));for(let i=0;i<5000&&(agent.goal||nav.dock);i++)tick();assert(!agent.goal&&!nav.dock,'complete meal and back away');assert(nav.isWalkable(root.position));}
 assert(docked&&ate,'actually reached and used bowls');assert(Number.isFinite(nearest),'collision checks must sample actual foreleg geometry');
 // A user command during eating must back out before turning; no permanent pass-through.
 agent.cooldowns={};assert(agent.requestCare('eat'));for(let i=0;i<3000&&state!=='eat';i++)tick();assert(nav.dock);const exit={...nav.dock.entry};agent.interrupt();assert(move.goTo({x:0,z:0}));assert.deepEqual(move.path[0],exit);for(let i=0;i<3000&&move.path.length;i++)tick();assert(!nav.dock);assert(nav.isWalkable(root.position));assert(!nav.isWalkable({x:1.5,z:6.28}));agent.dispose();
 console.log('PASS feeding collision, eat/drink, measured uploaded forelegs, interrupted retreat',JSON.stringify({file,front:life.feedingFront,nearest}));
 }
})().catch(e=>{console.error(e);process.exitCode=1;});
