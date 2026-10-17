/* Run desktop_transfer_server.py first. Real main process + WebGL + island callbacks. */
const {chromium,_electron}=require('playwright'),assert=require('node:assert/strict'),path=require('node:path'),fs=require('node:fs'),os=require('node:os');
const base=process.env.PET_TEST_BASE||'http://127.0.0.1:5091';
const output=fs.mkdtempSync(path.join(os.tmpdir(),'pait-transfer-'));
async function until(test,timeout=60000){const end=Date.now()+timeout;while(Date.now()<end){if(await test())return;await new Promise(r=>setTimeout(r,100));}throw Error('Timed out waiting for desktop phase');}
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.PET_TEST_CHROME||'C:/Program Files/Google/Chrome/Application/chrome.exe',args:['--enable-webgl','--ignore-gpu-blocklist']});let app;
 try{
  const page=await browser.newPage({viewport:{width:1280,height:850}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(base+'/__qa/login');await page.waitForFunction(()=>window.__den?.petModel?.userData.accessories?.length===2,null,{timeout:90000});
  await page.evaluate(async()=>{const d=await(await fetch('/api/portals')).json();for(const t of d.trips.filter(t=>t.mine&&['pairing','active'].includes(t.status)))await fetch('/api/portals/return',{method:'POST',headers:{'Content-Type':'application/json','X-Profile-Scope':d.scope},body:JSON.stringify({trip:t.id})});});
  await page.waitForTimeout(2200);
  await page.locator('[data-dock-panel="dock-actions"]').click();await page.locator('#btn-portals').click();await page.locator('[data-kind=desktop]').click();
  await page.waitForFunction(()=>!document.querySelector('[data-confirm]').disabled,null,{timeout:90000});await page.locator('[data-confirm]').click();
  await page.waitForFunction(()=>document.querySelector('[data-pair] code')?.textContent);const code=await page.locator('[data-pair] code').innerText();
  const env={...process.env};delete env.ELECTRON_RUN_AS_NODE;
  app=await _electron.launch({executablePath:process.env.PET_TEST_ELECTRON||path.resolve('desktop/node_modules/electron/dist/electron.exe'),args:[path.resolve('desktop'),'--user-data-dir='+path.join(output,'profile')],env,timeout:30000});
  for(const p of app.windows()){p.on('pageerror',e=>console.error('Electron page error:',e.message));p.on('console',m=>{if(m.type()==='error')console.error('Electron:',m.text());});}
  const control=app.windows().find(p=>p.url().endsWith('/index.html'))||await app.waitForEvent('window',{predicate:p=>p.url().endsWith('/index.html')});await control.waitForFunction(()=>!!window.paitDesktop);
  await app.evaluate(()=>{globalThis.transferTestFetch=globalThis.fetch;globalThis.fetch=async(...args)=>{if(String(args[0]).includes('/wardrobe-v1/'))await new Promise(r=>setTimeout(r,2000));return globalThis.transferTestFetch(...args);};});
  await control.locator('#origin').fill(base);await control.locator('#code').fill(code);await control.locator('#pair button').click();
  await until(async()=>await control.evaluate(async()=>(await paitDesktop.command('state')).phase==='preparing'));
  assert(await page.evaluate(()=>__den.petModel.visible),'island stays visible during preparation');
  await until(async()=>await control.evaluate(async()=>(await paitDesktop.command('state')).phase==='emerging'));
  console.log('Control phase:',await control.evaluate(async()=>(await paitDesktop.command('state')).phase));
  const petPage=app.windows().find(p=>p.url().endsWith('/pet.html'));assert(petPage);
  assert.equal(await petPage.evaluate(()=>pet.root.userData.accessories.length),2,'both real GLB accessories loaded via IPC');
  await petPage.waitForFunction(()=>crossing?.age>1.7&&crossing?.age<2.2);await petPage.screenshot({path:path.join(output,'emerging.png')});
  await until(async()=>await control.evaluate(async()=>(await paitDesktop.command('state')).phase==='roaming'),30000);
  await page.waitForFunction(()=>!__den.petModel.visible);
  const stats=await petPage.evaluate(()=>({calls:renderer.info.render.calls,triangles:renderer.info.render.triangles,accessories:pet.root.userData.accessories.length,clipped:pet.model.getObjectByProperty('isSkinnedMesh',true)?.material.clippingPlanes?.length||0}));
  assert(stats.calls>0&&stats.triangles>0);assert.equal(stats.clipped,0);
  await petPage.screenshot({path:path.join(output,'roaming.png')});
  const connectedState=await control.evaluate(()=>paitDesktop.command('state'));
  assert(Number.isFinite(connectedState.expiresAt));
  assert.match(await control.locator('#deadline').innerText(),/最迟返程/);
  // Exercise real main.js request handling: an application conflict, including a
  // legacy uncoded 409, must not recall the pet. Server-side recall must do so.
  for(const code of ['FOCUS_CONFLICT','REQUEST_CONFLICT',null]){
   await app.evaluate((_,code)=>{globalThis.conflictCount=0;globalThis.fetch=async(...args)=>{
    if(String(args[0]).endsWith('/ping')){globalThis.conflictCount++;return Response.json({error:'测试业务冲突',...(code?{code}:{})},{status:409});}
    return globalThis.transferTestFetch(...args);
   };},code);
   await until(async()=>await app.evaluate(()=>globalThis.conflictCount>0));
   assert.equal((await control.evaluate(()=>paitDesktop.command('state'))).connected,true);
   assert.equal((await control.evaluate(()=>paitDesktop.command('state'))).trip,connectedState.trip);
  }
  await app.evaluate(()=>{globalThis.fetch=globalThis.transferTestFetch;});
  await page.evaluate(async trip=>{const d=await(await fetch('/api/portals')).json();const r=await fetch('/api/portals/return',{method:'POST',headers:{'Content-Type':'application/json','X-Profile-Scope':d.scope},body:JSON.stringify({trip})});if(!r.ok)throw Error('Recall failed');},connectedState.trip);
  await until(async()=>await control.evaluate(async()=>!(await paitDesktop.command('state')).connected));await page.waitForFunction(()=>__den.petModel.visible);
  assert.deepEqual(errors,[]);
  // A failed equipped asset must never acknowledge ready or hide the island pet.
  await app.evaluate(()=>{const original=globalThis.fetch;globalThis.fetch=async(...args)=>String(args[0]).includes('/wardrobe-v1/')?new Response('unavailable',{status:503}):original(...args);});
  await page.locator('[data-kind=desktop]').click();await page.waitForFunction(()=>!document.querySelector('[data-confirm]').disabled,null,{timeout:60000});await page.locator('[data-confirm]').click();await page.waitForFunction(()=>document.querySelector('[data-pair] code')?.textContent);
  await control.locator('#code').fill(await page.locator('[data-pair] code').innerText());await control.locator('#pair button').click();
  await until(async()=>await control.evaluate(async()=>(await paitDesktop.command('state')).connected));await until(async()=>await control.evaluate(async()=>!(await paitDesktop.command('state')).connected),30000);
  assert(await page.evaluate(()=>__den.petModel.visible));
  // Cancel while bytes are in flight. Their late completion must not activate a trip.
  await app.evaluate(()=>{globalThis.transferReadyCount=0;globalThis.fetch=async(...args)=>{if(String(args[0]).endsWith('/ready'))globalThis.transferReadyCount++;if(String(args[0]).endsWith('.glb'))await new Promise(r=>setTimeout(r,3000));return globalThis.transferTestFetch(...args);};});
  await page.waitForTimeout(2200);
  await page.locator('[data-kind=desktop]').click();await page.waitForFunction(()=>!document.querySelector('[data-confirm]').disabled,null,{timeout:60000});await page.locator('[data-confirm]').click();await page.waitForFunction(()=>document.querySelector('[data-pair] code')?.textContent);
  await control.locator('#code').fill(await page.locator('[data-pair] code').innerText());await control.locator('#pair button').click();await until(async()=>await control.evaluate(async()=>(await paitDesktop.command('state')).phase==='preparing'));
  await control.locator('#return').click();await until(async()=>await control.evaluate(async()=>!(await paitDesktop.command('state')).connected));await page.waitForTimeout(3500);
  assert.equal(await app.evaluate(()=>globalThis.transferReadyCount),0);assert(await page.evaluate(()=>__den.petModel.visible));
  console.log(JSON.stringify({passed:'Actual island approach, slow preparation, IPC wardrobe, entry acknowledgement, desktop emerging/settling, deadline, business/legacy conflicts without recall, server recall, accessory failure rollback, cancellation with bytes in flight',stats,output},null,2));
 }finally{if(app)await app.close();await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1});
