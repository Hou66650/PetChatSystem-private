/* Full-clip browser validation for independently modeled growth stages. */
const fs=require('node:fs'),path=require('node:path'),os=require('node:os'),http=require('node:http'),assert=require('node:assert/strict');
const {chromium}=require('playwright');
const root=path.resolve(__dirname,'..'),out=fs.mkdtempSync(path.join(os.tmpdir(),'pet-growth-motion-'));
const den=fs.readFileSync(path.join(root,'templates/den.html'),'utf8');
const playAction=den.slice(den.indexOf('function playAction(key, timeScale)'),den.indexOf('function playOnceThen(key, next)'));
assert(playAction.includes('crossFadeFrom'),'production playAction is required');
const scripts=['vendor/three.min.js','vendor/GLTFLoader.js','den/pet-model-bounds.js','den/scene-navigation.js','den/mistwood-layout.js','den/pet-locomotion.js','den/pet-grounding.js','den/head-look.js','den/shiba-expression.js'];
const html=`<!doctype html><meta charset="utf-8"><style>body{margin:0;background:#d7dfda;font:16px sans-serif}#label{padding:8px}canvas{display:block}</style><div id="label">Loading</div>${scripts.map(s=>'<script src="/static/js/'+s+'"></script>').join('')}<script>
const T=THREE,renderer=new T.WebGLRenderer({antialias:true,preserveDrawingBuffer:true});renderer.setSize(640,520);renderer.outputEncoding=T.sRGBEncoding;renderer.toneMapping=T.ACESFilmicToneMapping;document.body.append(renderer.domElement);
const scene=new T.Scene();scene.background=new T.Color('#d7dfda');scene.add(new T.HemisphereLight(0xfff8ef,0x607a69,1.3));const sun=new T.DirectionalLight(0xffead9,1.8);sun.position.set(-3,6,4);scene.add(sun);
const floor=new T.Mesh(new T.PlaneGeometry(20,20),new T.MeshStandardMaterial({color:0x80977c,roughness:1}));floor.rotation.x=-Math.PI/2;floor.position.y=-.003;scene.add(floor);
const camera=new T.PerspectiveCamera(35,640/520,.01,60);camera.position.set(2.5,1.75,3.5);const loader=new T.GLTFLoader();let current;
window.prepare=async function(spec){
 if(current){scene.remove(current.pet);current.mixer.stopAllAction();current.pet.traverse(o=>{o.geometry?.dispose();for(const m of o.material?(Array.isArray(o.material)?o.material:[o.material]):[]){m.map?.dispose();m.dispose();}});}
 const started=performance.now(),g=await loader.loadAsync('/static/models/'+spec.file),loadMs=performance.now()-started,model=g.scene;
 model.traverse(o=>{if(o.isSkinnedMesh&&!spec.actualBounds)o.skeleton.pose();});model.updateMatrixWorld(true);
 const box=spec.actualBounds?PetModelBounds.measure(T,model):new T.Box3().setFromObject(model),origH=box.max.y-box.min.y;model.scale.setScalar(spec.height/origH);model.updateMatrixWorld(true);
 const scaled=spec.actualBounds?box.clone().applyMatrix4(new T.Matrix4().makeScale(model.scale.x,model.scale.y,model.scale.z)):new T.Box3().setFromObject(model);model.position.set(-(scaled.min.x+scaled.max.x)/2,-scaled.min.y,-(scaled.min.z+scaled.max.z)/2);
 const pet=new T.Group();pet.userData.height=spec.height;pet.add(model);scene.add(pet);camera.position.set(spec.height*2.8,spec.height*1.8,spec.height*3.4);
 const mixer=new T.AnimationMixer(model),actions={};let activeAction=null,state='idle';
 ${playAction}
 const faceTrack=t=>/^(eye_[LR]|lid_[LR])\./.test(t.name);
 for(const clip of g.animations){
  const name=clip.name.split('|').pop(),key='clip_'+name,c=clip.clone();
  c.tracks=c.tracks.filter(t=>{
   if(t.name.includes('morphTargetInfluences'))return false;
   if(!name.startsWith('blink'))return !faceTrack(t);
   const side=name==='blink_L'?'L':'R';return t.name.startsWith('eye_'+side+'.')||t.name.startsWith('lid_'+side+'.');
  });
  actions[key]=mixer.clipAction(c);
 }
 playAction('clip_idle_breathe',1);
 const nav=new PetNavigation.Navigation({radius:10,bodyRadius:.4,rug:{x:0,z:0,radius:1,fade:1,base:0,rise:0}}),ground=spec.actualBounds?new PetGrounding.Controller(T,pet,model,nav):null;
 const look=new PetHeadLook.Controller(T,pet,{relaxBehind:spec.cat}),expression=new ShibaExpression.Controller(model,{eyeRetraction:0});
 let textures=0;model.traverse(o=>{if(o.isMesh&&o.material.map)textures++;});
 current={pet,model,mixer,actions,ground,look,expression,
  start(name){state=name;playAction('clip_'+name,1);if(!actions['clip_'+name])throw Error('missing '+name);},
  step(frames){for(let i=0;i<frames;i++){ground?.beforeFrame();look.beforeFrame();mixer.update(1/60);expression.update(1/60,state,activeAction.time/activeAction.getClip().duration);look.update(1/60,camera.position,{state});ground?.update(1/60,{state});pet.updateMatrixWorld(true);model.traverse(o=>{if(o.isBone&&!o.matrixWorld.elements.every(Number.isFinite))throw Error('nonfinite bone');});}},
  render(label){camera.lookAt(pet.position.x,spec.height*.5,pet.position.z);renderer.render(scene,camera);document.getElementById('label').textContent=spec.name+' — '+label;},
  report(){pet.updateMatrixWorld(true);const measured=PetModelBounds.measure(T,model),box=new T.Box3().setFromObject(model),feet=['FL_foot','FR_foot','HL_foot','HR_foot'].map(name=>{const bone=model.getObjectByName(name);return bone?bone.getWorldPosition(new T.Vector3()).y:null;});return {minY:measured.min.y,maxY:measured.max.y,boxMinY:box.min.y,modelY:model.position.y,groundLift:ground?.lift||0,feet,drawCalls:renderer.info.render.calls,triangles:renderer.info.render.triangles};}
 };
 current.render('idle');return {loadMs,textures,clips:g.animations.map(a=>({name:a.name.split('|').pop(),duration:a.duration}))};
};
</script>`;
const server=http.createServer((req,res)=>{
 if(req.url==='/'){res.setHeader('Content-Type','text/html; charset=utf-8');res.end(html);return;}
 const url=new URL(req.url,'http://localhost'),file=path.resolve(root,'.'+decodeURIComponent(url.pathname));
 if(!file.startsWith(path.join(root,'static')+path.sep)||!fs.existsSync(file)||!fs.statSync(file).isFile()){res.writeHead(404).end();return;}
 res.setHeader('Content-Type',file.endsWith('.js')?'text/javascript':file.endsWith('.glb')?'model/gltf-binary':'application/octet-stream');fs.createReadStream(file).pipe(res);
});
const matrices={
 cat:[
  {name:'cat-juvenile',file:'pet-growth-v1/cat/tabby-juvenile.glb',height:.58,cat:true,actualBounds:true},
  {name:'cat-adolescent',file:'pet-growth-v1/cat/tabby-adolescent.glb',height:.72,cat:true,actualBounds:true},
  {name:'cat-adult',file:'petchat-cat-v3/cat.glb',height:.85,cat:true,actualBounds:true},
 ],
 shiba:[
  {name:'shiba-juvenile',file:'pet-growth-v1/shiba/default-juvenile.glb',height:.64,actualBounds:true},
  {name:'shiba-adolescent',file:'pet-growth-v1/shiba/default-adolescent.glb',height:.82,actualBounds:true},
  {name:'shiba-adult',file:'pet-growth-v1/shiba/default-adult.glb',height:.95,actualBounds:true},
 ],
 husky:[
  {name:'husky-juvenile',file:'pet-growth-v1/husky/default-juvenile.glb',height:.72,actualBounds:true},
  {name:'husky-adolescent',file:'pet-growth-v1/husky/default-adolescent.glb',height:.91,actualBounds:true},
  {name:'husky-adult',file:'petchat-husky-v3/xueqiu.glb',height:1.05,actualBounds:true},
 ],
 shepherd:[
  {name:'shepherd-juvenile',file:'pet-growth-v1/shepherd/default-juvenile.glb',height:.76,actualBounds:true},
  {name:'shepherd-adolescent',file:'pet-growth-v1/shepherd/default-adolescent.glb',height:.96,actualBounds:true},
  {name:'shepherd-adult',file:'pet-growth-v1/shepherd/default-adult.glb',height:1.12,actualBounds:true},
 ],
};
(async()=>{
 await new Promise(r=>server.listen(0,'127.0.0.1',r));let browser;
 try{
  browser=await chromium.launch({headless:true,...(process.env.PET_TEST_CHROME?{executablePath:process.env.PET_TEST_CHROME}:{})});
  const page=await browser.newPage({viewport:{width:640,height:560}}),errors=[],report=[];
  page.on('pageerror',e=>errors.push(e.message));await page.goto('http://127.0.0.1:'+server.address().port);
  const species=process.env.PET_GROWTH_SPECIES||'cat';assert(matrices[species],'unknown growth matrix');
  for(const spec of matrices[species]){
   const loaded=await page.evaluate(spec=>prepare(spec),spec);assert(loaded.textures>0,'embedded texture required');assert.equal(loaded.clips.length,35);
   for(const clip of loaded.clips){
    await page.evaluate(name=>current.start(name),clip.name);
    const middle=Math.max(1,Math.round(clip.duration*30)),ending=Math.max(1,Math.round(clip.duration*30)+18);
    await page.evaluate(frames=>current.step(frames),middle);
    await page.evaluate(()=>current.render('mid'));await page.screenshot({path:path.join(out,spec.name+'-'+clip.name+'-mid.png')});
    await page.evaluate(frames=>current.step(frames),ending);await page.evaluate(()=>current.render('end'));
    await page.screenshot({path:path.join(out,spec.name+'-'+clip.name+'-end.png')});
    const data=await page.evaluate(()=>current.report());assert(data.triangles>1000&&data.drawCalls>1);assert(Number.isFinite(data.minY)&&data.minY>-.05,spec.name+' '+clip.name+' ground '+data.minY);assert(data.maxY<10,'bounded mesh');
    report.push({pet:spec.name,clip:clip.name,loadMs:loaded.loadMs,...data});
   }
   console.log('Verified '+spec.name+' 35 clips');
  }
  assert.deepEqual(errors,[]);fs.writeFileSync(path.join(out,'report.json'),JSON.stringify(report,null,2));
  console.log('PASS growth GLBs: every clip fully advanced in Chromium with real skinning and textures');console.log(out);
 }finally{await browser?.close();server.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
