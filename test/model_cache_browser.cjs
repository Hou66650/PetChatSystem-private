// Real browser storage + loading UI; isolated profile, local fixture, no account.
const {chromium}=require('playwright'),http=require('node:http'),path=require('node:path'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..');
(async()=>{
 const server=http.createServer((req,res)=>{res.setHeader('Content-Type','text/html');res.end('<!doctype html><html><body></body></html>');});
 await new Promise(r=>server.listen(0,'127.0.0.1',r));let browser;
 try {
  browser=await chromium.launch({channel:process.env.PAIT_TEST_BROWSER||'msedge',headless:true});
  const page=await browser.newPage();await page.goto('http://127.0.0.1:'+server.address().port);
  await page.evaluate(()=>{window.mode='download';window.fetch=async(url,opts={})=>{
   if(mode==='offline')throw new TypeError('offline');
   if(mode==='hang')return new Promise((ok,fail)=>opts.signal.addEventListener('abort',()=>fail(new DOMException('timeout','AbortError'))));
   if(mode==='cached')return new Response(null,{status:304});
   const bytes=new ArrayBuffer(24),v=new DataView(bytes);v.setUint32(0,0x46546c67,true);v.setUint32(4,2,true);v.setUint32(8,24,true);
   return new Response(bytes,{headers:{ETag:'"test"'}});
  };});
  for(const name of ['static/js/glass-loading.js','static/js/den/selected-assets.js','test/model_cache_browser.js'])await page.addScriptTag({path:path.join(root,name)});
  assert.match(await page.evaluate(()=>testModelCacheStorage()),/^PASS/);
  await page.evaluate(async()=>{
   window.cache=new SelectedAssets.ModelCache({store:new SelectedAssets.ModelStore(indexedDB,'pait-cache-ui-test')});
   window.loader=new SelectedAssets.Loader({parse(b,p,ok){ok({scene:{traverse(){}}});}},(...args)=>fetch(...args),cache);
   await loader.glb('/static/models/test.glb?v=1',loader.begin());
   mode='cached';await loader.glb('/static/models/test.glb?v=2',loader.begin());
  });
  assert.equal(await page.locator('.failed').count(),0,'304 must not show failure');
  await page.evaluate(async()=>{mode='offline';await loader.glb('/static/models/test.glb',loader.begin());});
  assert.equal(await page.locator('.failed').count(),0,'successful offline fallback must not show failure');
  await page.evaluate(async()=>{mode='hang';await loader.glb('/static/models/test.glb',loader.begin());});
  assert.equal(await page.locator('.failed').count(),0,'bounded validation timeout falls back successfully');
  await page.waitForTimeout(450);assert.equal(await page.evaluate(()=>PaitLoading.activeCount()),0);
  await page.evaluate(async()=>{
   const pending=loader.glb('/static/models/test.glb',loader.begin()).catch(e=>e.name);
   setTimeout(()=>loader.begin(),100);
   if(await pending!=='AbortError')throw Error('selection cancellation was swallowed');
  });
  assert.equal(await page.evaluate(()=>PaitLoading.activeCount()),0);
  console.log('PASS real browser: IndexedDB persistence/LRU, conditional 304 UI, offline/timeout fallback and cancellation');
 } finally {await browser?.close();await new Promise(r=>server.close(r));}
})().catch(e=>{console.error(e);process.exitCode=1;});
