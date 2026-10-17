/* Semantic park actions use authored clips; one-shots settle into stable poses. */
(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.ParkMotion=api;})(globalThis,function(){
 const clips={idle:['idle_breathe','Idle'],walk:['motion_walk','walk','Walk'],run:['motion_trot','trot','run'],sniff:['sniff'],happy:['happy','tail_greeting'],bow:['play_bow','happy'],greet:['tail_greeting','paw_greeting','wave_paw'],look:['curious_listen','alert_scan','idle_breathe'],sit:['sit_idle','idle_breathe'],sleep:['sleep_loop','sit_idle','idle_breathe'],stretch:['stretch','shake_off','idle_breathe']};
 class Motion{
  constructor(pet){this.pet=pet;this.key=null;this.current=null;this.elapsed=0;this.next=null;this.lock=0;}
  find(names){return names.map(n=>this.pet.clips.find(c=>c.name.split('|').pop()===n)).find(Boolean)||null;}
  start(clip,once=false,speed=1){if(!clip)return;const p=this.pet,next=p.mixer.clipAction(clip);if(this.current===next&&!once){next.setEffectiveTimeScale(speed);return;}const old=this.current||p.active;next.reset().setEffectiveWeight(1).setEffectiveTimeScale(speed);next.setLoop(once?p.T.LoopOnce:p.T.LoopRepeat,once?1:Infinity);next.clampWhenFinished=once;next.fadeIn(.22).play();if(old&&old!==next)old.fadeOut(.22);this.current=next;p.active=next;this.elapsed=0;this.lock=once?clip.duration/speed:0;}
  update(action,dt,speed=1){
   if(action!==this.key){const before=this.key;this.key=action;this.next=this.find(clips[action]||clips.idle);
    const transition=action==='sleep'?'lie_down':action==='sit'?'sit_down':['sleep','sit'].includes(before)?'stand_up':null;
    const clip=transition&&this.find([transition]);if(clip)this.start(clip,true);else{this.start(this.next,false,speed);this.next=null;}
   }
   this.elapsed+=dt;if(this.next&&this.elapsed>=this.lock){this.start(this.next,false,speed);this.next=null;}else if(!this.next&&this.current)this.current.setEffectiveTimeScale(speed);
   this.pet.update(dt);
  }
 }
 return {Motion,clips};
});
