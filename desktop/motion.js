/* Physical window movement in screen DIP, shared with deterministic tests. */
'use strict';
class Motion {
 constructor(x,y){this.x=x;this.y=y;this.vx=0;this.vy=0;this.yaw=0;}
 step(target,dt){
  dt=Math.max(0,Math.min(.05,dt));const dx=(target?.x??this.x)-this.x,dy=(target?.y??this.y)-this.y,d=Math.hypot(dx,dy);
  const angle=d>.6?Math.atan2(Math.sin(Math.atan2(dx,dy)-this.yaw),Math.cos(Math.atan2(dx,dy)-this.yaw)):0;
  const turn=Math.max(-2.8*dt,Math.min(2.8*dt,angle));this.yaw=Math.atan2(Math.sin(this.yaw+turn),Math.cos(this.yaw+turn));this.turnRate=dt?turn/dt:0;
  const desired=target?Math.min(80,Math.sqrt(2*200*d))*Math.max(0,Math.cos(angle))**4:0;
  const vx=d>.1?dx/d*desired:0,vy=d>.1?dy/d*desired:0;
  const dvx=vx-this.vx,dvy=vy-this.vy,dv=Math.hypot(dvx,dvy),k=dv?Math.min(1,200*dt/dv):0;
  this.vx+=dvx*k;this.vy+=dvy*k;
  const speed=Math.hypot(this.vx,this.vy),step=speed*dt;
  if(target&&d<=Math.max(.6,step)){this.x=target.x;this.y=target.y;this.vx=this.vy=0;return {...this,speed:0,arrived:true};}
  this.x+=this.vx*dt;this.y+=this.vy*dt;
  return {...this,speed,arrived:false};
 }
 halt(){this.vx=this.vy=this.turnRate=0;}
}
function clampTarget(point,area){return {x:Math.max(area.x,Math.min(area.x+Math.max(0,area.width-280),point.x)),y:Math.max(area.y,Math.min(area.y+Math.max(0,area.height-300),point.y))};}
module.exports={Motion,clampTarget};
