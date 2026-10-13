(function(){
 'use strict';
 const $=id=>document.getElementById(id);let archive=null,epoch=0;
 const initial=Number(new URLSearchParams(location.search).get('petId'));
 if(window.COMPANION_PETS.some(p=>p.id===initial)) $('pet-select').value=initial;
 const endpoint=path=>path+'?petId='+encodeURIComponent($('pet-select').value);
 function notice(text,error=false){$('notice').textContent=text;$('notice').className=error?'error':'';}
 async function api(path,method='GET',data){const r=await fetch(endpoint(path),{method,headers:{'Content-Type':'application/json'},...(method==='GET'?{}:{body:JSON.stringify(data||{})})});const d=await r.json();if(!r.ok)throw Error(d.error||'暂时无法保存');return d;}
 function factNode(m){
  const d=document.createElement('div');d.className='fact';
  const label=document.createElement('label');label.textContent=archive.categories[m.category];label.htmlFor='memory-'+m.id;
  const input=document.createElement('input');input.id=label.htmlFor;input.value=m.value;input.maxLength=80;
  const source=document.createElement('p');source.className='source';source.textContent=(m.confirmed?'你已确认':'来自对话，可修改')+' · '+m.source_quote;
  const buttons=document.createElement('div');buttons.className='toolbar';
  const save=document.createElement('button');save.textContent='保存修改';
  const forget=document.createElement('button');forget.textContent='忘记这条';
  save.onclick=()=>mutate('/api/companion/memories/'+m.id,'PATCH',{value:input.value},'已经按你的修改记好了');
  forget.onclick=()=>mutate('/api/companion/memories/'+m.id,'DELETE',{},'已经忘记这条，旧聊天也不会再用于回答');
  buttons.append(save,forget);d.append(label,input,source,buttons);return d;
 }
 function render(d){archive=d;$('toggle-memory').textContent=d.enabled?'记忆已开启 · 点击暂停':'记忆已暂停 · 点击恢复';$('toggle-memory').setAttribute('aria-pressed',String(d.enabled));
  $('identity').textContent=d.guest?'当前是此浏览器的访客档案。登录后使用独立的账号档案，可跨设备继续；访客档案不会自动合并。':'这是你的账号专属档案，可在登录后跨设备继续。';
  const p=d.pet;$('pet-name').textContent=p.name;$('pet-species').textContent=p.species;
  $('pet-avatar').src='/images/'+window.COMPANION_PETS.find(x=>x.id===p.id).avatar;
  const behavior=p.behavior;$('behavior-label').textContent='现在的陪伴方式 · '+behavior.label;
  $('behavior-summary').textContent=behavior.summary;
  $('behavior-source').textContent=behavior.sourceText?'根据你说的：“'+behavior.sourceText+'”自动调整':'继续聊天，它会从你明确分享的陪伴偏好中慢慢了解你。';
  $('pet-style').textContent='它会怎样陪你：'+p.companionStyle;
  $('pet-rules').replaceChildren();for(const rule of p.personalizedRules||[]){const li=document.createElement('li');li.textContent=rule;$('pet-rules').append(li);}
  $('pet-basis').textContent=d.enabled?(p.basis.length?'依据你的 '+p.basis.length+' 条偏好与称呼调整回应，保留它原本的性格。':'多聊几次，或主动添加一条偏好，让它慢慢熟悉你。'):'记忆已暂停，这些偏好暂不用于对话。';
  $('pet-personality').textContent=p.basePersonality;$('pet-count').textContent='已保存 '+p.interactionCount+' 次对话';
  for(const [id,personal] of [['user-facts',false],['pet-facts',true]]){const root=$(id);root.replaceChildren();const rows=d.memories.filter(m=>(m.pet_id!==0)===personal);rows.forEach(m=>root.append(factNode(m)));if(!rows.length){const empty=document.createElement('p');empty.className='empty';empty.textContent=personal?'属于你们的昵称和回忆会出现在这里。':'还没有记忆。从一句“以后叫我……”开始吧。';root.append(empty);}}
  const selectedCategory=$('category').value||'name';$('category').replaceChildren();Object.entries(d.categories).forEach(([v,t])=>{const o=document.createElement('option');o.value=v;o.textContent=t;$('category').append(o);});$('category').value=selectedCategory;
 }
 async function load(){const token=++epoch;try{const d=await api('/api/companion');if(token===epoch){render(d);if($('history-panel').open)loadHistory();}}catch(e){notice(e.message,true);}}
 async function mutate(path,method,data,message){const token=epoch;document.querySelectorAll('button').forEach(b=>b.disabled=true);try{const d=await api(path,method,data);if(token===epoch){render(d);notice(message);if(window.BroadcastChannel){const ch=new BroadcastChannel('companion-memory:'+d.scope);ch.postMessage('changed');ch.close();}}}catch(e){notice(e.message,true);}finally{document.querySelectorAll('button').forEach(b=>b.disabled=false);}}
 async function loadHistory(){const token=epoch;try{const d=await api('/api/companion/history');if(token!==epoch)return;$('history').replaceChildren();for(const r of d.messages){const div=document.createElement('div');div.className='history-row';const meta=document.createElement('small');meta.textContent=(r.role==='user'?'我':archive.pet.name)+' · '+new Date(r.created_at).toLocaleString();const text=document.createElement('span');text.textContent=r.content;div.append(meta,text);$('history').append(div);}if(!d.messages.length)$('history').textContent='这里还没有聊天记录。';}catch(e){notice(e.message,true);}}
 $('pet-select').onchange=()=>{notice('');load();};
 $('toggle-memory').onclick=()=>archive&&mutate('/api/companion','PATCH',{enabled:!archive.enabled},archive.enabled?'已暂停记录和读取记忆':'已恢复记忆');
 $('add-form').onsubmit=async e=>{e.preventDefault();await mutate('/api/companion/memories','POST',{category:$('category').value,value:$('fact-value').value},'已经加入你的档案');$('fact-value').value='';};
 $('history-panel').ontoggle=()=>{if($('history-panel').open)loadHistory();};
 $('clear-history').onclick=async()=>{if(!confirm('清除与这只宠物的聊天记录？已提取的记忆保留，可单独忘记。'))return;try{await api('/api/companion/history','DELETE');await load();await loadHistory();notice('聊天记录已清除');}catch(e){notice(e.message,true);}};
 $('clear-all').onclick=async()=>{if(!confirm('清除你的全部宠物记忆和聊天记录？此操作无法撤销。'))return;await mutate('/api/companion','DELETE',{},'全部记忆和聊天已清除');await loadHistory();};
 load();
})();
