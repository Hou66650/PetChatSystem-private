/* Same touch UI and action ownership on desktop Web and ArkWeb; no paid API calls. */
const {chromium}=require('playwright'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),os=require('node:os');
const A=require('../static/js/den/action-catalog');
(async()=>{
 const device=process.env.PET_DEVICE_CDP;
 const browser=device?await chromium.connectOverCDP(device):await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',args:['--enable-webgl','--ignore-gpu-blocklist']});
 const out=fs.mkdtempSync(path.join(os.tmpdir(),'pait-actions-tablet-'));let page;
 try{
  page=device?browser.contexts()[0].pages()[0]:await browser.newPage({viewport:{width:1280,height:800},hasTouch:true,isMobile:true,userAgent:'Mozilla/5.0 (Linux; OpenHarmony 6.1) AppleWebKit/537.36 Chrome/132.0.0.0 Mobile Safari/537.36 ArkWeb/4.1.6'});
  assert(page);const errors=[];page.on('pageerror',e=>{errors.push(e.message);console.error('PAGE ERROR',e.message);});page.setDefaultTimeout(30000);
  if(!device)await page.goto('http://127.0.0.1:5091/__qa/login');
  else if(!page.url().includes('/den'))await page.goto(new URL('/den?pet=3',page.url()).href);
  await page.waitForFunction(()=>window.__den?.petModel&&window.__denAnimDebug?.()?.scale==='1.000',null,{timeout:120000});
  const tap=async selector=>{const element=page.locator(selector);await element.scrollIntoViewIfNeeded();if(device){const cdp=await page.context().newCDPSession(page),r=await element.boundingBox();await cdp.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[{x:r.x+r.width/2,y:r.y+r.height/2,id:1}]});await cdp.send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});await cdp.detach();}else await element.tap();};
  const open=async()=>{if(await page.locator('#dock-actions').isHidden())await tap('[data-dock-panel="dock-actions"]');await tap('#btn-shiba-acting');await page.waitForFunction(()=>document.getElementById('shiba-acting-dialog').open);};
  const report={device:!!device,pets:[],actions:[],errors};
  for(const pet of device?[3]:process.env.PET_ACTION_PETS?process.env.PET_ACTION_PETS.split(',').map(Number):[1,2,3,4]){
   if(await page.evaluate(id=>!__denLocomotionDebug()||__denLocomotionDebug().petId!==id,pet)){await page.evaluate(id=>__den.spawnPet(id),pet);await page.waitForFunction(id=>__denLocomotionDebug()?.petId===id&&__denAnimDebug().scale==='1.000',pet,{timeout:120000});}
   await open();
   const available=await page.locator('[data-companion-action]:enabled').evaluateAll(nodes=>nodes.map(n=>n.dataset.companionAction));
   assert.equal(available.length,30);report.pets.push({pet,available});
   await tap('#shiba-acting-dialog form button');
   // Every stationary action uses real touch controls and the actual model's clip.
   for(const a of A.catalog.filter(a=>a.id!=='walk')){
    await open();await tap('[data-companion-action="'+a.id+'"]');
    const key=A.denKey(a.id);
    await page.waitForFunction(key=>__denAnimDebug().state===key,key);
    if(a.enter)await page.waitForFunction(name=>__denAnimDebug().active.split('|').pop()===name,a.clips[0]);
    else if(!a.loop)await page.waitForFunction(names=>names.includes(__denAnimDebug().active?.split('|').pop()),a.clips);
    report.actions.push({pet,id:a.id,...await page.evaluate(()=>__denAnimDebug())});
   }
   await open();await tap('[data-companion-action="sleep"]');await page.waitForFunction(()=>__denAnimDebug().active?.endsWith('sleep_loop'));
   for(const id of ['walk','run','trot']){
    await open();const start=await page.evaluate(()=>({x:__den.petModel.position.x,z:__den.petModel.position.z}));await tap('[data-companion-action="'+id+'"]');await page.waitForFunction(()=>['walk','run','trot','turnLeft','turnRight'].includes(__denAnimDebug().state));
    await page.waitForFunction(s=>Math.hypot(__den.petModel.position.x-s.x,__den.petModel.position.z-s.z)>.1,start);
    if(await page.locator('#dock-actions').isHidden())await tap('[data-dock-panel="dock-actions"]');await tap('#btn-companion-stop');await page.waitForFunction(()=>__denAnimDebug().state==='idle');
   }
   console.log('PASS touch actions, posture transitions and locomotion for pet '+pet);
  }
  await open();await page.screenshot({path:path.join(out,'actions.png')});await tap('#shiba-acting-dialog form button');
  if(await page.locator('#dock-actions').isHidden())await tap('[data-dock-panel="dock-actions"]');await tap('#btn-companion-stop');assert.deepEqual(errors,[]);fs.writeFileSync(path.join(out,'report.json'),JSON.stringify(report,null,2));console.log(out);
 }catch(error){if(page){console.log(await page.evaluate(()=>({anim:window.__denAnimDebug?.(),motion:window.__denLocomotionDebug?.(),status:document.getElementById('dialogue-status')?.textContent})));await page.screenshot({path:path.join(out,'failure.png')}).catch(()=>{});console.log(out);}throw error;}finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
