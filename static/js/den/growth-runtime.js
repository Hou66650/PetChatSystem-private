/* Event-driven growth; no extra render loop, camera access or model downloads. */
(function(){'use strict';
 const states=new Map();let adapter=null,token=0,refreshing=false,active=0,refreshTimer=null,effectAt=0,photoAt=0,voice=null;
 let unlocked=false,ctx=null,ambient=null,stepAt=0,chirpAt=0;
 function context(){if(!unlocked)return null;if(!ctx){const C=window.AudioContext||window.webkitAudioContext;if(!C)return null;ctx=new C();}if(ctx.state==='suspended')void ctx.resume().catch(()=>{});return ctx;}
 function silent(){return document.hidden||!adapter||adapter.busy?.();}
 function stop(){voice?.stop();voice=null;try{ambient?.stop();}catch{}ambient=null;try{navigator.vibrate?.(0);window.PaitHarmonyAudio?.cancelPulse?.();}catch{} }
 function noise(duration,volume,frequency){const c=context();if(!c)return;const b=c.createBuffer(1,Math.ceil(c.sampleRate*duration),c.sampleRate),samples=b.getChannelData(0);for(let i=0;i<samples.length;i++)samples[i]=(Math.random()*2-1)*(1-i/samples.length);const s=c.createBufferSource(),g=c.createGain(),f=c.createBiquadFilter();s.buffer=b;g.gain.value=volume;f.type='lowpass';f.frequency.value=frequency;s.connect(f).connect(g).connect(c.destination);s.start();s.onended=()=>{s.disconnect();f.disconnect();g.disconnect();};}
 function ambience(p){if(ambient||p.ambient!=='rain'||silent())return;const c=context();if(!c)return;const b=c.createBuffer(1,c.sampleRate*2,c.sampleRate),samples=b.getChannelData(0);for(let i=0;i<samples.length;i++)samples[i]=Math.random()*2-1;const s=c.createBufferSource(),g=c.createGain(),f=c.createBiquadFilter();s.buffer=b;s.loop=true;g.gain.value=.022;f.type='lowpass';f.frequency.value=900;s.connect(f).connect(g).connect(c.destination);s.start();ambient=s;s.onended=()=>{s.disconnect();f.disconnect();g.disconnect();};}
 async function load(petId){try{const r=await fetch('/api/growth/'+petId+'?runtime=1',{cache:'no-store',paitQuiet:true,signal:AbortSignal.timeout(4000)});const d=await r.json();if(!r.ok||d.scope!==window.COMPANION_SCOPE)throw Error('scope');states.set(petId,d);return d;}catch{states.delete(petId);return null;}}
 async function refresh(){if(!adapter||document.hidden||refreshing)return;const pet=adapter.pet(),t=token;refreshing=true;try{const d=await load(pet);if(t!==token||pet!==adapter.pet()||!d?.enrolled)return;adapter.changed?.(d);await photos(d,pet,t);}finally{refreshing=false;}}
 async function photos(d,pet,t){if(silent()||!d.memoryEnabled||!d.prefs.autoPhoto||Date.now()-photoAt<10000||!adapter.capture)return;const events=d.memories.filter(m=>!m.hasPhoto&&d.serverTime-m.created>=0&&d.serverTime-m.created<25);if(!events.length)return;
  let image;try{image=adapter.capture();}catch{return;}if(!image||t!==token){clearTimeout(refreshTimer);refreshTimer=setTimeout(()=>void refresh(),1800);return;}photoAt=Date.now();
  for(const event of events.slice(0,5)){if(t!==token||document.hidden||pet!==adapter.pet())return;try{const r=await fetch('/api/growth/'+pet+'/memories/'+event.id+'/photo',{method:'POST',headers:{'Content-Type':'application/json','X-Profile-Scope':window.COMPANION_SCOPE},body:JSON.stringify({image}),paitQuiet:true,signal:AbortSignal.timeout(5000)});if(r.ok)event.hasPhoto=true;}catch{}}
 }
 function interaction(e){const {petId,kind}=e.detail||{};if(petId!==adapter?.pet()||silent())return;const d=states.get(petId);if(!d?.enrolled||!d.memoryEnabled)return;adapter.mood?.({pet:'放松',hand:'亲近',feed:'满足',game:'兴奋',gaze:'安心',gesture:'好奇',visit:'好奇'}[kind]||'平静');if(!unlocked||Date.now()-effectAt<8000)return;effectAt=Date.now();
  if(['pet','hand'].includes(kind)&&d.prefs.haptics){try{if(window.PaitHarmonyAudio?.pulse)window.PaitHarmonyAudio.pulse(d.prefs.haptics);else navigator.vibrate?.([12*d.prefs.haptics,35,12*d.prefs.haptics]);}catch{}}
  if(d.prefs.sound&&window.PetSounds?.effect){voice?.stop();voice=window.PetSounds.effect(petId,petId===3?(['pet','hand','gaze'].includes(kind)?'purr':'meow'):(kind==='visit'?'bark':'whine'),d.appearance.voiceRate);}
 }
 function recorded(e){if(e.detail?.petId!==adapter?.pet())return;clearTimeout(refreshTimer);refreshTimer=setTimeout(()=>void refresh(),800);}
 window.PetGrowth={load,state:id=>states.get(id),bind(a){adapter=a;active=a.pet();token++;},
  tick(){if(!adapter)return;const pet=adapter.pet();if(pet!==active){active=pet;token++;stop();return;}const d=states.get(pet);if(!d?.enrolled||!d.memoryEnabled||silent()){if(ambient||voice)stop();return;}ambience(d.prefs);const now=Date.now();
   if(d.prefs.footsteps&&adapter.walking?.()&&now-stepAt>420){stepAt=now;noise(.045,.035,adapter.surface?.()==='wood'?1500:650);}
   if(d.prefs.ambient==='insects'&&now-chirpAt>7000){chirpAt=now;const c=context();if(c){const s=c.createOscillator(),g=c.createGain();s.frequency.value=3600;g.gain.setValueAtTime(.009,c.currentTime);g.gain.exponentialRampToValueAtTime(.0001,c.currentTime+.18);s.connect(g).connect(c.destination);s.start();s.stop(c.currentTime+.18);s.onended=()=>{s.disconnect();g.disconnect();};}}
  },actions(id){const d=states.get(id);return !d?.enrolled?[]:[['curious','好奇观察',7],['greet','开心问候',30],['affection','亲密撒娇',100]].filter(a=>d.appearance.togetherDays>=a[2]);},stop};
 document.addEventListener('pointerdown',()=>{unlocked=true;},{once:true});document.addEventListener('pet-growth-interaction',interaction);document.addEventListener('pet-growth-recorded',recorded);
 document.addEventListener('visibilitychange',()=>{if(document.hidden){stop();void ctx?.suspend();}else void refresh();});window.addEventListener('pagehide',stop);
 window.addEventListener('storage',e=>{if(e.key==='pet-growth-change:'+window.COMPANION_SCOPE){stop();void refresh();}});
 setInterval(()=>{if(adapter&&!document.hidden){window.PetGrowth.tick();}},200);setInterval(()=>void refresh(),45000);
})();
