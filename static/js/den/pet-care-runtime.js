(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.PetCareRuntime=api;})(typeof window!=='undefined'?window:globalThis,function(){
 'use strict';
 class Controller{
  constructor(a){this.a=a;this.scope=a.scope;this.lastComfort=0;this.lastCall=0;this.epoch=0;this.enabled=true;this.ready=false;this.calls={enabled:false,clips:[]};this.pending=null;this.seen=new Set();this.fetcher=a.fetcher||fetch;this.clock=a.now||Date.now;this.audio=null;this.objectUrl=null;this.unlocked=false;
   this.unlock=()=>{this.unlocked=true;};document.addEventListener('pointerdown',this.unlock,{once:true});
   this.change=e=>{if(e.detail?.scope===this.scope&&e.detail?.petId===this.a.pet().id)void this.refresh();};document.addEventListener('pet-care-changed',this.change);
   this.visibility=()=>{if(document.hidden)this.stopAudio();else void this.poll();};document.addEventListener('visibilitychange',this.visibility);
   this.timer=setInterval(()=>void this.tick(),1000);void this.refresh();
  }
  async request(path,post=false){const r=await this.fetcher(path+'?petId='+this.a.pet().id,{method:post?'POST':'GET',headers:post?{'Content-Type':'application/json','X-Profile-Scope':this.scope}:{},body:post?'{}':undefined,cache:'no-store',paitQuiet:true});const d=await r.json();if(!r.ok||d.scope!==this.scope)throw Error('Care state unavailable');return d;}
  async refresh(){if(this.disposed)return;if(this.polling){this.refreshRequested=true;return;}this.refreshing=true;this.lastRefreshAttempt=this.clock();const token=++this.epoch;this.ready=false;this.pending=null;this.stopAudio();this.lastPet=this.a.pet().id;try{const [care,calls]=await Promise.all([this.request('/api/pet-care'),this.request('/api/pet-calls')]);if(token!==this.epoch)return;this.enabled=!!care.settings.emotion;if(!this.enabled)this.a.cancelComfort();this.calls=calls;this.ready=care.signedIn!==false;this.lastRefresh=this.clock();}catch{if(token===this.epoch)this.ready=false;}finally{if(token===this.epoch)this.refreshing=false;}}
  handle(data){if(data?.event&&!this.seen.has(data.event.id)){this.seen.add(data.event.id);this.nudge('我记下了你提到的“'+data.event.title+'”，确认一下时间，再让我惦记它吧。',true);}
   const emotion=data?.emotion;if(!emotion||!this.ready||!this.enabled)return;
   if(emotion.action==='space'){this.pending=null;this.a.cancelComfort();return;}
   if(emotion.action!=='company'||this.clock()-this.lastComfort<120000)return;
   this.pending={pet:this.a.pet().id,until:this.clock()+20000};
  }
  async tick(){if(this.disposed)return;if(this.lastPet!==this.a.pet().id){this.nudgeEl?.remove();this.pending=null;this.stopAudio();this.a.cancelComfort();return this.refresh();}if(this.a.stopped?.())return;const now=this.clock();if(!this.ready){if(!this.refreshing&&now-(this.lastRefreshAttempt||0)>15000)await this.refresh();return;}
   if(this.a.voiceActive?.())this.stopAudio();
   if(this.unlocked&&!document.hidden&&this.a.available()&&this.greetedPet!==this.lastPet){this.greetedPet=this.lastPet;void this.call('greeting');}
   if(this.pending){if(this.pending.pet!==this.a.pet().id||now>this.pending.until)this.pending=null;else if(!document.hidden&&this.a.available()){this.pending=null;this.lastComfort=now;await this.a.comfort();}}
   if(now-(this.lastPoll||0)>15000)void this.poll();
   if(now-(this.lastRefresh||0)>60000&&!this.refreshing)await this.refresh();
  }
  notifications(){try{return typeof Notification!=='undefined'&&Notification.permission==='granted'&&localStorage.getItem('pait-care-notifications:'+this.scope)==='true';}catch{return false;}}
  async poll(){if(this.disposed||!this.ready||this.polling||document.hidden&&!this.notifications()||!document.hidden&&!this.a.noticeAvailable())return;
   this.polling=true;this.lastPoll=this.clock();const token=this.epoch;try{const d=await this.request('/api/pet-care/claim',true);if(token!==this.epoch||d.petId!==this.a.pet().id||!d.notice)return;
    if(document.hidden&&this.notifications()){try{const n=new Notification('派特岛 · 有一份小小的惦记',{body:'它记得你提过的重要事情，给你留了一句鼓励。',tag:'pait-care-'+d.notice.id});n.onclick=()=>{window.focus();n.close();this.nudge(d.notice.message,false);};}catch{this.nudge(d.notice.message,false);}}
    else this.nudge(d.notice.message,false);
   }catch{}finally{this.polling=false;if(this.refreshRequested){this.refreshRequested=false;void this.refresh();}}
  }
  nudge(message,confirm){if(this.disposed)return;this.nudgeEl?.remove();const box=document.createElement('aside');box.className='pet-care-nudge';box.setAttribute('role','status');const p=document.createElement('p');p.textContent=message;const open=document.createElement('button');open.textContent=confirm?'确认时间':'看看它惦记的事';open.onclick=()=>{box.remove();this.a.open();};const dismiss=document.createElement('button');dismiss.textContent='知道啦';dismiss.onclick=()=>box.remove();box.append(p,open,dismiss);document.body.append(box);this.nudgeEl=box;}
  async call(kind,{explicit=false,imprint=null}={}){const settings=imprint?.originalCalls||this.calls,policy=imprint?.policy||this.a.imprint?.(),cooldown=policy?.vocality==='quiet'?180000:45000;
   if(this.disposed||!this.ready||!this.unlocked||document.hidden||this.a.stopped?.()||this.a.voiceActive?.()||!settings.enabled||!explicit&&this.clock()-this.lastCall<cooldown)return;
   if(!imprint&&policy?.calls?.[kind]){const pet=this.a.pet().id,token=this.epoch,serial=this.audioSerial;try{const r=await this.fetcher('/api/pet-imprint/'+pet,{cache:'no-store',paitQuiet:true,signal:AbortSignal.timeout(5000)}),d=await r.json();if(r.ok&&d.scope===this.scope&&d.petId===pet&&pet===this.a.pet().id&&token===this.epoch&&serial===this.audioSerial&&d.enabled&&d.policy.calls[kind])return this.call(kind,{explicit,imprint:d});}catch{}return;}
   // An explicitly bound recording is fetched through its current confirmed revision.
   const selected=imprint?.policy?.calls?.[kind],choices=settings.clips.filter(c=>c.kind===kind);if(!selected&&!choices.length)return;
   const clip=selected||choices[Math.floor(Math.random()*choices.length)],token=this.epoch,pet=this.a.pet().id;this.lastCall=this.clock();this.stopAudio();const serial=this.audioSerial;
   const path=selected?'/api/pet-imprint/'+pet+'/call/'+kind+'?revision='+imprint.revision:'/api/pet-calls/'+clip.id;
   try{const r=await this.fetcher(path,{cache:'no-store',paitQuiet:true,signal:AbortSignal.timeout(5000)});if(!r.ok||r.headers.get('X-Profile-Scope')!==this.scope)return;const blob=await r.blob();if(token!==this.epoch||serial!==this.audioSerial||pet!==this.a.pet().id||document.hidden||this.a.stopped?.()||this.a.voiceActive?.())return;this.objectUrl=URL.createObjectURL(blob);this.audio=new Audio(this.objectUrl);this.audio.volume=.65;this.audio.onended=()=>this.stopAudio();await this.audio.play();this.a.vocalize?.(Math.min(clip.duration,3));}catch{if(serial===this.audioSerial)this.stopAudio();}
  }
  stopAudio(){this.audioSerial=(this.audioSerial||0)+1;if(this.audio){this.audio.pause();this.audio.onended=null;this.audio=null;}if(this.objectUrl){URL.revokeObjectURL(this.objectUrl);this.objectUrl=null;}}
  manual(){this.pending=null;this.a.cancelComfort();}
  dispose(){this.disposed=true;this.epoch++;this.pending=null;this.a.cancelComfort();clearInterval(this.timer);this.stopAudio();this.nudgeEl?.remove();document.removeEventListener('pointerdown',this.unlock);document.removeEventListener('pet-care-changed',this.change);document.removeEventListener('visibilitychange',this.visibility);}
 }
 return {Controller};
});
