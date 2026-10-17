const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const {stripTypeScriptTypes}=require('node:module');
const flush=async()=>{for(let i=0;i<30;i++)await Promise.resolve();};
const source=stripTypeScriptTypes(fs.readFileSync('harmony/entry/src/main/ets/service/WebAudioCapture.ets','utf8').replace(/^import .*;\r?\n/gm,'').replace(/export /g,''));
function native(){
 let trusted=true,grant=async()=>({authResults:[0]}),callback,stops=0,releases=0,created=0;
 const capturer={state:2,on(t,cb){callback=cb},off(){},async start(){},async stop(){stops++;},async release(){releases++;}};
 const ctx={Uint8Array,JSON,Error,audio:{AudioState:{STATE_RUNNING:2},AudioSamplingRate:{SAMPLE_RATE_16000:16000},AudioChannel:{CHANNEL_1:1},AudioSampleFormat:{SAMPLE_FORMAT_S16LE:1},AudioEncodingType:{ENCODING_TYPE_RAW:0},SourceType:{SOURCE_TYPE_VOICE_COMMUNICATION:7},async createAudioCapturer(options){assert.equal(options.streamInfo.samplingRate,16000);created++;return capturer;}},
  abilityAccessCtrl:{createAtManager:()=>({requestPermissionsFromUser:()=>grant()})},util:{Base64Helper:class{encodeToStringSync(x){return Buffer.from(x).toString('base64')}}}};
 vm.runInNewContext(source+'\nglobalThis.Capture=WebAudioCapture;',ctx);
 const capture=new ctx.Capture(()=>({}),()=>trusted);
 return {capture,setTrusted:v=>trusted=v,setGrant:f=>grant=f,emit:b=>callback(b),stats:()=>({stops,releases,created}),capturer};
}
(async()=>{
 const a=native();assert.equal(a.capture.start('one'),'pending');await flush();assert.equal(JSON.parse(a.capture.read('one')).state,'ready');
 for(let i=0;i<15;i++)a.emit(new Int16Array([i]).buffer);
 assert.equal(JSON.parse(a.capture.read('one')).chunks.length,10);assert.equal(JSON.parse(a.capture.read('one')).chunks.length,0);
 a.setTrusted(false);assert.equal(JSON.parse(a.capture.read('one')).chunks.length,0);assert.equal(a.capture.start('bad'),'denied');
 a.setTrusted(true);a.capture.stop('wrong');assert.equal(JSON.parse(a.capture.read('one')).state,'ready');
 a.capture.close();await flush();assert.equal(a.stats().releases,1);assert.equal(a.stats().stops,1);
 const late=native();let grant;late.setGrant(()=>new Promise(r=>grant=r));late.capture.start('pending');late.capture.close();grant({authResults:[0]});await flush();assert.equal(late.stats().created,0);
 const denied=native();denied.setGrant(async()=>({authResults:[-1]}));denied.capture.start('deny');await flush();assert.equal(JSON.parse(denied.capture.read('deny')).state,'denied');assert.equal(denied.stats().created,0);
 const interrupted=native();interrupted.capture.start('call');await flush();interrupted.capturer.state=1;assert.equal(JSON.parse(interrupted.capture.read('call')).state,'stopped');await flush();assert.equal(interrupted.stats().releases,1);
 // Execute the actual browser controller with a native proxy and fake socket.
 let timer,hidden,stopped=0,sent=[],chunk=Buffer.from(new Int16Array([1000,-1000]).buffer).toString('base64');
 const ctx={window:{document:{hidden:false,addEventListener(t,f){hidden=f},removeEventListener(){}}},console,performance,crypto:require('node:crypto'),Uint8Array,Int16Array,atob:s=>Buffer.from(s,'base64').toString('binary'),setTimeout,clearTimeout,setInterval:f=>(timer=f,1),clearInterval(){timer=null},PCMPlayer:class{unlock(){}destroy(){}},RealtimeClient:class{constructor(){this.metrics={};this._session={}}async fetchSession(){}async connect(){}close(){}sendAudio(b){sent.push([...new Int16Array(b)]);}}};
 ctx.window.PaitHarmonyAudio={start:()=> 'pending',read:()=>JSON.stringify({state:'ready',chunks:[chunk]}),stop:()=>stopped++};
 vm.runInNewContext(fs.readFileSync('static/js/realtime/realtime-controller.js','utf8'),ctx);
 const controller=new ctx.window.RealtimeController({petId:1});controller._startWatch=()=>{};
 await controller.start();assert.equal(controller.state,'READY');timer();assert.deepEqual(sent,[[1000,-1000]]);assert(controller.lastLevel<0);
 controller.setMuted(true);timer();assert.equal(sent.length,1);
 ctx.window.document.hidden=true;hidden();assert.equal(controller.state,'STOPPED');assert.equal(stopped,1);assert.equal(timer,null);
 console.log('PASS Harmony voice: permission denial/cancel, trusted caller, PCM bounds, interruption cleanup, browser forwarding, mute and background stop');
})().catch(e=>{console.error(e);process.exitCode=1;});
