const api=window.paitDesktop,$=id=>document.getElementById(id);
function render(s){window.PaitLoading?.sync('desktop-model',s.connected&&s.phase==='preparing','正在准备桌宠模型与饰品');$('status').textContent=s.status;$('pair').hidden=s.connected;$('connected').hidden=!s.connected;$('sense').checked=s.sensing;$('sense').disabled=s.phase!=='roaming';
 $('deadline').textContent=Number.isFinite(s.expiresAt)?'本次最迟返程：'+new Date(s.expiresAt*1000).toLocaleString('zh-CN')+'（本机时区）。召回、断线或关闭客户端会提前结束。':'当前服务未提供最迟返程时间。';
}
api.subscribe(render);api.command('state').then(render);
$('pair').onsubmit=async e=>{e.preventDefault();$('status').textContent='正在配对…';try{await window.PaitLoading.run('正在配对桌面传送门',async()=>{const s=await api.command('pair',{origin:$('origin').value,code:$('code').value});if(!s.ok)throw Error(s.error||'配对未完成');});}catch(e){$('status').textContent=e.message;return;}$('code').value='';};
$('return').onclick=()=>window.PaitLoading.run('正在返回悬浮岛',async()=>{const s=await api.command('return');if(s.error)throw Error(s.error);}).catch(e=>{$('status').textContent=e.message;});$('sense').onchange=()=>api.command('sense',$('sense').checked);
