const vm=require('vm'),fs=require('fs'),assert=require('assert'),crypto=require('crypto');
const root=process.env.PETCHAT_ROOT||require('path').resolve(__dirname,'..');
const source=f=>fs.readFileSync(root+'/static/js/realtime/'+f+'.js','utf8');
let passed=0;
async function test(name,fn){await fn();passed++;console.log('PASS',name);}
function setup(){
 const frames=[],events=[],warnings=[],failures=[];let closed=0;
 const ctx=vm.createContext({window:{},console:{warn(){}},performance,crypto,setTimeout,clearTimeout,setInterval,clearInterval,Map,Set});
 vm.runInContext(source('realtime-client'),ctx);vm.runInContext(source('realtime-controller'),ctx);
 const controller=new ctx.window.RealtimeController({petId:1,onWarning:e=>warnings.push(e),onError:e=>failures.push(e)});
 const c=new ctx.window.RealtimeClient({petId:1,player:{interrupt:()=>0,append(){}},onEvent:(t,d)=>{events.push([t,d]);controller._onClientEvent(t,d);}});
 controller._client=c;controller.state='READY';
 c._session={config:{instructions:'original',turn_detection:{type:'server_vad'},input_audio_format:'pcm16',output_audio_format:'pcm',chat_mode:'audio',voice:'tongtong'}};
 c._ws={readyState:1,send:s=>frames.push(JSON.parse(s)),close:()=>closed++};
 const emit=(type,data={})=>c._dispatch({type,...data});
 const ready=()=>{emit('session.created');emit('session.updated',{session:{instructions:'original'}});};
 return {ctx,c,controller,emit,ready,frames,events,warnings,failures,closed:()=>closed};
}
(async()=>{
 await test('profile updates preserve the full GLM config and skip unchanged instructions',()=>{
  const x=setup();x.ready();assert.equal(x.c.updateInstructions('original'),false);assert.equal(x.frames.length,1);
  assert(x.c.updateInstructions('calm'));
  const update=x.frames[1].session;assert.equal(update.input_audio_format,'pcm16');assert.equal(update.output_audio_format,'pcm');assert.equal(update.turn_detection.type,'server_vad');assert.equal(update.beta_fields.chat_mode,'audio');assert.equal(update.voice,'tongtong');
  x.emit('session.updated',{session:{instructions:'calm'}});assert.equal(x.c.updateInstructions('calm'),false);x.c.close();
 });
 await test('updates wait for speech and responses, then coalesce and serialize until acknowledged',()=>{
  const x=setup();x.ready();x.emit('input_audio_buffer.speech_started');x.c.updateInstructions('first');assert.equal(x.frames.length,1);
  x.emit('input_audio_buffer.speech_stopped');x.c.updateInstructions('between-stop-and-response');assert.equal(x.frames.length,1);
  x.emit('response.created',{response:{id:'r1'}});x.c.updateInstructions('second');assert.equal(x.frames.length,1);
  x.emit('response.done',{response:{id:'r1'}});assert.equal(x.frames[1].session.instructions,'second');
  x.c.updateInstructions('third');x.c.updateInstructions('last');assert.equal(x.frames.length,2);
  x.emit('session.updated',{session:{instructions:'second'}});assert.equal(x.frames[2].session.instructions,'last');
  x.emit('session.updated',{session:{instructions:'last'}});assert.equal(x.c._appliedInstructions,'last');x.c.close();
 });
 await test('observed 1210 then session.updated keeps the call alive and does not resend rejected updates',()=>{
  const x=setup();x.ready();x.c.updateInstructions('new profile');
  x.emit('error',{error:{code:'1210',type:'session_update_validate_error',message:'API 调用参数有误，请检查文档。'}});
  x.emit('session.updated',{session:{instructions:'original'}});
  assert.equal(x.closed(),0);assert.equal(x.failures.length,0);assert.equal(x.warnings[0].kind,'profile_update');assert.equal(x.c._appliedInstructions,'original');
  const count=x.frames.length;x.c.updateInstructions('newer profile');assert.equal(x.frames.length,count);
  x.emit('input_audio_buffer.speech_started');x.emit('input_audio_buffer.speech_stopped');x.emit('response.created',{response:{id:'next'}});x.emit('response.audio.delta',{delta:'audio'});assert.equal(x.controller.state,'AI_SPEAKING');x.c.close();
 });
 await test('a failed profile update cannot interrupt a reply being played',()=>{
  const x=setup();x.ready();x.controller.state='AI_SPEAKING';x.emit('error',{error:{code:'1210',type:'session_update_validate_error'}});
  assert.equal(x.controller.state,'AI_SPEAKING');assert.equal(x.closed(),0);x.c.close();
 });
 await test('authentication errors remain fatal and show the actual code',()=>{
  const x=setup();x.ready();x.emit('error',{error:{code:'1002',type:'authentication_error'}});
  assert.equal(x.closed(),1);assert.equal(x.controller.state,'ERROR');assert(x.failures[0].message.includes('1002'));assert.equal(x.warnings.length,0);
 });
 await test('an initial config rejection fails initialization instead of pretending the call is ready',()=>{
  const x=setup();let rejected;x.c._dispatch({type:'error',error:{code:'1210',type:'session_update_validate_error'}},e=>rejected=e);
  assert(rejected);assert.equal(x.controller.state,'ERROR');assert.equal(x.closed(),1);assert.equal(x.warnings.length,0);
 });
 await test('closing clears a queued profile update',()=>{
  const x=setup();x.ready();x.c.updateInstructions('pending');x.c.close();const count=x.frames.length;x.emit('session.updated');assert.equal(x.frames.length,count);assert.equal(x.c._sessionUpdate,null);
 });
 await test('an acknowledgement containing the old instructions cannot cause an update loop',()=>{
  const x=setup();x.ready();x.c.updateInstructions('new profile');x.emit('session.updated',{session:{instructions:'original'}});
  assert.equal(x.c._appliedInstructions,'original');assert.equal(x.c._updatesDisabled,true);assert.equal(x.frames.length,2);assert.equal(x.warnings[0].code,'profile_update_not_applied');assert.equal(x.closed(),0);x.c.close();
 });
 await test('a missing update acknowledgement leaves the call usable and stops retries',()=>{
  const x=setup();let timeout;x.ctx.setTimeout=(fn)=>{timeout=fn;return 0;};x.ready();x.c.updateInstructions('new');timeout();
  assert.equal(x.c._updatesDisabled,true);assert.equal(x.closed(),0);assert.equal(x.warnings[0].code,'profile_update_timeout');x.c.close();
 });
 await test('an old cancelled response cannot release an update during the new response',()=>{
  const x=setup();x.ready();x.emit('response.created',{response:{id:'old'}});x.emit('input_audio_buffer.speech_started');x.c.updateInstructions('new');
  x.emit('input_audio_buffer.speech_stopped');x.emit('response.created',{response:{id:'new'}});x.emit('response.done',{response:{id:'old',status:'cancelled'}});assert.equal(x.frames.length,1);
  x.emit('response.done',{response:{id:'new',status:'completed'}});assert.equal(x.frames.length,2);x.c.close();
 });
 console.log(JSON.stringify({passed,failed:0}));
})().catch(e=>{console.error(e);process.exitCode=1;});
