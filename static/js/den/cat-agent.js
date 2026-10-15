(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.CatAgent=api;})(typeof window!=='undefined'?window:globalThis,function(){
 'use strict';
 const distance=(a,b)=>Math.hypot(a.x-b.x,a.z-b.z);
 const words={drink:'喝一点清水',paw:'好奇地扒扒门',nibble:'尝尝猫草',observe:'看看周围',sniff:'闻闻新气味',rub:'蹭蹭脸',jump:'轻轻跳一下',groom:'整理毛发',stretch:'伸个懒腰',rest:'歇一会儿',eat:'吃点饭',sleep:'回窝睡一会儿'};
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
  constructor({model,locomotion,life,scope,animate,telemetry=false,homeReady=true,canEat=()=>true,canDrink=()=>true,relationship=()=>({}),social=()=>false,onComplete=()=>{},onStatus=()=>{},fetcher=(...args)=>fetch(...args),storage=globalThis.localStorage,now=()=>Date.now()}){
   Object.assign(this,{model,locomotion,life,scope,animate,onStatus,onComplete,canEat,canDrink,relationship,social,fetcher,storage,now});
   this.trace=new Trace();this.homeReady=homeReady;this.hunger=.45;this.thirst=.25;this.careUntil=0;this.lastNeedsSave=0;this.telemetry=telemetry;this.stream=globalThis.crypto?.randomUUID?.()||`${Date.now()}-${Math.random()}`;this.events=[];this.lastTelemetry=0;this.perceived=[];this.reason='等待环境感知';
   this.catalog=[];this.memory={};this.energy=.85;this.goal=null;this.phase='loading';this.disposed=false;this.epoch=0;this.next=0;this.pending=null;this.networkAfter=0;this.lastDecision=-Infinity;this.networkFailures=0;this.advice=null;this.agenda=[];this.socialAfter=this.now()+20000;this.wasBlocked=false;this.cooldowns={};this.lastTarget=null;
   this.key='pait-cat-exploration:'+scope;
   try{const saved=JSON.parse(storage?.getItem(this.key)||'{}');for(const [id,m] of Object.entries(saved))if(m&&Number.isFinite(m.visits)&&m.visits>=0)this.memory[id]=m;}catch(e){}
   try{const n=JSON.parse(storage?.getItem(this.key+':needs')||'{}');if(Number.isFinite(n.energy))this.energy=Math.max(.1,Math.min(1,n.energy));if(n.position&&Number.isFinite(n.position.x)&&Number.isFinite(n.position.z)&&locomotion.navigation.isWalkable(n.position)){model.position.x=n.position.x;model.position.z=n.position.z;}if(Number.isFinite(n.thirst))this.thirst=Math.max(0,Math.min(1,n.thirst));if(Number.isFinite(n.hunger))this.hunger=Math.max(0,Math.min(1,n.hunger));}catch(e){}
   locomotion.autonomous=false;life.autonomous=false;
   this.ready=this.load();
  }
  get acting(){return !!this.goal&&['acting','aligning'].includes(this.phase);}
  status(text){this.text=text;this.emit(true);this.onStatus({text,phase:this.phase,source:this.source||'local',energy:this.energy,visited:Object.values(this.memory).filter(m=>m.visits>0).length,total:this.catalog.length});}
  snapshot(){this.trace.sample(this.model.position,this.now());return {trail:this.trace.points.map(p=>[...p]),route:this.locomotion.path.slice(0,64).map(p=>[+p.x.toFixed(3),+p.z.toFixed(3)]),phase:this.disposed?'stopped':this.phase,text:this.text||'',reason:this.reason||'',source:this.source||'local',target:this.goal?.target||'',action:this.goal?.action||'',energy:this.energy,hunger:this.hunger,thirst:this.thirst,x:this.model.position.x,z:this.model.position.z,pathLength:this.locomotion.path.length,candidates:this.perceived,enabled:this.locomotion.enabled};}
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
   if(!this.homeReady)this.catalog=this.catalog.filter(p=>!['home','food','water'].includes(p.id));
   const bond=this.relationship?.()||{};this.entryChoice=bond.regularWindow===Math.floor(new Date(this.now()).getHours()/3)&&this.catalog.some(p=>p.id==='bridge')?{target:'bridge',action:'observe',source:'local',reason:'这个时段常与你见面，去入口附近看看'}:null;
   this.phase='idle';this.next=this.now()+4000;this.status(this.catalog.length?'想看看今天的小岛':'探索地图暂不可用，先在附近走走');
   if(!this.catalog.length){this.locomotion.autonomous=true;this.life.autonomous=true;}
  }
  point(p){return p.normal?{x:p.x+p.normal.x*(this.locomotion.navigation.clearance+.04),z:p.z+p.normal.z*(this.locomotion.navigation.clearance+.04)}:{x:p.x,z:p.z};}
  candidates(){return this.catalog.filter(p=>(p.id!=='food'||this.canEat())&&(p.id!=='water'||this.canDrink())&&this.now()>=(this.cooldowns[p.id]||0)&&this.locomotion.navigation.route(this.model.position,this.point(p)));}
  saveNeeds(){try{this.storage?.setItem(this.key+':needs',JSON.stringify({energy:this.energy,hunger:this.hunger,thirst:this.thirst,position:this.locomotion.navigation.isWalkable(this.model.position)?{x:this.model.position.x,z:this.model.position.z}:undefined}));}catch(e){}}
  care(candidates){
   if(this.now()<this.careUntil)return null;
   if(this.energy<.3&&candidates.some(p=>p.id==='home'))return {target:'home',action:'sleep',source:'local',reason:'精力偏低，优先回到木屋软垫恢复体力'};
   if(this.hunger>=.65&&candidates.some(p=>p.id==='food'))return {target:'food',action:'eat',source:'local',reason:'饥饿值较高，优先到食碗进食'};
   if(this.thirst>=.65&&candidates.some(p=>p.id==='water'))return {target:'water',action:'drink',source:'local',reason:'有些口渴，到清水盆喝水'};
   return null;
  }
  requestVisit(target){if(!this.locomotion.enabled||!['grass','catnip','hammock'].includes(target)||!this.catalog.some(p=>p.id===target))return false;this.interrupt();void this.plan({target,action:target==='grass'?'nibble':target==='catnip'?'sniff':'rest',source:'local',reason:'响应你的温室互动邀请'});return true;}
  requestCare(action){if(action==='drink'&&!this.canDrink()){this.status('水盆空了，请点击水盆加水');return false;}if(action==='eat'&&!this.canEat()){this.status('食盆空了，请点击食盆补充口粮');return false;}if(!this.locomotion.enabled||!['eat','sleep','drink'].includes(action)||!this.homeReady)return false;this.interrupt();void this.plan({target:action==='eat'?'food':action==='drink'?'water':'home',action,user:true,source:'local',reason:'响应你的照料指令'});return true;}
  fallback(candidates){
   const care=this.care(candidates);if(care)return care;
   const relation=this.relationship?.()||{};
   const score=p=>{const m=this.memory[p.id]||{},age=Math.min(1,(this.now()/1000-(m.updated||0))/300),novelty=1/(1+(m.visits||0));return age*1.5+novelty*(.8+(relation.personality?.curiosity||.5))+(p.id===relation.preferredPlace? .35:0)+(p.id==='toys'&&relation.favoriteToy? .3:0)-(p.id===this.lastTarget?2:0)-distance(this.model.position,this.point(p))*.025;};
   const ordered=[...candidates].sort((a,b)=>score(b)-score(a));
   const p=this.energy<.3?ordered.find(p=>p.actions.includes('rest'))||ordered[0]:ordered[0];
   const action=this.energy<.3&&p.actions.includes('rest')?'rest':p.actions[(this.memory[p.id]?.visits||0)%p.actions.length];
   return {target:p.id,action:['eat','sleep','drink'].includes(action)?p.actions.includes('observe')?'observe':'sniff':action,source:'local'};
  }
  async plan(forced=null){
   const candidates=this.candidates();this.perceived=candidates.map(p=>p.id);this.reason='已按当前位置检查地点可达性；本地策略优先较少访问地点，低精力优先休息';if(!candidates.length){this.next=this.now()+12000;this.status('先等等，寻找可以安全到达的地方');return;}
   this.lastDecision=this.now();const epoch=++this.epoch;this.pending=new AbortController();const abort=this.pending;this.phase='planning';this.status('看看附近还有什么没探索过');
   const continuation=this.agenda?.shift();const urgent=forced||this.care(candidates)||(continuation&&candidates.some(p=>p.id===continuation.target&&p.actions.includes(continuation.action))?continuation:null)||this.entryChoice;this.entryChoice=null;let plan=urgent||{...this.fallback(candidates),reason:'结合需求、相处偏好、近期经历与路线选择目标'};
   // Model advice never suspends the body. Consume a fresh proposal at a goal boundary.
   if(!urgent&&this.advice&&this.now()-this.advice.at<45000&&candidates.some(p=>p.id===this.advice.plan.target&&p.actions.includes(this.advice.plan.action))){plan=this.advice.plan;this.advice=null;}
   this.pending=null;
   if(!urgent&&!this.adviceBusy&&this.now()>=this.networkAfter){
    this.adviceBusy=true;this.adviceAbort=new AbortController();const signal=this.adviceAbort.signal;
    const timer=setTimeout(()=>this.adviceAbort?.abort(),28000);this.networkAfter=this.now()+30000;
    this.request('/api/cat-agent/decide',{candidates:candidates.map(p=>p.id),energy:this.energy,hunger:this.hunger},signal)
     .then(remote=>{if(this.disposed||this.scopeLost)return;if(remote.source==='model')this.advice={plan:remote,at:this.now()};this.networkFailures=0;this.networkAfter=this.now()+Math.max(15,Math.min(300,Number(remote.retryAfter)||0))*1000;})
     .catch(()=>{this.networkFailures=Math.min(4,this.networkFailures+1);this.networkAfter=this.now()+Math.min(120,8*2**this.networkFailures)*1000;})
     .finally(()=>{clearTimeout(timer);this.adviceBusy=false;});
   }
   if(this.disposed||this.scopeLost||epoch!==this.epoch||!this.locomotion.enabled)return;
   const place=candidates.find(p=>p.id===plan.target);
   if(!place||!place.actions.includes(plan.action)||(!urgent&&['eat','sleep','drink'].includes(plan.action))){plan=this.fallback(candidates);}
   const target=candidates.find(p=>p.id===plan.target),point=this.point(target);
   // Results are proposals. Revalidate against the live navigator before execution.
   if(!this.locomotion.goTo(point,{gait:this.energy>.65&&distance(this.model.position,point)>2?'trot':'walk'})){this.phase='idle';this.cooldowns[target.id]=this.now()+60000;this.next=this.now()+5000;this.reason='目标路线重新校验失败';this.status('路线受阻，稍后重新规划');return;}
   this.reason=plan.reason||'候选地点及动作已通过本地校验';this.locomotion.owner='agent';this.source=plan.source==='model'?'model':'local';
   this.goal={target:target.id,action:plan.action,user:!!forced?.user,point,time:0,progress:0,lastPosition:{x:this.model.position.x,z:this.model.position.z},event:globalThis.crypto?.randomUUID?.()||`${this.now()}-${Math.random().toString(36).slice(2)}`};
   this.lastTarget=target.id;this.phase='walking';this.next=this.lastDecision+8000;this.status('想去'+target.name+words[plan.action]);
  }
  interrupt(text='先陪你，探索等一会儿',preserveAgenda=false){
   ++this.epoch;if(!preserveAgenda)this.agenda=[];this.pending?.abort();this.pending=null;
   if(this.goal){const external=this.locomotion.owner==='command'&&this.locomotion.path!==this.life.approach?.path;if(!external)this.animate('idle');if(this.locomotion.owner==='agent')this.locomotion.interrupt(3);this.life.cancel(external);}
   this.goal=null;this.phase='idle';this.next=Math.max(this.lastDecision+8000,this.now()+500);this.status(text);
  }
  finish(result){
   const g=this.goal;if(!g)return;this.reason=result==='completed'?'目标动作完成，更新地点访问记录':'执行受阻或超时，目标进入短暂冷却';
   if(result==='completed'){this.onComplete({...g});if(g.action==='eat'&&this.thirst>.35&&this.canDrink())this.agenda=[{target:'water',action:'drink',source:'local',reason:'吃过饭，接着去喝一点水'}];else if(g.action==='drink')this.agenda=[{target:'home',action:'groom',source:'local',reason:'喝过水，找安静的地方整理毛发'}];}
   const previous=this.memory[g.target]||{visits:0};this.memory[g.target]={target:g.target,visits:previous.visits+(result==='completed'?1:0),result,updated:this.now()/1000};this.save();
   if(result==='blocked')this.cooldowns[g.target]=this.now()+90000;
   this.energy=Math.max(.1,Math.min(1,this.energy+(result==='completed'?(g.action==='rest'?.25:['eat','sleep','drink'].includes(g.action)?0:-.06):0)));
   if(['eat','sleep','drink'].includes(g.action))this.careUntil=this.now()+120000;this.saveNeeds();
   this.interrupt(result==='completed'?'记住这里了，待会儿再去别处看看':'这边不太好走，待会儿换个地方',result==='completed');this.animate('idle');
   // Fixed bounded payload; idempotent report never feeds personal chat archives.
   const reportAbort=new AbortController(),timer=setTimeout(()=>reportAbort.abort(),8000);
   this.request('/api/cat-agent/report',{target:g.target,result,event:g.event},reportAbort.signal).then(d=>{if(!this.disposed&&!this.scopeLost)this.merge(d.memory);}).catch(()=>{}).finally(()=>clearTimeout(timer));
  }
  step(dt,blocked){
   if(this.disposed||this.scopeLost||!this.catalog.length)return;this.trace.sample(this.model.position,this.now(),blocked);this.emit();
   dt=Math.min(.05,Math.max(0,dt));this.energy=Math.max(.05,Math.min(1,this.energy-dt*.0007));this.hunger=Math.min(1,this.hunger+dt*.001);this.thirst=Math.min(1,this.thirst+dt*.0008);if(this.now()-this.lastNeedsSave>15000){this.saveNeeds();this.lastNeedsSave=this.now();}
   if(blocked||!this.locomotion.enabled||this.locomotion.owner==='command'){
    // CatLife's own wall approach uses command ownership; it is still the active task.
    const ownWall=this.acting&&this.goal.action==='rub'&&this.life.approach&&this.locomotion.path===this.life.approach.path;
    if(!ownWall||blocked||!this.locomotion.enabled){this.wasBlocked=true;if(this.goal||this.pending)this.interrupt(!this.locomotion.enabled?'自由活动已关闭':'先陪你，探索等一会儿');return;}
   }
   if(this.wasBlocked){this.wasBlocked=false;this.next=Math.max(this.lastDecision+8000,this.now()+500);}
   if(!this.goal&&this.now()>=this.socialAfter){this.socialAfter=this.now()+120000+(1-(this.relationship?.()?.personality?.sociability||.5))*90000;const r=this.relationship?.()||{};if(r.familiarity>=.15&&this.energy>.4&&this.hunger<.65&&this.social?.(r)){this.next=this.now()+15000;return;}}
   if(!this.goal){if(!this.pending&&this.now()>=this.next&&this.locomotion.owner!=='command')void this.plan();return;}
   const g=this.goal;g.time+=dt;
   if(this.phase==='walking'){if(distance(this.model.position,g.lastPosition||this.model.position)>.03){g.lastPosition={x:this.model.position.x,z:this.model.position.z};g.progress=0;}else g.progress=(g.progress||0)+dt;if(g.progress>8){this.finish('blocked');return;}}
   if(g.time>100){this.finish('blocked');return;}
   if(this.phase==='walking'&&!this.locomotion.path.length){
    if(distance(this.model.position,g.point)>.2){this.finish('blocked');return;}
    this.phase='aligning';g.time=0;this.locomotion.interrupt(30);
   }else if(this.phase==='aligning'){
    if((g.action==='eat'&&!this.canEat())||(g.action==='drink'&&!this.canDrink())){this.finish('blocked');return;}
    const place=this.catalog.find(p=>p.id===g.target);if(Number.isFinite(place.yaw)&&this.model.rotation){const angle=Math.atan2(Math.sin(place.yaw-this.model.rotation.y),Math.cos(place.yaw-this.model.rotation.y));this.model.rotation.y+=Math.max(-dt*2,Math.min(dt*2,angle));if(Math.abs(angle)>.04)return;}
    this.phase='acting';g.time=0;
    if(g.action==='rub'){if(!this.life.seekWall()){this.finish('blocked');return;}}
    else if(['jump','groom','stretch'].includes(g.action)){if(!this.life.begin(g.action)){this.finish('blocked');return;}}
    else if(g.action==='paw')this.animate('wave');
    else if(g.target==='hammock')this.animate('sleep');
    else if(g.action==='rest'){g.restStage='lower';this.animate('sitDown');}
    else if(g.action==='nibble')this.animate('eat');
    else if(['eat','sleep','drink'].includes(g.action))this.animate(g.action==='drink'?'eat':g.action);
    else this.animate(g.action==='sniff'?'sniff':g.action==='observe'?'curious':'idle');
    this.status('在'+place.name+words[g.action]);
   }else if(this.phase==='acting'){
    if(g.action==='rest'&&g.target!=='hammock'){
     if(g.restStage==='lower'&&g.time>=1.2){g.restStage='seated';this.animate('sit');}
     if(g.restStage==='seated'&&g.time>=8){g.restStage='rise';this.animate('standUp');}
    }
    if(g.action==='eat')this.hunger=Math.max(0,this.hunger-dt*.065);
    if(g.action==='drink')this.thirst=Math.max(0,this.thirst-dt*.08);
    if(g.action==='sleep')this.energy=Math.min(1,this.energy+dt*.025);
    const gesture=['rub','jump','groom','stretch'].includes(g.action);
    if(gesture&&!this.life.active&&!this.life.approach&&g.time>.1)this.finish('completed');
    else if(!gesture&&g.time>=(g.action==='sleep'?24:g.action==='eat'?10:g.action==='drink'?6:g.action==='rest'?(g.target==='hammock'?8:9.5):g.action==='nibble'?6:3.5))this.finish('completed');
   }
  }
  dispose(){this.adviceAbort?.abort();this.saveNeeds();this.interrupt('');this.disposed=true;this.text='已离开猫咪小岛';this.emit(true);this.loadAbort?.abort();this.locomotion.autonomous=true;this.life.autonomous=true;}
 }
 return {Controller,Trace};
});
