/* Deterministic seekable timeline shared by browser playback and MP4 export. */
(()=>{'use strict';
 const $=id=>document.getElementById(id),ns='http://www.w3.org/2000/svg',duration=9;
 const el=(tag,attrs,parent)=>{const n=document.createElementNS(ns,tag);for(const [k,v]of Object.entries(attrs))n.setAttribute(k,v);parent.append(n);return n;};
 const clamp=x=>Math.max(0,Math.min(1,x)),smooth=x=>{x=clamp(x);return x*x*(3-2*x);},phase=(t,a,b)=>smooth((t-a)/(b-a));
 const scale=.8,tx=960-512*scale,ty=500-512*scale;
 $('words').innerHTML=PawBrand.foreground;$('words').querySelector('#paw').remove();$('words').setAttribute('transform',`translate(${tx} ${ty}) scale(${scale})`);
 const temp=el('g',{visibility:'hidden'},$('stage'));temp.innerHTML=PawBrand.foreground;
 const entries=PawIslands.map(source=>{const p={...source,...PawBrand.pads.find(p=>p.key===source.key)};
  const x=960+p.world[0]*27,y=513+p.world[1]*27,size=(p.key==='park'?18:9)*1.32*27;
  const picture=el('image',{href:p.key+'.png',x:x-size/2,y:y-size/2,width:size,height:size},$('islands'));
  const outline=el('path',{},$('outlines'));
  const label=el('text',{x,y:y+(p.key==='park'?242:155)},$('labels'));label.textContent=p.name;
  const shape=temp.querySelector(`[data-pad="${p.key}"]`),targets=[];
  if(p.d){const length=shape.getTotalLength(),samples=[];for(let i=0;i<2048;i++){const q=shape.getPointAtLength(i/2048*length);samples.push(q);}for(let i=0;i<128;i++){const a=i/128*Math.PI*2,dx=Math.cos(a),dy=Math.sin(a);let best=null,cost=Infinity;for(const q of samples){if(q.x*dx+q.y*dy<0)continue;const c=Math.abs(q.x*dy-q.y*dx);if(c<cost){cost=c;best=q;}}targets.push([tx+(p.cx+best.x)*scale,ty+(p.cy+best.y)*scale]);}}
  else{const rot=p.angle*Math.PI/180;for(let i=0;i<128;i++){const a=i/128*Math.PI*2,rel=a-rot,r=1/Math.sqrt((Math.cos(rel)/p.rx)**2+(Math.sin(rel)/p.ry)**2);targets.push([tx+(p.cx+Math.cos(a)*r)*scale,ty+(p.cy+Math.sin(a)*r)*scale]);}}
  return {picture,outline,targets,source:p.points.map(q=>[x+q[0]*27,y+q[1]*27])};
 });temp.remove();
 let time=0,playing=false,start=0,raf=0;
 function seek(t){time=Math.max(0,Math.min(duration,t));const morph=phase(time,3.2,6),draw=phase(time,1.2,2.8);
  $('islands').style.opacity=1-phase(time,2.4,3.8);$('labels').style.opacity=1-phase(time,1.2,2.2);$('cloud').style.opacity=1-phase(time,2.3,4);
  entries.forEach(e=>{const points=e.source.map((a,i)=>[a[0]+(e.targets[i][0]-a[0])*morph,a[1]+(e.targets[i][1]-a[1])*morph]);e.outline.setAttribute('d',points.map((p,i)=>(i?'L':'M')+p.map(n=>n.toFixed(2)).join(' ')).join(' ')+' Z');e.outline.setAttribute('stroke-width',4+(23*scale-4)*morph);e.outline.setAttribute('pathLength','1');e.outline.setAttribute('stroke-dasharray','1');e.outline.setAttribute('stroke-dashoffset',String(1-draw));e.outline.style.opacity=clamp((time-1.2)/.35);});
  $('words').style.opacity=phase(time,5.7,7.1);$('name').style.opacity=phase(time,7,7.8);$('seek').value=time;$('time').textContent=time.toFixed(1)+' / 9.0 秒';
 }
 function pause(){playing=false;cancelAnimationFrame(raf);$('play').textContent='播放';}
 function frame(now){seek((now-start)/1000);if(time>=duration){pause();return;}raf=requestAnimationFrame(frame);}
 function play(){if(time>=duration)seek(0);playing=true;start=performance.now()-time*1000;$('play').textContent='暂停';raf=requestAnimationFrame(frame);}
 $('play').onclick=()=>playing?pause():play();$('restart').onclick=()=>{pause();seek(0);play();};$('seek').oninput=e=>{pause();seek(+e.target.value);};
 $('fullscreen').onclick=async()=>{try{if(document.fullscreenElement)await document.exitFullscreen();else await $('stage').requestFullscreen();}catch{$('time').textContent='浏览器未允许全屏，可用 F11';}};
 document.addEventListener('keydown',e=>{if(e.target.matches('input'))return;if(e.code==='Space'){e.preventDefault();$('play').click();}if(e.key.toLowerCase()==='r')$('restart').click();if(e.key.toLowerCase()==='f')$('fullscreen').click();});
 document.addEventListener('visibilitychange',()=>{if(document.hidden)pause();});
 if(new URLSearchParams(location.search).has('clean'))document.body.classList.add('clean');
 window.PawFilm={seek,pause,duration,ready:Promise.all([...document.querySelectorAll('image')].map(n=>new Promise((ok,fail)=>{const i=new Image();i.onload=ok;i.onerror=fail;i.src=n.getAttribute('href');})))};
 seek(0);
})();
