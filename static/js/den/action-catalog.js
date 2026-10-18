/* Shared desktop action vocabulary. Only an authored clip enables an action. */
(function(root,factory){const api=factory();if(typeof module==='object')module.exports=api;else {root.PetActionCatalog=api;root.DesktopActions=api;}})(globalThis,()=>{
 'use strict';
 const catalog=[
  {id:'idle',label:'安静陪伴',clips:['idle_breathe','Idle','idle'],loop:true},
  {id:'walk',label:'散步',clips:['motion_walk','Walk','walk'],loop:true,wire:'walk'},
  {id:'turnLeft',label:'向左探身',clips:['turn_left']},
  {id:'turnRight',label:'向右探身',clips:['turn_right']},
  {id:'sniff',label:'嗅一嗅',clips:['sniff'],auto:true,wire:'sniff'},
  {id:'sit',label:'坐下陪你',clips:['sit_idle'],enter:'sit_down',exit:'stand_up',loop:true,hold:7,auto:true},
  {id:'sleep',label:'趴下打盹',clips:['sleep_loop'],enter:'lie_down',exit:'stand_up',loop:true,hold:9,auto:true,wire:'sleep'},
  {id:'petting',label:'享受摸头',clips:['touch_head'],wire:'petting'},
  {id:'happy',label:'开心一下',clips:['happy'],auto:true,wire:'happy'},
  {id:'stretch',label:'伸懒腰',clips:['stretch'],auto:true},
  {id:'shake',label:'抖抖毛',clips:['shake_off'],auto:true},
  {id:'lick',label:'舔舔鼻子',clips:['nose_lick'],auto:true},
  {id:'tail',label:'摇尾迎接',clips:['tail_greeting'],auto:true,wire:'happy'},
  {id:'paw',label:'抬爪问好',clips:['paw_greeting'],auto:true,wire:'happy'},
  {id:'bow',label:'邀请玩耍',clips:['play_bow'],auto:true,wire:'happy'},
  {id:'surprise',label:'吃惊张望',clips:['surprised']},
  {id:'affection',label:'撒个娇',clips:['affection'],auto:true,wire:'happy'},
  {id:'yawn',label:'打哈欠',clips:['sleepy_yawn'],auto:true},
  {id:'alert',label:'警觉巡视',clips:['alert_scan'],auto:true},
  {id:'shy',label:'害羞回望',clips:['shy_look'],auto:true},
  {id:'ears',label:'竖起耳朵',clips:['ear_perk'],auto:true},
  {id:'listen',label:'歪头倾听',clips:['curious_listen'],auto:true},
  {id:'wave',label:'挥爪招呼',clips:['wave_paw'],wire:'happy'},
  {id:'speak',label:'张嘴回应',clips:['speak']},
  {id:'chew',label:'嚼嚼嘴',clips:['eat']}
 ].map(Object.freeze);
 const byId=new Map(catalog.map(a=>[a.id,a]));
 function find(clips,names){return names.map(n=>clips.find(c=>c.name.split('|').pop()===n)).find(Boolean);}
 function supported(clips){return catalog.flatMap(a=>{
  const clip=find(clips,a.clips),enter=a.enter&&find(clips,[a.enter]),exit=a.exit&&find(clips,[a.exit]);
  if(!clip||a.enter&&(!enter||!exit))return [];
  return [{id:a.id,label:a.label,duration:Math.min(30,(enter?.duration||0)+(a.hold||clip.duration)+.4)}];
 });}
 function wire(id){return byId.get(id)?.wire||'idle';}
 function choose(supportedIds,recent,random=Math.random){
  const pool=catalog.filter(a=>a.auto&&supportedIds.includes(a.id)&&!recent.includes(a.id));
  return pool.length?pool[Math.min(pool.length-1,Math.floor(Math.max(0,random())*pool.length))].id:'idle';
 }
 const denKeys={tail:'greet',paw:'pawGreeting',bow:'playBow',lick:'noseLick',listen:'curious',speak:'talk',chew:'eat',wave:'wavePaw'};
 const denKey=id=>denKeys[id]||id;
 return {catalog,byId,find,supported,wire,choose,denKey};
});
