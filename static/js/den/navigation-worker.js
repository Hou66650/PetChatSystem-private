/* Reuse the exact navigation and approach-selection code used on the page. */
'use strict';
importScripts('/static/js/den/scene-navigation.js'+self.location.search,'/static/js/den/cat-agent.js'+self.location.search);
let cached=null,nav=null;
self.onmessage=({data:{id,state,from,places,docks}})=>{
 try{
  if(!cached||cached.key!==state.key||cached.valid.length!==state.valid.length||cached.valid.some((v,i)=>v!==state.valid[i])){
   nav=Object.assign(Object.create(PetNavigation.Navigation.prototype),JSON.parse(state.key),{edgeClear:new Map(),nodes:[]});
   for(let z=-nav.n;z<=nav.n;z++)for(let x=-nav.n;x<=nav.n;x++)nav.nodes.push({x:x*nav.cell,z:z*nav.cell,gx:x,gz:z,valid:!!state.valid[nav.nodes.length]});
   cached=state;
  }
  const context={model:{position:from},locomotion:{navigation:nav},life:{feedingDock:p=>docks[p.id]}};
  const results=places.map(p=>{const point=CatAgent.Controller.prototype.point.call(context,p),path=nav.route(from,point);return {id:p.id,point,path,reachable:!!path};});
  self.postMessage({id,results});
 }catch(error){self.postMessage({id,error:String(error.message||error)});}
};
