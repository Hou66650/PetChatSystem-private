/* Owner-side utility agent. Decisions run at 4 Hz; animation never calls an LLM. */
(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.ParkAgent=api;})(globalThis,function(){
 'use strict';
 const labels={explore:'寻找草坪里的新气味',play:'想追一会儿球',rest:'找个安静地方歇一会儿',greet:'想认识附近的伙伴',observe:'停下来看看周围'};
 const distance=(a,b)=>Math.hypot(a.x-b.x,a.z-b.z),clamp=x=>Math.max(0,Math.min(1,x));
 class Agent{
  constructor({navigation,personality='curious',random=Math.random}){this.nav=navigation;this.personality=personality;this.random=random;this.enabled=true;this.until=0;this.energy=.8;this.curiosity=.65;this.social=.65;this.playfulness=.8;this.recent=new Map();this.visited=[];this.plan=null;this.phase=0;this.sent=false;this.deadline=0;this.activity='idle';this.goal=null;this.peer=null;this.reason='';this.blockedUntil=0;}
  interrupt(now,seconds=12){this.plan=null;this.goal=null;this.peer=null;this.activity='idle';this.until=now+seconds;this.reason='先听主人的，稍后继续自己玩';}
  enable(value,now){this.enabled=value;this.interrupt(now,0);}
  failed(now){this.recent.set(this.activity,now);this.interrupt(now,1.5);this.blockedUntil=now+4;}
  candidates(pos,peers){
   const free=p=>this.nav.inside(p.x,p.z,.3)&&peers.every(o=>distance(o,p)>1.5)&&distance(pos,p)>1.2;
   const points=[{x:-4,z:2},{x:4,z:2.8},{x:-3,z:-3.7},{x:3,z:-3.4},{x:0,z:4.4}];
   for(let i=0;i<10;i++){const a=this.random()*Math.PI*2,r=2.8+this.random()*2.1;points.push({x:Math.cos(a)*r,z:Math.sin(a)*r});}
   return points.filter(free).sort((a,b)=>{
    const score=p=>Math.min(4,...this.visited.map(v=>distance(v,p)))-distance(pos,p)*.08;
    return score(b)-score(a);
   });
  }
  choose(now,pos,peers){
   const points=this.candidates(pos,peers),go=(p,speed=1)=>({point:p,speed}),act=(action,seconds)=>({action,seconds});
   const options=[],cool=k=>Math.max(0,1-(now-(this.recent.get(k)??-100))/35)*1.1;
   const add=(kind,score,steps,peer=null)=>options.push({kind,score:score-cool(kind)+this.random()*.12,steps,peer});
   if(points.length){
    add('explore',this.curiosity+(this.personality==='curious'?.3:0),[go(points[0]),act('sniff',3),act('look',2)]);
    const ball=points.find(p=>distance(pos,p)<6);
    if(ball)add('play',this.playfulness+this.energy*.25,[act('bow',1.8),{...go(ball,1.7),ball},{...act('sniff',2),prop:ball},act('happy',2)]);
    const quiet=[...points].sort((a,b)=>Math.min(10,...peers.map(p=>distance(p,b)))-Math.min(10,...peers.map(p=>distance(p,a))))[0];
    add('rest',(1-this.energy)*2.6+(this.personality==='careful'?.15:0),[go(quiet,.8),act('sit',3),act('sleep',9),act('stretch',2.5)]);
   }
   if(now>=this.blockedUntil)for(const p of peers){
    if(['sleep','sit'].includes(p.action)||distance(p,pos)>8||distance(p,pos)<1.1)continue;
    const d=distance(pos,p)||1,point={x:p.x+(pos.x-p.x)/d*1.6,z:p.z+(pos.z-p.z)/d*1.6};
    if(!this.nav.inside(point.x,point.z,.3)||!this.nav.route(pos,point).length||peers.some(q=>q.id!==p.id&&distance(point,q)<1.4))continue;
    add('greet',this.social+(this.personality==='gentle'?.4:this.personality==='careful'?-.4:.1),[go(point,.85),{...act('greet',2.5),face:p},act('sniff',2),act('bow',2)],{id:p.id,x:p.x,z:p.z});break;
   }
   add('observe',.12,[act('look',2.5)]);
   if(this.energy<.22&&points.length)options.find(o=>o.kind==='rest').score+=3;
   const chosen=options.sort((a,b)=>b.score-a.score)[0];this.plan=chosen.steps;this.activity=chosen.kind;this.peer=chosen.peer;this.reason=labels[chosen.kind];this.phase=0;this.sent=false;this.recent.set(chosen.kind,now);
  }
  tick({now,dt,pos,peers=[],moving=false}){
   if(!this.enabled||now<this.until)return null;
   dt=Math.min(1,Math.max(0,dt));this.energy=clamp(this.energy+(this.activity==='rest'?.024:-(moving?.012:.003))*dt);this.curiosity=clamp(this.curiosity+.012*dt);this.social=clamp(this.social+.01*dt);this.playfulness=clamp(this.playfulness+.009*dt);
   if(this.peer&&!peers.some(p=>p.id===this.peer.id&&distance(p,this.peer)<2)){this.failed(now);return {cancel:true,message:'伙伴走远了，先玩自己的。'};}
   if(!this.plan)this.choose(now,pos,peers);
   let step=this.plan[this.phase];
   if(this.sent){
    if(step.point&&distance(pos,step.point)>.3){if(now>this.deadline){this.failed(now);return {cancel:true,message:'这边有些拥挤，换一个地方。'};}return null;}
    if(!step.point&&now<this.deadline)return null;
    this.phase++;this.sent=false;step=this.plan[this.phase];
    if(!step){
     if(this.activity==='explore')this.curiosity=.12;
     if(this.activity==='play')this.playfulness=.08;
     if(this.activity==='greet')this.social=.08;
     this.visited.push({...pos});if(this.visited.length>5)this.visited.shift();this.plan=null;this.goal=null;this.peer=null;this.activity='idle';return null;
    }
   }
   this.sent=true;this.deadline=now+(step.point?25:step.seconds);this.goal=step.ball||step.prop||null;
   return {destination:step.point,action:step.ball?'ball':step.action||'idle',duration:step.point?25:step.seconds,speed:step.speed||1,goal:this.goal,face:step.face,activity:this.activity,message:this.reason};
  }
 }
 return {Agent,labels};
});
