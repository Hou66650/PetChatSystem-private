const api=window.paitDesktop,$=id=>document.getElementById(id);
function render(s){$('status').textContent=s.status;$('pair').hidden=s.connected;$('connected').hidden=!s.connected;$('sense').checked=s.sensing;}
api.subscribe(render);api.command('state').then(render);
$('pair').onsubmit=async e=>{e.preventDefault();$('status').textContent='正在配对…';await api.command('pair',{origin:$('origin').value,code:$('code').value});$('code').value='';};
$('return').onclick=()=>api.command('return');$('sense').onchange=()=>api.command('sense',$('sense').checked);
