// Isolated local fixture: no logged-in browser, live API, or paid service.
const {app,BrowserWindow}=require('electron'),fs=require('fs'),path=require('path'),os=require('os'),assert=require('assert'),{pathToFileURL}=require('url');
const root=path.resolve(__dirname,'..'),temp=fs.mkdtempSync(path.join(os.tmpdir(),'pait-loading-test-'));
app.setPath('userData',path.join(temp,'profile'));app.disableHardwareAcceleration();
const url=p=>pathToFileURL(path.join(root,p)).href,sleep=ms=>new Promise(r=>setTimeout(r,ms));
fs.writeFileSync(path.join(temp,'index.html'),`<!doctype html><html lang="zh"><head><meta charset="utf-8">
<link rel="stylesheet" href="${url('static/css/glass-loading.css')}">
<style>body{margin:0;min-height:100vh;background:radial-gradient(ellipse at 10% 10%,#d9ece0,transparent 50%),linear-gradient(140deg,#749591,#c3d1ba 60%,#efe4c5);font-family:system-ui;color:#294f45}main{padding:130px 10%;}h1{font-size:48px;font-weight:400}dialog{width:min(440px,80vw);padding:28px;border:1px solid white;border-radius:28px;background:#f7f9ef;color:#294f45}dialog::backdrop{background:#163c3744}</style>
<script>
window.fetch=async()=>{if(window.rejectFetch)throw window.rejectFetch;return window.mockResponse=new Response(window.body??'{"ok":true}',{status:window.httpStatus||200,headers:window.responseHeaders||{'Content-Type':'application/json'}})};
window.XMLHttpRequest=class extends EventTarget{constructor(){super();this.upload=new EventTarget();this.status=200;}open(){}send(){}abort(){this.dispatchEvent(new Event('abort'));}};
</script><script src="${url('static/js/glass-loading.js')}"></script>
<script src="${url('static/js/den/selected-assets.js')}"></script>
<script src="${url('static/js/realtime/realtime-controller.js')}"></script>
</head><body><main><small>PAIT ISLAND / 派特岛</small><h1>穿过云海，去见它。</h1><p>加载模型、声音与今天的小故事</p><button id="clickable">仍可操作页面</button></main><dialog id="preview"><h2>今天的小故事</h2><p>AI 正在为你们画一幅插画</p><form method="dialog"><button>关闭</button></form></dialog></body></html>`);
app.whenReady().then(async()=>{
 const w=new BrowserWindow({show:false,width:1100,height:760,webPreferences:{offscreen:true,sandbox:true}});
 const run=s=>w.webContents.executeJavaScript('(async()=>{'+(s.includes(';')?s:'return ('+s+');')+'})().then(v=>["boolean","number","string"].includes(typeof v)?v:null)'),clear=()=>run(`dispatchEvent(new PageTransitionEvent('pageshow',{persisted:true}));window.rejectFetch=null;window.httpStatus=200;window.responseHeaders=null;window.body=null;`);
 try{
  await w.loadFile(path.join(temp,'index.html'));await sleep(500);
  assert.equal(await run('PaitLoading.activeCount()'),0);
  await run(`window.a=PaitLoading.start('正在下载岛屿',{delay:0});a.update('正在下载岛屿',.42);window.b=PaitLoading.start('AI 正在绘制故事插画',{delay:0});`);await sleep(150);
  assert.equal(await run(`document.querySelector('[aria-valuenow]').getAttribute('aria-valuenow')`),'42');
  assert.equal(await run(`document.querySelectorAll('.indeterminate').length`),1);
  await run(`window.originalRow=document.querySelector('[data-loading-id]');a.update('正在下载岛屿',.53)`);await sleep(150);
  assert(await run(`originalRow===document.querySelector('[data-loading-id]')`),'Do not recreate animated DOM on each download chunk');
  assert(await run(`getComputedStyle(document.querySelector('.pait-glass-loading')).pointerEvents==='none'`));
  fs.writeFileSync(path.join(os.tmpdir(),'pait-glass-loading-desktop.png'),(await w.webContents.capturePage()).toPNG());
  await run(`preview.showModal()`);await sleep(100);
  assert(await run(`document.querySelector('.pait-glass-loading').parentNode===preview`));
  w.setContentSize(390,844);await sleep(150);
  assert(await run(`document.documentElement.scrollWidth<=innerWidth`));
  fs.writeFileSync(path.join(os.tmpdir(),'pait-glass-loading-dialog.png'),(await w.webContents.capturePage()).toPNG());
  await run(`preview.querySelector('button').click();a.done();b.cancel()`);await sleep(500);assert.equal(await run('PaitLoading.activeCount()'),0,'dialog form must not count as navigation');
  // Preserve Response identity, clone and native body semantics.
  await run(`window.r=await fetch('file:///api/test');window.copy=r.clone();window.result=await r.json()`);
  assert(await run(`r===mockResponse && r instanceof Response && r.bodyUsed && result.ok && (await copy.json()).ok`));await sleep(450);
  assert.equal(await run('PaitLoading.activeCount()'),0);
  // Streaming bytes: real percent, one bar retained until final chunk.
  await run(`window.responseHeaders={'Content-Length':'4'};window.body=new ReadableStream({start(c){window.source=c;c.enqueue(new Uint8Array([1,2]));}});window.r=await fetch('/model.glb');window.reader=r.body.getReader();await reader.read();`);await sleep(250);
  assert.equal(await run(`document.querySelector('[aria-valuenow]').getAttribute('aria-valuenow')`),'50');
  await run(`source.enqueue(new Uint8Array([3,4]));source.close();await reader.read();await reader.read()`);await sleep(450);assert.equal(await run('PaitLoading.activeCount()'),0);
  // Compressed transfer length cannot be compared with decoded bytes.
  await clear();await run(`window.responseHeaders={'Content-Length':'2','Content-Encoding':'gzip'};window.body=new ReadableStream({start(c){window.source=c;c.enqueue(new Uint8Array([1,2,3,4]));}});window.r=await fetch('/model.glb');window.reader=r.body.getReader();await reader.read()`);await sleep(250);
  assert(await run(`!document.querySelector('[aria-valuenow]') && !!document.querySelector('.indeterminate')`));
  await run(`await reader.cancel()`);await sleep(120);assert.equal(await run('PaitLoading.activeCount()'),0);
  // Parent-owned model task survives consumed response until parse finishes.
  await clear();await run(`window.loader=new SelectedAssets.Loader({parse(buffer,path,resolve){window.parsed=()=>resolve({scene:{traverse(){}}});}});window.ticket=loader.begin();window.loading=loader.glb('/cat.glb',ticket);`);await sleep(260);
  assert.equal(await run('PaitLoading.activeCount()'),1);
  assert(await run(`document.querySelector('.pait-glass-loading').textContent.includes('解析模型')`));
  await run(`parsed();await loading`);await sleep(450);assert.equal(await run('PaitLoading.activeCount()'),0);
  // User cancellation propagates without a failure warning.
  await run(`window.loading=loader.glb('/cat.glb',loader.begin());window.caught=loading.catch(e=>e.name)`);await sleep(220);await run(`loader.begin();parsed();window.abortName=await caught`);
  assert.equal(await run('abortName'),'AbortError');assert.equal(await run('PaitLoading.activeCount()'),0);
  // Errors never get swallowed or reported as 100% success.
  await clear();await run(`window.httpStatus=503;window.r=await fetch('file:///api/test')`);
  assert(await run(`r.status===503 && !!document.querySelector('.failed') && !document.querySelector('[aria-valuenow]')`));
  await clear();await run(`window.rejectFetch=new TypeError('Offline');window.errorName=await fetch('file:///api/test').catch(e=>e.name)`);assert.equal(await run('errorName'),'TypeError');
  await clear();await run(`window.rejectFetch=new DOMException('cancel','AbortError');await fetch('file:///api/test').catch(()=>{})`);assert.equal(await run('PaitLoading.activeCount()'),0);
  // Heartbeats, telemetry, voice identification and worker polls remain quiet.
  await clear();await run(`for(const p of ['/api/cat-agent/monitor','/api/cat-agent/telemetry','/api/voiceprint/identify','/api/portals?brief=1','/api/portals/sample','/api/portals/plan','/api/supplies/claim','/api/companion/voice-round','/api/pet-studio','/api/cat-agent/story-art'])await (await fetch('file://'+p)).json();await (await fetch('file:///api/other',{paitQuiet:true})).json()`);assert.equal(await run('PaitLoading.activeCount()'),0);
  // XHR upload switches from transmitted bytes to server-processing shimmer.
  await run(`window.x=new XMLHttpRequest();x.open('POST','file:///api/pet-studio/upload');x.send(new FormData());x.upload.dispatchEvent(new ProgressEvent('progress',{lengthComputable:true,loaded:25,total:100}))`);await sleep(220);
  assert.equal(await run(`document.querySelector('[aria-valuenow]').getAttribute('aria-valuenow')`),'25');
  await run(`x.upload.dispatchEvent(new Event('load'))`);await sleep(120);assert(await run(`!!document.querySelector('.indeterminate')`));
  await run(`x.abort()`);assert.equal(await run('PaitLoading.activeCount()'),0);
  // Named jobs and voice startup, with cleanup on completion and stop.
  await run(`PaitLoading.sync('rig',true,'Blender 正在适配');PaitLoading.sync('rig',true,'Blender 正在导出');`);assert.equal(await run('PaitLoading.activeCount()'),1);
  await run(`PaitLoading.sync('rig',false);window.voice=new RealtimeController({petId:3});voice._setState('CONNECTING')`);await sleep(450);assert.equal(await run('PaitLoading.activeCount()'),1);
  await run(`voice._setState('READY')`);await sleep(450);assert.equal(await run('PaitLoading.activeCount()'),0);
  await run(`voice._setState('RECONNECTING');voice.stop()`);assert.equal(await run('PaitLoading.activeCount()'),0);
  console.log('PASS loading UI: real/unknown progress, streaming/clone semantics, model parse/cancel, errors, silent polls, XHR uploads, modal/mobile, voice and named jobs');app.exit(0);
 }catch(e){console.error(e);app.exit(1);}
});
