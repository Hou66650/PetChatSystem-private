const {chromium}=require('playwright'),assert=require('node:assert/strict'),fs=require('node:fs');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',args:['--enable-webgl','--ignore-gpu-blocklist']});
 try{
  const a=await browser.newPage({viewport:{width:1440,height:1050}}),b=await browser.newPage({viewport:{width:1440,height:1050}}),errors=[],bad=[],events=[];
  for(const p of [a,b]){p.on('pageerror',e=>errors.push(e.message));p.on('response',r=>{if(r.url().endsWith('/api/park/sync')&&![200,423].includes(r.status()))bad.push(r.status());});}
  // Capture actual rendered pet roots without changing production behavior.
  await a.addInitScript(()=>{Object.defineProperty(window,'PortalPets',{configurable:true,set(api){const Original=api.Pet;api.Pet=class extends Original{constructor(...args){super(...args);window.__reviewPets??=[];window.__reviewPets.push(this);}};Object.defineProperty(window,'PortalPets',{value:api,writable:true,configurable:true});}});});
  await a.goto('http://127.0.0.1:5088/__qa/park-a');await b.goto('http://127.0.0.1:5088/__qa/park-b');
  await a.locator('#park-pet').selectOption('3');await a.locator('#park-join').click();
  const state=async()=>await(await b.request.get('http://127.0.0.1:5088/api/park')).json();
  let maxHeight=0,paused=false,finished=false,sawTunnel=false;const used=new Set();
  for(let i=0;i<300;i++){
   await a.waitForTimeout(500);const s=await state(),p=s.players[0];if(!p)continue;
   const f=p.behavior?.facility;
   if(i%20===0)console.log('sample',JSON.stringify({i,action:p.action,behavior:p.behavior,point:[p.x,p.z]}));if(f){used.add(f.id);events.push({id:f.id,progress:f.progress});}
   const y=await a.evaluate(()=>window.__reviewPets?.[0]?.root.position.y||0);maxHeight=Math.max(maxHeight,y);
   if(f?.id==='bridge'&&y>.4&&!paused){await a.locator('#park-auto').click();paused=true;await a.screenshot({path:'uploads/harmony-dev/park-facility-bridge.png'});}
   if(paused&&!f&&!finished){assert.equal(p.behavior.autonomous,false,'pause waits until safe exit');finished=true;await a.locator('#park-auto').click();}
   if(f?.id==='tunnel'&&p.z<-1&&!sawTunnel){sawTunnel=true;await a.screenshot({path:'uploads/harmony-dev/park-facility-tunnel.png'});}if(sawTunnel&&finished)break;
  }
  console.log('observed',{used:[...used],maxHeight,paused,finished,bad,errors});assert(used.has('bridge')&&used.has('tunnel'),'Agent autonomously selects both facilities');assert(maxHeight>.5,'pet stands on raised bridge deck');assert(finished,'pause deferred until back on lawn');
  assert.deepEqual(errors,[]);assert.deepEqual(bad,[]);
  // Leave releases presence and any shared approach reservation immediately.
  await a.locator('#park-leave').click();assert.equal((await state()).count,0);
  fs.writeFileSync('uploads/harmony-dev/park-facility-browser.json',JSON.stringify({maxHeight,used:[...used],paused,finished,events,errors,bad},null,2));
  console.log('PASS autonomous bridge + tunnel, rendered deck height',maxHeight,'remote progress, deferred pause, leave cleanup');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
