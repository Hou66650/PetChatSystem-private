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
 console.log('PASS computer vision: opt-in, no tablet models, bounded frame size/single flight, quiet same-origin upload, cancellation, stale result rejection and no hot fallback');
})().catch(e=>{console.error(e);process.exitCode=1;});
