/* Authored centre lines follow the unchanged detailed GLB; metres, Y up. */
(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.ParkFacilities=api;})(globalThis,function(){
 'use strict';
 function length(f){return f.path.slice(1).reduce((sum,p,i)=>sum+Math.hypot(p[0]-f.path[i][0],p[2]-f.path[i][2]),0);}
 function sample(f,distance){
  let d=Math.max(0,Math.min(length(f),distance));
  for(let i=1;i<f.path.length;i++){
   const a=f.path[i-1],b=f.path[i],n=Math.hypot(b[0]-a[0],b[2]-a[2]);
   if(d<=n||i===f.path.length-1){const t=Math.min(1,d/n);return {x:a[0]+(b[0]-a[0])*t,y:a[1]+(b[1]-a[1])*t,z:a[2]+(b[2]-a[2])*t,yaw:Math.atan2(b[0]-a[0],b[2]-a[2]),pitch:-Math.atan2(b[1]-a[1],n)};}d-=n;
  }
 }
 return {length,sample};
});
