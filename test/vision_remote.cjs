const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync('static/js/den_vision.js','utf8').replace(/^import .*;$/m,'');
const flush=()=>new Promise(r=>setImmediate(r));
function harness(){
 let resolveBlob,resolveRequest;const calls=[],errors=[],seen=[];
 const canvas={width:0,height:0,getContext:()=>({drawImage(){}}),toBlob(r){resolveBlob=r;}};
 const context={window:{},document:{createElement:()=>canvas},performance:{now:()=>100},AbortController,setTimeout,clearTimeout,clearInterval,cancelAnimationFrame(){},
  fetch:async(url,options)=>{calls.push({url,options});if(url.includes('capabilities'))return {ok:true,json:async()=>({enabled:true,token:'test-token'})};return new Promise(r=>resolveRequest=r);}};
 vm.runInNewContext(source,context);const d=new context.window.DenVision();d.configure({remote:true});d.generation=1;d.running=true;d.onError=kind=>errors.push(kind);d._consume=(...args)=>seen.push(args);
 const video={videoWidth:1280,videoHeight:720,readyState:2,currentTime:1};d.video=video;
 return {d,canvas,context,calls,errors,seen,video,blob:()=>resolveBlob({size:42}),reply:()=>resolveRequest({ok:true,json:async()=>({face:{faceLandmarks:[]},hand:{landmarks:[]},elapsedMs:12})})};
}
(async()=>{
 const h=harness();await h.d._models(1);assert.equal(h.d.backend,'computer');assert.equal(h.d.worker,null);assert.equal(h.d.face,null);assert.equal(h.d.hand,null);
 h.d._detect();h.video.currentTime++;h.d._detect();assert(h.d.pending);assert.equal(h.calls.length,1);
 assert.equal(h.canvas.width,640);assert.equal(h.canvas.height,360);
 h.blob();await flush();assert.equal(h.calls.length,2);assert.equal(h.calls[1].options.redirect,'error');assert.equal(h.calls[1].options.paitQuiet,true);
 h.reply();await flush();assert.equal(h.seen.length,1);assert.equal(h.d.pending,false);
 h.video.currentTime++;h.d._detect();h.d.stop();h.blob();await flush();assert.equal(h.calls.length,2,'cancelled encoding cannot upload');assert.equal(h.canvas.width,1);
 const late=harness();await late.d._models(1);late.d._detect();late.blob();await flush();const signal=late.calls[1].options.signal;late.d.stop();assert(signal.aborted);late.reply();await flush();assert.equal(late.seen.length,0,'late response cannot revive stopped interaction');
 const fail=harness();await fail.d._models(1);fail.context.fetch=async()=>{throw Error('offline');};fail.d._detect();fail.blob();await flush();assert.equal(fail.d.running,false);assert.deepEqual(fail.errors,['remote']);assert.equal(fail.d.worker,null,'no silent local inference fallback');
 const cancelled=harness();let done;cancelled.context.fetch=()=>new Promise(r=>done=r);const init=cancelled.d._models(1);cancelled.d.stop();done({ok:true,json:async()=>({enabled:true,token:'late'})});await init;assert.equal(cancelled.d.remoteToken,null);
 // Production encoder path: transfer rather than HTML toBlob, and release on every stop.
 const background=()=>{const h=harness(),workers=[],images=[];let takeBitmap;
  h.context.OffscreenCanvas=function(){};
  h.context.Worker=class{constructor(url){this.url=url;workers.push(this);}postMessage(data,transfer){this.sent={data,transfer};}terminate(){this.terminated=true;}};
  h.context.createImageBitmap=()=>new Promise(r=>takeBitmap=r);
  h.bitmap=()=>{const image={close(){this.closed=true;}};images.push(image);takeBitmap(image);};
  return {...h,workers,images};};
 const bg=background();await bg.d._models(1);bg.d._detect();bg.bitmap();await flush();
 assert.equal(bg.workers.length,1);const encoder=bg.workers[0];assert(encoder.url.includes('vision-encoder.js'));
 assert.equal(encoder.sent.transfer[0],bg.images[0]);assert.equal(bg.canvas.width,0,'no main-thread encoding');
 encoder.onmessage({data:{blob:{size:42}}});await flush();bg.reply();await flush();assert.equal(bg.seen.length,1);
 bg.video.currentTime++;bg.d._detect();bg.bitmap();await flush();assert.equal(bg.workers.length,1,'reuse one encoder');
 const deliverLate=encoder.onmessage;bg.d.stop();assert(encoder.terminated);deliverLate({data:{blob:{size:42}}});await flush();assert.equal(bg.calls.length,2,'cancelled worker cannot upload');
 const bitmapLate=background();await bitmapLate.d._models(1);bitmapLate.d._detect();bitmapLate.d.stop();bitmapLate.bitmap();await flush();assert(bitmapLate.images[0].closed);assert.equal(bitmapLate.workers.length,0);
 const broken=background();await broken.d._models(1);broken.d._detect();broken.bitmap();await flush();broken.workers[0].onerror();await flush();assert(!broken.d.running);assert(broken.workers[0].terminated);assert.equal(broken.calls.length,1);
 const direct=background();direct.context.VideoFrame=class{constructor(video,options){assert.equal(video,direct.video);assert(Number.isInteger(options.timestamp));}close(){this.closed=true;}};
 direct.context.createImageBitmap=()=>{throw Error('VideoFrame must avoid GPU bitmap conversion');};
 await direct.d._models(1);direct.d._detect();assert.equal(direct.workers.length,1);assert(direct.workers[0].sent.data.image instanceof direct.context.VideoFrame);direct.d.stop();await flush();assert(direct.workers[0].terminated);
 const unsupported=background();unsupported.context.VideoFrame=class{constructor(){throw Error('unsupported video input');}};
 await unsupported.d._models(1);unsupported.d._detect();unsupported.bitmap();await flush();assert.equal(unsupported.workers.length,1);unsupported.d.stop();await flush();
 // Completion-paced scheduling does not overlap or add a full interval to a slow frame.
 const loop=harness();loop.d.backend='computer';let resolveDetect,now=0,scheduled;
 loop.context.performance.now=()=>now;loop.context.setTimeout=(f,delay)=>{scheduled={f,delay};return 1;};
 loop.d._detect=()=>new Promise(r=>resolveDetect=r);
 const slow=loop.d._remoteLoop();assert.equal(scheduled,undefined);now=180;resolveDetect();await slow;assert.equal(scheduled.delay,0);
 now=200;const fast=loop.d._remoteLoop();now=225;resolveDetect();await fast;assert.equal(scheduled.delay,75);
 scheduled=undefined;const stopping=loop.d._remoteLoop();loop.d.stop();resolveDetect();await stopping;assert.equal(scheduled,undefined);
 console.log('PASS computer vision: opt-in, no tablet models, bounded frame size/single flight, quiet same-origin upload, cancellation, stale result rejection and no hot fallback');
})().catch(e=>{console.error(e);process.exitCode=1;});
