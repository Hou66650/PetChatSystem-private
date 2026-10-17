/* Run test/park_review_server.py first; all purchases use its temporary database. */
const {chromium}=require('playwright'),assert=require('node:assert/strict'),fs=require('node:fs'),os=require('node:os'),path=require('node:path');
const base=process.env.PET_TEST_BASE||'http://127.0.0.1:5088',output=fs.mkdtempSync(path.join(os.tmpdir(),'pait-wardrobe-'));
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.PET_TEST_CHROME||'C:/Program Files/Google/Chrome/Application/chrome.exe',args:['--enable-webgl','--ignore-gpu-blocklist']});
 try{
  const context=await browser.newContext({viewport:{width:1365,height:1000}}),page=await context.newPage(),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.goto(base+'/__qa/park-a');await page.goto(base+'/pet-shop?pet=1');
  const ready=()=>page.waitForFunction(()=>document.querySelector('#shop-loading').textContent==='',null,{timeout:60000});
  await ready();await page.locator('#shop-buy').click();await page.locator('#shop-confirm').waitFor({state:'visible'});
  assert.equal((await (await page.request.get(base+'/api/wardrobe')).json()).balance,160,'opening confirmation never buys');
  await page.locator('#shop-cancel').click();await page.locator('#shop-buy').click();await page.locator('#shop-confirm-buy').click();
  await page.waitForFunction(()=>document.querySelector('#shop-balance').textContent==='100');
  assert.deepEqual((await (await page.request.get(base+'/api/wardrobe')).json()).equipped,{});
  await page.locator('#shop-equip').click();await page.waitForFunction(()=>document.querySelector('#shop-slots').textContent.includes('苔绿领结'));
  await page.locator('[data-item=daisy]').click();await ready();await page.locator('#shop-buy').click();await page.locator('#shop-confirm-buy').click();await page.waitForFunction(()=>document.querySelector('#shop-balance').textContent==='20');await page.locator('#shop-equip').click();
  await page.waitForFunction(()=>document.querySelector('#shop-slots').textContent.includes('雏菊发饰'));
  await page.screenshot({path:path.join(output,'01-outfit-desktop.png')});
  await page.reload();await ready();assert((await page.locator('#shop-slots').textContent()).includes('雏菊发饰'));
  await page.locator('[data-item=blue-beret]').click();await ready();assert(await page.locator('#shop-buy').isDisabled());
  for(const id of ['1','2','3','4']){
   await page.locator('#shop-pet').selectOption(id);await ready();
   await page.locator('[data-item=daisy]').click();await ready();await page.locator('[data-motion=walk]').click();await page.waitForTimeout(450);
   await page.screenshot({path:path.join(output,'pet-'+id+'.png')});
  }
  await page.setViewportSize({width:390,height:844});await page.screenshot({path:path.join(output,'02-mobile.png'),fullPage:true});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  await page.locator('[data-view=owned]').click();assert.equal(await page.locator('.shop-card').count(),2);
  await page.locator('#shop-pet').selectOption('1');await ready();await page.locator('.shop-slot').filter({hasText:'头饰'}).getByRole('button',{name:'卸下'}).click();
  await page.waitForFunction(()=>document.querySelector('#shop-slots').textContent.includes('头饰 · 未穿戴'));
  // Exercise real GLBs and all growth profiles, checking sockets and animation parenting.
  const report=await page.evaluate(async()=>{
   const manifest=await (await fetch('/static/data/pet-growth-models.json')).json(),result=[];
   for(const entry of manifest.stages){
    const asset=entry.assets.default||entry.assets.tabby;
    const gltf=await new Promise((resolve,reject)=>new THREE.GLTFLoader().load(asset.path,resolve,undefined,reject));
    const p=new PortalPets.Pet(THREE,gltf,{height:entry.height});
    const items=[{id:'daisy',slot:'head',design:'flower',color:'#f4e9cc'},{id:'moss-bow',slot:'neck',design:'bow',color:'#718c75'}];
    await p.wardrobeReady;
    if(await p.wardrobe.apply(items)!==2)throw Error('Missing sockets: '+asset.path);
    const locals=p.root.userData.accessories.map(o=>o.position.clone());
    for(const action of ['idle','walk','run','sleep','petting']){
     p.play(action);for(let i=0;i<20;i++)p.update(.05);p.root.updateMatrixWorld(true);
     p.root.userData.accessories.forEach((o,i)=>{
      if(!o.parent.name.startsWith('SOCKET_')||o.position.distanceTo(locals[i])>1e-6)throw Error('Detached outfit');
      if(!o.matrixWorld.elements.every(Number.isFinite))throw Error('Non-finite outfit');
     });
    }
    await p.wardrobe.apply(items);if(p.root.userData.accessories.length!==2)throw Error('Duplicate outfit');
    p.wardrobe.dispose();if(p.root.userData.accessories.length)throw Error('Failed removal');
    SelectedAssets.disposeTree(p.root);result.push(entry.pet+':'+entry.stage);
   }
   return result;
  });
  assert.equal(report.length,12);
  await page.goto(base+'/den?pet=1');
  await page.waitForFunction(()=>window.__den?.petModel?.userData.accessories?.length===1,null,{timeout:90000});
  await page.evaluate(async()=>{const scope=(await(await fetch('/api/wardrobe')).json()).scope;const r=await fetch('/api/wardrobe/equip',{method:'POST',headers:{'Content-Type':'application/json','X-Profile-Scope':scope},body:JSON.stringify({petId:1,item:'daisy'})});if(!r.ok)throw Error('Equip failed');window.dispatchEvent(new StorageEvent('storage',{key:'pait-wardrobe-change'}));});
  await page.waitForFunction(()=>__den.petModel.userData.accessories.length===2);
  await page.evaluate(()=>__den.spawnPet(2));
  await page.waitForFunction(()=>__den.petModel.userData.height===1.05&&__den.petModel.userData.wardrobeKey==='[]',null,{timeout:90000});
  assert.equal(await page.evaluate(()=>__den.petModel.userData.accessories.length),0);
  assert.deepEqual(errors,[]);
  const second=await browser.newContext(),other=await second.newPage();await other.goto(base+'/__qa/park-b');const otherState=await (await other.request.get(base+'/api/wardrobe')).json();assert(!otherState.owned.includes('daisy'));
  console.log(JSON.stringify({passed:'Purchase confirmation, shared wallet, persistent slots, unequip, owned filter, account isolation, four live GLBs, mobile width, 12 growth rigs × 5 motions',report,output},null,2));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1});
