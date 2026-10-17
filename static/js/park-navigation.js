/* Shared measured layout, bounded A* only when the user chooses a destination. */
(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.ParkNavigation=api;})(globalThis,function(){
 'use strict';
 function create(config){
  const {ellipse,obstacles,grid,clearance}=config,nx=Math.ceil(ellipse.x/grid),nz=Math.ceil(ellipse.z/grid),nodes=new Map();
  function inside(x,z,pad=0){return Number.isFinite(x)&&Number.isFinite(z)&&(x/ellipse.x)**2+(z/ellipse.z)**2<=1+1e-9&&obstacles.every(o=>Math.hypot(x-o.x,z-o.z)>=o.radius+pad-1e-9);}
  function segment(a,b,pad=0){if(!inside(a.x,a.z,pad)||!inside(b.x,b.z,pad))return false;const dx=b.x-a.x,dz=b.z-a.z,length=dx*dx+dz*dz;return obstacles.every(o=>{const t=length?Math.max(0,Math.min(1,((o.x-a.x)*dx+(o.z-a.z)*dz)/length)):0;return Math.hypot(a.x+t*dx-o.x,a.z+t*dz-o.z)>=o.radius+pad-1e-9;});}
  const key=(i,j)=>i+','+j;
  for(let i=-nx;i<=nx;i++)for(let j=-nz;j<=nz;j++){const p={x:i*grid,z:j*grid};if(inside(p.x,p.z,clearance))nodes.set(key(i,j),{...p,i,j,key:key(i,j)});}
  function nearest(p){if(inside(p.x,p.z,clearance))return {x:p.x,z:p.z};let best=null,d=Infinity;for(const n of nodes.values()){const v=Math.hypot(n.x-p.x,n.z-p.z);if(v<d){d=v;best=n;}}return best?{x:best.x,z:best.z}:null;}
  function anchor(p){let best=null,d=Infinity;for(const n of nodes.values()){const v=Math.hypot(n.x-p.x,n.z-p.z);if(v<d&&segment(p,n)){d=v;best=n;}}return best;}
  function route(from,to){
   if(!inside(from.x,from.z))return [];const end=nearest(to);if(!end)return [];if(segment(from,end,clearance))return [end];
   const start=anchor(from),goal=anchor(end);if(!start||!goal)return [];
   const open=new Set([start.key]),cost=new Map([[start.key,0]]),previous=new Map(),closed=new Set();
   while(open.size){let current=null,score=Infinity;for(const id of open){const n=nodes.get(id),s=cost.get(id)+Math.hypot(n.x-goal.x,n.z-goal.z);if(s<score){score=s;current=n;}}
    if(current.key===goal.key){let id=goal.key,path=[end];while(id){path.push(nodes.get(id));id=previous.get(id);}path.push(from);path.reverse();
     // String-pull only where the entire segment remains clear.
     const result=[];let i=0;while(i<path.length-1){let j=path.length-1;while(j>i+1&&!segment(path[i],path[j],clearance))j--;result.push({x:path[j].x,z:path[j].z});i=j;}return result;
    }
    open.delete(current.key);closed.add(current.key);
    for(let dx=-1;dx<=1;dx++)for(let dz=-1;dz<=1;dz++){if(!dx&&!dz)continue;const n=nodes.get(key(current.i+dx,current.j+dz));if(!n||closed.has(n.key)||!segment(current,n,clearance))continue;const next=cost.get(current.key)+Math.hypot(dx,dz)*grid;if(next<(cost.get(n.key)??Infinity)){cost.set(n.key,next);previous.set(n.key,current.key);open.add(n.key);}}
   }return [];
  }
  return {inside,segment,nearest,route,config};
 }
 return {create};
});
