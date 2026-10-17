const assert=require('node:assert/strict'),{Motion,clampTarget}=require('../desktop/motion');
for(const target of [{x:200,y:0},{x:-200,y:0},{x:0,y:-200},{x:150,y:200}]){
 const m=new Motion(0,0);let prev={...m},done=false;
 for(let i=0;i<1500;i++){
  const r=m.step(target,1/30);assert(r.speed<=80.001);assert(Math.hypot(m.vx-prev.vx,m.vy-prev.vy)<=200/30+.01||r.arrived);
  assert(Math.abs(Math.atan2(Math.sin(m.yaw-prev.yaw),Math.cos(m.yaw-prev.yaw)))<=2.8/30+.001);assert([m.x,m.y,m.yaw].every(Number.isFinite));prev={...m};
  if(r.arrived){done=true;break;}
 }
 assert(done,'must reach destination after turning');assert.equal(m.x,target.x);assert.equal(m.y,target.y);
}
const area={x:-1920,y:20,width:1920,height:1080};assert.deepEqual(clampTarget({x:5000,y:5000},area),{x:-280,y:800});
console.log('PASS desktop motion: turn limits, acceleration, speed, arrival, negative-origin bounds');
