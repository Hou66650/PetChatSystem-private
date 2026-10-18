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
  assert.equal(connectedState.chatEnabled,true);assert.equal(connectedState.voiceEnabled,true);
  assert.equal(connectedState.token,undefined,'bearer never reaches renderer');
  assert.match((await control.evaluate(()=>paitDesktop.command('model',{trip:'forged'}))).error,/变化/);
  assert.match((await control.evaluate(()=>paitDesktop.command('model'))).error,/仅宠物/);
  assert.match((await petPage.evaluate(()=>paitDesktop.command('chat',{message:'forged'}))).error,/控制台/);
  await control.locator('#message').fill('你好，桌面上的伙伴');await control.locator('#send').click();
  await control.getByText('柴犬：我在桌面陪你。',{exact:false}).waitFor();
  await control.getByRole('button',{name:'用它的声音朗读',exact:true}).click();
  await control.waitForFunction(()=>audio!==null&&!audio.paused);await control.locator('#stop-audio').click();
  assert.equal(await control.evaluate(()=>audio),null);
  assert.notEqual((await control.evaluate(()=>paitDesktop.command('state'))).reaction,'success');
  await control.screenshot({path:path.join(output,'chat.png')});
  // Real UI -> durable approval -> server clock -> main-process OS notification.
  await control.locator('#tool-title').fill('派特岛测试提醒');await control.locator('#tool-duration').fill('10');await control.locator('#tool-unit').selectOption('1');await control.locator('#tool-propose').click();
  const reminder=control.locator('.task-card').filter({hasText:'派特岛测试提醒'});
  await reminder.getByRole('button',{name:'批准并执行',exact:true}).waitFor();
  assert.match(await reminder.innerText(),/等待你的批准/);assert.doesNotMatch(await reminder.innerText(),/设置成功/);
  await reminder.getByRole('button',{name:'批准并执行',exact:true}).click();await reminder.getByText('任务：设置成功',{exact:true}).waitFor();
  await until(async()=>await reminder.innerText().then(text=>text.includes('提醒已到点')&&/系统报告已显示|通知结果未知|系统不支持通知/.test(text)),30000);
  const notificationResult=await reminder.innerText();console.log('OS delivery result:',notificationResult);
  // Natural language creates only a pending card. Rejection cannot start a timer.
  await control.locator('#message').fill('专注1分钟');await control.locator('#send').click();
  const focus=control.locator('.task-card').filter({hasText:'专注时间'});await focus.getByRole('button',{name:'拒绝',exact:true}).click();await focus.getByText('任务：审批已取消',{exact:true}).waitFor();
  await control.locator('#tool-kind').selectOption('focus_timer.start');await control.locator('#tool-title').fill('派特岛测试专注');await control.locator('#tool-propose').click();
  const timer=control.locator('.task-card').filter({hasText:'派特岛测试专注'});await timer.getByRole('button',{name:'批准并执行',exact:true}).click();await timer.getByText('任务：设置成功',{exact:true}).waitFor();
  const remaining=timer.locator('[data-due]');await remaining.waitFor();const initialRemaining=await remaining.textContent();assert.match(initialRemaining,/剩余 00:/);
  await until(async()=>await remaining.textContent()!==initialRemaining,4000);await control.screenshot({path:path.join(output,'focus-timer.png')});
  await timer.getByRole('button',{name:'取消计时',exact:true}).click();await timer.getByText('效果：效果已取消',{exact:true}).waitFor();
  await control.screenshot({path:path.join(output,'tasks.png')});
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
  assert.equal(await control.locator('#messages').innerText(),'');
  assert.deepEqual(errors,[]);
  // Corrupt valid GLB bytes in transit: hash mismatch must recall before ready.
  await app.evaluate(()=>{globalThis.badHashDownloads=0;globalThis.fetch=async(...args)=>{
   const response=await globalThis.transferTestFetch(...args);
   if(String(args[0]).endsWith('.glb')){const bytes=new Uint8Array(await response.arrayBuffer());bytes[bytes.length-1]^=1;globalThis.badHashDownloads++;return new Response(bytes,{status:200});}
   return response;
  };});
  await page.locator('[data-kind=desktop]').click();await page.waitForFunction(()=>!document.querySelector('[data-confirm]').disabled,null,{timeout:60000});await page.locator('[data-confirm]').click();await page.waitForFunction(()=>document.querySelector('[data-pair] code')?.textContent);
  await control.locator('#code').fill(await page.locator('[data-pair] code').innerText());await control.locator('#pair button').click();
  await until(async()=>await app.evaluate(()=>globalThis.badHashDownloads>0));
  await until(async()=>await control.evaluate(async()=>!(await paitDesktop.command('state')).connected));
  assert(await page.evaluate(()=>__den.petModel.visible));
  // A failed equipped asset must never acknowledge ready or hide the island pet.
  await app.evaluate(()=>{globalThis.fetch=async(...args)=>String(args[0]).includes('/wardrobe-v1/')?new Response('unavailable',{status:503}):globalThis.transferTestFetch(...args);});
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
  console.log(JSON.stringify({passed:'Actual island approach, slow preparation, IPC wardrobe, entry acknowledgement, desktop emerging/settling, chat and original-voice playback, approvals, reminder due and OS receipt, focus rejection and cancellation, IPC role isolation, deadline, business/legacy conflicts without recall, server recall, hash mismatch, accessory failure rollback, cancellation with bytes in flight',stats,output},null,2));
 }finally{if(app)await app.close();await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1});
