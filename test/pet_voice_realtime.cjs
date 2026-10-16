const fs=require('fs'),vm=require('vm'),assert=require('assert');
const read=f=>fs.readFileSync(__dirname+'/../static/js/realtime/'+f+'.js','utf8');
const delay=()=>new Promise(r=>setImmediate(r));
const defer=()=>{let resolve;const promise=new Promise(r=>resolve=r);return {promise,resolve};};
function setup(){
 const calls=[],events=[],pending=defer(),player={append(){throw Error('must not play native voice');},interrupt(){return 0;},async appendEncoded(bytes,current){if(current()){this.played=(this.played||0)+1;return true;}return false;}};
 const ctx=vm.createContext({window:{},console,performance,setTimeout,clearTimeout,AbortController,fetch:async(url,options)=>{calls.push({url,options});return pending.promise;}});vm.runInContext(read('realtime-client'),ctx);
 const c=new ctx.window.RealtimeClient({petId:1,player,onEvent:(type,data)=>events.push({type,data})});c._session={customVoice:{id:'owned-voice',scope:'account-scope'},config:{}};
 const emit=(type,data={})=>c._dispatch({type,...data});
 const response=()=>{emit('input_audio_buffer.speech_started');emit('input_audio_buffer.speech_stopped');emit('response.created',{response:{id:'r'}});emit('response.audio_transcript.delta',{response_id:'r',delta:'今天我们一起散步吧。'});emit('response.audio.delta',{response_id:'r',delta:'ignored'});emit('response.done',{response:{id:'r',status:'completed'}});};
 return {c,emit,response,calls,events,pending,player};
}
(async()=>{
 const a=setup();a.response();a.emit('response.done',{response:{id:'r',status:'completed'}});
 assert.equal(a.calls.length,1);const body=JSON.parse(a.calls[0].options.body);assert.equal(body.voiceProfileId,'owned-voice');assert.equal(body.petId,1);assert.equal(a.calls[0].options.headers['X-Profile-Scope'],'account-scope');
 assert(!a.events.some(e=>e.type==='response.audio.delta'));
 a.pending.resolve({ok:true,arrayBuffer:async()=>new ArrayBuffer(4)});await delay();assert.equal(a.player.played,1);assert(a.events.some(e=>e.type==='custom.audio.ready'));a.c.close();
 for(const mode of ['interrupt','close','decoding']){
  const b=setup();b.response();let decoded;
  if(mode==='decoding'){decoded=defer();b.player.appendEncoded=async(bytes,current)=>{await decoded.promise;if(current())b.player.played=1;return current();};b.pending.resolve({ok:true,arrayBuffer:async()=>new ArrayBuffer(4)});await delay();}
  if(mode==='close')b.c.close();else b.emit('input_audio_buffer.speech_started');
  assert(b.calls[0].options.signal.aborted);
  b.pending.resolve({ok:true,arrayBuffer:async()=>new ArrayBuffer(4)});decoded?.resolve();await delay();
  assert(!b.player.played);assert(!b.events.some(e=>e.type==='custom.audio.ready'));b.c.close();
 }
 const f=setup();f.response();f.pending.resolve({ok:false,json:async()=>({error:'音色已变化'})});await delay();assert(f.events.some(e=>e.type==='custom.audio.error'&&e.data.message==='音色已变化'));f.c.close();
 const ctx=vm.createContext({window:{},console,performance,setTimeout,clearTimeout,setInterval,clearInterval});vm.runInContext(read('realtime-controller'),ctx);
 let warnings=0;const controller=new ctx.window.RealtimeController({petId:1,onWarning:()=>warnings++});controller._onClientEvent('response.created',{response:{id:'r'}});controller._onClientEvent('response.done',{response:{id:'r',status:'completed'},customVoice:true});assert.equal(warnings,0);assert.equal(controller.state,'AI_THINKING');
 controller._onClientEvent('custom.audio.ready',{});assert.equal(controller.state,'AI_SPEAKING');controller._setState('AI_THINKING');controller._onClientEvent('custom.audio.error',{message:'未返回声音'});assert.equal(controller.state,'READY');assert.equal(warnings,1);
 console.log('PASS custom voice routing, native suppression, duplicate completion, interruption, hangup, late decoding, errors, and speaking state');
})().catch(e=>{console.error(e);process.exitCode=1;});
