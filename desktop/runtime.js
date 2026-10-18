'use strict';
const {app,BrowserWindow,ipcMain,screen,Menu,Notification}=require('electron');
const path=require('node:path'),{pathToFileURL}=require('node:url'),{execFile}=require('node:child_process');
const {createHash,randomUUID}=require('node:crypto'),{clampTarget}=require('./motion'),{TripContext}=require('./trip-context');
const {validateHookSpeech,validateReaction}=require('./vendor/openpets/events.cjs');
const {DeliveryDispatcher}=require('./notifications');
const Actions=require('./actions');
let control,pairing=false,quitting=false,generation=0,status='请在网页确认桌面传送，再粘贴一次性配对码。';
const contexts=new Map(),senders=new Map();
const phases=['preparing','entering','emerging','roaming'];
const messages={preparing:'正在准备宠物与饰品',entering:'正在走入小岛传送门',emerging:'正在走出桌面传送门',roaming:'正在桌面陪伴你'};
function live(c){return !!c?.alive&&contexts.get(c.trip)===c;}
function checkedOrigin(raw){const u=new URL(raw);if(u.username||u.password||u.pathname!=='/'||u.search||u.hash)throw Error('只填写网站根地址');if(u.protocol!=='https:'&&!(u.protocol==='http:'&&['127.0.0.1','localhost','[::1]'].includes(u.hostname)))throw Error('公网连接必须使用 HTTPS；HTTP 仅允许本机地址');return u.origin;}
function windowFor(file,options){const w=new BrowserWindow({icon:path.join(__dirname,'../static/images/pait-app-icon-f5.png'),...options,webPreferences:{preload:path.join(__dirname,'preload.js'),contextIsolation:true,nodeIntegration:false,sandbox:true,backgroundThrottling:false}});w.webContents.setWindowOpenHandler(()=>({action:'deny'}));w.webContents.on('will-navigate',e=>e.preventDefault());w.loadFile(path.join(__dirname,file));return w;}
function sender(e){
 const c=senders.get(e.sender.id),w=e.sender===control?.webContents?control:c?.window,file=w===control?'index.html':'pet.html';
 if(!w||w.isDestroyed()||e.sender!==w.webContents||e.senderFrame!==w.webContents.mainFrame||e.senderFrame.url!==pathToFileURL(path.join(__dirname,file)).href)throw Error('无效的客户端来源');return c;
}
function state(c){return live(c)?{connected:true,status:c.status,sensing:c.sensing,action:c.action,actions:c.actions,autonomous:c.autonomous,pet:c.pet,trip:c.trip,phase:c.phase,expiresAt:c.expiresAt,generation:c.generation,version:c.manifest?.version,chatEnabled:!!c.manifest?.chatEnabled,voiceEnabled:!!c.manifest?.voiceEnabled,toolsEnabled:!!c.manifest?.toolsEnabled,tasks:c.tasks||[],taskClock:c.taskClock,reaction:c.reaction,assetSha256:c.manifest?.modelSha256}:{connected:false,status};}
function taskSnapshot(c,snapshot){c.tasks=snapshot.tasks;c.taskClock={serverTime:snapshot.serverTime,observedAt:Date.now()};publish(c);}
function publish(c){for(const w of [c?.window,control])if(w&&!w.isDestroyed()&&(w!==control||!c||senders.get(w.webContents.id)===c))w.webContents.send('desktop:state',state(c));}
function reaction(c,value,text){if(!live(c))return;c.reaction=validateReaction(value);c.status=validateHookSpeech(text);publish(c);}
function stop(c,message){
 if(!live(c))return;status=message;c.dispose();contexts.delete(c.trip);for(const [id,owner] of senders)if(owner===c)senders.delete(id);
 if(c.window&&!c.window.isDestroyed()){c.window.webContents.send('desktop:state',{connected:false,status});c.window.destroy();}
 if(control&&!control.isDestroyed())control.webContents.send('desktop:state',state());
}
async function request(c,op,body){
 if(!live(c))throw Error('行程已变化');const task=c.signal(['chat','speech'].includes(op)?180000:op==='plan'?32000:10000);
 try{
  const endpoint=op.startsWith('tasks/')?'/api/desktop/v1/'+op.slice(6):'/api/portals/desktop/'+op;
  const r=await fetch(c.origin+endpoint,{method:body?'POST':'GET',headers:{'Content-Type':'application/json',Authorization:'Bearer '+c.token},body:body?JSON.stringify(body):undefined,redirect:'error',signal:task.signal});
  const d=await r.json();if(!live(c))throw Error('行程已变化');
  if(!r.ok){if(r.status===409&&d.code==='TRIP_ENDED')stop(c,'宠物已返回小岛。');const error=Error(d.error||'连接失败');error.code=d.code;throw error;}
  if(Number.isFinite(d.expiresAt))c.expiresAt=d.expiresAt;return d;
 }finally{task.release();}
}
async function recall(c){
 if(!live(c))return;stop(c,'桌宠已收起，正在返回小岛；断网时小岛会在超时后自动接回。');
 try{await fetch(c.origin+'/api/portals/desktop/return',{method:'POST',headers:{'Content-Type':'application/json',Authorization:'Bearer '+c.token},body:'{}',redirect:'error',signal:AbortSignal.timeout(10000)});}catch(_){}
}
function syncPhase(c,phase){if(!live(c)||!phases.includes(phase)||phases.indexOf(phase)<phases.indexOf(c.phase))return;const changed=c.phase!==phase;c.phase=phase;if(changed){c.status=messages[phase];if(phase==='emerging')c.window.showInactive();publish(c);}}
async function refresh(c){
 const manifest=await request(c,'manifest',{}),old=c.manifest;
 if(old&&(old.modelSha256!==manifest.modelSha256||JSON.stringify(old.accessories)!==JSON.stringify(manifest.accessories))){await recall(c);throw Error('宠物模型已变化，请重新传送');}
 c.manifest=manifest;if(old?.toolsEnabled&&!manifest.toolsEnabled)c.deliveryDispatcher?.dispose();if(old?.version!==manifest.version||old?.chatEnabled!==manifest.chatEnabled||old?.voiceEnabled!==manifest.voiceEnabled||old?.toolsEnabled!==manifest.toolsEnabled)publish(c);return manifest;
}
async function bytes(url,c,limit,hash,authenticated=false){
 if(!/^[a-f0-9]{64}$/.test(hash||''))throw Error('模型缺少校验信息');const task=c.signal(30000);
 try{
  const r=await fetch(url,{headers:authenticated?{Authorization:'Bearer '+c.token}:{},redirect:'error',signal:task.signal});
  if(!r.ok||Number(r.headers.get('content-length'))>limit){await r.body?.cancel();throw Error('模型资源不可用或超过预算');}
  const reader=r.body.getReader(),chunks=[];let size=0;
  try{while(true){const {done,value}=await reader.read();if(done)break;size+=value.length;if(size>limit||!live(c))throw Error('模型超过资源预算或行程已结束');chunks.push(value);}}catch(e){await reader.cancel();throw e;}finally{reader.releaseLock();}
  if(!live(c))throw Error('行程已结束');const out=Buffer.concat(chunks);
  if(size<20||out.readUInt32LE(0)!==0x46546c67||out.readUInt32LE(4)!==2||out.readUInt32LE(8)!==size)throw Error('不是有效的 GLB 模型');
  if(createHash('sha256').update(out).digest('hex')!==hash)throw Error('模型校验不一致，请重新传送');return out.buffer.slice(out.byteOffset,out.byteOffset+out.byteLength);
 }finally{task.release();}
}
async function pair(raw){
 if(contexts.size)throw Error('当前阶段只开放一只桌宠，请先召回');const origin=checkedOrigin(raw.origin);
 if(typeof raw.code!=='string'||raw.code.trim().length<20||raw.code.trim().length>80)throw Error('请输入网页生成的一次性配对码');
 const r=await fetch(origin+'/api/portals/desktop/pair',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({code:raw.code.trim()}),redirect:'error',signal:AbortSignal.timeout(10000)}),d=await r.json();if(!r.ok)throw Error(d.error||'配对失败');
 const c=new TripContext(origin,d,++generation);contexts.set(c.trip,c);senders.set(control.webContents.id,c);
 try{
  if(d.protocol!==2)throw Error('服务器版本过旧，请升级后再传送');await refresh(c);
  c.deliveryDispatcher=new DeliveryDispatcher({Notification,alive:()=>live(c)&&!!c.manifest?.toolsEnabled,sendAck:async body=>{
   // Receipts remain valid for this one claimed attempt after trip cancellation.
   const r=await fetch(c.origin+'/api/desktop/v1/ack',{method:'POST',headers:{'Content-Type':'application/json',Authorization:'Bearer '+c.token},body:JSON.stringify(body),redirect:'error',signal:AbortSignal.timeout(10000)});
   if(!r.ok)throw Error('通知回执未确认');
  }});
  c.window=windowFor('pet.html',{width:280,height:300,frame:false,transparent:true,backgroundColor:'#00000000',alwaysOnTop:true,skipTaskbar:true,resizable:false,show:false});senders.set(c.window.webContents.id,c);
  c.window.on('closed',()=>{if(live(c))void recall(c);});
  const a=screen.getPrimaryDisplay().workArea,p=clampTarget({x:a.x+a.width/2-140,y:a.y+a.height-300},a);c.motion.x=p.x;c.motion.y=p.y;c.window.setPosition(Math.round(p.x),Math.round(p.y));publish(c);
  c.every(()=>void heartbeat(c),500);c.every(()=>void think(c),32000);c.every(()=>frame(c),16);return {ok:true};
 }catch(error){await recall(c);throw error;}
}
function event(c,kind){if(!live(c)||c.phase!=='roaming')return;const a=screen.getPrimaryDisplay().workArea;c.events.push({id:randomUUID(),kind,x:(c.motion.x-a.x)/a.width,z:(c.motion.y-a.y)/a.height});c.events=c.events.slice(-12);}
function setAction(c,id,replay=false){if(c.action===id&&!replay)return;c.action=id;c.actionSerial++;c.poseReady=false;publish(c);}
function perform(c,id){
 if(!live(c)||c.phase!=='roaming')throw Error('请等待宠物到达桌面');
 const action=c.actions.find(a=>a.id===id);if(!action)throw Error('这只宠物尚未适配该动作');
 c.motion.halt();c.target=null;c.lastWalk=Date.now();c.lastCursor=Date.now();if(!c.chatBusy&&!c.speechBusy){c.status=messages.roaming;c.reaction='idle';}
 c.animationUntil=Date.now()+action.duration*1000+1200;
 if(id==='walk'){const a=screen.getPrimaryDisplay().workArea;c.target=clampTarget({x:c.motion.x<a.x+a.width/2?a.x+a.width-280:a.x,y:c.motion.y},a);c.animationUntil=0;}
 setAction(c,id,true);return {ok:true};
}
function petting(c){if(!live(c)||c.phase!=='roaming')return;const id=c.actions.some(a=>a.id==='petting')?'petting':'idle';if(c.actions.some(a=>a.id===id))perform(c,id);event(c,'pet');}
ipcMain.handle('desktop:command',async(e,command,data)=>{
 const c=sender(e),isControl=e.sender===control.webContents;
 try{
  if(command==='state')return state(c);
  if(command==='pair'){if(!isControl)throw Error('请在控制台配对');if(pairing)throw Error('正在配对，请稍候');pairing=true;try{return await pair(data||{});}finally{pairing=false;}}
  if(!live(c))throw Error('尚未配对');
  // trip is an optional stale-message guard, never an identity selector.
  if(data?.trip&&data.trip!==c.trip)throw Error('行程已变化');
  if(['model','accessory','ready','arrived'].includes(command)){
   if(isControl)throw Error('仅宠物窗口可操作模型');
   if(command==='model'){
    const p=c.pet.model,privateModel=c.pet.custom===true&&p==='/api/portals/desktop/model';
    if(!privateModel&&(typeof p!=='string'||!/^\/static\/models\/[a-zA-Z0-9_./-]+\.glb$/.test(p)||p.includes('..')))throw Error('模型路径无效');
    const raw=await bytes(c.origin+p,c,50*1024*1024,c.manifest.modelSha256,privateModel);c.modelLoaded=true;return {bytes:raw,pet:c.pet,trip:c.trip,sha256:c.manifest.modelSha256,generation:c.generation};
   }
   if(command==='accessory'){
    const id=data.item;if(!['moss-bow','coral-bow','daisy','blue-beret'].includes(id)||!c.pet.wardrobe?.some(i=>i.id===id))throw Error('该饰品不属于本次穿搭');
    const raw=await bytes(c.origin+'/static/models/wardrobe-v1/'+id+'.glb',c,4*1024*1024,c.manifest.accessories[id]);c.accessoriesLoaded.add(id);return {bytes:raw,trip:c.trip,generation:c.generation};
   }
   if(command==='ready'&&(!c.modelLoaded||(c.pet.wardrobe||[]).some(i=>!c.accessoriesLoaded.has(i.id))))throw Error('模型与饰品尚未完成校验');
   if(command==='ready'){
    c.actions=Actions.catalog.flatMap(a=>{const supplied=data?.actions?.find(x=>x.id===a.id);return supplied&&Number.isFinite(supplied.duration)&&supplied.duration>0&&supplied.duration<=30?[{id:a.id,label:a.label,duration:supplied.duration}]:[];});
   }
   const d=await request(c,command,{});syncPhase(c,d.phase);return d;
  }
  if(command==='return'){await recall(c);return {ok:true};}
  if(['task-propose','task-approve','task-cancel','task-retry'].includes(command)){
   if(!isControl||c.phase!=='roaming')throw Error('请在控制台操作本次行程的任务');
   const result=await request(c,'tasks/'+command.slice(5),data);
   // A failed refresh cannot turn a confirmed approval into a false failure.
   try{taskSnapshot(c,await request(c,'tasks/state',{}));}catch(_){}
   if(command==='task-approve'&&result.task?.status==='succeeded'&&!result.duplicate){
    reaction(c,'success','任务已确认并开始执行');
    const timer=setTimeout(()=>{c.timers.delete(timer);if(live(c)&&c.reaction==='success')reaction(c,'idle','正在桌面陪伴你');},2200);c.timers.add(timer);
   }
   return result;
  }
  if(command==='chat'||command==='speech'){
   if(!isControl||c.phase!=='roaming'||!c.manifest.chatEnabled)throw Error('请等待宠物到达桌面后在控制台聊天');
   if(data?.version!==c.manifest.version)throw Error('档案已更新，请重新发送');
   const busyKey=command==='chat'?'chatBusy':'speechBusy';if(c[busyKey])throw Error('正在处理上一条请求');c[busyKey]=true;
   reaction(c,command==='chat'?'thinking':'working',command==='chat'?'正在听你说话':'正在准备宠物声音');
   try{
    const d=await request(c,command,data);await refresh(c);if(!c.manifest.chatEnabled||(command==='speech'&&!c.manifest.voiceEnabled)||d.version!==c.manifest.version)throw Error('档案或能力已更新，已丢弃旧结果');reaction(c,'idle','正在桌面陪伴你');
    if(command==='speech')return {bytes:Uint8Array.from(Buffer.from(d.audio,'base64')),mime:d.mime,version:d.version,trip:c.trip};return {...d,trip:c.trip};
   }finally{c[busyKey]=false;}
  }
  if(command==='action')return perform(c,data?.id);
  if(command==='autonomous'){
   if(c.phase!=='roaming')throw Error('请等待宠物到达桌面');
   c.autonomous=data===true;c.target=null;c.motion.halt();c.animationUntil=0;c.lastWalk=Date.now();setAction(c,'idle');publish(c);return {ok:true};
  }
  if(command==='pose'){
   if(isControl||data?.generation!==c.generation||data?.assetSha256!==c.manifest.modelSha256||data?.serial!==c.actionSerial)throw Error('动作回执不属于当前模型或行程');
   c.poseReady=data.ready===true;return {ok:true};
  }
  if(command==='pet'){petting(c);return {ok:true};}
  if(command==='sense'){c.sensing=data===true&&c.phase==='roaming';publish(c);return {ok:true};}
  if(command==='menu'){Menu.buildFromTemplate([{label:'和它聊天',enabled:c.phase==='roaming',click:()=>control.show()},{label:'摸摸它',enabled:c.phase==='roaming',click:()=>petting(c)},{label:'陪伴动作',enabled:c.phase==='roaming',submenu:c.actions.map(a=>({label:a.label,click:()=>perform(c,a.id)}))},{label:'自主活动',type:'checkbox',checked:c.autonomous,click:item=>{c.autonomous=item.checked;c.target=null;c.motion.halt();c.animationUntil=0;setAction(c,'idle');publish(c);}},{label:'返回悬浮岛',click:()=>void recall(c)}]).popup({window:c.window});return {ok:true};}
  if(command==='ignore'&&!isControl){c.window.setIgnoreMouseEvents(data===true,{forward:true});return {ok:true};}
  throw Error('未知客户端操作');
 }catch(error){if(live(c)){reaction(c,'error',command.startsWith('task-')?'操作结果请以任务卡为准':'这次操作未能完成');if(error.code==='CONTEXT_CHANGED')await refresh(c).catch(()=>{});}return {error:error.message,code:error.code};}
});
function sense(c){
 if(!c.actions.some(a=>a.id==='walk')||!c.autonomous||!c.sensing||c.sensorBusy||Date.now()-c.lastSensor<6000)return;c.lastSensor=Date.now();c.sensorBusy=true;
 c.sensor=execFile('powershell.exe',['-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',path.join(__dirname,'sense.ps1')],{windowsHide:true,timeout:4000,maxBuffer:16384},(error,stdout)=>{
  c.sensorBusy=false;c.sensor=null;if(error||!live(c)||!c.autonomous||!c.sensing||c.phase!=='roaming'||Date.now()<c.animationUntil)return;
  try{const d=JSON.parse(stdout);if(!['document','video','desktop'].includes(d.kind)||Date.now()-c.lastContext<30000)return;c.lastContext=Date.now();const a=screen.getPrimaryDisplay().workArea;let p={x:a.x+a.width-290,y:a.y+a.height-310};if(d.bounds&&['video','desktop'].includes(d.kind)){const b=screen.screenToDipPoint({x:Math.round(d.bounds.x),y:Math.round(d.bounds.y)});p={x:b.x,y:b.y-300};}c.target={...clampTarget(p,a),purpose:d.kind==='desktop'?'icon':d.kind};}catch(_){}
 });
}
async function heartbeat(c){
 if(!live(c)||c.busy)return;c.busy=true;const now=Date.now();
 try{
  if(now-c.lastPing>=2000){
   c.lastPing=now;await request(c,'ping',{});await refresh(c);
   if(c.phase==='roaming'){
    taskSnapshot(c,await request(c,'tasks/state',{}));
    if(c.manifest.toolsEnabled){const claimed=await request(c,'tasks/claim',{});if(claimed.delivery)c.deliveryDispatcher.deliver(claimed.delivery);}
   }
  }
  if(c.phase==='roaming'&&now-c.lastSample>=2000){c.lastSample=now;event(c,'position');const a=screen.getPrimaryDisplay().workArea,batch=c.events.splice(0,12);try{await request(c,'sample',{snapshot:{visitor:{x:(c.motion.x-a.x)/a.width,z:(c.motion.y-a.y)/a.height,yaw:c.motion.yaw,action:Actions.wire(c.action)}},events:batch});}catch(e){if(live(c))c.events=[...batch,...c.events].slice(-12);throw e;}}
  const d=await request(c,'state');c.lastContact=Date.now();syncPhase(c,d.phase);
 }catch(e){if(live(c)){if(Date.now()-c.lastContact>45000)stop(c,'连接中断，桌宠已收起；小岛会自动接回。');else reaction(c,'error','连接暂时未能确认');}}finally{c.busy=false;}
}
async function think(c){if(!live(c)||c.phase!=='roaming'||!c.autonomous||Date.now()<c.animationUntil)return;try{const d=await request(c,'plan',{});if(!live(c)||c.phase!=='roaming'||!c.autonomous||Date.now()<c.animationUntil)return;if(d.visitor==='rest'&&c.actions.some(a=>a.id==='sleep')){perform(c,'sleep');event(c,'rest');}else if(d.visitor==='cursor'&&c.actions.some(a=>a.id==='walk')){const p=screen.getCursorScreenPoint();c.target=clampTarget({x:p.x-140,y:p.y-220},screen.getPrimaryDisplay().workArea);}}catch(_){} }

