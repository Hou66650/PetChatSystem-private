'use strict';
const api=window.paitDesktop,$=id=>document.getElementById(id);
let current={},busy=false,audio=null,audioUrl=null,speechEpoch=0;
function stopAudio(){speechEpoch++;audio?.pause();audio=null;if(audioUrl)URL.revokeObjectURL(audioUrl);audioUrl=null;}
function controls(){const enabled=current.connected&&current.phase==='roaming'&&current.chatEnabled;$('message').disabled=!enabled;$('send').disabled=!enabled||busy;}
function render(s){
 if(s.trip!==current.trip||s.version!==current.version||(!s.chatEnabled&&current.chatEnabled)||(!s.voiceEnabled&&current.voiceEnabled)){
  stopAudio();$('messages').replaceChildren();$('chat-error').textContent='';busy=false;
 }
 current=s;window.PaitLoading?.sync('desktop-model',s.connected&&s.phase==='preparing','正在准备桌宠模型与饰品');
 $('status').textContent=s.status;$('pair').hidden=s.connected;$('connected').hidden=!s.connected;$('sense').checked=s.sensing;$('sense').disabled=s.phase!=='roaming';
 $('deadline').textContent=Number.isFinite(s.expiresAt)?'本次最迟返程：'+new Date(s.expiresAt*1000).toLocaleString('zh-CN')+'（本机时区）。召回或断线会提前结束。':'当前服务未提供最迟返程时间。';controls();
 const selected=$('action-select').value,items=s.actions||[],signature=items.map(a=>a.id).join(',');
 if($('action-select').dataset.signature!==signature){$('action-select').replaceChildren(...items.map(a=>new Option(a.label,a.id)));$('action-select').dataset.signature=signature;if(items.some(a=>a.id===selected))$('action-select').value=selected;}
 $('action-play').disabled=s.phase!=='roaming'||!items.length;$('action-select').disabled=$('action-play').disabled;
 $('autonomous').checked=s.autonomous!==false;$('autonomous').disabled=s.phase!=='roaming';
 $('action-status').textContent=items.length?items.length+' 个已适配动作 · 当前：'+(items.find(a=>a.id===s.action)?.label||'安静陪伴'):'正在读取这只宠物支持的动作';
 window.DesktopTasks?.render(s);
}
function matches(trip,version){return current.connected&&current.chatEnabled&&current.trip===trip&&current.version===version;}
function line(label,text){const p=document.createElement('p');p.textContent=label+'：'+text;$('messages').append(p);while($('messages').children.length>40)$('messages').firstChild.remove();p.scrollIntoView({block:'nearest'});return p;}
api.subscribe(render);api.command('state').then(render);
$('pair').onsubmit=async e=>{e.preventDefault();$('status').textContent='正在配对…';try{const s=await api.command('pair',{origin:$('origin').value,code:$('code').value});if(!s.ok)throw Error(s.error||'配对未完成');$('code').value='';}catch(e){$('status').textContent=e.message;}};
$('return').onclick=()=>api.command('return');$('sense').onchange=()=>api.command('sense',$('sense').checked);$('stop-audio').onclick=stopAudio;
$('chat-form').onsubmit=async e=>{
 e.preventDefault();if(busy||!current.chatEnabled||current.phase!=='roaming')return;
 const message=$('message').value.trim();if(!message)return;
 const {trip,version}=current,requestId=crypto.randomUUID();busy=true;controls();$('chat-error').textContent='';line('我',message);$('message').value='';
 try{
  const tool=window.DesktopTasks?.parse(message);
  if(tool){await window.DesktopTasks.propose(tool.capability,tool.title,tool.seconds);if(matches(trip,version))line('宠物','审批卡已准备好，请核对参数后批准。尚未开始执行。');return;}
  const r=await api.command('chat',{requestId,version,message});if(!matches(trip,version))return;if(r.error)throw Error(r.error);
  const p=line(current.pet?.name||'宠物',r.reply);
  if(current.voiceEnabled){
   const button=document.createElement('button');button.type='button';button.textContent=r.reply.length>1000?'用它的声音朗读前 1000 字':'用它的声音朗读';p.append(document.createElement('br'),button);
   let request=crypto.randomUUID(),localAudio=null;
   button.onclick=async()=>{
    stopAudio();const turn=speechEpoch;button.disabled=true;
    try{
     if(!localAudio){const voice=await api.command('speech',{requestId:request,replyRequestId:requestId,version});if(!matches(trip,version)||turn!==speechEpoch)return;if(voice.error)throw Error(voice.error);localAudio=voice.bytes;}
     if(!matches(trip,version)||turn!==speechEpoch)return;
     audioUrl=URL.createObjectURL(new Blob([localAudio],{type:'audio/wav'}));audio=new Audio(audioUrl);const playing=audio;audio.onended=()=>{if(audio===playing)stopAudio();};await audio.play();
    }catch(error){if(matches(trip,version))$('chat-error').textContent=error.message;}
    finally{button.disabled=false;}
   };
  }
 }catch(error){if(matches(trip,version))$('chat-error').textContent=error.message+'；结果不确定时不会自动重发。';}
 finally{if(matches(trip,version)){busy=false;controls();}}
};
window.addEventListener('beforeunload',stopAudio);

$('action-form').onsubmit=async e=>{e.preventDefault();const r=await api.command('action',{trip:current.trip,id:$('action-select').value});if(r.error)$('action-status').textContent=r.error;};
$('autonomous').onchange=()=>api.command('autonomous',$('autonomous').checked);
