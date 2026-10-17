/* Batch route queries off the render thread; execution still uses live navigation. */
(function(root){
 'use strict';
 const version=typeof document!=='undefined'?new URL(document.currentScript.src).search:'';
 function key(nav){
  const data={};
  for(const name of ['radius','clearance','cell','n','size','domains','obstacles','water','bridges','rug','surfaces','dock'])data[name]=nav[name];
  return JSON.stringify(data);
 }
 function snapshot(nav){const valid=new Uint8Array(nav.nodes.length);for(let i=0;i<valid.length;i++)valid[i]=nav.nodes[i].valid?1:0;return {key:key(nav),valid};}
 function matches(nav,state){
  if(key(nav)!==state.key||nav.nodes.length!==state.valid.length)return false;
  for(let i=0;i<state.valid.length;i++)if(!!nav.nodes[i].valid!==!!state.valid[i])return false;
  return true;
 }
 class Planner {
  constructor(){this.worker=null;this.serial=0;this.job=null;this.disposed=false;}
  query(state,from,places,docks,signal){
   this.cancel();
   if(this.disposed||signal?.aborted)return Promise.reject(new Error('cancelled'));
   return new Promise((resolve,reject)=>{
    const id=++this.serial;
    const finish=(error,value)=>{if(this.job?.id!==id)return;clearTimeout(this.job.timer);signal?.removeEventListener('abort',abort);this.job=null;error?reject(error):resolve(value);};
    const abort=()=>this.cancel();
    this.job={id,finish,timer:setTimeout(()=>this.cancel(new Error('route worker timeout')),15000)};
    signal?.addEventListener('abort',abort,{once:true});
    try{
     if(!this.worker){
      const worker=this.worker=new Worker('/static/js/den/navigation-worker.js'+version);
      this.worker.onmessage=({data})=>{if(data.id===this.job?.id)this.job.finish(data.error?new Error(data.error):null,data.results);};
      this.worker.onerror=()=>{if(this.worker===worker)this.cancel(new Error('route worker unavailable'));};
     }
     // Copy the compact validity bitmap, never detach or mutate the live grid.
     this.worker.postMessage({id,state,from,places,docks});
    }catch(error){this.cancel(error);}
   });
  }
  cancel(error=new Error('cancelled')){if(this.job){this.worker?.terminate();this.worker=null;this.job.finish(error);}}
  dispose(){this.cancel();this.worker?.terminate();this.worker=null;this.disposed=true;}
 }
 const api={Planner,snapshot,matches};
 if(typeof module==='object'&&module.exports)module.exports=api;else root.PetRoutePlanner=api;
})(typeof window!=='undefined'?window:globalThis);
