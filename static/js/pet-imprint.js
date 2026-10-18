(()=>{'use strict';
 const $=id=>document.getElementById(id);let state=null,epoch=0,busy=false,referenceUrl=null;
 const initial=Number(new URLSearchParams(location.search).get('petId'));if([1,2,3,4].includes(initial))$('pet').value=String(initial);
 const pet=()=>Number($('pet').value),url=()=>'/api/pet-imprint/'+pet();
 function message(text,error=false){$('status').textContent=text;$('status').className=error?'error':'';}
 function lock(value){busy=value;document.querySelectorAll('main button,main input,main select,main textarea').forEach(e=>e.disabled=value);}
 async function request(path,options={}){const r=await fetch(path,{cache:'no-store',...options,headers:{'Content-Type':'application/json','X-Profile-Scope':window.COMPANION_SCOPE,...options.headers}}),d=await r.json();if(!r.ok)throw Error(d.error||'读取失败');if(d.scope!==window.COMPANION_SCOPE)throw Error('账号已变化，请刷新');return d;}
 function options(){const kind=$('kind').value,selected=$('value').value;$('value').replaceChildren();let pairs=Object.entries(state.options[kind]||{});
  if(kind.startsWith('call_'))pairs=state.originalCalls.clips.filter(c=>c.kind===kind.slice(5)).map(c=>[c.id,c.name+'（'+c.duration.toFixed(1)+' 秒）']);
  for(const [v,label] of pairs){const o=document.createElement('option');o.value=v;o.textContent=label;$('value').append(o);}if(pairs.some(p=>p[0]===selected))$('value').value=selected;
 }
 function changed(){if(window.BroadcastChannel){const ch=new BroadcastChannel('companion-memory:'+window.COMPANION_SCOPE);ch.postMessage('changed');ch.close();}}
 function button(text,fn){const b=document.createElement('button');b.type='button';b.textContent=text;b.onclick=fn;return b;}
 function render(d){state=d;const selected=$('kind').value;$('kind').replaceChildren();for(const [value,label] of Object.entries(d.labels)){const o=document.createElement('option');o.value=value;o.textContent=label;$('kind').append(o);}if(selected)$('kind').value=selected;options();
  $('back').href=$('demo').href='/den?pet='+pet();$('archive').href='/companion?petId='+pet();
  $('policy').textContent=(d.enabled?'记忆已开启':'记忆已暂停，回忆暂不驱动表现')+'；'+d.cards.filter(c=>c.confirmed).length+' 条已确认。原声'+(d.originalCalls.enabled?'已开启':'尚未开启')+'。小岛中可打开“熟悉的样子”体验。';
  $('cards').replaceChildren();for(const card of d.cards){const node=document.createElement('article');node.className='card';const h=document.createElement('h3');h.textContent=d.labels[card.kind]+' · '+(card.confirmed?'已确认':'待确认');const expression=document.createElement('p');expression.textContent='岛上表达：'+(d.options[card.kind][card.value]||d.originalCalls.clips.find(c=>c.id===card.value)?.name||'原声已删除，请重新选择');const quote=document.createElement('p');quote.textContent='依据：'+card.evidence.quote;const source=document.createElement('p');source.className='note';source.textContent=card.evidence.type==='owner'?'来源：主人回忆':'来源：'+card.evidence.name+' · '+card.evidence.start+'–'+card.evidence.end+' 秒';
   const row=document.createElement('div');row.className='toolbar';if(!card.confirmed){const label=document.createElement('label'),check=document.createElement('input');label.className='confirm-label';check.type='checkbox';label.append(check,document.createTextNode('确认依据真实，并采用此表达方式'));node.append(label);row.append(button('确认并启用',()=>{if(!check.checked)return message('请先核对依据并勾选确认',true);void mutate('/'+card.id+'/confirm','POST',{confirmed:true});}));}else row.append(button('暂停这条',()=>mutate('/'+card.id+'/withdraw','POST',{})));
   row.append(button('修改',()=>{$('edit-id').value=card.id;$('kind').value=card.kind;options();$('value').value=card.value;$('quote').value=card.evidence.quote;$('source').value=card.evidence.type;sourceFields();$('media-name').value=card.evidence.name||'';$('start').value=card.evidence.start||0;$('end').value=card.evidence.end||1;$('form').scrollIntoView({behavior:'smooth'});}),button('删除',()=>{if(confirm('删除这条回忆？不会删除原片或原声库。'))void mutate('/'+card.id,'DELETE',{});}));node.prepend(h,expression,quote,source);node.append(row);$('cards').append(node);}
  if(!d.cards.length)$('cards').textContent='还没有记录。先留下一条你最熟悉的习惯。';
 }
 async function load(){const token=++epoch;try{const d=await request(url());if(token===epoch)render(d);}catch(e){if(token===epoch)message(e.message,true);}}
 async function mutate(path,method,data){if(busy||!state)return;const token=epoch;lock(true);try{const d=await request(url()+path,{method,body:JSON.stringify({...data,revision:state.revision})});if(token!==epoch)return;render(d);changed();message('已保存。只有确认后的回忆才参与表现。');$('edit-id').value='';$('quote').value='';}catch(e){message(e.message,true);await load();}finally{lock(false);}}
 function sourceFields(){$('media-fields').hidden=$('source').value!=='media';}
 $('kind').onchange=options;$('source').onchange=sourceFields;$('pet').onchange=()=>{$('form').reset();$('edit-id').value='';sourceFields();message('');void load();};
 $('form').onsubmit=e=>{e.preventDefault();const evidence={type:$('source').value,quote:$('quote').value};if(evidence.type==='media')Object.assign(evidence,{name:$('media-name').value,start:Number($('start').value),end:Number($('end').value)});const id=$('edit-id').value;void mutate(id?'/'+id:'',id?'PATCH':'POST',{kind:$('kind').value,value:$('value').value,evidence});};
 $('cancel-edit').onclick=()=>{$('form').reset();$('edit-id').value='';sourceFields();options();};
 $('calls').onclick=()=>window.PetCareUI.open(pet(),$('pet').selectedOptions[0].textContent);
 document.addEventListener('pet-care-changed',()=>void load());
 $('reference').onchange=()=>{const file=$('reference').files[0];if(referenceUrl)URL.revokeObjectURL(referenceUrl);referenceUrl=null;const player=$('reference-player');player.pause();player.removeAttribute('src');player.hidden=!file;if(file){referenceUrl=URL.createObjectURL(file);player.src=referenceUrl;$('media-name').value=file.name;}};
 addEventListener('pagehide',()=>{if(referenceUrl)URL.revokeObjectURL(referenceUrl);});load();
})();
