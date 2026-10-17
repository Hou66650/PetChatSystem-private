const fs=require('node:fs'),path=require('node:path'),os=require('node:os'),assert=require('node:assert/strict');
const {chromium}=require('playwright');
const base=process.env.PET_GROWTH_DEN_BASE||'http://127.0.0.1:5012',out=fs.mkdtempSync(path.join(os.tmpdir(),'pet-growth-den-'));
function monthsAgo(months){const now=new Date(),day=now.getUTCDate(),year=now.getUTCFullYear(),month=now.getUTCMonth()-months;const first=new Date(Date.UTC(year,month,1)),last=new Date(Date.UTC(year,month+1,0));first.setUTCDate(Math.min(day,last.getUTCDate()));return first.toISOString().slice(0,10);}
(async()=>{let browser;
 try{
  browser=await chromium.launch({headless:true,...(process.env.PET_TEST_CHROME?{executablePath:process.env.PET_TEST_CHROME}:{})});
  const context=await browser.newContext({viewport:{width:1280,height:800}}),page=await context.newPage(),errors=[],requests=[];
  page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(r.url().endsWith('.glb')||r.url().includes('.glb?'))requests.push(new URL(r.url()).pathname);});
  const waitStage=async(key,timeout=60000)=>page.waitForFunction(k=>window.__den?.petModel?.visible&&window.__den.petModel.userData.growthKey===k,key,{timeout});
  const setBirthday=async(birthday,pet=3)=>page.evaluate(async({birthday,pet})=>{
   const scope=(await(await fetch('/api/companion')).json()).scope,current=await(await fetch('/api/growth/'+pet)).json();
   const body={mode:'real',name:'阶段测试宠物',personality:'gentle',birthday,adopted:new Date().toISOString().slice(0,10),estimated:true,likes:'',breed:''};
   const response=await fetch('/api/growth/'+pet,{method:current.enrolled?'PATCH':'POST',headers:{'Content-Type':'application/json','X-Profile-Scope':scope},body:JSON.stringify(body)}),data=await response.json();
   if(!response.ok)throw Error(JSON.stringify(data));window.dispatchEvent(new StorageEvent('storage',{key:'pet-growth-change:'+scope}));return data.appearance.stage;
  },{birthday,pet});
  await page.goto(base+'/den?pet=3');await page.waitForFunction(()=>window.__den?.petModel,undefined,{timeout:90000});
  assert.equal(await setBirthday(monthsAgo(3)),'幼年');await waitStage('3:幼年:tabby');
  let data=await page.evaluate(()=>({height:__den.petModel.userData.height,center:__den.petModel.userData.cameraCenter,visible:__den.petModel.visible}));assert.equal(data.height,.58);assert(data.visible);assert(Math.abs(data.center-.29)<1e-6);
  await page.screenshot({path:path.join(out,'cat-juvenile-den.png')});
  await page.route('**/static/models/pet-growth-v1/cat/tabby-adolescent.glb*',async route=>{await new Promise(r=>setTimeout(r,700));await route.continue();});
  assert.equal(await setBirthday(monthsAgo(7)),'少年');
  await page.waitForTimeout(150);assert.equal(await page.evaluate(()=>__den.petModel.userData.growthKey),'3:幼年:tabby','old stage remains visible while the next GLB loads');
  await waitStage('3:少年:tabby');await page.screenshot({path:path.join(out,'cat-adolescent-den.png')});
  assert.equal(await setBirthday(monthsAgo(13)),'成年');await waitStage('3:成年:tabby');await page.screenshot({path:path.join(out,'cat-adult-den.png')});
  await setBirthday(monthsAgo(3));await setBirthday(monthsAgo(7));await waitStage('3:少年:tabby');
  await page.reload();await waitStage('3:少年:tabby',90000);assert(await page.evaluate(()=>__den.petModel.visible),'cached reload keeps a visible pet');
  await page.route('**/static/models/pet-growth-v1/cat/tabby-juvenile.glb*',async route=>{await new Promise(r=>setTimeout(r,900));await route.continue();});
  await setBirthday(monthsAgo(3));await page.evaluate(()=>__den.spawnPet(1));await page.waitForFunction(()=>window.__den?.petModel&&__den.petModel.userData.height===.95&&__den.petModel.visible,undefined,{timeout:90000});
  await page.waitForTimeout(1200);assert.equal(await page.evaluate(()=>__den.petModel.userData.height),.95,'late stage result cannot replace a newly selected pet');
  assert.equal(await setBirthday(monthsAgo(3),1),'幼年');await waitStage('1:幼年:default',90000);assert.equal(await page.evaluate(()=>__den.petModel.userData.height),.64);
  await page.screenshot({path:path.join(out,'shiba-juvenile-den.png')});
  await setBirthday(monthsAgo(7),2);await page.evaluate(()=>__den.spawnPet(2));await waitStage('2:少年:default',90000);assert.equal(await page.evaluate(()=>__den.petModel.userData.height),.91);
  await page.screenshot({path:path.join(out,'husky-adolescent-den.png')});
  await setBirthday(monthsAgo(13),4);await page.evaluate(()=>__den.spawnPet(4));await waitStage('4:成年:default',90000);assert.equal(await page.evaluate(()=>__den.petModel.userData.height),1.12);
  await page.screenshot({path:path.join(out,'shepherd-adult-den.png')});
  assert.deepEqual(errors,[]);
  const fallback=await browser.newContext({viewport:{width:1000,height:700}}),broken=await fallback.newPage();
  await broken.goto(base+'/gpt');
  await broken.evaluate(async birthday=>{
   const scope=(await(await fetch('/api/companion')).json()).scope,response=await fetch('/api/growth/3',{method:'POST',headers:{'Content-Type':'application/json','X-Profile-Scope':scope},body:JSON.stringify({mode:'real',name:'回退测试猫',personality:'gentle',birthday,adopted:new Date().toISOString().slice(0,10),estimated:true,likes:'',breed:''})});
   if(!response.ok)throw Error(await response.text());
  },monthsAgo(3));
  await broken.route('**/static/models/pet-growth-v1/cat/tabby-juvenile.glb*',route=>route.abort());
  await broken.goto(base+'/den?pet=3');
  await broken.waitForFunction(()=>window.__den?.petModel?.userData.growthFallback==='asset-load'&&__den.petModel.visible,undefined,{timeout:90000});
  await broken.screenshot({path:path.join(out,'cat-load-fallback.png')});await fallback.close();
  fs.writeFileSync(path.join(out,'requests.json'),JSON.stringify(requests,null,2));console.log('PASS actual /den: stages, atomic switch, cached reload, failure fallback and pet-switch cancellation');console.log(out);
 }finally{await browser?.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
