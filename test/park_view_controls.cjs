// Run the isolated park_review_server.py fixture; no real account or device required.
const {chromium}=require('playwright'),assert=require('node:assert/strict');
const base=process.env.PET_TEST_BASE||'http://127.0.0.1:5088';
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.PET_TEST_CHROME||'C:/Program Files/Google/Chrome/Application/chrome.exe'});
 try{
  const page=await browser.newPage({viewport:{width:1245,height:756}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(base+'/__qa/park-b');await page.waitForFunction(()=>document.querySelector('#pet-park').dataset.scene==='ready',null,{timeout:60000});
  await page.locator('#park-join').click();await page.waitForFunction(()=>document.querySelector('#park-leave')?.hidden===false);
  const presence=async()=>{const r=await page.request.get(base+'/api/park');return (await r.json()).players.find(p=>p.mine);};const original=await presence();assert(original);
  await page.locator('#park-visibility').click();assert(await page.locator('.park-dock').isHidden());assert(await page.locator('.navbar').isHidden());assert(await page.locator('#park-visibility').isVisible());assert.equal(await page.locator('#park-visibility').textContent(),'显示界面');
  assert.equal(await page.locator('#park-canvas').evaluate(e=>e.getBoundingClientRect().top),0);assert.equal((await presence()).id,original.id,'hiding presentation must retain the current park session');
  await page.locator('#park-visibility').click();assert(await page.locator('.park-dock').isVisible());
  await page.locator('#park-fullscreen').click();await page.waitForFunction(()=>document.fullscreenElement?.id==='pet-park');assert.equal(await page.locator('#park-fullscreen').textContent(),'退出全屏');
  await page.locator('#park-visibility').click();assert(await page.locator('#park-fullscreen').isHidden());await page.locator('#park-visibility').click();await page.locator('#park-fullscreen').click();await page.waitForFunction(()=>!document.fullscreenElement);assert(await page.locator('.navbar').isVisible());
  await page.evaluate(()=>{document.getElementById('pet-park').requestFullscreen=()=>Promise.reject(new Error('simulated denial'));});
  await page.locator('#park-fullscreen').click();assert.equal(await page.locator('#park-fullscreen').textContent(),'退出铺满');assert(await page.locator('.park-view-message').isVisible());await page.keyboard.press('Escape');assert.equal(await page.locator('#park-fullscreen').textContent(),'全屏');
  await page.setViewportSize({width:430,height:932});await page.locator('#park-visibility').click();const box=await page.locator('#park-visibility').boundingBox();assert(box.x>=0&&box.y>=0&&box.x+box.width<=430&&box.y+box.height<=932,'restore button stays on screen');await page.keyboard.press('Escape');assert(await page.locator('.park-dock').isVisible());
  assert.equal((await presence()).id,original.id);await page.locator('#park-leave').click();assert.deepEqual(errors,[]);console.log('PASS fullscreen/exit, UI hide/restore, retained presence, denial fallback, Escape and narrow-screen recovery');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1});
