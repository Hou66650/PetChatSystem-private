// Run the isolated loopback test/park_review_server.py fixture first.
const {chromium}=require('playwright'),assert=require('node:assert/strict');
const nav=require('../static/js/park-navigation.js').create(require('../static/models/paw-commons-v2/navigation.json'));
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.PET_TEST_CHROME||'C:/Program Files/Google/Chrome/Application/chrome.exe',args:['--enable-webgl','--ignore-gpu-blocklist']});
 try{
  const page=await browser.newPage({viewport:{width:1440,height:1050}}),errors=[],sync=[];let fail=true;
  page.on('pageerror',e=>errors.push(e.message));
  // Read the actual camera; page layout/controls may adjust it after startup.
  await page.route('**/static/js/public-park.js*',async route=>{const response=await route.fetch(),source=await response.text();assert(source.includes('const self={x:0,z:0,yaw:0};'));await route.fulfill({response,body:source.replace('const self={x:0,z:0,yaw:0};','const self={x:0,z:0,yaw:0};window.__parkTestCamera=camera;').replace('function destination(p,message,fromOwner=true){','function destination(p,message,fromOwner=true){window.__parkPicked={...p};')});});
  await page.route('**/static/models/paw-commons-v2/play.glb*',route=>fail?route.abort():route.continue());
  await page.goto('http://127.0.0.1:5088/__qa/park-a');
  await page.waitForFunction(()=>document.querySelector('#pet-park').dataset.scene==='failed');
  assert(await page.locator('#park-join').isDisabled());assert(await page.locator('#park-retry').isVisible());
  fail=false;await page.locator('#park-retry').click();await page.waitForFunction(()=>document.querySelector('#pet-park').dataset.scene==='ready',null,{timeout:30000});
  await page.locator('#park-join').click();await page.locator('#park-auto').click();await page.waitForTimeout(6500);
  const snapshot=async()=> (await (await page.request.get('http://127.0.0.1:5088/api/park')).json()).players.find(p=>p.mine);
  const start=await snapshot();assert(start);
  const target=nav.nearest({x:.6-start.x,z:-1.6-start.z});assert(!nav.segment(start,target),'journey must cross the tree without routing');
  const point=await page.evaluate(target=>{
   const r=document.querySelector('#park-canvas').getBoundingClientRect(),camera=window.__parkTestCamera;
   const v=new THREE.Vector3(target.x,0,target.z).project(camera);return {x:r.left+(v.x+1)*r.width/2,y:r.top+(1-v.y)*r.height/2};
  },target);
  assert.equal(await page.evaluate(p=>document.elementFromPoint(p.x,p.y)?.id,point),'park-canvas');
  page.on('response',r=>{if(r.url().endsWith('/api/park/sync'))sync.push(r.status());});
  await page.mouse.click(point.x,point.y);
  const picked=await page.evaluate(()=>window.__parkPicked);
  assert(picked&&Math.hypot(picked.x-target.x,picked.z-target.z)<.05,'focusing canvas preserves pointer destination');
  let prior=start,reached=false,samples=0;
  for(let i=0;i<60;i++){
   await page.waitForTimeout(500);const p=await snapshot();assert(p,'presence retained');assert(nav.inside(p.x,p.z));assert(nav.segment(prior,p),'server samples stay outside the bed');prior=p;samples++;
   if(Math.hypot(p.x-target.x,p.z-target.z)<.3){reached=true;break;}
  }
  if(!reached)console.error({start:{x:start.x,z:start.z},target,last:{x:prior.x,z:prior.z},sync,status:await page.locator('#park-status').textContent()});
  assert(reached,'click destination reached by routing around central tree');assert(sync.length>2);assert(sync.every(s=>s===200),'no collision or resync errors');
  await page.locator('#park-leave').click();
  const conditional=[];page.on('request',r=>{if(r.url().includes('/paw-commons-v2/play.glb'))conditional.push(r.headers()['if-none-match']);});
  await page.reload();await page.waitForFunction(()=>document.querySelector('#pet-park').dataset.scene==='ready',null,{timeout:30000});
  assert(conditional.some(Boolean),'IndexedDB warm load revalidates the stored model');
  assert.deepEqual(errors,[]);console.log('PASS runtime failure/retry, client routing with server validation ('+samples+' samples), persistent cache revalidation');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
