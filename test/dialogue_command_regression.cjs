const assert=require('assert'),fs=require('fs'),vm=require('vm'),crypto=require('crypto');
const root=process.env.PETCHAT_ROOT||require('path').resolve(__dirname,'..');
const {parseCommands,Runner}=require(root+'/static/js/den/dialogue-actions.js');
const source=n=>fs.readFileSync(root+'/static/js/realtime/'+n+'.js','utf8');
const defer=()=>{let resolve;const promise=new Promise(r=>resolve=r);return{promise,resolve};};
let passed=0;async function test(name,fn){await fn();passed++;console.log('PASS',name);}
function setup(){
 const pending=defer(),elements=new Map(),executed=[],saved=[],transcripts=[];let writes=0,epoch=0;
 const panel={hidden:true,querySelector(k){if(!elements.has(k))elements.set(k,{textContent:'',style:{},className:''});return elements.get(k);}};
 const context=vm.createContext({window:{},console,performance,crypto,setTimeout,clearTimeout,setInterval,clearInterval,Map,Set,
  localStorage:{getItem:()=>null},document:{getElementById:()=>({})},fetch:()=>{writes++;return pending.promise;}});
 vm.runInContext(source('realtime-controller'),context);
 vm.runInContext("RealtimeController=class extends window.RealtimeController {async start(){this._setState('READY');}}",context);
 vm.runInContext(source('realtime-client'),context);vm.runInContext(source('realtime-ui'),context);
 context.window.RealtimeUI.prototype._ensurePanel=()=>panel;
 const runner=new Runner({status(){},begin(){},cancel(){},finish(){},label:a=>a,execute:async a=>executed.push(a)});
 const ui=new context.window.RealtimeUI({surface:'den',getPet:()=>({id:1,name:'球球'}),
  onState:s=>{if(s==='USER_SPEAKING')runner.cancel();},onTurnStart:()=>({token:runner.serial,epoch}),
  onUserTranscript:(text,pet,turn)=>{transcripts.push(text);if(turn.token!==runner.serial||turn.epoch!==epoch)return false;const actions=parseCommands(text,[pet.name]);if(!actions.length)return false;runner.run(actions);return true;},
  onSaved:(data,pet,turn,latest)=>saved.push({data,latest})});
 const start=async()=>{await ui.start();const c=new context.window.RealtimeClient({petId:1,player:{append(){},interrupt:()=>0},onEvent:(t,d)=>ui.controller?._onClientEvent(t,d)});c._session={profileRevision:0,profileScope:'test',config:{}};c.updateInstructions=()=>{};ui.controller._client=c;return c;};
 const reply=()=>pending.resolve({ok:true,json:async()=>({profile:{revision:0,enabled:true},actions:['sit'],instructions:'updated'})});
 return {ui,runner,context,executed,saved,transcripts,start,reply,elements,writes:()=>writes,switchPet:()=>epoch++};
}
(async()=>{
 await test('explicit Chinese commands and polite aliases map to executable clips',()=>{
  for(const [text,expected] of [['坐下',['sit']],['请你坐下来吧',['sit']],['休息',['lie_down']],['休息一下',['lie_down']],['趴下',['lie_down']],['起来',['stand']],['挥挥爪',['wave']],['闻闻',['sniff']],['自由活动',['wander']],['不要动',['stop']],['安静陪我',['quiet']],['球球，过来坐下',['come','sit']],['请先坐下，然后休息一下',['sit','lie_down']]])assert.deepEqual(parseCommands(text,['球球']),expected,text);
 });
 await test('negations, questions, quotes and mentions never trigger the fast path',()=>{
  for(const text of ['不要坐下','别休息','你会坐下吗','你能坐下吗？','我想坐下','我要休息','我说的是“坐下”','如果我说坐下你会怎样','坐下是什么意思','过来但不要坐下','坐下然后删除数据','坐下再趴下再起来再挥手','我喜欢安静陪我聊天的朋友'])assert.deepEqual(parseCommands(text,['球球']),[],text);
 });
 await test('real ASR punctuation is accepted without accepting incomplete chains',()=>{
  assert.deepEqual(parseCommands('请你。坐下。'),['sit']);assert.deepEqual(parseCommands('请你。休息一下。'),['lie_down']);
  assert.deepEqual(parseCommands('坐下然后'),[]);assert.deepEqual(parseCommands('坐下再'),[]);
 });
 await test('final ASR starts the action before the AI reply or any archive request',async()=>{
  const x=setup(),c=await x.start();c._dispatch({type:'input_audio_buffer.speech_started'});c._dispatch({type:'input_audio_buffer.committed',item_id:'u1'});
  c._dispatch({type:'conversation.item.input_audio_transcription.completed',item_id:'u1',transcript:'休息'});
  assert.deepEqual(x.executed,['lie_down']);assert.equal(x.writes(),0);x.ui.stop();
 });
 await test('duplicate ASR and the late model result cannot replay an already executed command',async()=>{
  const x=setup(),c=await x.start();c._dispatch({type:'input_audio_buffer.speech_started'});c._dispatch({type:'input_audio_buffer.committed',item_id:'u1'});
  const asr={type:'conversation.item.input_audio_transcription.completed',item_id:'u1',transcript:'坐下'};c._dispatch(asr);c._dispatch(asr);
  c._dispatch({type:'response.created',response:{id:'r1'}});c._dispatch({type:'response.done',response:{id:'r1'}});x.reply();await x.ui._saveQueue;
  assert.deepEqual(x.executed,['sit']);assert.equal(x.writes(),1);assert.equal(x.saved[0].latest,false);x.ui.stop();
 });
 await test('ASR from an interrupted older turn cannot command the current pet',async()=>{
  const x=setup(),c=await x.start();for(const id of ['old','new']){c._dispatch({type:'input_audio_buffer.speech_started'});c._dispatch({type:'input_audio_buffer.committed',item_id:id});}
  c._dispatch({type:'conversation.item.input_audio_transcription.completed',item_id:'old',transcript:'坐下'});assert.deepEqual(x.executed,[]);
  c._dispatch({type:'conversation.item.input_audio_transcription.completed',item_id:'new',transcript:'休息'});assert.deepEqual(x.executed,['lie_down']);x.ui.stop();
 });
 await test('manual cancellation before ASR prevents delayed execution',async()=>{
  const x=setup(),c=await x.start();c._dispatch({type:'input_audio_buffer.speech_started'});c._dispatch({type:'input_audio_buffer.committed',item_id:'u1'});x.runner.cancel();
  c._dispatch({type:'conversation.item.input_audio_transcription.completed',item_id:'u1',transcript:'坐下'});assert.deepEqual(x.executed,[]);x.ui.stop();
 });
 await test('switching pets before ASR prevents execution in the new scene',async()=>{
  const x=setup(),c=await x.start();c._dispatch({type:'input_audio_buffer.speech_started'});c._dispatch({type:'input_audio_buffer.committed',item_id:'u1'});x.switchPet();
  c._dispatch({type:'conversation.item.input_audio_transcription.completed',item_id:'u1',transcript:'坐下'});assert.deepEqual(x.executed,[]);x.ui.stop();
 });
 await test('complex requests still use the validated model plan after archiving',async()=>{
  const x=setup(),c=await x.start();c._dispatch({type:'input_audio_buffer.speech_started'});c._dispatch({type:'input_audio_buffer.committed',item_id:'u1'});
  c._dispatch({type:'conversation.item.input_audio_transcription.completed',item_id:'u1',transcript:'你能先走到我面前然后坐下来陪我吗'});c._dispatch({type:'response.created',response:{id:'r1'}});c._dispatch({type:'response.done',response:{id:'r1'}});
  assert.deepEqual(x.executed,[]);x.reply();await x.ui._saveQueue;assert.equal(x.saved[0].latest,true);x.ui.stop();
 });
 console.log(JSON.stringify({passed,failed:0}));
})().catch(e=>{console.error(e);process.exitCode=1;});
