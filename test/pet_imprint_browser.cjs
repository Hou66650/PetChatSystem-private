// Uses test/imprint_review_server.py only. No production account or private clip is confirmed.
const {chromium}=require('playwright'),assert=require('node:assert/strict'),fs=require('node:fs'),os=require('node:os'),path=require('node:path');
const base=process.env.PET_IMPRINT_BASE||'http://127.0.0.1:5094',out=fs.mkdtempSync(path.join(os.tmpdir(),'pait-imprint-review-'));
(async()=>{const browser=await chromium.launch({headless:true,executablePath:process.env.PET_TEST_CHROME||'C:/Program Files/Google/Chrome/Application/chrome.exe'});let page,created=[];
 try{page=await browser.newPage({viewport:{width:1400,height:900}});const errors=[];page.on('pageerror',e=>errors.push(e.message));await page.goto(base+'/__qa/tangyuan');await page.waitForFunction(()=>document.querySelectorAll('.card').length>=3);
  assert(await page.locator('#policy').textContent());
  await page.locator('#kind').selectOption('greeting');await page.locator('#value').selectOption('sit');await page.locator('#quote').fill('测试样本：坐在身边等待主人。');await page.locator('#form button[type=submit]').click();await page.waitForFunction(()=>[...document.querySelectorAll('.card')].some(e=>e.textContent.includes('测试样本')));
  const card=page.locator('.card').filter({hasText:'测试样本'});assert((await card.textContent()).includes('待确认'));await card.locator('input[type=checkbox]').check();await card.getByRole('button',{name:'确认并启用'}).click();await page.waitForFunction(()=>[...document.querySelectorAll('.card')].some(e=>e.textContent.includes('测试样本')&&e.textContent.includes('已确认')));
  const state=await(await page.request.get(base+'/api/pet-imprint/1')).json();created=state.cards.filter(c=>c.evidence.quote.startsWith('测试样本')).map(c=>c.id);assert.equal(state.policy.responses.greeting.action,'sit');assert.equal(state.policy.vocality,'quiet');
  await page.screenshot({path:path.join(out,'memory-cards.png'),fullPage:true});
  await page.locator('#calls').click();await page.locator('[data-tab-calls]').click();assert(await page.locator('[data-media]').isVisible());
  const sources=page.getByRole('button',{name:/继续剪辑待确认音轨/});if(await sources.count()){await sources.first().click();await page.locator('[data-editor]').waitFor({state:'visible'});await page.waitForFunction(()=>document.querySelector('[data-source-player]').readyState>=1);assert.equal(await page.locator('[data-confirmed]').isChecked(),false);}
  await page.locator('[data-close]').click();
  await page.setViewportSize({width:430,height:932});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);await page.screenshot({path:path.join(out,'memory-mobile.png')});await page.setViewportSize({width:1400,height:900});
  await page.goto(base+'/den?pet=1');await page.waitForFunction(()=>window.__den?.petModel&&window.__denBehavior?.()?.imprint?.responses?.greeting,undefined,{timeout:90000});
  assert.equal(await page.evaluate(()=>__denBehavior().mode),'lively');assert.equal(await page.evaluate(()=>__denBehavior().imprint.vocality),'quiet');
  await page.waitForFunction(()=>window.__denCareDebug().available,undefined,{timeout:30000});
  // Open the same button handler without relying on the responsive dock's collapsed section.
  await page.locator('#btn-imprint').evaluate(b=>b.click());await page.getByRole('button',{name:'我回来了',exact:true}).click();
  await page.waitForFunction(()=>window.__denDialogue.debug().log.some(x=>x.includes('正在坐下')),undefined,{timeout:20000});
  await page.waitForFunction(()=>!window.__denDialogue.debug().active,undefined,{timeout:25000});
  assert((await page.locator('#growth-mood').textContent()).includes('测试样本'));
  await page.screenshot({path:path.join(out,'den-reunion.png')});
  const current=await(await page.request.get(base+'/api/pet-imprint/1')).json();await page.request.post(base+'/api/pet-imprint/1/'+created[0]+'/withdraw',{headers:{'X-Profile-Scope':current.scope},data:{revision:current.revision}});
  await page.locator('#btn-imprint').evaluate(b=>b.click());await page.getByRole('button',{name:'我回来了',exact:true}).click();await page.waitForFunction(()=>document.getElementById('growth-mood').textContent.includes('还没有确认'),undefined,{timeout:8000});
  let next=await(await page.request.get(base+'/api/pet-imprint/1')).json();
  next=await(await page.request.post(base+'/api/pet-imprint/1',{headers:{'X-Profile-Scope':next.scope},data:{revision:next.revision,kind:'play',value:'play_bow',evidence:{type:'owner',quote:'测试样本：仅验证邀玩动作映射。'}}})).json();
  const playCard=next.cards.find(c=>c.evidence.quote==='测试样本：仅验证邀玩动作映射。');created.push(playCard.id);
  await page.request.post(base+'/api/pet-imprint/1/'+playCard.id+'/confirm',{headers:{'X-Profile-Scope':next.scope},data:{revision:next.revision,confirmed:true}});
  await page.reload();await page.waitForFunction(()=>window.__denCareDebug?.().available,undefined,{timeout:90000});
  await page.locator('#btn-imprint').evaluate(b=>b.click());await page.getByRole('button',{name:'一起玩一会儿',exact:true}).click();
  await page.waitForFunction(()=>window.__denDialogue.debug().log.some(x=>x.includes('邀请你一起玩')),undefined,{timeout:20000});
  await page.waitForFunction(()=>!window.__denDialogue.debug().active,undefined,{timeout:15000});assert.equal(await page.evaluate(()=>__denDialogue.debug().status),'动作已完成');
  const outline=await browser.newPage();await outline.goto(require('node:url').pathToFileURL(path.resolve('docs/roadshow-5min-outline.html')).href);
  assert.equal(await outline.locator('article.slide').count(),11);assert.equal(await outline.locator('article.slide').evaluateAll(es=>es.reduce((n,e)=>n+Number(e.dataset.seconds),0)),285);
  await outline.locator('#s04').scrollIntoViewIfNeeded();await outline.locator('#s04').screenshot({path:path.join(out,'roadshow-memory-slide.png')});
  await outline.locator('#script-toggle').click();assert(await outline.locator('body').evaluate(e=>e.classList.contains('script-only')));await outline.close();
  assert.deepEqual(errors,[]);console.log(JSON.stringify({passed:'draft/confirm UI, original source resume, narrow layout, real GLB come/sit/play-bow, withdrawal, 11-slide 285-second outline',out}));
 }finally{if(page)for(const id of created){const d=await(await page.request.get(base+'/api/pet-imprint/1')).json();await page.request.delete(base+'/api/pet-imprint/1/'+id,{headers:{'X-Profile-Scope':d.scope},data:{revision:d.revision}});}await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
