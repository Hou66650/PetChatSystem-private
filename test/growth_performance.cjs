const fs=require('node:fs'),path=require('node:path'),os=require('node:os'),assert=require('node:assert/strict');
const {chromium}=require('playwright');
const base=process.env.PET_GROWTH_DEN_BASE||'http://127.0.0.1:5012',out=fs.mkdtempSync(path.join(os.tmpdir(),'pet-growth-performance-'));
const stages=[['幼年',3],['少年',7],['成年',13],['幼年',3]];
function monthsAgo(months){const now=new Date(),day=now.getUTCDate(),date=new Date(Date.UTC(now.getUTCFullYear(),now.getUTCMonth()-months,1)),last=new Date(Date.UTC(now.getUTCFullYear(),now.getUTCMonth()-months+1,0));date.setUTCDate(Math.min(day,last.getUTCDate()));return date.toISOString().slice(0,10);}
function percentile(values,p){const sorted=[...values].sort((a,b)=>a-b);return sorted[Math.min(sorted.length-1,Math.floor((sorted.length-1)*p))];}
(async()=>{let browser;
 try{
  browser=await chromium.launch({headless:true,...(process.env.PET_TEST_CHROME?{executablePath:process.env.PET_TEST_CHROME}:{})});
  const page=await browser.newPage({viewport:{width:1280,height:800}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
  const cdp=await page.context().newCDPSession(page);
  const waitStage=(pet,stage)=>page.waitForFunction(key=>__den?.petModel?.userData.growthKey===key&&__den.petModel.visible,`${pet}:${stage}:${pet===3?'tabby':'default'}`,{timeout:90000});
  const setBirthday=async(birthday,pet)=>page.evaluate(async({birthday,pet})=>{
   const scope=(await(await fetch('/api/companion')).json()).scope,current=await(await fetch('/api/growth/'+pet)).json();
   const body={mode:'real',name:'性能测试宠物',personality:'gentle',birthday,adopted:new Date().toISOString().slice(0,10),estimated:true,likes:'',breed:''};
   const response=await fetch('/api/growth/'+pet,{method:current.enrolled?'PATCH':'POST',headers:{'Content-Type':'application/json','X-Profile-Scope':scope},body:JSON.stringify(body)}),data=await response.json();
   if(!response.ok)throw Error(JSON.stringify(data));window.dispatchEvent(new StorageEvent('storage',{key:'pet-growth-change:'+scope}));
  },{birthday,pet});
  const gotoStage=async(pet,stage)=>{
   const started=Date.now();await setBirthday(monthsAgo(stages.find(s=>s[0]===stage)[1]),pet);
   const current=await page.evaluate(()=>__den.petModel?.userData.growthKey||'');
   if(!current.startsWith(pet+':'))await page.evaluate(pet=>__den.spawnPet(pet),pet);
   await waitStage(pet,stage);await page.waitForTimeout(600);return Date.now()-started;
  };
  const sample=async(pet,stage)=>{
   const switchMs=await gotoStage(pet,stage);
   const frames=await page.evaluate(()=>new Promise(resolve=>{const values=[];let previous;function tick(now){if(previous)values.push(now-previous);previous=now;if(values.length>=60)resolve(values);else requestAnimationFrame(tick);}requestAnimationFrame(tick);}));
   await cdp.send('HeapProfiler.collectGarbage');
   const memory=await page.evaluate(()=>({heap:performance.memory?.usedJSHeapSize||0,geometries:__den.renderer.info.memory.geometries,textures:__den.renderer.info.memory.textures,calls:__den.renderer.info.render.calls,triangles:__den.renderer.info.render.triangles}));
   return {pet,stage,switchMs,frameMean:frames.reduce((a,b)=>a+b,0)/frames.length,p50:percentile(frames,.5),p95:percentile(frames,.95),p99:percentile(frames,.99),memory};
  };
  await page.goto(base+'/den?pet=3');await page.waitForFunction(()=>__den?.petModel,undefined,{timeout:90000});
  const report=[];
  for(const pet of [3,1,2,4])for(const stage of ['幼年','少年','成年'])report.push(await sample(pet,stage));
  const hot=await sample(3,'幼年');
  const switches=[];
  for(let i=0;i<20;i++){
   const stage=i%2?'成年':'幼年',switchMs=await gotoStage(3,stage);
   await cdp.send('HeapProfiler.collectGarbage');
   const memory=await page.evaluate(()=>({heap:performance.memory?.usedJSHeapSize||0,geometries:__den.renderer.info.memory.geometries,textures:__den.renderer.info.memory.textures}));
   switches.push({index:i+1,stage,switchMs,memory});
  }
  assert.deepEqual(errors,[]);
  const result={environment:'local headless Chromium; not a MatePad benchmark',report,hot,switches};
  fs.writeFileSync(path.join(out,'report.json'),JSON.stringify(result,null,2));
  for(const row of report)console.log(row.pet,row.stage,'switchMs',row.switchMs,'p50/p95/p99',row.p50.toFixed(1),row.p95.toFixed(1),row.p99.toFixed(1),'heapMiB',(row.memory.heap/1048576).toFixed(1));
  console.log('hot juvenile switchMs',hot.switchMs,'20-switch heap first/last',switches[0].memory.heap,switches.at(-1).memory.heap,'geometry first/last',switches[0].memory.geometries,switches.at(-1).memory.geometries);
  console.log('PASS growth performance matrix and 20 stage switches');console.log(out);
 }finally{await browser?.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
