const assert=require('node:assert/strict');
const fs=require('node:fs'),vm=require('node:vm');
const {Loader,disposeTree}=require('../static/js/den/selected-assets.js');
const flush=()=>new Promise(r=>setImmediate(r));
function resource(){return {disposed:0,dispose(){this.disposed++}};}
function model(){
 const geometry=resource(),image={closed:0,close(){this.closed++}},texture={...resource(),isTexture:true,image};
 const material={...resource(),map:texture},skeleton=resource();
 return {scene:{traverse(fn){fn({geometry,material,skeleton});fn({geometry,material:[material],skeleton});}},geometry,material,texture,skeleton};
}
(async()=>{
 const requests=[],parsed=[];
 const loader=new Loader({parse(buffer,path,resolve){parsed.push(resolve)}},async function(url,options){'use strict';assert.equal(this,undefined,'Fetch must not receive Loader as its receiver');requests.push({url,...options});return {ok:true,arrayBuffer:async()=>new ArrayBuffer(8)}});
 assert.equal(requests.length,0,'Constructing a loader does not preload');
 const a=loader.begin(),first=loader.glb('/a.glb',a);await flush();
 const rejected=assert.rejects(first,{name:'AbortError'});
 const b=loader.begin();assert(a.signal.aborted);
 const late=model();parsed.shift()(late);await rejected;
 for(const key of ['geometry','material','texture','skeleton'])assert.equal(late[key].disposed,1,'Late parsed models released once');
 assert.equal(late.texture.image.closed,1);
 const selected=loader.glb('/b.glb',b);await flush();const valid=model();parsed.shift()(valid);assert.equal(await selected,valid);
 disposeTree(valid.scene);assert.equal(valid.texture.disposed,1);
 await assert.rejects(loader.glb('/never.glb',a),{name:'AbortError'});assert.deepEqual(requests.map(x=>x.url),['/a.glb','/b.glb']);
 const pending=[];const bitmaps=[];
 const THREE={Color:class {},Texture:class {constructor(image){this.image=image;this.repeat={set(){}};this.offset={set(){}};this.disposed=0}dispose(){this.disposed++}updateMatrix(){}},LinearFilter:1,sRGBEncoding:1};
 const context={window:{},THREE,AbortController,console,fetch:(url,options)=>new Promise(resolve=>pending.push({url,options,resolve})),createImageBitmap:async()=>{const b={width:1600,height:900,closed:0,close(){this.closed++}};bitmaps.push(b);return b}};
 vm.runInNewContext(fs.readFileSync('static/js/den/sky-background.js','utf8'),context);
 const scene={},sky=new context.window.SkyBackground(scene,{dataset:{},clientWidth:1200,clientHeight:900},'/snow');
 assert.equal(pending.length,0);sky.set('day',0);sky.set('day',0);assert.equal(pending.length,1,'Same pending sky is reused');
 sky.set('night',0);assert(pending[0].options.signal.aborted);
 pending[0].resolve({ok:true,blob:async()=>({})});await flush();assert.equal(bitmaps[0].closed,1,'Late background bitmap released');
 pending[1].resolve({ok:true,blob:async()=>({})});await flush();const old=sky.texture;assert(old);
 sky.set('night',0);assert.equal(pending.length,2);
 sky.set('day',0,'/sakura');assert.equal(old.disposed,1);assert.equal(old.image.closed,1);
 sky.set(null,0);assert(pending[2].options.signal.aborted);assert.equal(pending.length,3);
 assert.deepEqual(pending.map(x=>x.url),['/snow/day.webp','/snow/night.webp','/sakura/day.webp']);
 console.log('PASS: selected-only requests, cancellation, stale GLB/bitmap disposal, shared resource disposal, sky/theme changes, no speculative loads');
})().catch(e=>{console.error(e);process.exitCode=1});
