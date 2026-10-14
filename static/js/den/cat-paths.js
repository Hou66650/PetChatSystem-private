(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.CatPaths=api;})(typeof window!=='undefined'?window:globalThis,function(){
 'use strict';
 const valid=p=>Array.isArray(p)&&p.length>=2&&p.every(Number.isFinite);
 function trail(points,after=-Infinity){
  let d='',previous=null,length=0,count=0;
  for(const p of points||[]){if(!valid(p)||![3,4].includes(p.length)||p[2]<=after)continue;
   const distance=previous?Math.hypot(p[0]-previous[0],p[1]-previous[1]):0;
   const continuous=previous&&!p[3]&&p[2]>previous[2]&&p[2]-previous[2]<=5000&&distance<1.5;
   d+=(continuous?' L':' M')+p[0]+' '+p[1];if(continuous)length+=distance;previous=p;count++;
  }return {d,length,count};
 }
 function route(position,points){const all=[position,...(points||[])];if(!points?.length||!all.every(valid))return '';return all.map((p,i)=>(i?'L':'M')+p[0]+' '+p[1]).join(' ');}
 return {trail,route};
});
