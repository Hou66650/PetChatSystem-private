const {chromium}=require('playwright'),assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.PET_TEST_CHROME||'C:/Program Files/Google/Chrome/Application/chrome.exe',args:['--enable-webgl','--ignore-gpu-blocklist']});
 try{
  const a=await browser.newPage({viewport:{width:1440,height:1050}}),b=await browser.newPage({viewport:{width:1440,height:1050}}),errors=[],bad=[];
  for(const p of [a,b]){p.on('pageerror',e=>errors.push(e.message));p.on('response',r=>{if(r.url().endsWith('/api/park/sync')&&r.status()!==200)bad.push(r.status());});}
  await a.goto('http://127.0.0.1:5088/__qa/park-a');await b.goto('http://127.0.0.1:5088/__qa/park-b');
  await a.locator('#park-join').click();await b.locator('#park-pet').selectOption('3');await b.locator('#park-join').click();
  await a.waitForFunction(()=>[...document.querySelectorAll('#park-players button')].filter(x=>x.dataset.ready==='true').length===2,null,{timeout:30000});
  const state=async p=>(await (await p.request.get('http://127.0.0.1:5088/api/park')).json());
  let first=(await state(a)).players.find(p=>p.mine),distance=0,previous=first;const acts=new Set(),intent=new Set();
  for(let i=0;i<50;i++){
   await a.waitForTimeout(500);const s=await state(a),self=s.players.find(p=>p.mine);assert.equal(s.count,2);assert(self.behavior.autonomous);distance+=Math.hypot(self.x-previous.x,self.z-previous.z);previous=self;acts.add(self.action);intent.add(self.behavior.activity);
  }
  assert(distance>2,'no clicks needed after entering');assert(intent.size>=2,'chooses successive activities');assert(acts.has('bow')||acts.has('sniff')||acts.has('greet'));
  await a.locator('#park-auto').click();await a.waitForTimeout(1000);const paused=(await state(a)).players.find(p=>p.mine);await a.waitForTimeout(2200);const later=(await state(a)).players.find(p=>p.mine);assert(Math.hypot(later.x-paused.x,later.z-paused.z)<.01);assert.equal(later.behavior.autonomous,false);
  await a.locator('.park-help summary').click();await a.locator('[data-action=greet]').click();await a.waitForTimeout(900);assert.equal((await state(b)).players.find(p=>!p.mine).action,'greet');
  await a.locator('#park-auto').click();await a.waitForTimeout(1600);assert((await state(a)).players.find(p=>p.mine).behavior.autonomous);
  await b.locator('#park-leave').click();await a.waitForFunction(()=>document.querySelector('#park-count').textContent.includes('1 /'));
  await a.locator('#park-leave').click();assert(await a.locator('#park-auto').isDisabled());
  assert.deepEqual(errors,[]);assert.deepEqual(bad,[]);console.log('PASS two autonomous pets, movement',distance.toFixed(2),'m; activities',Array.from(intent),'; pause, intervention, resume and departure');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
