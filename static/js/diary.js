/* Daily pet-authored pages. Chat history stays in its original store. */
(function(){
 'use strict';
 const $=id=>document.getElementById(id),contentEl=$('diary-content'),countEl=$('diary-count');
 const petSel=$('f-pet'),dateSel=$('f-date'),kwInput=$('f-kw'),exportBtn=$('btn-export-pdf'),more=$('btn-load-more');
 const PET_NAMES={1:'球球',2:'雪球',3:'团子',4:'大壮'},DATE_LABELS={all:'全部日期',7:'最近 7 天',30:'最近 30 天'};
 let entries=[],lastGrouped=[],nextBefore=null,loading=false;
 const localDateKey=d=>new Intl.DateTimeFormat('sv-SE',{timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit'}).format(d);
 const dayNumber=s=>Date.parse(s+'T00:00:00+08:00')/86400000;
 const fmtDateTitle=s=>s.replace('-','年').replace('-','月')+'日';
 function currentFilters(){return {pet:petSel.value,date:dateSel.value,kw:kwInput.value.trim().toLocaleLowerCase()};}
 function filterDesc(f){return '宠物：'+(f.pet==='all'?'全部宠物':PET_NAMES[f.pet])+'｜范围：'+DATE_LABELS[f.date]+(f.kw?'｜关键词：'+kwInput.value.trim():'');}
 function render(){
  const f=currentFilters(),today=dayNumber(localDateKey(new Date()));
  const rows=entries.filter(e=>(f.pet==='all'||String(e.petId)===f.pet)&&(f.date==='all'||(today-dayNumber(e.day)>=0&&today-dayNumber(e.day)<Number(f.date)))&&(!f.kw||(e.body+e.name+e.title).toLocaleLowerCase().includes(f.kw)));
  const groups=new Map();for(const e of rows){if(!groups.has(e.day))groups.set(e.day,[]);groups.get(e.day).push(e);}
  lastGrouped=[...groups].sort((a,b)=>b[0].localeCompare(a[0])).map(([key,entries])=>({key,entries}));
  countEl.textContent='已加载 '+entries.length+' 篇 · 当前显示 '+rows.length+' 篇'+(nextBefore?'（可加载更早日记）':'');
  exportBtn.disabled=!rows.length;contentEl.replaceChildren();
  if(!rows.length){const empty=document.createElement('p');empty.className='diary-empty';empty.textContent=entries.length?'没有符合筛选条件的日记。':'还没有记下今天的故事。去小窝探索、摸摸宠物或聊聊天，再回来翻开日记吧。';contentEl.append(empty);}
  for(const g of lastGrouped){const section=document.createElement('section'),h=document.createElement('h3');section.className='diary-day';h.className='diary-day-title';h.textContent=fmtDateTitle(g.key);section.append(h);for(const e of g.entries)section.append(entryEl(e));contentEl.append(section);}
 }
 function entryEl(e){
  const article=document.createElement('article'),main=document.createElement('div'),title=document.createElement('strong'),body=document.createElement('p'),del=document.createElement('button');
  article.className='diary-entry';main.className='diary-entry-main';title.textContent=e.name+' · '+e.title+(e.draft?' · 今天还在续写':'');body.textContent=e.body;main.append(title,body);
  del.type='button';del.className='diary-del';del.textContent='删除';del.setAttribute('aria-label','删除'+e.name+'在'+e.day+'的日记');
  del.addEventListener('click',async()=>{if(!confirm('删除'+e.name+'在'+e.day+'的这一篇日记？原聊天记录会保留，这一天的日记不会自动重新生成。'))return;
   del.disabled=true;try{const r=await fetch('/api/diary/'+e.petId+'/'+e.day,{method:'DELETE',headers:{'Content-Type':'application/json'},body:'{}'});if(!r.ok)throw Error('delete');entries=entries.filter(x=>x.petId!==e.petId||x.day!==e.day);render();toast('日记已删除，原聊天记录已保留','success');}catch(error){del.disabled=false;toast('暂时无法删除，请稍后重试','error');}});
  article.append(main,del);return article;
 }
 async function load(){
  if(loading)return;loading=true;more.disabled=true;
  try{const r=await fetch('/api/diary'+(nextBefore?'?before='+encodeURIComponent(nextBefore):''),{cache:'no-store'});if(!r.ok)throw Error('diary');const data=await r.json();
   const merged=new Map(entries.map(e=>[e.day+':'+e.petId,e]));for(const e of data.entries)merged.set(e.day+':'+e.petId,e);entries=[...merged.values()];nextBefore=data.nextBefore;render();more.hidden=!nextBefore;more.textContent='加载更早的日记';
  }catch(error){if(!entries.length)contentEl.textContent='日记暂时加载失败，请稍后重试。';more.hidden=false;more.textContent='重试加载';toast('日记暂时未能读取','error');}finally{loading=false;more.disabled=false;}
 }
 async function buildPdf(){
  const pages=lastGrouped.flatMap(g=>g.entries.map(e=>({...e}))),pdf=new window.jspdf.jsPDF('p','mm','a4');
  const filter=filterDesc(currentFilters());let first=true;
  for(const entry of pages){
   const box=document.createElement('div');box.style.cssText='position:fixed;left:-9999px;top:0;width:794px;background:#fffdf8;color:#3c342c;font-family:Microsoft YaHei,PingFang SC,sans-serif;padding:44px 48px;box-sizing:border-box;';
   const title=document.createElement('h1'),meta=document.createElement('p'),body=document.createElement('p'),foot=document.createElement('p');
   title.textContent=entry.name+' · '+entry.title;title.style.fontSize='26px';
   meta.textContent=fmtDateTitle(entry.day)+(entry.draft?' · 今天还在续写':'')+'｜'+filter;meta.style.cssText='font-size:13px;color:#786b5e';
   body.textContent=entry.body;body.style.cssText='white-space:pre-line;font-size:16px;line-height:1.9';foot.textContent='派特岛 · 宠物的每日手记 · 导出于 '+localDateKey(new Date());foot.style.cssText='font-size:12px;color:#786b5e;margin-top:28px';box.append(title,meta,body,foot);document.body.append(box);
   let canvas;
   try{
    canvas=await html2canvas(box,{scale:2,backgroundColor:'#fffdf8'});
    const width=pdf.internal.pageSize.getWidth(),height=pdf.internal.pageSize.getHeight(),pixelsPerMm=canvas.width/width,pageHeight=Math.floor(height*pixelsPerMm);
    for(let y=0;y<canvas.height;y+=pageHeight){const slice=document.createElement('canvas');slice.width=canvas.width;slice.height=Math.min(pageHeight,canvas.height-y);slice.getContext('2d').drawImage(canvas,0,y,canvas.width,slice.height,0,0,canvas.width,slice.height);
     if(!first)pdf.addPage();pdf.addImage(slice.toDataURL('image/png'),'PNG',0,0,width,slice.height/pixelsPerMm);first=false;slice.width=slice.height=1;
    }
   }finally{box.remove();if(canvas)canvas.width=canvas.height=1;}
  }
  pdf.save('宠物每日手记_'+localDateKey(new Date())+'.pdf');
 }

 exportBtn.addEventListener('click',async()=>{if(!lastGrouped.length)return;exportBtn.disabled=true;exportBtn.textContent='生成中…';try{await buildPdf();toast('PDF 已导出','success');}catch(error){toast('PDF 生成失败','error');}finally{exportBtn.disabled=!lastGrouped.length;exportBtn.textContent='导出 PDF';}});
 petSel.addEventListener('change',render);dateSel.addEventListener('change',render);let timer;
 kwInput.addEventListener('input',()=>{clearTimeout(timer);timer=setTimeout(render,150);});
 $('btn-reset-filters').addEventListener('click',()=>{petSel.value='all';dateSel.value='all';kwInput.value='';render();});
 more.addEventListener('click',load);$('diary-date').textContent=localDateKey(new Date())+' · 北京时间';load();
})();
