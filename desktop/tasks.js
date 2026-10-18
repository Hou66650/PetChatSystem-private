'use strict';
window.DesktopTasks=(()=>{
 const $=id=>document.getElementById(id),api=window.paitDesktop;
 let state={},fingerprint='',pending=false;
 const taskNames={awaiting_approval:'等待你的批准',succeeded:'设置成功',cancelled:'审批已取消',expired:'审批已过期'};
 const effectNames={scheduled:'等待提醒到点',running:'专注计时中',due:'提醒已到点',completed:'专注已结束',cancelled:'效果已取消'};
 const deliveryNames={pending:'等待通知',attempting:'正在投递',delivered:'系统报告已显示（不代表已读）',failed:'系统不支持通知',unknown:'通知结果未知，可能已经显示',missed:'已错过通知时限',suppressed:'已确认未调用通知'};
 const date=value=>new Date(value*1000).toLocaleString('zh-CN');
 function el(tag,text){const node=document.createElement(tag);if(text!==undefined)node.textContent=text;return node;}
 function notice(text){$('task-error').textContent=text;}
 function countdowns(){
  const clock=state.taskClock,now=clock?clock.serverTime+(Date.now()-clock.observedAt)/1000:Date.now()/1000;
  for(const node of $('task-list').querySelectorAll('[data-due]')){
   const seconds=Math.max(0,Math.ceil(Number(node.dataset.due)-now));
   node.textContent=seconds?'剩余 '+String(Math.floor(seconds/60)).padStart(2,'0')+':'+String(seconds%60).padStart(2,'0'):'已到时间，等待服务器确认';
  }
 }
 setInterval(countdowns,1000);
 async function send(op,data){
  const trip=state.trip;const response=await api.command('task-'+op,{requestId:crypto.randomUUID(),...data});
  if(state.trip!==trip)return null;if(response.error)throw Error(response.error);return response;
 }
 function button(parent,text,run){const b=el('button',text);b.type='button';b.onclick=async()=>{b.disabled=true;notice('');try{await run();}catch(e){notice(e.message);}finally{b.disabled=false;}};parent.append(b);return b;}
 function render(s){
  state=s;$('tools-panel').hidden=!s.connected;
  const enabled=s.phase==='roaming'&&s.toolsEnabled;
  for(const control of $('tool-form').elements)control.disabled=!enabled||pending;
  $('tools-hint').textContent=enabled?'仅本次桌面行程有效。召回或断线会取消未完成的计时与待审批任务。':'当前工具未开放，聊天和原有传送功能不受影响。';
  const key=JSON.stringify([s.trip,s.toolsEnabled,s.tasks||[]]);if(key===fingerprint)return;fingerprint=key;
  const list=$('task-list');list.replaceChildren();
  for(const task of s.tasks||[]){
   const card=el('article');card.className='task-card';card.dataset.taskId=task.id;
   card.append(el('strong',(task.capability==='focus_timer.start'?'专注 · ':'提醒 · ')+task.params.title));
   card.append(el('p','任务：'+(taskNames[task.status]||task.status)));
   if(task.status==='awaiting_approval'){
    card.append(el('p',task.capability==='focus_timer.start'?'批准后专注 '+task.params.seconds+' 秒':'提醒时间：'+date(task.params.dueAt)));
    card.append(el('small','审批截止：'+date(task.approval_expires)+'；行程最迟结束：'+date(task.trip_expires)+'（本机时区）'));
    button(card,'批准并执行',()=>send('approve',{taskId:task.id,taskVersion:task.version,paramsHash:task.params_hash})).disabled=!enabled;
    button(card,'拒绝',()=>send('cancel',{taskId:task.id}));
   }
   if(task.effect){
    const effect=task.effect;card.append(el('p','效果：'+(effectNames[effect.state]||effect.state)));
    card.append(el('small','到点时间：'+date(effect.due_at)));
    if(['scheduled','running'].includes(effect.state)){
     const remaining=el('p');remaining.dataset.due=effect.due_at;card.append(remaining);
     button(card,'取消计时',()=>send('cancel',{taskId:task.id}));
    }
    for(const delivery of effect.deliveries){
     card.append(el('small','通知尝试 '+delivery.attempt+'：'+(deliveryNames[delivery.state]||delivery.state)));
     if(['unknown','failed','missed'].includes(delivery.state)&&!delivery.cancel_requested&&delivery===effect.deliveries.at(-1)&&enabled){
      button(card,'再次投递…',async()=>{
       // Explicit inline confirmation; no automatic retry on unknown outcomes.
       const confirmation=el('div');confirmation.className='retry-confirm';confirmation.append(el('p','通知可能已经送达，再次投递可能重复。是否仍要再次投递？'));
       button(confirmation,'我已了解，仍要投递',async()=>{await send('retry',{taskId:task.id,deliveryId:delivery.id,confirmDuplicate:true});confirmation.remove();});
       button(confirmation,'不再投递',()=>confirmation.remove());card.querySelector('.retry-confirm')?.remove();card.append(confirmation);
      });
     }
    }
   }
   list.append(card);
  }
  countdowns();
 }
 async function propose(capability,title,seconds){
  if(pending||!state.toolsEnabled||state.phase!=='roaming')throw Error('请等待到达桌面并开启工具');
  pending=true;render(state);notice('');
  try{return await send('propose',{capability,title,seconds,contextVersion:state.version});}
  finally{pending=false;render(state);}
 }
 $('tool-form').onsubmit=async e=>{e.preventDefault();try{await propose($('tool-kind').value,$('tool-title').value,Number($('tool-duration').value)*Number($('tool-unit').value));}catch(error){notice(error.message);}};
 function parse(message){
  let m=message.match(/^(?:请)?(?:帮我)?\s*(\d+)\s*(秒|分钟|小时)后提醒我\s*(.+)$/);
  if(m)return {capability:'reminder.create',seconds:Number(m[1])*({'秒':1,'分钟':60,'小时':3600}[m[2]]),title:m[3]};
  m=message.match(/^(?:开始)?专注(?:计时)?\s*(\d+)\s*(秒|分钟)$/);
  if(m)return {capability:'focus_timer.start',seconds:Number(m[1])*(m[2]==='分钟'?60:1),title:'专注时间'};
  return null;
 }
 return {render,propose,parse};
})();
