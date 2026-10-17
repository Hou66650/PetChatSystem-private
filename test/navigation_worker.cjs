/* Run the browser worker's real imports/protocol on a separate Node thread. */
const assert=require('node:assert/strict');
const api=require('../static/js/den/navigation-planner');
const {Navigation}=require('../static/js/den/scene-navigation');
const {Controller}=require('../static/js/den/cat-agent');
const catalog=require('../static/data/cat-world.json');
const layout=require('../static/js/den/mistwood-layout');
const farm=require('../static/js/den/farm-garden');
const BrowserWorker=require('./helpers/browser-route-worker.cjs');
global.Worker=BrowserWorker;
(async()=>{
 const nav=new Navigation({...farm.navigation(layout,require('../static/data/farm-layout.json')),bodyRadius:.619});
 const from={x:0,z:0},dynamic={id:'plant',x:3,z:2,radius:.4,approaches:[],actions:['observe']};
 const places=[...catalog,dynamic],docks={food:{entry:{x:.4,z:.4}}};
 const reference=()=>places.map(p=>{const point=Controller.prototype.point.call({model:{position:from},locomotion:{navigation:nav},life:{feedingDock:q=>docks[q.id]}},p),path=nav.route(from,point);return {id:p.id,point,path,reachable:!!path};});
 const planner=new api.Planner(),state=api.snapshot(nav);let finished=false;
 const promise=planner.query(state,from,places,docks).then(r=>{finished=true;return r;});
 await new Promise(r=>setImmediate(r));assert.equal(finished,false,'main event loop runs during real background computation');
 assert.deepEqual(await promise,reference(),'all static and dynamic approaches match original algorithm');
 assert(api.matches(nav,state));assert.equal(state.valid.byteLength,nav.nodes.length,'snapshot buffer remains owned by page');
 assert.deepEqual(await planner.query(api.snapshot(nav),from,places,docks),reference(),'cached navigation matches');
 nav.obstacles.push({kind:'rect',x:1,z:0,w:.5,d:2});for(const n of nav.nodes)n.valid=nav.isWalkable(n);nav.edgeClear.clear();
 assert(!api.matches(nav,state));assert.deepEqual(await planner.query(api.snapshot(nav),from,places,docks),reference(),'changed obstacles rebuild worker cache');
 nav.dock={obstacle:'food',entry:{x:0,z:0},target:{x:0,z:.1},clearance:.05};
 assert.deepEqual(await planner.query(api.snapshot(nav),from,places,docks),reference(),'dock state uses identical routing');
 const abort=new AbortController(),cancelled=planner.query(api.snapshot(nav),from,places,docks,abort.signal);abort.abort();await assert.rejects(cancelled,/cancelled/);assert.equal(planner.worker,null);
 assert.deepEqual(await planner.query(api.snapshot(nav),from,places,docks),reference(),'new worker after cancellation');
 const disposed=planner.query(api.snapshot(nav),from,places,docks);planner.dispose();await assert.rejects(disposed,/cancelled/);await assert.rejects(planner.query(state,from,places,docks),/cancelled/);
 global.Worker=class{constructor(){queueMicrotask(()=>this.onerror());}postMessage(){}terminate(){this.terminated=true;}};
 const failed=new api.Planner();await assert.rejects(failed.query(state,from,places,docks),/unavailable/);assert.equal(failed.worker,null);failed.dispose();global.Worker=BrowserWorker;

 // Controlled delivery verifies agent priority and stale-result rejection, not just worker math.
 class DeferredPlanner{
  query(state,from,places,docks,signal){this.signal=signal;return new Promise(resolve=>this.deliver=()=>resolve(places.map(p=>({id:p.id,point:{x:p.x,z:p.z},path:[{x:p.x,z:p.z}],reachable:true}))));}
  dispose(){}
 }
 global.PetRoutePlanner={...api,Planner:DeferredPlanner};
 const small=new Navigation({radius:4}),model={position:{x:0,z:0}};let goCalls=0,eat=true,dock={entry:{x:1,z:0}};
 const move={navigation:small,enabled:true,owner:'idle',path:[],goTo(p){goCalls++;this.path=[p];this.owner='command';return true;},interrupt(){this.path=[];this.owner='interaction';}};
 const agent=new Controller({model,locomotion:move,life:{cancel(){},feedingDock:()=>dock},scope:'test',animate(){},storage:null,canEat:()=>eat,fetcher:async()=>({ok:true,json:async()=>({catalog:[...catalog.slice(0,4),{id:'food',name:'food',x:1,z:0,station:true,actions:['eat','observe']}],memory:[],scope:'test'})})});
 await agent.ready;agent.networkAfter=Infinity;
 for(const mutate of [()=>model.position.x+=.1,()=>small.obstacles.push({kind:'rect',x:3,z:3,w:1,d:1}),()=>agent.catalog=[...agent.catalog,{id:'new',x:1,z:1,actions:['observe']}],()=>agent.catalog[0].x+=.1,()=>small.nodes[0].valid=!small.nodes[0].valid,()=>move.owner='command',()=>move.enabled=false,()=>eat=false,()=>dock={entry:{x:2,z:0}}]){
  move.owner='idle';move.enabled=true;eat=true;const before=goCalls,job=agent.plan();assert(agent.pending);mutate();agent.routePlanner.deliver();await job;assert.equal(goCalls,before,'stale proposal never starts movement');assert.equal(agent.pending,null);
 }
 move.owner='idle';move.enabled=true;let job=agent.plan();const oldPlanner=agent.routePlanner;agent.interrupt();oldPlanner.deliver();await job;assert.equal(agent.goal,null,'interruption rejects late delivery');
 job=agent.plan();agent.routePlanner.deliver();await job;assert(agent.goal,'fresh result starts original selection');assert.equal(move.owner,'agent');assert.equal(agent.plannedPoints,null,'temporary approaches cleared');
 agent.interrupt();move.owner='idle';agent.catalog=[{id:'home',name:'home',x:1,z:0,actions:['observe']}];agent.routePlanner.query=async()=>{throw Error('offline worker');};await agent.plan();assert(agent.goal,'worker failure preserves synchronous fallback');assert(agent.routeWorkerFailed);
 agent.interrupt();move.owner='idle';agent.routeWorkerFailed=false;agent.routePlanner=new DeferredPlanner();
 global.document={hidden:true};agent.interrupt();assert.equal(agent.routePlanner,null,'hidden page releases idle worker');delete global.document;
 agent.interrupt();move.owner='idle';job=agent.plan();const late=agent.routePlanner.deliver;agent.dispose();late();await job;assert.equal(agent.goal,null,'disposed controller cannot move');
 delete global.PetRoutePlanner;delete global.Worker;
 console.log('PASS background route parity, cache invalidation, main-thread responsiveness, cancellation, user priority, stale scene/position/grid and disposal');
})().catch(e=>{console.error(e);process.exit(1)});
