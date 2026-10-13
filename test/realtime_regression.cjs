const vm=require('vm'),fs=require('fs'),assert=require('assert'),crypto=require('crypto');
const root=process.env.PETCHAT_ROOT||require('path').resolve(__dirname,'..');
const source=f=>fs.readFileSync(root+'/static/js/realtime/'+f+'.js','utf8');
const defer=()=>{let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b;});return {promise,resolve,reject};};
const base=()=>({window:{},console,performance,crypto,setTimeout,clearTimeout,setInterval,clearInterval,Map,fetch:async()=>{},btoa:s=>Buffer.from(s).toString('base64')});
let passed=0;
async function test(name,fn){await fn();passed++;console.log('PASS',name);}
(async()=>{
 await test('late ASR and duplicate response.done archive one correctly paired turn',()=>{
  const ctx=vm.createContext(base());vm.runInContext(source('realtime-client'),ctx);const rounds=[];
  const c=new ctx.window.RealtimeClient({petId:1,player:{interrupt:()=>0,append:()=>{}},onEvent:(t,d)=>{if(t==='round.done')rounds.push(d);}});
  const emit=(type,data={})=>c._dispatch({type,...data});
  emit('input_audio_buffer.speech_started');emit('input_audio_buffer.committed',{item_id:'u1'});emit('response.created',{response:{id:'r1'}});
  emit('response.audio_transcript.delta',{response_id:'r1',delta:'回答一'});emit('response.done',{response:{id:'r1'}});assert.equal(rounds.length,0);
  emit('input_audio_buffer.speech_started');emit('input_audio_buffer.committed',{item_id:'u2'});emit('response.created',{response:{id:'r2'}});
  emit('conversation.item.input_audio_transcription.completed',{item_id:'u1',transcript:'第一句'});
  emit('conversation.item.input_audio_transcription.completed',{item_id:'u2',transcript:'第二句'});
  emit('response.audio_transcript.delta',{response_id:'r2',delta:'回答二'});emit('response.done',{response:{id:'r2'}});emit('response.done',{response:{id:'r1'}});
  assert.deepEqual(rounds.map(x=>[x.userText,x.assistantText,x.turnId]),[['第一句','回答一',1],['第二句','回答二',2]]);
 });
 await test('closing while microphone permission is pending releases late stream',async()=>{
  const pending=defer();let tracksStopped=0;
  const ctx=vm.createContext({...base(),PCMPlayer:class{unlock(){}destroy(){}},navigator:{mediaDevices:{getUserMedia:()=>pending.promise}}});
  vm.runInContext(source('realtime-controller'),ctx);const c=new ctx.window.RealtimeController({petId:1});
  const starting=c.start();c.stop();pending.resolve({getTracks:()=>[{stop:()=>tracksStopped++}]});await starting;
  assert.equal(c.state,'STOPPED');assert.equal(tracksStopped,1);assert.equal(c._client,null);
 });
 await test('closing during session fetch cannot create a late socket',async()=>{
  const pending=defer();let connections=0;
  const ctx=vm.createContext({...base(),PCMPlayer:class{destroy(){}},RealtimeClient:class{fetchSession(){return pending.promise;}connect(){connections++;}close(){}}});
  vm.runInContext(source('realtime-controller'),ctx);const c=new ctx.window.RealtimeController({petId:1,synthetic:true});
  const starting=c.start();c.stop();pending.resolve();await starting;assert.equal(connections,0);assert.equal(c.state,'STOPPED');
 });
 function uiSetup(fetcher=async()=>({ok:true,json:async()=>({profile:{revision:0},instructions:'updated',actions:['sit']})})){
  const els=new Map();const panel={hidden:true,querySelector(k){if(!els.has(k))els.set(k,{textContent:'',style:{},className:''});return els.get(k);}};
  const controllers=[];
  class FakeController{
   constructor(opts){this.opts=opts;this.state='IDLE';this._client={_session:{profileRevision:0},updateInstructions:()=>{this.updated=true;}};controllers.push(this);}
   async start(){this.state='REQUESTING_PERMISSION';this.opts.onState(this.state);}
   stop(){this.state='STOPPED';this.opts.onState(this.state);}
  }
  const ctx=vm.createContext({...base(),fetch:fetcher,RealtimeController:FakeController,localStorage:{getItem:()=>null},document:{getElementById:()=>({})}});
  vm.runInContext(source('realtime-ui'),ctx);ctx.window.RealtimeUI.prototype._ensurePanel=()=>panel;
  return {Class:ctx.window.RealtimeUI,controllers,panel,ctx};
 }
 await test('permission-pending counts as active; second toggle closes it',async()=>{
  const x=uiSetup();const u=new x.Class({getPet:()=>({id:1})});await u.start();assert(u.isActive());u.toggle();assert(!u.isActive());assert.equal(x.controllers.length,1);
 });
 await test('completed voice is attributed to starting pet, not changed selection',async()=>{
  const x=uiSetup();let id=1,captured;const u=new x.Class({getPet:()=>({id}),onRound:(a,b,p)=>{captured=p.id;}});
  await u.start();id=2;x.controllers[0].opts.onTranscripts({userText:'你好',assistantText:'你好',done:true,turnId:1});await u._saveQueue;
  assert.equal(captured,1);u.stop();
 });
 await test('interruption while analysis is pending suppresses old action eligibility',async()=>{
  const pending=defer();const x=uiSetup(()=>pending.promise);let latest;
  const u=new x.Class({getPet:()=>({id:1}),onSaved:(d,p,c,current)=>{latest=current;}});await u.start();const emit=x.controllers[0].opts.onTranscripts;
  emit({reset:true,turnId:1});emit({done:true,turnId:1,userText:'坐下',assistantText:'好呀'});
  await Promise.resolve();await Promise.resolve();emit({reset:true,turnId:2});
  pending.resolve({ok:true,json:async()=>({profile:{revision:0},instructions:'new'})});await u._saveQueue;assert.equal(latest,false);u.stop();
 });
 await test('stopping during analysis suppresses late profile/action callback',async()=>{
  const pending=defer();const x=uiSetup(()=>pending.promise);let saved=0;const u=new x.Class({getPet:()=>({id:1}),onSaved:()=>saved++});await u.start();
  x.controllers[0].opts.onTranscripts({done:true,turnId:1,userText:'坐下',assistantText:'好呀'});
  await Promise.resolve();await Promise.resolve();u.stop();pending.resolve({ok:true,json:async()=>({profile:{revision:0}})});await u._saveQueue;assert.equal(saved,0);
 });
 await test('cancelling a pet restart cannot reopen microphone',async()=>{
  const x=uiSetup();const u=new x.Class({getPet:()=>({id:1})});await u.start();u.restartForPet();u.stop();await new Promise(r=>setTimeout(r,360));assert.equal(x.controllers.length,1);
 });
 await test('a completed queued round is still archived after hang-up',async()=>{
  let writes=0;const x=uiSetup(async()=>{writes++;return {ok:true,json:async()=>({profile:{revision:0}})};});
  const u=new x.Class({getPet:()=>({id:1})});await u.start();
  x.controllers[0].opts.onTranscripts({done:true,turnId:1,userText:'记住偏好',assistantText:'好的'});u.stop();await u._saveQueue;assert.equal(writes,1);
 });
 await test('slow analysis updates memory but cannot execute an expired action',async()=>{
  const pending=defer(),x=uiSetup(()=>pending.promise);let clock=0,eligible;
  x.ctx.performance={now:()=>clock};const u=new x.Class({getPet:()=>({id:1}),onSaved:(d,p,c,current)=>eligible=current});await u.start();
  const emit=x.controllers[0].opts.onTranscripts;emit({reset:true,turnId:1});emit({done:true,turnId:1,userText:'坐下',assistantText:'好呀'});
  clock=31000;pending.resolve({ok:true,json:async()=>({profile:{revision:0},instructions:'new',actions:['sit']})});await u._saveQueue;assert.equal(eligible,false);u.stop();
 });
 await test('a changed account or forgotten profile ends the stale voice session',async()=>{
  const x=uiSetup(async()=>({ok:false,status:409,json:async()=>({error:'档案已更新'})}));let error;
  const u=new x.Class({getPet:()=>({id:1}),onError:e=>error=e.code});await u.start();
  x.controllers[0].opts.onTranscripts({done:true,turnId:1,userText:'你好',assistantText:'你好'});await u._saveQueue;
  assert.equal(u.isActive(),false);assert.equal(error,'profile_changed');
 });
 await test('motion policy changes actual speed and rest interval',()=>{
  const {Controller}=require(root+'/static/js/den/pet-locomotion.js');const c=new Controller({navigation:{},model:{},speed:.4});c.setBehavior({speedScale:.8,idleSeconds:[14,22]});assert(Math.abs(c.speed-.32)<.001);assert.equal(c.wait,14);c.setBehavior(null);assert.equal(c.speed,.4);assert.equal(c.wait,4);
 });
 console.log(JSON.stringify({passed,failed:0}));
})().catch(e=>{console.error(e);process.exit(1);});
