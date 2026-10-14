(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.CatAgent=api;})(typeof window!=='undefined'?window:globalThis,function(){
 'use strict';
 const distance=(a,b)=>Math.hypot(a.x-b.x,a.z-b.z);
 const words={observe:'看看周围',sniff:'闻闻新气味',rub:'蹭蹭脸',jump:'轻轻跳一下',groom:'整理毛发',stretch:'伸个懒腰',rest:'歇一会儿',eat:'吃点饭',sleep:'回窝睡一会儿'};
 class Trace{
  constructor(){this.points=[];this.lastSample=-Infinity;}
  sample(p,t,breakPath=false){
   if(breakPath)this.breakPending=true;
   if(!Number.isFinite(p.x)||!Number.isFinite(p.z)||!Number.isFinite(t)||t-this.lastSample<200)return;
   this.lastSample=t;const last=this.points.at(-1);
   if(last&&Math.hypot(last[0]-p.x,last[1]-p.z)<.015)return;
   this.points.push([+p.x.toFixed(3),+p.z.toFixed(3),Math.floor(t),this.breakPending?1:0]);this.breakPending=false;this.points=this.points.slice(-32);
  }
 }
 class Controller{
  constructor({model,locomotion,life,scope,animate,telemetry=false,homeReady=true,onStatus=()=>{},fetcher=(...args)=>fetch(...args),storage=globalThis.localStorage,now=()=>Date.now()}){
   Object.assign(this,{model,locomotion,life,scope,animate,onStatus,fetcher,storage,now});
   this.trace=new Trace();this.homeReady=homeReady;this.hunger=.45;this.careUntil=0;this.lastNeedsSave=0;this.telemetry=telemetry;this.stream=globalThis.crypto?.randomUUID?.()||`${Date.now()}-${Math.random()}`;this.events=[];this.lastTelemetry=0;this.perceived=[];this.reason='等待环境感知';
   this.catalog=[];this.memory={};this.energy=.85;this.goal=null;this.phase='loading';this.disposed=false;this.epoch=0;this.next=0;this.pending=null;this.networkAfter=0;this.lastDecision=-Infinity;this.networkFailures=0;this.wasBlocked=false;this.cooldowns={};this.lastTarget=null;
   this.key='pait-cat-exploration:'+scope;
   try{const saved=JSON.parse(storage?.getItem(this.key)||'{}');for(const [id,m] of Object.entries(saved))if(m&&Number.isFinite(m.visits)&&m.visits>=0)this.memory[id]=m;}catch(e){}
   try{const n=JSON.parse(storage?.getItem(this.key+':needs')||'{}');if(Number.isFinite(n.energy))this.energy=Math.max(.1,Math.min(1,n.energy));if(Number.isFinite(n.hunger))this.hunger=Math.max(0,Math.min(1,n.hunger));}catch(e){}
   locomotion.autonomous=false;life.autonomous=false;
   this.ready=this.load();
  }
  get acting(){return !!this.goal&&['acting','aligning'].includes(this.phase);}
  status(text){this.text=text;this.emit(true);this.onStatus({text,phase:this.phase,source:this.source||'local',energy:this.energy,visited:Object.values(this.memory).filter(m=>m.visits>0).length,total:this.catalog.length});}
  snapshot(){this.trace.sample(this.model.position,this.now());return {trail:this.trace.points.map(p=>[...p]),route:this.locomotion.path.slice(0,64).map(p=>[+p.x.toFixed(3),+p.z.toFixed(3)]),phase:this.disposed?'stopped':this.phase,text:this.text||'',reason:this.reason||'',source:this.source||'local',target:this.goal?.target||'',action:this.goal?.action||'',energy:this.energy,hunger:this.hunger,x:this.model.position.x,z:this.model.position.z,pathLength:this.locomotion.path.length,candidates:this.perceived,enabled:this.locomotion.enabled};}
  emit(event=false){
   if(!this.telemetry||this.scopeLost)return;
   if(event){this.events.push(this.snapshot());this.events=this.events.slice(-12);}
   if(this.sending)return;
   if(!this.events.length&&this.now()-this.lastTelemetry<2000)return;
   const queued=this.events.shift(),snapshot=queued||this.snapshot();this.lastTelemetry=this.now();this.sending=true;
   const abort=new AbortController(),timer=setTimeout(()=>abort.abort(),4000);
   // Monitoring failure never blocks movement or decision execution.
   Promise.resolve().then(()=>this.fetcher('/api/cat-agent/telemetry',{method:'POST',headers:{'Content-Type':'application/json','X-Profile-Scope':this.scope},body:JSON.stringify({stream:this.stream,event:!!queued,snapshot}),signal:abort.signal}))
    .then(r=>{if(r.status===409){this.scopeLost=true;this.interrupt('账号已变化，请刷新页面');}}).catch(()=>{})
    .finally(()=>{clearTimeout(timer);this.sending=false;if(this.events.length&&!this.scopeLost)this.emit();});
  }
  async request(url,body,signal){
   const r=await this.fetcher(url,body?{method:'POST',headers:{'Content-Type':'application/json','X-Profile-Scope':this.scope},body:JSON.stringify(body),signal}:{signal,cache:'no-store'});
   if(r.status===409){this.scopeLost=true;this.interrupt('账号已变化，请刷新页面');throw Error('scope');}
   if(!r.ok)throw Error('network');const d=await r.json();
   if(d.scope&&d.scope!==this.scope){this.scopeLost=true;this.interrupt('账号已变化，请刷新页面');throw Error('scope');}return d;
  }
  merge(rows){for(const r of rows||[])if(Number.isFinite(r.visits)){
   const old=this.memory[r.target];if(!old||r.visits>=old.visits)this.memory[r.target]=r;
  }this.save();}
  save(){try{this.storage?.setItem(this.key,JSON.stringify(this.memory));}catch(e){}}
  async load(){
   this.loadAbort=new AbortController();const timer=setTimeout(()=>this.loadAbort.abort(),10000);
   try{const d=await this.request('/api/cat-agent',null,this.loadAbort.signal);if(this.disposed)return;this.catalog=d.catalog;this.merge(d.memory);}
   catch(e){if(this.disposed||this.scopeLost)return;
    clearTimeout(timer);this.loadAbort=new AbortController();const fallbackTimer=setTimeout(()=>this.loadAbort.abort(),5000);
    try{const r=await this.fetcher('/static/data/cat-world.json',{signal:this.loadAbort.signal});if(!r.ok)throw Error('catalog');const data=await r.json();if(!this.disposed)this.catalog=data;}catch(err){}finally{clearTimeout(fallbackTimer);}
   }finally{clearTimeout(timer);}
   if(this.disposed||this.scopeLost)return;
   if(!this.homeReady)this.catalog=this.catalog.filter(p=>!['home','food'].includes(p.id));
   this.phase='idle';this.next=this.now()+4000;this.status(this.catalog.length?'想看看今天的小岛':'探索地图暂不可用，先在附近走走');
   if(!this.catalog.length){this.locomotion.autonomous=true;this.life.autonomous=true;}
  }
  point(p){return p.normal?{x:p.x+p.normal.x*(this.locomotion.navigation.clearance+.04),z:p.z+p.normal.z*(this.locomotion.navigation.clearance+.04)}:{x:p.x,z:p.z};}
  candidates(){return this.catalog.filter(p=>this.now()>=(this.cooldowns[p.id]||0)&&this.locomotion.navigation.route(this.model.position,this.point(p)));}
  saveNeeds(){try{this.storage?.setItem(this.key+':needs',JSON.stringify({energy:this.energy,hunger:this.hunger}));}catch(e){}}
  care(candidates){
   if(this.now()<this.careUntil)return null;
   if(this.energy<.3&&candidates.some(p=>p.id==='home'))return {target:'home',action:'sleep',source:'local',reason:'精力偏低，优先回到木屋软垫恢复体力'};
   if(this.hunger>=.65&&candidates.some(p=>p.id==='food'))return {target:'food',action:'eat',source:'local',reason:'饥饿值较高，优先到食碗进食'};
   return null;
  }
  requestCare(action){if(!this.locomotion.enabled||!['eat','sleep'].includes(action)||!this.homeReady)return false;this.interrupt();void this.plan({target:action==='eat'?'food':'home',action,source:'local',reason:'响应你的照料指令'});return true;}
  fallback(candidates){
   const care=this.care(candidates);if(care)return care;
   const ordered=[...candidates].sort((a,b)=>(a.id===this.lastTarget)-(b.id===this.lastTarget)||(this.memory[a.id]?.visits||0)-(this.memory[b.id]?.visits||0)||(this.memory[a.id]?.updated||0)-(this.memory[b.id]?.updated||0));
   const p=this.energy<.3?ordered.find(p=>p.actions.includes('rest'))||ordered[0]:ordered[0];
   const action=this.energy<.3&&p.actions.includes('rest')?'rest':p.actions[(this.memory[p.id]?.visits||0)%p.actions.length];
   return {target:p.id,action:['eat','sleep'].includes(action)?'observe' in p.actions?'observe':'sniff':action,source:'local'};
  }
  async plan(forced=null){
   const candidates=this.candidates();this.perceived=candidates.map(p=>p.id);this.reason='已按当前位置检查地点可达性；本地策略优先较少访问地点，低精力优先休息';if(!candidates.length){this.next=this.now()+12000;this.status('先等等，寻找可以安全到达的地方');return;}
   this.lastDecision=this.now();const epoch=++this.epoch;this.pending=new AbortController();const abort=this.pending;this.phase='planning';this.status('看看附近还有什么没探索过');
   const urgent=forced||this.care(candidates);let plan=urgent||{...this.fallback(candidates),reason:this.reason};const timer=setTimeout(()=>abort.abort(),10000);
   try{if(!urgent&&this.now()>=this.networkAfter){const remote=await this.request('/api/cat-agent/decide',{candidates:candidates.map(p=>p.id),energy:this.energy,hunger:this.hunger},abort.signal);plan=remote;this.networkFailures=0;this.networkAfter=this.now()+Math.max(0,Math.min(300,Number(remote.retryAfter)||0))*1000;}}
   catch(e){if(this.scopeLost||epoch!==this.epoch||this.disposed)return;this.networkFailures=Math.min(4,this.networkFailures+1);const delay=Math.min(120,8*2**this.networkFailures);this.networkAfter=this.now()+delay*1000;plan.reason='网络请求失败，退避 '+delay+' 秒，继续本地探索';}
   finally{clearTimeout(timer);if(this.pending===abort)this.pending=null;}
   if(this.disposed||this.scopeLost||epoch!==this.epoch||!this.locomotion.enabled)return;
   const place=candidates.find(p=>p.id===plan.target);
   if(!place||!place.actions.includes(plan.action)||(!urgent&&['eat','sleep'].includes(plan.action))){plan=this.fallback(candidates);}
   const target=candidates.find(p=>p.id===plan.target),point=this.point(target);
   // Results are proposals. Revalidate against the live navigator before execution.
   if(!this.locomotion.goTo(point,{gait:this.energy>.65?'trot':'walk'})){this.phase='idle';this.cooldowns[target.id]=this.now()+60000;this.next=this.now()+5000;this.reason='目标路线重新校验失败';this.status('路线受阻，稍后重新规划');return;}
   this.reason=plan.reason||'候选地点及动作已通过本地校验';this.locomotion.owner='agent';this.source=plan.source==='model'?'model':'local';
   this.goal={target:target.id,action:plan.action,point,time:0,event:globalThis.crypto?.randomUUID?.()||`${this.now()}-${Math.random()}`};
   this.lastTarget=target.id;this.phase='walking';this.next=this.lastDecision+8000;this.status('想去'+target.name+words[plan.action]);
  }
  interrupt(text='先陪你，探索等一会儿'){
   ++this.epoch;this.pending?.abort();this.pending=null;
   if(this.goal){const external=this.locomotion.owner==='command'&&this.locomotion.path!==this.life.approach?.path;if(!external)this.animate('idle');if(this.locomotion.owner==='agent')this.locomotion.interrupt(3);this.life.cancel(external);}
   this.goal=null;this.phase='idle';this.next=Math.max(this.lastDecision+8000,this.now()+500);this.status(text);
  }
  finish(result){
   const g=this.goal;if(!g)return;this.reason=result==='completed'?'目标动作完成，更新地点访问记录':'执行受阻或超时，目标进入短暂冷却';
   const previous=this.memory[g.target]||{visits:0};this.memory[g.target]={target:g.target,visits:previous.visits+(result==='completed'?1:0),result,updated:this.now()/1000};this.save();
   if(result==='blocked')this.cooldowns[g.target]=this.now()+90000;
   this.energy=Math.max(.1,Math.min(1,this.energy+(result==='completed'?(g.action==='rest'?.25:['eat','sleep'].includes(g.action)?0:-.06):0)));
   if(['eat','sleep'].includes(g.action))this.careUntil=this.now()+120000;this.saveNeeds();
   this.interrupt(result==='completed'?'记住这里了，待会儿再去别处看看':'这边不太好走，待会儿换个地方');this.animate('idle');
   // Fixed bounded payload; idempotent report never feeds personal chat archives.
   const reportAbort=new AbortController(),timer=setTimeout(()=>reportAbort.abort(),8000);
   this.request('/api/cat-agent/report',{target:g.target,result,event:g.event},reportAbort.signal).then(d=>{if(!this.disposed&&!this.scopeLost)this.merge(d.memory);}).catch(()=>{}).finally(()=>clearTimeout(timer));
  }
  step(dt,blocked){
   if(this.disposed||this.scopeLost||!this.catalog.length)return;this.trace.sample(this.model.position,this.now(),blocked);this.emit();
   dt=Math.min(.05,Math.max(0,dt));this.energy=Math.max(.05,Math.min(1,this.energy-dt*.0007));this.hunger=Math.min(1,this.hunger+dt*.001);if(this.now()-this.lastNeedsSave>15000){this.saveNeeds();this.lastNeedsSave=this.now();}
   if(blocked||!this.locomotion.enabled||this.locomotion.owner==='command'){
    // CatLife's own wall approach uses command ownership; it is still the active task.
    const ownWall=this.acting&&this.goal.action==='rub'&&this.life.approach&&this.locomotion.path===this.life.approach.path;
    if(!ownWall||blocked||!this.locomotion.enabled){this.wasBlocked=true;if(this.goal||this.pending)this.interrupt(!this.locomotion.enabled?'自由活动已关闭':'先陪你，探索等一会儿');return;}
   }
   if(this.wasBlocked){this.wasBlocked=false;this.next=Math.max(this.lastDecision+8000,this.now()+500);}
   if(!this.goal){if(!this.pending&&this.now()>=this.next&&this.locomotion.owner!=='command')void this.plan();return;}
   const g=this.goal;g.time+=dt;
   if(g.time>100){this.finish('blocked');return;}
   if(this.phase==='walking'&&!this.locomotion.path.length){
    if(distance(this.model.position,g.point)>.2){this.finish('blocked');return;}
    this.phase='aligning';g.time=0;this.locomotion.interrupt(30);
   }else if(this.phase==='aligning'){
    const place=this.catalog.find(p=>p.id===g.target);if(Number.isFinite(place.yaw)&&this.model.rotation){const angle=Math.atan2(Math.sin(place.yaw-this.model.rotation.y),Math.cos(place.yaw-this.model.rotation.y));this.model.rotation.y+=Math.max(-dt*2,Math.min(dt*2,angle));if(Math.abs(angle)>.04)return;}
    this.phase='acting';g.time=0;
    if(g.action==='rub'){if(!this.life.seekWall()){this.finish('blocked');return;}}
    else if(['jump','groom','stretch'].includes(g.action)){if(!this.life.begin(g.action)){this.finish('blocked');return;}}
    else if(['eat','sleep'].includes(g.action))this.animate(g.action);
    else this.animate(g.action==='sniff'?'sniff':g.action==='observe'?'curious':'idle');
    this.status('在'+place.name+words[g.action]);
   }else if(this.phase==='acting'){
    if(g.action==='eat')this.hunger=Math.max(0,this.hunger-dt*.065);
    if(g.action==='sleep')this.energy=Math.min(1,this.energy+dt*.025);
    const gesture=['rub','jump','groom','stretch'].includes(g.action);
    if(gesture&&!this.life.active&&!this.life.approach&&g.time>.1)this.finish('completed');
    else if(!gesture&&g.time>=(g.action==='sleep'?24:g.action==='eat'?10:g.action==='rest'?8:3.5))this.finish('completed');
   }
  }
  dispose(){this.saveNeeds();this.interrupt('');this.disposed=true;this.text='已离开猫咪小岛';this.emit(true);this.loadAbort?.abort();this.locomotion.autonomous=true;this.life.autonomous=true;}
 }
 return {Controller,Trace};
});
