/* Actual textured GLBs + the den's playAction, in an isolated Chromium session.
 * Run with Playwright on NODE_PATH and PET_TEST_CHROME pointing to Chrome.
 * Screenshots/report go to a temporary folder, never into user data or Git.
 */
const fs=require('node:fs'),path=require('node:path'),os=require('node:os'),http=require('node:http'),assert=require('node:assert/strict');
const {chromium}=require('playwright');
const root=path.resolve(__dirname,'..'),out=fs.mkdtempSync(path.join(os.tmpdir(),'pet-motion-render-'));
const customFile=process.env.PET_MOTION_TEST_GLB&&path.resolve(process.env.PET_MOTION_TEST_GLB);
if(customFile)assert(fs.statSync(customFile).isFile(),'uploaded fixture must be a local GLB');
const den=fs.readFileSync(path.join(root,'templates/den.html'),'utf8');
const playAction=den.slice(den.indexOf('function playAction(key, timeScale)'),den.indexOf('function playOnceThen(key, next)'));
assert(playAction.includes('crossFadeFrom'),'use the production animation transition');
const scripts=['vendor/three.min.js','vendor/GLTFLoader.js','den/pet-model-bounds.js','den/scene-navigation.js','den/mistwood-layout.js','den/pet-locomotion.js','den/pet-grounding.js','den/head-look.js','den/cat-life.js','den/shiba-expression.js'];
const html=`<!doctype html><meta charset="utf-8"><style>body{margin:0;background:#d7dfda;font:18px sans-serif}#label{padding:12px}canvas{display:block}</style><div id="label">Loading actual pet models</div>${scripts.map(s=>'<script src="/static/js/'+s+'"></script>').join('')}<script>
const T=THREE,renderer=new T.WebGLRenderer({antialias:true,preserveDrawingBuffer:true});renderer.setSize(900,650);renderer.outputEncoding=T.sRGBEncoding;renderer.toneMapping=T.ACESFilmicToneMapping;document.body.append(renderer.domElement);
const scene=new T.Scene();scene.background=new T.Color('#d7dfda');scene.add(new T.HemisphereLight(0xfff8ef,0x607a69,1.3));const sun=new T.DirectionalLight(0xffead9,1.8);sun.position.set(-3,6,4);scene.add(sun);
const floor=new T.Mesh(new T.PlaneGeometry(20,20),new T.MeshStandardMaterial({color:0x80977c,roughness:1}));floor.rotation.x=-Math.PI/2;floor.position.y=-.003;scene.add(floor);
const grid=new T.GridHelper(12,24,0x63795d,0x97aa91);grid.position.y=.001;scene.add(grid);
const camera=new T.PerspectiveCamera(35,900/650,.01,60);camera.position.set(3.2,2.3,4.5);
const loader=new T.GLTFLoader();let current;
window.prepare=async function(spec){
 if(current){scene.remove(current.pet);if(current.home)scene.remove(current.home);}floor.position.y=-.003;
 const g=await loader.loadAsync(spec.custom?'/__fixture/custom.glb':'/static/models/'+spec.file),model=g.scene;
 model.traverse(o=>{if(o.isSkinnedMesh&&!spec.custom)o.skeleton.pose();});model.updateMatrixWorld(true);
 const box=spec.custom?PetModelBounds.measure(T,model):new T.Box3().setFromObject(model),origH=box.max.y-box.min.y;model.scale.setScalar(spec.height/origH);model.updateMatrixWorld(true);
 const scaled=spec.custom?box.clone().applyMatrix4(new T.Matrix4().makeScale(model.scale.x,model.scale.y,model.scale.z)):new T.Box3().setFromObject(model);model.position.set(-(scaled.min.x+scaled.max.x)/2,-scaled.min.y,-(scaled.min.z+scaled.max.z)/2);
 const pet=new T.Group();pet.userData.height=spec.height;pet.add(model);scene.add(pet);
 const mixer=new T.AnimationMixer(model),actions={};let activeAction=null,state='idle';
 ${playAction}
 for(const [key,names] of Object.entries({idle:['idle_breathe'],walk:spec.custom?['walk']:['motion_walk','walk'],trot:spec.custom?['walk']:['motion_trot','trot'],run:['run'],turnLeft:['turn_left'],turnRight:['turn_right'],sit:spec.custom?['sit_down']:['sit_idle'],sleep:['sleep_loop'],eat:['eat'],sniff:['sniff'],stretch:['stretch']})){
  const clip=names.map(n=>g.animations.find(c=>c.name.split('|').pop()===n)).find(Boolean);
  if(clip){const c=clip.clone();c.tracks=c.tracks.filter(t=>!t.name.includes('morphTargetInfluences')&&!/^(eye_[LR]|lid_[LR])\\./.test(t.name));if(spec.custom&&key==='sit'){c.duration=1;for(const track of c.tracks){const last=track.values.slice(-track.getValueSize());track.times=new Float32Array([0,1]);track.values=new Float32Array([...last,...last]);}}actions[key]=mixer.clipAction(c);}
 }
 const nav=new PetNavigation.Navigation({radius:10,bodyRadius:.4,rug:{x:0,z:0,radius:1,fade:1,base:0,rise:0}});
 const move=new PetLocomotion.Controller({navigation:nav,model:pet,speed:.34,strideSpeed:.42*spec.height/origH,gaits:PetLocomotion.gaitSpeeds(actions,spec.height/origH),animate(k,s){state=k;playAction(k,s);},rest(){state='idle';playAction('idle',1);}});move.autonomous=false;
 const look=new PetHeadLook.Controller(T,pet,{relaxBehind:spec.cat}),expression=spec.custom?null:new ShibaExpression.Controller(model,{eyeRetraction:0});
 const life=spec.cat?new CatLife.Controller(T,pet,move):null,ground=spec.cat?new PetGrounding.Controller(T,pet,model,nav):null;
 playAction('idle',1);let time=0,maxYawStep=0,lastYaw=0,maxAcceleration=0,maxAliasCadenceError=0,lastMoveSpeed=0,textures=0;const clips=new Set(),rates=[];
 model.traverse(o=>{if(o.isMesh&&o.material.map)textures++;});
 current={pet,model,move,
  setPose(key){if(!actions[key])throw Error('missing required pose '+key);move.interrupt();state=key;playAction(key,1);},
  async feeding(){
   this.home=(await loader.loadAsync('/static/models/petchat-cat-home-v1/cat-home.glb')).scene;scene.add(this.home);
   nav.obstacles=MistwoodLayout.obstacles;nav.surfaces=MistwoodLayout.surfaces;nav.rug=MistwoodLayout.rug;
   const dock=life.feedingDock({station:'feedingStation',x:1.15});if(!dock)throw Error('missing feeding dock');
   pet.position.set(dock.target.x,.035,dock.target.z);pet.rotation.y=0;lastYaw=0;floor.position.y=.032;
   this.setPose('eat');nav.dock=dock;camera.position.set(3.6,1.8,3.5);
  },
  step(dt){
   ground?.beforeFrame();life?.beforeFrame();look.beforeFrame();
   const before=move.velocity,position=pet.position.clone(),oldAction=activeAction,oldState=state,oldRate=activeAction.timeScale;move.update(dt);
   const moved=pet.position.distanceTo(position)/dt;
   if(oldState!==state&&['walk','trot','run'].includes(oldState)&&['walk','trot','run'].includes(state)&&oldAction.getClip().name===activeAction.getClip().name&&lastMoveSpeed>.05&&moved>.05){
    maxAliasCadenceError=Math.max(maxAliasCadenceError,Math.abs((activeAction.timeScale/oldRate)/(moved/lastMoveSpeed)-1));
   }
   lastMoveSpeed=moved;
   if(move.path.length)maxAcceleration=Math.max(maxAcceleration,Math.abs(move.velocity-before)/dt);
   mixer.update(dt);time+=dt;expression?.update(dt,state,activeAction.time/activeAction.getClip().duration);
   look.update(dt,life?life.attention(camera.position,null):camera.position,{state,locomotionFocus:!!life?.lookingAlongRoute});
   life?.pose(dt,state,expression);ground?.update(dt,{state});pet.updateMatrixWorld(true);
   model.traverse(o=>{if(o.isBone&&!o.matrixWorld.elements.every(Number.isFinite))throw Error('nonfinite bone');});
   maxYawStep=Math.max(maxYawStep,Math.abs(pet.rotation.y-lastYaw));lastYaw=pet.rotation.y;clips.add(activeAction.getClip().name);rates.push(activeAction.timeScale);
  },
  render(label){camera.lookAt(pet.position.x,.45,pet.position.z);renderer.render(scene,camera);document.getElementById('label').textContent=spec.name+' — '+label+' — '+state+' / '+move.velocity.toFixed(3)+' m/s';},
  report(){return {file:spec.file,textures,time,clips:[...clips],maxYawStep,maxAcceleration,maxAliasCadenceError,position:pet.position.toArray(),moves:move.moves,drawCalls:renderer.info.render.calls,triangles:renderer.info.render.triangles,rateRange:[Math.min(...rates),Math.max(...rates)]};}
 };
 current.render('idle');return {clips:Object.keys(actions),textures};
};
window.sample=function(phase){const c=current;
 if(phase==='start')c.move.goTo({x:0,z:3},{gait:'run'});
 if(phase==='turn')c.move.goTo({x:-2,z:c.pet.position.z},{gait:'walk'});
 if(phase==='start'||phase==='cruise'||phase==='turn'){for(let i=0;i<(phase==='cruise'?120:18);i++)c.step(1/60);}
 if(phase==='arrived'){let i=0;for(;i<3600&&c.move.path.length;i++)c.step(1/60);if(c.move.path.length)throw Error('route did not finish');for(let j=0;j<30;j++)c.step(1/60);}
 c.render(phase);return c.report();};
window.pose=async function(name){const c=current;
 if(name==='feeding')await c.feeding();else c.setPose(name);
 for(let i=0;i<180;i++)c.step(1/60);c.render(name);return c.report();};
window.recordTour=async function(spec){
 await prepare(spec);const c=current,stream=renderer.domElement.captureStream(30),chunks=[];
 const recorder=new MediaRecorder(stream,{mimeType:'video/webm'});recorder.ondataavailable=e=>{if(e.data.size)chunks.push(e.data);};
 const stopped=new Promise(r=>recorder.onstop=r);recorder.start();c.move.goTo({x:0,z:3},{gait:'run'});
 let previous=performance.now(),elapsed=0,turned=false;
 await new Promise(resolve=>{function tick(now){const dt=Math.max(.001,Math.min(.05,(now-previous)/1000));previous=now;elapsed+=dt;
  if(elapsed>2.3&&!turned){turned=true;c.move.goTo({x:-2,z:c.pet.position.z},{gait:'walk'});}
  c.step(dt);c.render('replay');if(elapsed<11)requestAnimationFrame(tick);else resolve();}requestAnimationFrame(tick);});
 recorder.stop();await stopped;stream.getTracks().forEach(t=>t.stop());
 const blob=new Blob(chunks,{type:'video/webm'});return await new Promise(r=>{const reader=new FileReader();reader.onload=()=>r(reader.result.split(',')[1]);reader.readAsDataURL(blob);});
};
</script>`;
const server=http.createServer((req,res)=>{
 if(req.url==='/'){res.setHeader('Content-Type','text/html; charset=utf-8');res.end(html);return;}
 if(customFile&&req.url==='/__fixture/custom.glb'){res.setHeader('Content-Type','model/gltf-binary');fs.createReadStream(customFile).pipe(res);return;}
 const url=new URL(req.url,'http://localhost'),file=path.resolve(root,'.'+decodeURIComponent(url.pathname));
 if(!file.startsWith(path.join(root,'static')+path.sep)||!fs.existsSync(file)||!fs.statSync(file).isFile()){res.writeHead(404).end();return;}
 res.setHeader('Content-Type',file.endsWith('.js')?'text/javascript':file.endsWith('.glb')?'model/gltf-binary':'application/octet-stream');fs.createReadStream(file).pipe(res);
});
(async()=>{
 await new Promise(r=>server.listen(0,'127.0.0.1',r));let browser;
 try{
  browser=await chromium.launch({headless:true,...(process.env.PET_TEST_CHROME?{executablePath:process.env.PET_TEST_CHROME}:{})});
  const page=await browser.newPage({viewport:{width:900,height:700}}),errors=[],report=[];
  page.on('pageerror',e=>errors.push(e.message));await page.goto('http://127.0.0.1:'+server.address().port);
  const specs=customFile?[{name:'Uploaded',file:'private-fixture',height:.85,cat:true,custom:true}]:[{name:'Shiba',file:'petchat-shiba-v4/qiuqiu.glb',height:.95},{name:'Husky',file:'petchat-husky-v3/xueqiu.glb',height:1.05},{name:'Cat',file:'petchat-cat-v3/cat.glb',height:.85,cat:true},{name:'Shepherd',file:'petchat-shepherd-v2/shepherd.glb',height:1.12}];
  for(const spec of specs){
   const loaded=await page.evaluate(spec=>prepare(spec),spec);assert(loaded.textures>0,'actual embedded textures loaded');
   for(const phase of ['start','cruise','turn','arrived']){
    const data=await page.evaluate(phase=>sample(phase),phase);assert(data.triangles>1000&&data.drawCalls>1);assert(data.maxYawStep<=3.2/60+1e-8);assert(data.maxAcceleration<=1.6+1e-8,'smooth command speed changes on the real rig');
    assert(data.maxAliasCadenceError<1e-6,'reusing a walk clip for trot must preserve cadence per metre');
    if(phase==='arrived')assert(data.moves>0);
    await page.screenshot({path:path.join(out,spec.name+'-'+phase+'.png')});report.push({pet:spec.name,phase,...data});
   }
   if(process.env.PET_TEST_VIDEO==='1')fs.writeFileSync(path.join(out,spec.name+'.webm'),Buffer.from(await page.evaluate(spec=>recordTour(spec),spec),'base64'));
   if(spec.custom)for(const phase of ['sit','sleep','eat','sniff','stretch','feeding']){
    const data=await page.evaluate(name=>pose(name),phase);await page.screenshot({path:path.join(out,spec.name+'-'+phase+'.png')});report.push({pet:spec.name,phase,...data});
   }
   console.log('Verified '+spec.name);
  }
  assert.deepEqual(errors,[]);fs.writeFileSync(path.join(out,'report.json'),JSON.stringify(report,null,2));
  console.log('PASS actual textured Chromium GLBs: start/run/turn/arrival, production playAction, finite bones and bounded yaw');console.log(out);
 }finally{await browser?.close();server.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
