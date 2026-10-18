const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');const path=require('node:path');
(async()=>{
 const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
 const out=fs.mkdtempSync(path.join(require('node:os').tmpdir(),'pait-habit-review-'));
 try{const page=await browser.newPage({viewport:{width:1360,height:960}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('http://127.0.0.1:5058/__qa/tangyuan');
  await page.locator('#studio-create input[name=name]').fill('习惯分析测试');await page.locator('#studio-create button').click();
  await page.waitForFunction(()=>document.getElementById('memory-files')&&!document.getElementById('memory-files').disabled);
  const png=Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=','base64');
  await page.locator('#memory-files').setInputFiles({name:'sample.png',mimeType:'image/png',buffer:png});
  await page.waitForFunction(()=>document.getElementById('memory-status').textContent.includes('1 / 1'));
  await page.locator('#habit-analyze').click();assert((await page.locator('#memory-status').innerText()).includes('勾选'));
  await page.locator('#habit-consent').check();await page.locator('#habit-analyze').click();
  await page.waitForFunction(()=>document.querySelectorAll('.habit-event').length===1&&!document.getElementById('habit-analyze').disabled);
  const event=page.locator('.habit-event');assert.equal(await page.locator('#habit-candidates article').count(),0);
  await event.getByRole('button',{name:'确认这个事件'}).click();assert((await page.locator('#memory-status').innerText()).includes('核对'));
  await event.locator('input[type=checkbox]').last().check();await event.getByRole('button',{name:'确认这个事件'}).click();
  await page.locator('#habit-candidates article').waitFor();await page.waitForFunction(()=>!document.querySelector('#habit-candidates button').disabled);
  await page.locator('#habit-candidates button').click();await page.getByRole('button',{name:'已应用，点击撤回'}).waitFor();
  await page.locator('#habit-events').scrollIntoViewIfNeeded();await page.screenshot({path:path.join(out,'desktop.png')});
  await page.setViewportSize({width:430,height:932});await page.screenshot({path:path.join(out,'mobile.png')});
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
  await event.getByRole('button',{name:'撤回事件'}).click();await page.waitForFunction(()=>document.querySelectorAll('#habit-candidates article').length===0);
  assert.deepEqual(errors,[]);console.log('PASS consent, event review, apply, revoke and mobile layout; screenshots '+out);
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1});
