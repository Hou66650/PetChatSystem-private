// The device must already show /park in ArkWeb. This only tests viewing, not account actions.
const {chromium}=require('playwright'),assert=require('node:assert/strict'),fs=require('node:fs'),os=require('node:os'),path=require('node:path');
(async()=>{
 const browser=await chromium.connectOverCDP(process.env.PET_DEVICE_CDP||'http://127.0.0.1:9223'),output=fs.mkdtempSync(path.join(os.tmpdir(),'pait-harmony-park-'));
 const page=browser.contexts()[0].pages().find(p=>new URL(p.url()).pathname==='/park');assert(page,'Open the park on the tablet first');let cdp;
 const pattern='**/static/js/public-park.js*',errors=[];page.on('pageerror',e=>errors.push(e.message));
 try{
  cdp=await page.context().newCDPSession(page);await cdp.send('Network.enable');await cdp.send('Network.setCacheDisabled',{cacheDisabled:true});
  await page.route(pattern,async route=>{const url=new URL(route.request().url());const response=await fetch((process.env.PET_DEVICE_HOST_BASE||'http://127.0.0.1:5008')+url.pathname+url.search),source=await response.text();assert(source.includes('const self={x:0,z:0,yaw:0};'));await route.fulfill({contentType:'application/javascript',body:source.replace('const self={x:0,z:0,yaw:0};',`const self={x:0,z:0,yaw:0};window.__parkQA={camera,atmosphere,renderer,controls,frames:0};const draw=renderer.render.bind(renderer);renderer.render=(...args)=>{window.__parkQA.frames++;return draw(...args);};`)});});
  await page.reload({waitUntil:'domcontentloaded',timeout:60000});await page.waitForFunction(()=>document.querySelector('#pet-park')?.dataset.scene==='ready',null,{timeout:60000});
  const info=()=>page.evaluate(()=>({ua:navigator.userAgent,profile:document.querySelector('#pet-park').dataset.renderProfile,viewport:[innerWidth,innerHeight],pixels:__parkQA.renderer.domElement.width*__parkQA.renderer.domElement.height,clouds:__parkQA.atmosphere.clouds.length,antialias:__parkQA.renderer.getContext().getContextAttributes().antialias,camera:__parkQA.camera.position.toArray(),distance:__parkQA.camera.position.distanceTo(__parkQA.controls.target),frames:__parkQA.frames}));
  const before=await info();assert.equal(before.profile,'harmony');assert.equal(before.clouds,2);assert(before.pixels<=900000);assert.equal(before.antialias,false);
  const [w,h]=before.viewport,x=w*.43,y=h*.42;
  await cdp.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[{x,y,id:1}]});for(let i=1;i<=8;i++)await cdp.send('Input.dispatchTouchEvent',{type:'touchMove',touchPoints:[{x:x+i*12,y,id:1}]});await cdp.send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});await page.waitForTimeout(600);const rotated=await info();assert.notDeepEqual(rotated.camera,before.camera);
  await cdp.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[{x,y,id:1},{x:x+140,y,id:2}]});for(let i=1;i<=6;i++)await cdp.send('Input.dispatchTouchEvent',{type:'touchMove',touchPoints:[{x:x-i*8,y,id:1},{x:x+140+i*8,y,id:2}]});await cdp.send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});assert((await info()).distance<rotated.distance);
  await page.waitForTimeout(1200);const start=await info();await page.waitForTimeout(5000);const end=await info();assert(end.frames>start.frames,'actual ArkWeb render keeps updating');
  const button=page.locator('.park-help summary');if(await button.count()){const tap=async()=>{const r=await button.boundingBox();await cdp.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[{x:r.x+r.width/2,y:r.y+r.height/2,id:1}]});await cdp.send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});};await tap();assert(await page.locator('.park-help').evaluate(e=>e.open));await tap();}
  assert.deepEqual(errors,[]);fs.writeFileSync(path.join(output,'report.json'),JSON.stringify({before,after:end,idleDrawsInFiveSeconds:end.frames-start.frames,touchRotate:true,touchPinch:true,errors},null,2));
  console.log(JSON.stringify({passed:'real ArkWeb cloud budget, single-finger rotation, two-finger zoom and touch controls',output,idleDrawsInFiveSeconds:end.frames-start.frames}));
 }finally{
  await page.unroute(pattern);if(cdp){await cdp.send('Network.setCacheDisabled',{cacheDisabled:false});await cdp.detach();}
  // Restore the production source, default view, and a usable page after instrumentation.
  await page.reload({waitUntil:'domcontentloaded',timeout:60000});await page.waitForFunction(()=>document.querySelector('#pet-park')?.dataset.scene==='ready',null,{timeout:60000});await page.waitForTimeout(1200);await page.screenshot({path:path.join(output,'device.png')});await browser.close();
 }
})().catch(e=>{console.error(e);process.exitCode=1});
