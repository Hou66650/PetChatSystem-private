// Run test/park_review_server.py first; uses its isolated database and no live accounts.
const {chromium}=require('playwright'),assert=require('node:assert/strict'),fs=require('node:fs'),os=require('node:os'),path=require('node:path');
const base=process.env.PET_TEST_BASE||'http://127.0.0.1:5088',output=fs.mkdtempSync(path.join(os.tmpdir(),'pait-park-clouds-'));
const harmony=process.env.PET_TEST_HARMONY==='1',wideViewport=harmony?{width:1245,height:756}:{width:1440,height:1000};
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.PET_TEST_CHROME||'C:/Program Files/Google/Chrome/Application/chrome.exe'});
 try{
  const page=await browser.newPage({viewport:wideViewport,...(harmony?{hasTouch:true,deviceScaleFactor:2.25,userAgent:'Mozilla/5.0 (Tablet; OpenHarmony 6.1) AppleWebKit/537.36 Chrome/132.0.0.0 Safari/537.36 ArkWeb/6.1.0.120'}:{})}),errors=[];page.on('pageerror',e=>errors.push(e.message));
  // Exercise a server retaining the old template while static JS has been updated.
  await page.route('**/park',async route=>{const response=await route.fetch();await route.fulfill({response,body:(await response.text()).replace(/<script src="[^" ]*home-atmosphere[^" ]*"><\/script>/g,'')});});
  await page.route('**/static/js/public-park.js*',async route=>{const response=await route.fetch(),source=await response.text();assert(source.includes('const self={x:0,z:0,yaw:0};'));await route.fulfill({response,body:source.replace('const self={x:0,z:0,yaw:0};',`const self={x:0,z:0,yaw:0};window.__parkQA={camera,scene,atmosphere,renderer,controls,frames:0};const draw=renderer.render.bind(renderer);renderer.render=(...args)=>{window.__parkQA.frames++;return draw(...args);};`)});});
  await page.goto(base+'/park');await page.waitForFunction(()=>document.querySelector('#pet-park').dataset.scene==='ready',null,{timeout:60000});
  const inspect=()=>page.evaluate(()=>{
   const q=window.__parkQA,model=q.scene.children.find(x=>x.userData.parkTier),box=new THREE.Box3().setFromObject(model);q.camera.updateMatrixWorld();
   const corners=[];for(const x of [box.min.x,box.max.x])for(const y of [box.min.y,box.max.y])for(const z of [box.min.z,box.max.z])corners.push(new THREE.Vector3(x,y,z).project(q.camera).toArray());
   return {corners,cloudTop:Math.max(...q.atmosphere.clouds.map(c=>c.position.y)),clouds:q.atmosphere.clouds.length,pixels:q.renderer.domElement.width*q.renderer.domElement.height,antialias:q.renderer.getContext().getContextAttributes().antialias,rockBottom:box.min.y,far:q.camera.far,aspect:q.camera.aspect,time:q.atmosphere.time.value,frames:q.frames};
  });
  let wide=await inspect();assert(wide.cloudTop<wide.rockBottom-3,'cloud deck leaves air below the island');assert(wide.far>=400,'sky dome is inside far plane');assert(wide.corners.every(([x,y,z])=>Math.abs(x)<1&&Math.abs(y)<1&&z<1),'full rock base fits wide view');
  if(harmony){assert.equal(wide.clouds,2);assert(wide.pixels<=900000);assert.equal(wide.antialias,false);}
  await page.waitForTimeout(1200);assert((await inspect()).time>wide.time,'clouds drift');await page.screenshot({path:path.join(output,'wide.png')});
  await page.emulateMedia({reducedMotion:'reduce'});await page.waitForTimeout(1000);const frozen=await inspect();await page.waitForTimeout(400);assert.equal((await inspect()).time,0);assert.equal((await inspect()).frames,frozen.frames,'reduced motion preserves idle render savings');
  await page.setViewportSize({width:430,height:932});await page.waitForTimeout(500);const narrow=await inspect();assert(narrow.corners.every(([x,y,z])=>Math.abs(x)<1&&Math.abs(y)<1&&z<1),'full island fits narrow viewport');await page.screenshot({path:path.join(output,'narrow.png')});
  await page.setViewportSize(wideViewport);await page.waitForTimeout(500);const restored=await inspect();assert(Math.abs(restored.corners[0][0]-wide.corners[0][0])<.001,'resize does not accumulate camera zoom');
  if(harmony){
   const cdp=await page.context().newCDPSession(page),before=await page.evaluate(()=>__parkQA.camera.position.toArray());
   await cdp.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[{x:520,y:340,id:1}]});for(let i=1;i<=8;i++)await cdp.send('Input.dispatchTouchEvent',{type:'touchMove',touchPoints:[{x:520+i*12,y:340,id:1}]});await cdp.send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});await page.waitForTimeout(500);
   assert.notDeepEqual(await page.evaluate(()=>__parkQA.camera.position.toArray()),before,'single finger rotates island');
   const distance=()=>page.evaluate(()=>__parkQA.camera.position.distanceTo(__parkQA.controls.target));const oldDistance=await distance();
   await cdp.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[{x:520,y:340,id:1},{x:680,y:340,id:2}]});for(let i=1;i<=6;i++)await cdp.send('Input.dispatchTouchEvent',{type:'touchMove',touchPoints:[{x:520-i*8,y:340,id:1},{x:680+i*8,y:340,id:2}]});await cdp.send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});assert(await distance()<oldDistance,'two fingers zoom');
  }
  assert.deepEqual(errors,[]);console.log(JSON.stringify({passed:'cloud clearance, sky clipping, desktop/mobile framing, reduced motion, cached-template dependency recovery',output}));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1});
