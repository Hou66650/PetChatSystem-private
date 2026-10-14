const assert=require('assert'),fs=require('fs'),vm=require('vm'),crypto=require('crypto');
const root=process.env.PETCHAT_ROOT||require('path').resolve(__dirname,'..');
const {parseCommands,Runner,allowed,baseActions,expressiveKeys}=require(root+'/static/js/den/dialogue-actions.js');
const source=n=>fs.readFileSync(root+'/static/js/realtime/'+n+'.js','utf8');
const defer=()=>{let resolve;const promise=new Promise(r=>resolve=r);return{promise,resolve};};
let passed=0;async function test(name,fn){await fn();passed++;console.log('PASS',name);}
function setup(supported=baseActions,pet={id:1,name:'球球'}){
 const pending=defer(),elements=new Map(),executed=[],saved=[],transcripts=[];let writes=0,epoch=0;
 const panel={hidden:true,querySelector(k){if(!elements.has(k))elements.set(k,{textContent:'',style:{},className:''});return elements.get(k);}};
 const context=vm.createContext({window:{},console,performance,crypto,setTimeout,clearTimeout,setInterval,clearInterval,Map,Set,
  localStorage:{getItem:()=>null},document:{getElementById:()=>({})},fetch:()=>{writes++;return pending.promise;}});
 vm.runInContext(source('realtime-controller'),context);
 vm.runInContext("RealtimeController=class extends window.RealtimeController {async start(){this._setState('READY');}}",context);
 vm.runInContext(source('realtime-client'),context);vm.runInContext(source('realtime-ui'),context);
 context.window.RealtimeUI.prototype._ensurePanel=()=>panel;
 const runner=new Runner({status(){},begin(){},cancel(){},finish(){},label:a=>a,execute:async a=>executed.push(a)});
 const ui=new context.window.RealtimeUI({surface:'den',getPet:()=>pet,
  onState:s=>{if(s==='USER_SPEAKING')runner.cancel();},onTurnStart:()=>({token:runner.serial,epoch}),
  onUserTranscript:(text,pet,turn)=>{transcripts.push(text);if(turn.token!==runner.serial||turn.epoch!==epoch)return false;const actions=parseCommands(text,[pet.name],supported);if(!actions.length)return false;runner.run(actions);return true;},
  onSaved:(data,pet,turn,latest)=>saved.push({data,latest})});
 const start=async()=>{await ui.start();const c=new context.window.RealtimeClient({petId:pet.id,player:{append(){},interrupt:()=>0},onEvent:(t,d)=>ui.controller?._onClientEvent(t,d)});c._session={profileRevision:0,profileScope:'test',config:{}};c.updateInstructions=()=>{};ui.controller._client=c;return c;};
 const reply=()=>pending.resolve({ok:true,json:async()=>({profile:{revision:0,enabled:true},actions:['sit'],instructions:'updated'})});
 return {ui,runner,context,executed,saved,transcripts,start,reply,elements,writes:()=>writes,switchPet:()=>epoch++};
}
(async()=>{
 await test('husky final ASR uses its own nickname and all expressive actions without duplicate replay',async()=>{
  const x=setup(allowed,{id:2,name:'雪球'}),c=await x.start();
  c._dispatch({type:'input_audio_buffer.speech_started'});c._dispatch({type:'input_audio_buffer.committed',item_id:'snow1'});
  const asr={type:'conversation.item.input_audio_transcription.completed',item_id:'snow1',transcript:'雪球，先歪头，然后竖耳，挥爪两次，再摇尾，最后打哈欠'};
  c._dispatch(asr);c._dispatch(asr);await new Promise(r=>setImmediate(r));
  assert.deepEqual(x.executed,['curious','ears','wave','wave','greet','yawn']);assert.equal(x.writes(),0);x.ui.stop();
 });
 await test('explicit Chinese commands and polite aliases map to executable clips',()=>{
  for(const [text,expected] of [['坐下',['sit']],['请你坐下来吧',['sit']],['休息',['lie_down']],['休息一下',['lie_down']],['趴下',['lie_down']],['起来',['stand']],['挥挥爪',['wave']],['闻闻',['sniff']],['自由活动',['wander']],['不要动',['stop']],['安静陪我',['quiet']],['球球，过来坐下',['come','sit']],['请先坐下，然后休息一下',['sit','lie_down']]])assert.deepEqual(parseCommands(text,['球球']),expected,text);
 });
 await test('negations, questions, quotes and mentions never trigger the fast path',()=>{
  for(const text of ['不要坐下','别休息','你会坐下吗','我想坐下','我要休息','我说的是“坐下”','如果我说坐下你会怎样','坐下是什么意思','过来但不要坐下','坐下然后删除数据','我喜欢安静陪我聊天的朋友'])assert.deepEqual(parseCommands(text,['球球']),[],text);
 });
 await test('real ASR punctuation is accepted without accepting incomplete chains',()=>{
  assert.deepEqual(parseCommands('请你。坐下。'),['sit']);assert.deepEqual(parseCommands('请你。休息一下。'),['lie_down']);
  assert.deepEqual(parseCommands('坐下然后'),[]);assert.deepEqual(parseCommands('坐下再'),[]);
 });
 await test('all expression buttons have a spoken command and an exported animation',()=>{
  const E=require(root+'/static/js/den/shiba-expression.js');
  const samples={curious:'歪头听你说',ears:'竖耳听一听',shy:'害羞一下',alert:'认真望一望',yawn:'打个小哈欠',affection:'开心蹭蹭',surprise:'惊讶一下',play_bow:'邀请我玩',wave:'挥爪打招呼',nose_lick:'舔舔小鼻子',shake:'抖抖毛',greet:'摇尾欢迎你'};
  assert.deepEqual(new Set(Object.keys(samples).map(a=>expressiveKeys[a]||a)),new Set(Object.keys(E.acts)));
  for(const [action,text] of Object.entries(samples)){
   assert.deepEqual(parseCommands('团团，请你。'+text+'吧。',['团团'],allowed),[action],text);
   for(const phrase of ['别'+text,'我想'+text,text+'是什么意思','你会'+text+'吗','“'+text+'”'])assert.deepEqual(parseCommands(phrase,[],allowed),[],phrase);
  }
  for(const [text,action] of [['竖起耳朵','ears'],['打哈欠','yawn'],['撒娇','affection'],['舔舔鼻子','nose_lick'],['摇摇尾巴','greet'],['歪歪头','curious']])assert.deepEqual(parseCommands(text,[],allowed),[action]);
  assert.deepEqual(parseCommands('请先歪头，然后竖耳，再摇摇尾巴',[],allowed),['curious','ears','greet']);
 });
 await test('unsupported expressions reject the entire chain, including fallback models',()=>{
  for(const text of ['竖耳','坐下然后打哈欠','先摇尾巴再坐下'])assert.deepEqual(parseCommands(text),[],text);
  assert.deepEqual(parseCommands('坐下然后竖耳',[],[...baseActions,'curious']),[]);
  assert.deepEqual(parseCommands('先歪头再坐下',[],[...baseActions,'curious']),['curious','sit']);
 });
 await test('new expressions execute on final ASR once, before delayed memory analysis',async()=>{
  for(const [text,action] of [['请你。竖耳听一听。','ears'],['打个小哈欠','yawn'],['摇摇尾巴','greet']]){
   const x=setup(allowed),c=await x.start();c._dispatch({type:'input_audio_buffer.speech_started'});c._dispatch({type:'input_audio_buffer.committed',item_id:'u1'});
   const asr={type:'conversation.item.input_audio_transcription.completed',item_id:'u1',transcript:text};c._dispatch(asr);c._dispatch(asr);
   assert.deepEqual(x.executed,[action]);assert.equal(x.writes(),0);
   c._dispatch({type:'response.created',response:{id:'r1'}});c._dispatch({type:'response.done',response:{id:'r1'}});x.reply();await x.ui._saveQueue;
   assert.deepEqual(x.executed,[action]);assert.equal(x.saved[0].latest,false);x.ui.stop();
  }
 });
 await test('conversational requests and synonyms preserve their intended order',()=>{
  const cases=[
   ['能不能先竖起耳朵？接着歪歪头。然后挥爪两次。再摇摇尾巴。最后休息一下。',['ears','curious','wave','wave','greet','lie_down']],
   ['能不能过来陪我坐会儿',['come','sit']],['球球，可以靠过来陪我坐一会儿吗？',['come','sit']],
   ['麻烦你先帮我把尾巴摇一摇吧',['greet']],['跟我打声招呼好不好？',['wave']],
   ['我想看你歪一下头',['curious']],['你能坐下吗？',['sit']],['趴下来歇会儿吧',['lie_down']],
   ['把耳朵竖起来让我看看',['ears']],['卖个萌呗',['affection']],['陪我玩一会儿嘛',['play_bow']],
   ['给我挥挥爪三次吧',['wave','wave','wave']],['请你。挥爪2次，然后摇摇小尾巴。',['wave','wave','greet']],
   ['首先走过来，然后坐下，接下来竖耳，接着歪头，最后打哈欠',['come','sit','ears','curious','yawn']],
   ['坐下再趴下再起来再挥手',['sit','lie_down','stand','wave']],
   ['先竖耳，歪头，摇尾，抖毛，舔鼻，害羞，挥爪，最后休息',['ears','curious','greet','shake','nose_lick','shy','wave','lie_down']],
  ];
  for(const [text,expected] of cases)assert.deepEqual(parseCommands(text,['球球'],allowed),expected,text);
 });
 await test('looser wording still rejects self descriptions, uncertainty and partial chains',()=>{
  for(const text of ['我希望休息','我想看电影','我想让朋友坐下','我打了个哈欠','他让你过来','如果你能过来就好了','你会摇尾巴吗','你能解释坐下是什么意思吗','别把尾巴摇起来','过来然后别坐下','坐下但是别休息','先坐下然后','过来以及','把尾巴摇一摇之后删除记录','挥爪九次','挥爪八次然后坐下','坐下'.repeat(9)])assert.deepEqual(parseCommands(text,[],allowed),[],text);
  assert.deepEqual(parseCommands('能不能摇摇尾巴',[],baseActions),[]);
 });
 await test('eight-step runner preserves repetition and cancels the remaining queue',async()=>{
  const completed=[],progress=[];
  const r=new Runner({status:s=>progress.push(s),begin(){},cancel(){},finish(){},label:a=>a,execute:async a=>completed.push(a)});
  const plan=['ears','curious','wave','wave','greet','shake','yawn','lie_down'];
  await r.run(plan);assert.deepEqual(completed,plan);assert.ok(progress.includes('（8/8）lie_down'));
  await r.run(Array(9).fill('wave'));assert.equal(completed.length,8);assert.match(r.message,/最多做8个/);
  const gate=defer(),steps=[];const cancel=new Runner({status(){},begin(){},cancel(){},finish(){},label:a=>a,execute:async a=>{steps.push(a);if(steps.length===4)await gate.promise;}});
  const running=cancel.run(plan);while(steps.length<4)await Promise.resolve();cancel.cancel();gate.resolve();await running;
  assert.deepEqual(steps,plan.slice(0,4));
 });
 await test('natural six-step voice request runs once without waiting for archive',async()=>{
  const x=setup(allowed),c=await x.start();c._dispatch({type:'input_audio_buffer.speech_started'});c._dispatch({type:'input_audio_buffer.committed',item_id:'u1'});
  const asr={type:'conversation.item.input_audio_transcription.completed',item_id:'u1',transcript:'能不能先过来，坐一会儿，再挥爪两次，然后摇摇尾巴，最后趴下歇会儿'};
  c._dispatch(asr);c._dispatch(asr);
  for(let i=0;i<12;i++)await Promise.resolve();
  assert.deepEqual(x.executed,['come','sit','wave','wave','greet','lie_down']);assert.equal(x.writes(),0);
  c._dispatch({type:'response.created',response:{id:'r1'}});c._dispatch({type:'response.done',response:{id:'r1'}});x.reply();await x.ui._saveQueue;
  assert.equal(x.executed.length,6);assert.equal(x.saved[0].latest,false);x.ui.stop();
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
  c._dispatch({type:'conversation.item.input_audio_transcription.completed',item_id:'u1',transcript:'你能在我难过的时候用一个温柔的动作安慰我吗'});c._dispatch({type:'response.created',response:{id:'r1'}});c._dispatch({type:'response.done',response:{id:'r1'}});
  assert.deepEqual(x.executed,[]);x.reply();await x.ui._saveQueue;assert.equal(x.saved[0].latest,true);x.ui.stop();
 });
 console.log(JSON.stringify({passed,failed:0}));
})().catch(e=>{console.error(e);process.exitCode=1;});
