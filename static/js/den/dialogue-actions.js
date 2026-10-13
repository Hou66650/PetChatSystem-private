/* Executable action vocabulary only. Models never supply JS, bone names or coordinates. */
(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.DialogueActions=api;})(typeof window!=='undefined'?window:globalThis,function(){
 'use strict';
 const allowed=new Set(['come','sit','lie_down','stand','wave','sniff','happy','wander','stop','quiet']);
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
 return {Runner,allowed};
});
