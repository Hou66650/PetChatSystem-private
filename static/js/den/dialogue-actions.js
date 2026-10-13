/* Executable action vocabulary only. Models never supply JS, bone names or coordinates. */
(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.DialogueActions=api;})(typeof window!=='undefined'?window:globalThis,function(){
 'use strict';
 const allowed=new Set(['come','sit','lie_down','stand','wave','sniff','happy','wander','stop','quiet','curious','play_bow','shy','yawn','affection','alert','surprise','nose_lick','shake','greet']);
 class Runner{
  constructor(adapter){this.adapter=adapter;this.serial=0;this.active=false;this.log=[];}
  cancel(reason='已停止'){this.serial++;if(this.active||this.adapter.isHeld?.())this.adapter.cancel();this.active=false;this.status(reason);}
  status(message){this.message=message;this.log.push(message);this.log=this.log.slice(-20);this.adapter.status(message);}
  async run(plan){
   this.cancel('');const commands=Array.isArray(plan)?plan.filter(a=>typeof a==='string'&&allowed.has(a)).slice(0,3):[];
   if(!commands.length)return;
   const token=this.serial;this.active=true;this.adapter.begin();
   const current=()=>token===this.serial;
   try{for(const action of commands){if(!current())return;this.status(this.adapter.label(action));await this.adapter.execute(action,current);}
    if(current()){this.active=false;this.adapter.finish(commands[commands.length-1]);this.status('动作已完成');}
   }catch(e){if(current()){this.active=false;this.adapter.cancel();this.status(e.message||'这次没能完成动作，请再试一次');}}
  }
 }
 // Fast path for complete, explicit commands only. Never match words inside
 // a question, quotation, negation or a sentence about the user's own activity.
 function parseCommands(message, names=[]){
  if(typeof message!=='string'||message.length>120)return [];
  let text=message.normalize('NFKC').replace(/\s+/g,'').replace(/[。.!！,，~～]+$/g,'');
  if(!text||/[?？“”"'「」『』]/.test(text))return [];
  for(const name of [...names].filter(Boolean).sort((a,b)=>b.length-a.length)){
   const prefix=String(name).normalize('NFKC').replace(/\s+/g,'');
   if(prefix&&text.startsWith(prefix)){text=text.slice(prefix.length).replace(/^[,，、]+/,'');break;}
  }
  const patterns=[
   ['sit',/^(?:坐下来|坐下|坐好)/],
   ['lie_down',/^(?:休息休息|休息|趴下来|趴下|躺下来|躺下|睡觉|睡一会儿?)/],
   ['stand',/^(?:站起来|站起|起来|起立)/],
   ['come',/^(?:过来|到我(?:身边|这里|这儿)|来我(?:身边|这里|这儿)|靠近我)/],
   ['wave',/^(?:挥挥爪爪|挥挥爪|挥爪爪|挥爪|挥挥手|挥手|打个招呼)/],
   ['sniff',/^(?:闻闻|闻一下|嗅嗅)/],
   ['happy',/^(?:开心一点|开心点|开心一下)/],
   ['wander',/^(?:自由活动|自己玩|去散步|去玩|散步|走走)/],
   ['stop',/^(?:停止动作|停下来|停下|不要动|别动)/],
   ['quiet',/^(?:安静地陪我|安静陪我|安静一点|安静点)/],
  ];
  const commands=[];
  while(text&&commands.length<3){
   text=text.replace(/^(?:(?:请|麻烦|拜托)[,，。]*(?:你)?|你)[,，。]*/,'');
   text=text.replace(/^先/,'');
   const found=patterns.find(([,pattern])=>pattern.test(text));
   if(!found)return [];
   const [action,pattern]=found;
   text=text.replace(pattern,'').replace(/^(?:一下|一会儿?|一小会儿?)?/,'').replace(/^[吧呀啊哦啦]/,'');
   commands.push(action);
   text=text.replace(/^[,，、;；。]+/,'');
   if(/^(?:然后|接着|再)$/.test(text))return [];
   text=text.replace(/^(?:然后|接着|再)/,'');
  }
  return text?[]:commands;
 }
 return {Runner,allowed,parseCommands};
});
