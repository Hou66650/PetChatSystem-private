(()=>{'use strict';
 const $=id=>document.getElementById(id),scope=window.PET_SHOP_SCOPE,slots={head:'头饰',neck:'颈饰',coat:'猫咪毛色'};
 const requested=Number(new URLSearchParams(location.search).get('pet'));
 let petId=[1,2,3,4].includes(requested)?requested:location.pathname==='/cat-market'?3:1;
 let data,selected='moss-bow',view='all',filter='all',busy=false,ready=false,previewing=true,pending=null;
 let pet,renderer,scene,camera,controls,loader,modelKey='',previewEpoch=0,readEpoch=0;
 $('shop-pet').value=String(petId);
 const note=text=>$('shop-note').textContent=text;
 async function api(operation,body){
  const r=await fetch('/api/wardrobe'+(operation?'/'+operation:'?petId='+petId),operation?{method:'POST',headers:{'Content-Type':'application/json','X-Profile-Scope':scope},body:JSON.stringify({petId,...body})}:{cache:'no-store'});
  const d=await r.json();if(!r.ok)throw Error(d.error||'商店暂不可用');if(d.scope!==scope)throw Error('账号已变化，请刷新页面');return d;
 }
 function icon(item){
  const el=document.createElement('span');el.className='shop-art';
  const color=/^#[0-9a-f]{6}$/i.test(item.color)?item.color:'#718c75';
  if(item.slot==='coat'){el.innerHTML=`<svg viewBox="0 0 96 80" aria-label="毛色色样，选中后查看实际模型"><path d="M19 31L18 12 35 22Q48 17 61 22L78 12 77 31Q89 65 48 67Q7 65 19 31" fill="${color}"/><path d="M28 30l9 7m30-7l-9 7M42 23l6 10 6-10" fill="none" stroke="#fff8e9" stroke-width="5" stroke-linecap="round"/><ellipse cx="48" cy="54" rx="17" ry="10" fill="#eee5d3"/></svg>`;return el;}
  const img=document.createElement('img');img.src='/static/images/wardrobe-v1/'+item.id+'.png';img.alt=item.name+'独立模型实拍渲染';el.append(img);return el;

 }
 function active(item){return item.slot==='coat'?data.activeCoat===item.id:data.equipped[item.slot]===item.id;}
 function paint(){
  if(!data)return;
  const item=data.catalog.find(x=>x.id===selected),owned=data.owned.includes(selected);
  $('shop-balance').textContent=data.balance;$('shop-daily').disabled=busy||data.guest||data.dailyClaimed;$('shop-daily').textContent=data.dailyClaimed?'今日已领取':'领取今日 30 枚';
  $('shop-pet').disabled=busy;$('shop-home').href='/den?pet='+petId;$('shop-coat-filter').hidden=petId!==3;
  for(const b of document.querySelectorAll('[data-view]'))b.setAttribute('aria-pressed',String(b.dataset.view===view));
  for(const b of document.querySelectorAll('[data-slot]'))b.setAttribute('aria-pressed',String(b.dataset.slot===filter));
  const items=data.catalog.filter(x=>(filter==='all'||x.slot===filter)&&(view!=='owned'||data.owned.includes(x.id)));
  $('shop-catalog').replaceChildren(...items.map(x=>{const b=document.createElement('button');b.className='shop-card';b.dataset.item=x.id;b.disabled=busy;b.setAttribute('aria-pressed',String(x.id===selected));const title=document.createElement('strong');title.textContent=x.name;const sub=document.createElement('small');sub.textContent=active(x)?'已穿戴':data.owned.includes(x.id)?'已拥有 · 可搭配':x.price+' 枚代币';b.append(icon(x),title,sub);b.onclick=()=>{selected=x.id;previewing=true;note('');void preview();};return b;}));
  $('shop-empty').hidden=items.length>0;
  document.querySelector('.shop-detail').hidden=items.length===0;
  $('shop-tag').textContent=slots[item.slot]+' / '+(previewing?'正在试戴':'当前穿搭');$('shop-name').textContent=item.name;$('shop-description').textContent=item.description;$('shop-price').textContent=owned?'已永久拥有':item.price+' 枚岛屿代币';
  const compatible=item.slot==='coat'||data.compatible;
  $('shop-detail-image').hidden=item.slot==='coat';$('shop-detail-image').href='/static/images/wardrobe-v1/'+item.id+'.png';
  $('shop-compatibility').textContent=compatible?'':data.compatibilityNote;
  $('shop-buy').hidden=owned;$('shop-buy').disabled=busy||data.guest||data.balance<item.price||!compatible||!ready;
  $('shop-equip').hidden=!owned;$('shop-equip').disabled=busy||data.guest||active(item)||!compatible||!ready||!previewing;$('shop-equip').textContent=active(item)?'已穿戴':'穿戴这件';
  $('shop-login').hidden=!data.guest;
  $('shop-slots').replaceChildren(...['head','neck'].map(slot=>{const row=document.createElement('div');row.className='shop-slot';const label=document.createElement('span');label.textContent=slots[slot]+' · '+(data.catalog.find(x=>x.id===data.equipped[slot])?.name||'未穿戴');row.append(label);if(data.equipped[slot]){const b=document.createElement('button');b.textContent='卸下';b.disabled=busy||data.guest;b.onclick=()=>act('unequip',{slot});row.append(b);}return row;}));
  const names={welcome:'初次见面礼',daily:'每日奖励',explore:'探索奖励',journey:'串门奖励',purchase:'毛色购买',wardrobe_purchase:'装扮购买',supply_purchase:'补给购买'};
  $('shop-ledger').replaceChildren(...data.ledger.map(x=>{const li=document.createElement('li');li.textContent=(names[x.kind]||'岛屿代币')+' '+(x.amount>0?'+':'')+x.amount+' · '+new Date(x.created*1000).toLocaleString();return li;}));
 }
 function setup(){
  renderer=new THREE.WebGLRenderer({canvas:$('shop-canvas'),alpha:true,antialias:true});window.PaitWebCompat?.prepareRenderer(renderer);renderer.setPixelRatio(Math.min(devicePixelRatio,1.5));renderer.outputEncoding=THREE.sRGBEncoding;renderer.toneMapping=THREE.ACESFilmicToneMapping;
  scene=new THREE.Scene();scene.add(new THREE.HemisphereLight(0xffffff,0xa7b3a0,1.3));const sun=new THREE.DirectionalLight(0xfff1da,1.5);sun.position.set(2,4,3);scene.add(sun);
  camera=new THREE.PerspectiveCamera(33,1,.01,30);camera.position.set(1.15,.85,2.2);controls=new THREE.OrbitControls(camera,renderer.domElement);controls.target.set(0,.48,0);controls.enableDamping=true;controls.minDistance=.8;controls.maxDistance=4;
  loader=new SelectedAssets.Loader(new THREE.GLTFLoader());const resize=()=>{const c=$('shop-canvas');renderer.setSize(c.clientWidth,c.clientHeight,false);camera.aspect=c.clientWidth/c.clientHeight;camera.updateProjectionMatrix();};new ResizeObserver(resize).observe($('shop-canvas'));resize();
  let last=performance.now();function tick(now){requestAnimationFrame(tick);if(document.hidden||now-last<32)return;pet?.update(Math.min(.05,(now-last)/1000));last=now;controls.update();renderer.render(scene,camera);}requestAnimationFrame(tick);
 }
 async function preview(){
  const epoch=++previewEpoch;ready=false;paint();
  if(!loader){$('shop-loading').textContent='三维预览不可用，请检查浏览器硬件加速后重新加载。';return;}
  const item=data.catalog.find(x=>x.id===selected),coat=previewing&&item.slot==='coat';
  const spec=coat?{...data.pet,model:item.model,height:item.height,custom:false}:data.pet;
  const key=spec.model+':'+spec.height;
  $('shop-loading').textContent='正在准备试戴…';
  try{
   if(modelKey!==key||!pet){
    const ticket=loader.begin();modelKey='';if(pet){scene.remove(pet.root);SelectedAssets.disposeTree(pet.root);pet=null;}
    const gltf=await loader.glb(spec.model,ticket);if(epoch!==previewEpoch||!loader.active(ticket))return;
    pet=new PortalPets.Pet(THREE,gltf,spec);scene.add(pet.root);modelKey=key;
   }
   if(epoch!==previewEpoch)return;
   const equipped={...data.equipped};if(previewing&&item.slot!=='coat')equipped[item.slot]=item.id;
   await pet.wardrobeReady;
   if(epoch!==previewEpoch)return;
   await pet.wardrobe.apply(Object.values(equipped).map(id=>data.catalog.find(x=>x.id===id)).filter(Boolean));
   if(epoch!==previewEpoch)return;
   ready=item.slot==='coat'||(!spec.custom&&pet.wardrobe.supports(item.slot,item.design));
   $('shop-loading').textContent=ready?'':spec.custom?data.compatibilityNote:'此模型缺少装扮挂点，暂不能试戴或购买。';
   $('shop-preview-label').textContent=previewing?'试戴效果 · 尚未保存':'已保存的当前穿搭';paint();
  }catch(e){if(e.name!=='AbortError'&&epoch===previewEpoch){$('shop-loading').textContent='预览加载失败，请点击重新加载重试。';ready=false;paint();}}
 }
 async function load(){
  const epoch=++readEpoch;busy=true;ready=false;paint();
  try{const d=await api();if(epoch!==readEpoch)return;data=d;if(!data.catalog.some(x=>x.id===selected))selected=data.catalog[0].id;note('');await preview();}catch(e){note(e.message);}finally{if(epoch===readEpoch){busy=false;paint();}}
 }
 async function act(operation,body={}){
  if(busy)return;busy=true;paint();
  try{data=await api(operation,body);note(operation==='buy'?'已收入衣橱，点击「穿戴这件」保存搭配。':operation==='daily'?'今日代币已到账。':'穿搭已保存，回到小岛即可看到。');
   if(['equip','unequip'].includes(operation)){previewing=false;try{localStorage.setItem('pait-wardrobe-change',Date.now().toString());if(body.item?.startsWith('coat:'))localStorage.setItem('pait-cat-coat-change',Date.now().toString());}catch(_){}await preview();}
  }catch(e){note(e.message);}finally{busy=false;paint();}
 }
 $('shop-pet').onchange=()=>{petId=Number($('shop-pet').value);filter='all';previewing=true;history.replaceState(null,'','/pet-shop?pet='+petId);void load();};
 function selectVisible(){
  if(!data)return;
  const visible=data.catalog.filter(x=>(filter==='all'||x.slot===filter)&&(view!=='owned'||data.owned.includes(x.id)));
  if(visible.length&&!visible.some(x=>x.id===selected)){selected=visible[0].id;previewing=true;void preview();}else paint();
 }
 for(const b of document.querySelectorAll('[data-view]'))b.onclick=()=>{if(busy)return;view=b.dataset.view;selectVisible();};
 for(const b of document.querySelectorAll('[data-slot]'))b.onclick=()=>{if(busy)return;filter=b.dataset.slot;selectVisible();};
 for(const b of document.querySelectorAll('[data-motion]'))b.onclick=()=>pet?.play(b.dataset.motion);
 $('shop-reset').onclick=()=>{if(!busy&&data){previewing=false;void preview();}};
 $('shop-retry').onclick=()=>{if(!busy){modelKey='';if(!loader)try{setup();}catch(e){note('三维预览不可用，请检查硬件加速。');return;}void load();}};
 $('shop-daily').onclick=()=>act('daily');
 $('shop-buy').onclick=()=>{const item=data.catalog.find(x=>x.id===selected);pending={item:item.id,petId};$('shop-confirm-text').textContent='花费 '+item.price+' 枚代币，永久拥有「'+item.name+'」。购买后剩余 '+(data.balance-item.price)+' 枚。';$('shop-confirm-warning').textContent='购买后不会自动穿戴。';$('shop-confirm-buy').textContent='确认购买';$('shop-confirm').showModal();};
 $('shop-cancel').onclick=()=>$('shop-confirm').close();
 $('shop-confirm-buy').onclick=()=>{const action=pending;pending=null;$('shop-confirm').close();if(action)void act(action.operation||'buy',{item:action.item});};
 $('shop-equip').onclick=()=>{const item=data.catalog.find(x=>x.id===selected);if(item.slot==='coat'&&data.pet.custom){pending={item:item.id,operation:'equip'};$('shop-confirm-text').textContent='启用「'+item.name+'」后，当前定制宠物将切换为标准猫咪。';$('shop-confirm-warning').textContent='定制模型仍保存在模型工作室，可在那里重新启用。';$('shop-confirm-buy').textContent='确认切换';$('shop-confirm').showModal();}else void act('equip',{item:selected});};
 try{setup();}catch(e){note('三维预览不可用，请检查浏览器硬件加速后重试。');}
 void load();
})();
