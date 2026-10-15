/* Executable action vocabulary only. Models never supply JS, bone names or coordinates. */
(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.DialogueActions=api;})(typeof window!=='undefined'?window:globalThis,function(){
 'use strict';
 const MAX_ACTIONS=8;
 const expressiveKeys=Object.freeze({curious:'curious',ears:'ears',play_bow:'playBow',shy:'shy',yawn:'yawn',affection:'affection',alert:'alert',surprise:'surprise',nose_lick:'noseLick',shake:'shake',greet:'greet'});
 const baseActions=['come','sit','lie_down','stand','wave','sniff','happy','wander','stop','quiet'];
 const allowed=new Set([...baseActions,...Object.keys(expressiveKeys)]);
 class Runner{
  constructor(adapter){this.adapter=adapter;this.serial=0;this.active=false;this.log=[];}
  cancel(reason='已停止'){this.serial++;if(this.active||this.adapter.isHeld?.())this.adapter.cancel();this.active=false;this.status(reason);}
  status(message){this.message=message;this.log.push(message);this.log=this.log.slice(-20);this.adapter.status(message);}
  async run(plan){
   this.cancel('');const commands=Array.isArray(plan)?plan.filter(a=>typeof a==='string'&&(this.adapter.actions||allowed).has(a)):[];
   if(commands.length>MAX_ACTIONS){this.status('一次最多做'+MAX_ACTIONS+'个动作，请分两次告诉我');return;}
   if(!commands.length)return;
   const token=this.serial;this.active=true;this.adapter.begin();
   const current=()=>token===this.serial;
   try{for(const [index,action] of commands.entries()){if(!current())return;this.status((commands.length>1?'（'+(index+1)+'/'+commands.length+'）':'')+this.adapter.label(action));await this.adapter.execute(action,current);}
    if(current()){this.active=false;this.adapter.finish(commands[commands.length-1]);this.status('动作已完成');}
   }catch(e){if(current()){this.active=false;this.adapter.cancel();this.status(e.message||'这次没能完成动作，请再试一次');}}
  }
 }
 // Common conversational requests are parsed as whole clauses. Unknown or
 // mixed-intent sentences fall back to the model; never scan for isolated keywords.
 const patterns=[
  ['curious',/^(?:歪头听你说|歪头听听|歪歪头|歪个头|歪一下头|把头歪一歪|把头歪一下|歪头)/],
  ['ears',/^(?:竖耳听一听|把耳朵竖起来|耳朵竖起来|竖起(?:小)?耳朵|竖竖耳朵|竖耳朵|竖耳)/],
  ['shy',/^(?:做个害羞的表情|害羞一下|害羞|羞一个)/],
  ['alert',/^(?:认真望一望|警觉地看看|观察一下|观察四周|看看四周|四处看看|东张西望|望一望)/],
  ['yawn',/^(?:打个小哈欠|打一个哈欠|打个哈欠|打哈欠)/],
  ['affection',/^(?:开心蹭蹭|蹭蹭我|蹭一蹭我|蹭一蹭|蹭蹭|跟我撒个娇|向我撒娇|撒个娇|撒撒娇|撒娇|卖个萌)/],
  ['surprise',/^(?:做个惊讶的表情|惊讶一下|惊讶)/],
  ['play_bow',/^(?:邀请我玩|邀请你玩|做个邀玩动作|趴低邀玩|陪我玩(?:一会儿?|会儿?)?|跟我玩(?:一会儿?|会儿?)?)/],
  ['nose_lick',/^(?:舔舔小鼻子|舔一舔鼻子|舔舔鼻子|舔鼻子|舔鼻)/],
  ['shake',/^(?:抖抖毛|抖一下毛|抖一抖毛|抖毛|抖抖身体|抖一抖身体)/],
  ['greet',/^(?:摇尾欢迎我|摇尾欢迎你|把尾巴摇一摇|把尾巴摇起来|尾巴摇一摇|尾巴摇起来|摇一摇尾巴|摇摇(?:小)?尾巴|摇尾巴|摇尾)/],
  ['sit',/^(?:陪我坐(?:一会儿?|会儿?)|坐下来陪我|坐下来|坐下|坐一会儿?|坐会儿?|坐好)/],
  ['lie_down',/^(?:趴下(?:来)?(?:歇(?:一会儿?|会儿?)|休息(?:一会儿?|会儿?)?)|休息休息|休息|趴下来|趴下|躺下来|躺下|歇一歇|歇(?:一会儿?|会儿?)|睡觉|睡一会儿?)/],
  ['stand',/^(?:站起来|站起|起来|起立)/],
  ['come',/^(?:走到我(?:面前|身边|这里|这儿)|走过来|过来|到我(?:身边|这里|这儿)|来我(?:身边|这里|这儿)|靠近我|靠过来|来这边)/],
  ['wave',/^(?:(?:跟我|和我|向我|给我)?(?:挥爪打招呼|挥挥爪爪|挥一挥爪子|挥挥爪|挥爪爪|挥爪|挥挥手|挥手|打个招呼|打声招呼|打招呼))/],
  ['sniff',/^(?:闻一闻|闻闻|闻一下|嗅一嗅|嗅嗅)/],
  ['happy',/^(?:开心一点|开心点|开心一下|高兴一点|高兴点)/],
  ['wander',/^(?:自由活动|自由走走|自己玩|去散散步|去散步|去玩|散散步|散步|走一走|走走)/],
  ['stop',/^(?:停止动作|停下来|停下|不要动|别动)/],
  ['quiet',/^(?:安静地陪我|安静陪我|安静一点|安静点|陪我安静一会儿?)/],
 ];
 const separators=/^[,，、;；。.!！]+/;
 const connector=/^(?:然后再|接下来|接着再|之后再|最后再|然后|接着|之后|最后|再|并且|还有|以及|和)/;
 const requestPrefix=/^(?:(?:你)?(?:能不能|可不可以|可以|能)|(?:请|麻烦|拜托)(?:你)?|(?:我想看你|我想让你|我希望你|让我看看(?:你)?)|帮我|给我|你)/;
 function parseCommands(message,names=[],supportedActions=baseActions){
  if(typeof message!=='string'||message.length>400)return [];
  let text=message.normalize('NFKC').replace(/\s+/g,'');
  if(!text||/[“”"'「」『』]/.test(text))return [];
  const petNames=[...names].filter(Boolean).map(n=>String(n).normalize('NFKC').replace(/\s+/g,'')).sort((a,b)=>b.length-a.length);
  function stripName(value){for(const name of petNames)if(value.startsWith(name))return value.slice(name.length).replace(separators,'');return value;}
  text=stripName(text);
  // "能不能…" and "…好不好" are requests; "你会…吗" stays a capability question.
  const politeQuestion=/^(?:你)?(?:能不能|可不可以|可以|能)/.test(text)||/(?:好不好|好不|好吗|行不行|行吗|可以吗)[?？。.!！]*$/.test(text);
  text=text.replace(/[?？。.!！,，~～]+$/g,'');
  if(!politeQuestion&&/[?？]/.test(message))return [];
  if(politeQuestion)text=text.replace(/[?？]/g,'。'); // ASR can punctuate a polite request mid-chain.
  text=text.replace(/(?:好不好|好不|好吗|行不行|行吗|可以吗)$/,'');
  if(politeQuestion)text=text.replace(/吗$/,'');
  text=text.replace(/[,，。]+$/,'');
  const supported=new Set(supportedActions),commands=[];
  while(text&&commands.length<MAX_ACTIONS){
   // Allow natural combinations such as "麻烦你先帮我…" without deleting free text.
   for(let i=0;i<5;i++){
    const before=text;text=stripName(text).replace(requestPrefix,'').replace(separators,'').replace(/^(?:首先|先)/,'');
    if(text===before)break;
   }
   const found=patterns.find(([,pattern])=>pattern.test(text));
   if(!found)return [];
   const [action,pattern]=found;
   if(!supported.has(action))return [];
   text=text.replace(pattern,'').replace(/^(?:一下下|一下|一会儿?|一小会儿?|会儿)/,'');
   let repeat=1;
   const times=text.match(/^(?:重复)?([一二两三四五六七八1-8])(?:次|遍|下)/);
   if(times){repeat=({'一':1,'二':2,'两':2,'三':3,'四':4,'五':5,'六':6,'七':7,'八':8})[times[1]]||Number(times[1]);text=text.slice(times[0].length);}
   if(commands.length+repeat>MAX_ACTIONS)return [];
   commands.push(...Array(repeat).fill(action));
   text=text.replace(/^(?:给我看看|给我看|让我看看|陪陪我|陪我)?/,'').replace(/^[吧呀啊哦啦嘛呗]+/,'').replace(separators,'');
   const join=text.match(connector);
   if(join){text=text.slice(join[0].length).replace(separators,'');if(!text)return [];}
  }
  return text?[]:commands;
 }
 return {Runner,allowed,baseActions,expressiveKeys,parseCommands,MAX_ACTIONS};
});
