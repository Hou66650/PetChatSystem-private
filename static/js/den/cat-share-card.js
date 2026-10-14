(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.CatShareCard=api;})(typeof window!=='undefined'?window:globalThis,function(){
 'use strict';
 function summary(data,selected,after=-Infinity){
  const stream=data?.streams?.find(s=>s.stream===selected);
  if(!stream)return null;
  // Export a snapshot of the selected session only; never export account IDs,
  // decision reasons, chat, or the account-wide cumulative memory table.
  const paths=typeof CatPaths!=='undefined'?CatPaths:require('./cat-paths');
  const trail=paths.trail(stream.snapshot?.trail,after);
  const events=(data.events||[]).filter(e=>e.stream===selected);
  const places=new Set(events.map(e=>e.snapshot?.target).filter(Boolean));
  const names=(data.catalog||[]).filter(p=>places.has(p.id)).map(p=>p.name);
  return {path:trail.d,distance:trail.length,points:trail.count,names:names.slice(0,5),
   time:stream.updated*1000,stale:data.serverTime-stream.updated>10||stream.snapshot?.phase==='stopped'};
 }
 function draw(canvas,s){
  canvas.width=1080;canvas.height=1350;const c=canvas.getContext('2d');
  const g=c.createLinearGradient(0,0,1080,1350);g.addColorStop(0,'#123f3c');g.addColorStop(.6,'#112d36');g.addColorStop(1,'#071d29');c.fillStyle=g;c.fillRect(0,0,1080,1350);
  for(let i=0;i<85;i++){c.fillStyle=`rgba(233,223,180,${.12+(i%5)*.05})`;c.beginPath();c.arc((i*137+83)%1080,(i*233+47)%1350,i%3+1,0,Math.PI*2);c.fill();}
  c.textAlign='left';c.fillStyle='#d7c591';c.font='24px sans-serif';c.fillText('派特岛   /   PAIT ISLAND',80,100);
  c.fillStyle='#f6f2df';c.font='bold 62px sans-serif';c.fillText('小小脚步，大大的世界',80,205);
  c.font='27px sans-serif';c.fillStyle='#b8d2c5';c.fillText('猫咪的雾林探索手记',80,260);
  c.save();c.translate(540,625);c.scale(38,38);
  c.fillStyle='#244d48';c.beginPath();c.arc(0,0,7.8,0,Math.PI*2);c.fill();
  c.strokeStyle='#689f9f';c.lineWidth=.34;c.beginPath();c.moveTo(-7.5,1.8);c.lineTo(7.5,1.8);c.stroke();
  c.strokeStyle='#d6c397';c.lineWidth=.48;c.beginPath();c.moveTo(0,-.2);c.lineTo(0,3.8);c.stroke();
  if(s.path){c.strokeStyle='#b6f3cf';c.lineWidth=.075;c.lineCap='round';c.lineJoin='round';c.stroke(new Path2D(s.path));}
  c.restore();
  c.fillStyle='#f6f2df';c.font='bold 44px sans-serif';c.fillText(s.distance.toFixed(1)+' 米',90,1000);c.fillText(s.points+' 个',580,1000);
  c.font='23px sans-serif';c.fillStyle='#b8d2c5';c.fillText('当前保留轨迹的路程',90,1042);c.fillText('真实轨迹采样点',580,1042);
  const lines=s.names.length?['记录中出现过的地点',...s.names.reduce((a,n,i)=>{if(i%2===0)a.push(n);else a[a.length-1]+='  ·  '+n;return a;},[])]:['还没有地点事件，等它慢慢认识这座岛。'];
  c.font='25px sans-serif';lines.forEach((line,i)=>c.fillText(line,90,1110+i*37));
  c.font='20px sans-serif';c.fillStyle='#93b5ae';c.fillText(new Date(s.time).toLocaleString('zh-CN',{hour12:false})+(s.stale?' · 最近一次记录':' · 观测快照'),90,1280);
  c.font='18px sans-serif';c.fillText('导航示意 · 仅当前会话保留记录，非全天统计 · 不含聊天与个人信息',90,1315);
 }
 return {summary,draw};
});
