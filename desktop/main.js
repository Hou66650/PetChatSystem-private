'use strict';
const {app,BrowserWindow,ipcMain,screen,Menu}=require('electron');
const path=require('node:path'),{pathToFileURL}=require('node:url'),{execFile}=require('node:child_process');
const {Motion,clampTarget}=require('./motion');
let control,petWindow,session=null,pairing=false,quitting=false,status='请在网页确认桌面传送，再粘贴一次性配对码。';
let sensing=false,action='idle',motion=new Motion(0,0),target=null,events=[],busy=false,lastWalk=0,lastCursor=0,lastSensor=0,lastContext=0,sensorBusy=false,lastFrame=Date.now(),animationUntil=0,lastPing=0,lastSample=0;
const phases=['preparing','entering','emerging','roaming'];
const messages={preparing:'已连接，正在准备宠物和饰品；请保留小岛页面。',entering:'宠物正在走入小岛传送门，请保持网页可见。',emerging:'宠物正在从桌面传送门走出。',roaming:'正在桌面探索；右键宠物可返回。'};
function checkedOrigin(raw){const u=new URL(raw);if(u.username||u.password||u.pathname!=='/'||u.search||u.hash)throw Error('只填写网站根地址');if(u.protocol!=='https:'&&!(u.protocol==='http:'&&['127.0.0.1','localhost','[::1]'].includes(u.hostname)))throw Error('公网连接必须使用 HTTPS；HTTP 仅允许本机地址');return u.origin;}
function trusted(e){return [control,petWindow].some(w=>w&&!w.isDestroyed()&&e.sender===w.webContents&&e.senderFrame===w.webContents.mainFrame&&e.senderFrame.url===pathToFileURL(path.join(__dirname,w===control?'index.html':'pet.html')).href);}
function windowFor(file,options){const w=new BrowserWindow({icon:path.join(__dirname,'../static/images/pait-app-icon-f4.png'),...options,webPreferences:{preload:path.join(__dirname,'preload.js'),contextIsolation:true,nodeIntegration:false,sandbox:true,backgroundThrottling:false}});w.webContents.setWindowOpenHandler(()=>({action:'deny'}));w.webContents.on('will-navigate',e=>e.preventDefault());w.loadFile(path.join(__dirname,file));return w;}
function state(){return {connected:!!session,status,sensing,action,pet:session?.pet,trip:session?.trip,phase:session?.phase,expiresAt:session?.expiresAt};}
function publish(){for(const w of [control,petWindow])if(w&&!w.isDestroyed())w.webContents.send('desktop:state',state());}
function stop(message){session=null;events=[];target=null;motion.halt();sensing=false;status=message;petWindow?.hide();publish();}
async function request(op,body,current=session){
 if(!current)throw Error('尚未配对');
 const r=await fetch(current.origin+'/api/portals/desktop/'+op,{method:body?'POST':'GET',headers:{'Content-Type':'application/json',Authorization:'Bearer '+current.token},body:body?JSON.stringify(body):undefined,redirect:'error',signal:AbortSignal.timeout(op==='plan'?32000:10000)});
 const d=await r.json();if(session!==current)throw Error('行程已变化');
 if(!r.ok){
  // Business conflicts must not destroy the pet's journey. Legacy uncoded 409s
  // are reconciled by the next heartbeat, never guessed from translated text.
  if(r.status===409&&d.code==='TRIP_ENDED')stop('宠物已返回小岛。');
  const error=Error(d.error||'连接失败');error.code=d.code;error.status=r.status;throw error;
 }
 if(Number.isFinite(d.expiresAt))current.expiresAt=d.expiresAt;
 return d;
}
function syncPhase(current,phase){if(session!==current||!phases.includes(phase)||phases.indexOf(phase)<phases.indexOf(current.phase))return;const changed=current.phase!==phase;current.phase=phase;status=messages[phase];if(changed){if(phase==='emerging')petWindow.showInactive();publish();}}
async function bytes(url,current,limit,authenticated=false){
 const r=await fetch(url,{headers:authenticated?{Authorization:'Bearer '+current.token}:{},redirect:'error',signal:AbortSignal.timeout(30000)});
 if(!r.ok||Number(r.headers.get('content-length'))>limit){await r.body?.cancel();throw Error('模型资源不可用或超过预算');}
 const reader=r.body.getReader(),chunks=[];let size=0;
 try{while(true){const {done,value}=await reader.read();if(done)break;size+=value.length;if(size>limit||session!==current)throw Error('模型超过资源预算或行程已结束');chunks.push(value);}}catch(e){await reader.cancel();throw e;}finally{reader.releaseLock();}
 if(session!==current)throw Error('行程已结束');const out=new Uint8Array(size);let offset=0;for(const c of chunks){out.set(c,offset);offset+=c.length;}
 if(size<20||new DataView(out.buffer).getUint32(0,true)!==0x46546c67)throw Error('不是有效的 GLB 模型');return out.buffer;
}
async function pair(raw){
 if(session)throw Error('请先召回当前宠物');const origin=checkedOrigin(raw.origin);
 if(typeof raw.code!=='string'||raw.code.trim().length<20||raw.code.trim().length>80)throw Error('请输入网页生成的一次性配对码');
 const r=await fetch(origin+'/api/portals/desktop/pair',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({code:raw.code.trim()}),redirect:'error',signal:AbortSignal.timeout(10000)}),d=await r.json();if(!r.ok)throw Error(d.error||'配对失败');
 session={origin,...d,lastContact:Date.now()};if(d.protocol!==2){try{await request('return',{});}finally{stop('服务器版本过旧，请先升级后再传送。');}throw Error(status);}
 status=messages.preparing;sensing=false;action='idle';target=null;events=[];animationUntil=0;lastFrame=Date.now();lastWalk=lastCursor=lastContext=Date.now();
 const a=screen.getPrimaryDisplay().workArea,p=clampTarget({x:a.x+a.width/2-140,y:a.y+a.height-300},a);motion=new Motion(p.x,p.y);petWindow.setPosition(Math.round(p.x),Math.round(p.y));publish();return {ok:true};
}
function event(kind){if(session?.phase!=='roaming')return;const a=screen.getPrimaryDisplay().workArea;events.push({id:require('node:crypto').randomUUID(),kind,x:(motion.x-a.x)/a.width,z:(motion.y-a.y)/a.height});events=events.slice(-12);}
function petting(){if(session?.phase!=='roaming')return;motion.halt();action='petting';animationUntil=Date.now()+2500;event('pet');publish();}
ipcMain.handle('desktop:command',async(e,command,data)=>{
 if(!trusted(e))throw Error('无效的客户端来源');
 try{
  if(command==='state')return state();
  if(command==='pair'){if(pairing)throw Error('正在配对，请稍候');pairing=true;try{return await pair(data||{});}finally{pairing=false;}}
  if(['model','accessory','ready','arrived'].includes(command)){
   const current=session;if(!current||data?.trip!==current.trip)throw Error('行程已变化');
   if(command==='model'){
    const p=current.pet.model,privateModel=current.pet.custom===true&&p==='/api/portals/desktop/model';
    if(!privateModel&&(typeof p!=='string'||!/^\/static\/models\/[a-zA-Z0-9_./-]+\.glb$/.test(p)||p.includes('..')))throw Error('模型路径无效');
    return {bytes:await bytes(current.origin+p,current,50*1024*1024,privateModel),pet:current.pet};
   }
   if(command==='accessory'){
    const id=data.item;if(!['moss-bow','coral-bow','daisy','blue-beret'].includes(id)||!current.pet.wardrobe?.some(i=>i.id===id))throw Error('该饰品不属于本次穿搭');
    return {bytes:await bytes(current.origin+'/static/models/wardrobe-v1/'+id+'.glb',current,4*1024*1024)};
   }
   const d=await request(command,{},current);syncPhase(current,d.phase);return d;
  }
  if(command==='return'){
   if(data?.trip&&data.trip!==session?.trip)return {ok:true};
   try{if(session)await request('return',{});}finally{stop('桌宠已收起，正在返回小岛；断网时小岛会在超时后自动接回。');}return {ok:true};
  }
  if(command==='pet'){petting();return {ok:true};}
  if(command==='sense'){sensing=data===true&&session?.phase==='roaming';publish();return {ok:true};}
  if(command==='menu'){Menu.buildFromTemplate([{label:'摸摸它',enabled:session?.phase==='roaming',click:petting},{label:'返回悬浮岛',click:async()=>{try{await request('return',{});stop('已返回悬浮岛。');}catch(e){status=e.message;publish();}}},{label:'显示传送控制台',click:()=>control.show()}]).popup({window:petWindow});return {ok:true};}
  if(command==='ignore'){if(e.sender===petWindow.webContents)petWindow.setIgnoreMouseEvents(data===true,{forward:true});return {ok:true};}
  throw Error('未知客户端操作');
 }catch(error){status=error.message;publish();return {error:status,code:error.code};}
});
function sense(){
 if(!sensing||sensorBusy||Date.now()-lastSensor<6000)return;lastSensor=Date.now();sensorBusy=true;const current=session;
 execFile('powershell.exe',['-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',path.join(__dirname,'sense.ps1')],{windowsHide:true,timeout:4000,maxBuffer:16384},(error,stdout)=>{
  sensorBusy=false;if(error||!sensing||session!==current||current.phase!=='roaming')return;
  try{const d=JSON.parse(stdout);if(!['document','video','desktop'].includes(d.kind)||Date.now()-lastContext<30000)return;lastContext=Date.now();const a=screen.getPrimaryDisplay().workArea;let p={x:a.x+a.width-290,y:a.y+a.height-310};if(d.bounds&&['video','desktop'].includes(d.kind)){const b=screen.screenToDipPoint({x:Math.round(d.bounds.x),y:Math.round(d.bounds.y)});p={x:b.x,y:b.y-300};}target={...clampTarget(p,a),purpose:d.kind==='desktop'?'icon':d.kind};}catch(_){ }
 });
}
async function heartbeat(){
 if(!session||busy)return;busy=true;const current=session,now=Date.now();
 try{
  if(now-lastPing>=2000){lastPing=now;await request('ping',{},current);}
  if(current.phase==='roaming'&&now-lastSample>=2000){lastSample=now;event('position');const a=screen.getPrimaryDisplay().workArea,batch=events.splice(0,12);try{await request('sample',{snapshot:{visitor:{x:(motion.x-a.x)/a.width,z:(motion.y-a.y)/a.height,yaw:motion.yaw,action}},events:batch},current);}catch(e){if(session===current)events=[...batch,...events].slice(-12);throw e;}}
  const d=await request('state',undefined,current);current.lastContact=Date.now();syncPhase(current,d.phase);
 }catch(e){if(session===current){if(Date.now()-current.lastContact>45000)stop('连接中断，桌宠已收起；小岛会自动接回。');else{status=e.message;publish();}}}finally{busy=false;}
}
async function think(){if(session?.phase!=='roaming')return;const current=session;try{const d=await request('plan',{},current);if(session!==current||current.phase!=='roaming')return;if(d.visitor==='rest'){motion.halt();action='sleep';animationUntil=Date.now()+5000;event('rest');publish();}else if(d.visitor==='cursor'){const c=screen.getCursorScreenPoint();target=clampTarget({x:c.x-140,y:c.y-220},screen.getPrimaryDisplay().workArea);}}catch(_){}}
function frame(){
 const now=Date.now(),dt=Math.min(.05,(now-lastFrame)/1000);lastFrame=now;if(session?.phase!=='roaming')return;
 const a=screen.getPrimaryDisplay().workArea,c=screen.getCursorScreenPoint();if(target)target={...target,...clampTarget(target,a)};sense();
 if(now>=animationUntil){
  if(Math.hypot(c.x-motion.x-140,c.y-motion.y-160)<100&&now-lastCursor>15000){lastCursor=now;petting();}
  else{
   if(!target&&now-lastWalk>4000){lastWalk=now;if(Math.random()<.25){action='sleep';animationUntil=now+5000;event('rest');publish();}else{target=clampTarget({x:a.x+Math.random()*Math.max(1,a.width-280),y:a.y+a.height-300},a);event('walk');}}
   if(now>=animationUntil){const m=motion.step(target,dt);const next=m.speed>1?'walk':'idle';if(action!==next){action=next;publish();}if(m.arrived&&target){const purpose=target.purpose;target=null;lastWalk=now;if(purpose){action='sleep';animationUntil=now+4000;event(purpose);publish();}}}
  }
 }
 const p=clampTarget(motion,a);motion.x=p.x;motion.y=p.y;petWindow.setPosition(Math.round(motion.x),Math.round(motion.y));
 petWindow.webContents.send('desktop:motion',{trip:session.trip,yaw:motion.yaw,turnRate:motion.turnRate||0,speed:Math.hypot(motion.vx,motion.vy),action});
}
app.whenReady().then(()=>{
 control=windowFor('index.html',{width:430,height:560,title:'派特岛 · 桌面传送门',autoHideMenuBar:true});
 petWindow=windowFor('pet.html',{width:280,height:300,frame:false,transparent:true,backgroundColor:'#00000000',alwaysOnTop:true,skipTaskbar:true,resizable:false,show:false});
 petWindow.on('close',()=>{if(!quitting)app.quit();});control.on('closed',()=>app.quit());setInterval(heartbeat,500);setInterval(think,32000);setInterval(frame,33);
});
app.on('before-quit',e=>{if(quitting)return;if(session){e.preventDefault();quitting=true;request('return',{}).catch(()=>{}).finally(()=>app.quit());}else quitting=true;});
