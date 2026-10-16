const fs = require('node:fs'), vm = require('node:vm'), assert = require('node:assert/strict');
const { stripTypeScriptTypes } = require('node:module');
let source = fs.readFileSync('harmony/entry/src/main/ets/components/NativePreview.ets', 'utf8');
source = source.slice(0, source.indexOf('  build()')) + '}';
source = source.replace(/^import .*;\r?\n/gm, '').replace('@Component', '')
  .replace('export struct NativePreview', 'class NativePreview').replace(/@State /g, '');
const js = stripTypeScriptTypes(source) + '\nglobalThis.Preview = NativePreview;';
const asset = { id: 'cat', path: '/static/models/petchat-cat-v3/cat.glb', cx: 1, cy: 2, cz: 3, scale: 2, triangles: 154155 };
function glb() { const b = new ArrayBuffer(20), d = new DataView(b);d.setUint32(0,0x46546c67,true);d.setUint32(4,2,true);d.setUint32(8,20,true);return b; }
function harness(response) {
  const events = [], nodes = [];
  const request = { async request(url, options) { events.push(['request',url,options.maxLimit]);return await response(); },destroy(){ events.push(['httpDestroy']); } };
  const content = { destroy(){ events.push(['contentDestroy']); } };
  const scene = { animations: [], environment: {}, destroy(){events.push(['sceneDestroy']);},
    importScene(){ const n={};nodes.push(n);return n; }, getResourceFactory(){return {
      async createScene(){return content;}, async createNode(){const n={};nodes.push(n);return n;},
      async createCamera(){return {};},async createLight(){return {};}
    };} };
  const context = { NATIVE_ASSETS:[asset],http:{createHttp:()=>request,RequestMethod:{GET:'GET'},HttpDataType:{ARRAY_BUFFER:1}},
    fs:{OpenMode:{CREATE:1,TRUNC:2,WRITE_ONLY:4},openSync:()=>({fd:1}),writeSync(){events.push(['write']);},closeSync(){},unlinkSync(){events.push(['unlink']);}},
    Scene:{async load(){events.push(['sceneLoad']);return scene;}},LightType:{DIRECTIONAL:1},EnvironmentBackgroundType:{BACKGROUND_NONE:0},ModelType:{SURFACE:1},Date,DataView,ArrayBuffer };
  vm.runInNewContext(js,context);
  const p=new context.Preview();p.origin='http://192.168.1.2:5005';p.getUIContext=()=>({getHostContext:()=>({cacheDir:'/app/cache'})});
  return {p,events,nodes};
}
(async()=>{
  const good=harness(async()=>({responseCode:200,result:glb()}));await good.p.load(0);
  assert(good.p.options);assert.equal(good.p.busy,false);
  assert.deepEqual(JSON.parse(JSON.stringify(good.nodes[1].position)),{x:-2,y:-4,z:-6});
  assert.equal(good.events[0][2],100*1024*1024,'large original islands must not hit NetworkKit default 5 MB limit');
  good.p.aboutToDisappear();assert(good.events.some(e=>e[0]==='sceneDestroy'));assert(good.events.some(e=>e[0]==='contentDestroy'));assert(good.events.some(e=>e[0]==='unlink'));
  const bad=harness(async()=>({responseCode:200,result:new ArrayBuffer(20)}));await bad.p.load(0);
  assert.match(bad.p.status,/GLB/);assert(!bad.events.some(e=>e[0]==='sceneLoad'));assert.equal(bad.p.busy,false);
  let finish;const cancelled=harness(()=>new Promise(r=>finish=r));const loading=cancelled.p.load(0);
  cancelled.p.aboutToDisappear();finish({responseCode:200,result:glb()});await loading;
  assert(!cancelled.events.some(e=>e[0]==='write'));assert.equal(cancelled.p.options,null);
  const unavailable=harness(async()=>({responseCode:404,result:glb()}));await unavailable.p.load(0);assert.match(unavailable.p.status,/404/);
  console.log('PASS original GLB validation, native scene ownership, normalization, large download and cancellation');
})().catch(e=>{console.error(e);process.exitCode=1;});
