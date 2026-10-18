// Against test/imprint_review_server.py: temporary account and deterministic vision double.
const {chromium}=require('playwright'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),os=require('node:os');
const base=process.env.PET_IMPRINT_BASE||'http://127.0.0.1:5094',out=fs.mkdtempSync(path.join(os.tmpdir(),'studio-memories-'));
(async()=>{const browser=await chromium.launch({executablePath:process.env.PET_TEST_CHROME||'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
try{
 const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto(base+'/__qa/tangyuan');await page.locator('#studio-existing-frame').waitFor();
 const legacy=page.frameLocator('#studio-existing-frame');await legacy.locator('#policy').getByText(/记忆已开启/).waitFor();
 await page.locator('#studio-create input[name=name]').fill('回忆整合测试');await page.locator('#studio-create button').click();
 await page.locator('#studio-name').getByText('回忆整合测试').waitFor();assert(await page.locator('#studio-memories').isVisible());assert(!(await page.locator('#studio-appearance').isVisible()));
 const png=Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=','base64');
 await page.locator('#memory-files').setInputFiles([{name:'example.png',mimeType:'image/png',buffer:png},{name:'duplicate.png',mimeType:'image/png',buffer:png},{name:'invalid.mp4',mimeType:'video/mp4',buffer:Buffer.from('invalid media')}]);
 await page.waitForFunction(()=>document.getElementById('memory-status').textContent.includes('2 / 3'));
 assert.equal(await page.locator('.memory-tile').count(),1);
 await page.locator('#memory-analyze').click();assert((await page.locator('#memory-status').textContent()).includes('勾选'));assert.equal(await page.locator('.memory-card').count(),0);
 await page.locator('#memory-consent').check();await page.locator('#memory-analyze').click();await page.locator('.memory-card').waitFor();await page.waitForFunction(()=>!document.getElementById('memory-analyze').disabled);
 let card=page.locator('.memory-card').first();await card.locator('textarea').fill('测试主人确认：它喜欢安静坐在身旁。');await card.locator('select').nth(0).selectOption('comfort');await card.locator('select').nth(1).selectOption('sit');await card.locator('input[type=checkbox]').check();await card.getByRole('button',{name:'确认并应用',exact:true}).click();
 await page.waitForFunction(()=>document.querySelector('.memory-card h4')?.textContent.includes('已应用'));
 let data=await(await page.request.get(base+'/api/pet-imprint/1')).json();assert.equal(data.policy.responses.comfort.action,'sit');
 await page.locator('#studio-tab-model').click();assert(await page.locator('#studio-appearance').isVisible());assert(!(await page.locator('#studio-memories').isVisible()));await page.locator('#studio-tab-memories').click();
 await page.screenshot({path:path.join(out,'desktop.png'),fullPage:true});await page.setViewportSize({width:430,height:932});
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);await page.locator('#studio-memories').scrollIntoViewIfNeeded();await page.screenshot({path:path.join(out,'mobile.png')});
 await page.locator('.memory-card').getByRole('button',{name:'撤回应用'}).click();await page.waitForFunction(()=>document.querySelector('.memory-card h4')?.textContent.includes('待主人'));
 data=await(await page.request.get(base+'/api/pet-imprint/1')).json();assert.equal(data.policy.responses.comfort,undefined);
 page.on('dialog',d=>d.accept());await page.locator('.memory-tile').getByRole('button',{name:'删除素材'}).click();await page.waitForFunction(()=>document.querySelectorAll('.memory-tile').length===0);assert.equal(await page.locator('.memory-card').count(),0);
 assert.deepEqual(errors,[]);console.log(JSON.stringify({ok:true,out,checks:['old memories embedded','batch partial failure and dedupe','explicit analysis consent','draft review','runtime policy','withdraw','source delete','mobile layout']}));
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1;});