function frame(c){
 const now=Date.now(),dt=Math.min(.05,(now-c.lastFrame)/1000);c.lastFrame=now;if(c.phase!=='roaming')return;
 const a=screen.getPrimaryDisplay().workArea,pointer=screen.getCursorScreenPoint();if(c.target)c.target={...c.target,...clampTarget(c.target,a)};sense(c);
 if(now>=c.animationUntil){
  if(c.autonomous&&Math.hypot(pointer.x-c.motion.x-140,pointer.y-c.motion.y-160)<100&&now-c.lastCursor>15000){c.lastCursor=now;petting(c);}
  else{
   if(c.autonomous&&!c.target&&now-c.lastWalk>5500){
    c.lastWalk=now;
    if(Math.random()<.7||!c.actions.some(a=>a.id==='walk')){
     const id=Actions.choose(c.actions.map(a=>a.id),c.recentActions);if(c.actions.some(a=>a.id===id)){perform(c,id);c.recentActions=[...c.recentActions,id].slice(-6);if(id==='sleep')event(c,'rest');}
    }else{c.target=clampTarget({x:a.x+Math.random()*Math.max(1,a.width-280),y:a.y+a.height-300},a);event(c,'walk');}
   }
   if(now>=c.animationUntil){
    const next=c.target?'walk':'idle';setAction(c,next);
    // Wait for this exact request's standing pose and gait blend before moving the window.
    if(c.target&&c.poseReady){const m=c.motion.step(c.target,dt);if(m.arrived){const purpose=c.target.purpose;c.target=null;c.lastWalk=now;c.motion.halt();setAction(c,'idle');if(purpose){event(c,purpose);if(c.actions.some(a=>a.id==='sit'))perform(c,'sit');}}}
    else c.motion.halt();
   }
  }
 }

 const p=clampTarget(c.motion,a);c.motion.x=p.x;c.motion.y=p.y;const x=Math.round(p.x),y=Math.round(p.y);if(c.windowX!==x||c.windowY!==y){c.window.setPosition(x,y);c.windowX=x;c.windowY=y;}
 c.window.webContents.send('desktop:motion',{trip:c.trip,generation:c.generation,assetSha256:c.manifest.modelSha256,yaw:c.motion.yaw,turnRate:c.motion.turnRate||0,speed:Math.hypot(c.motion.vx,c.motion.vy),action:c.action,actionSerial:c.actionSerial});
}
app.whenReady().then(()=>{if(process.platform==='win32')app.setAppUserModelId('com.pait.island.desktop');control=windowFor('index.html',{width:460,height:760,title:'派特岛 · 桌面陪伴',autoHideMenuBar:true});control.on('closed',()=>app.quit());});
app.on('before-quit',e=>{if(quitting)return;quitting=true;const trips=[...contexts.values()];if(trips.length){e.preventDefault();Promise.all(trips.map(recall)).finally(()=>app.quit());}});
