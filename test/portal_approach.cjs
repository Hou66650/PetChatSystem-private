// Run the real page callbacks and movement loop with a deterministic clock (no browser/account).
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const DialogueActions=require('../static/js/den/dialogue-actions');
const {Controller:Locomotion}=require('../static/js/den/pet-locomotion');
const {Navigation}=require('../static/js/den/scene-navigation');
const layout=require('../static/js/den/mistwood-layout');
const html=fs.readFileSync('templates/den.html','utf8');
function between(a,b){const start=html.indexOf(a);assert(start>=0,a);const end=html.indexOf(b,start);assert(end>start,b);return html.slice(start,end);}
function setup({state='idle',chat=false,enabled=true,held=false}={}){
 let now=0,waiters=[],transition=null,cancelled=0,requests=0;
 const elements=new Map(),el=key=>{if(!elements.has(key))elements.set(key,{hidden:true,open:false,textContent:'',replaceChildren(){},classList:{contains:()=>!chat}});return elements.get(key);};
 const context={console,performance:{now:()=>now},DialogueActions,clearTimeout(){},setTimeout(){},
  document:{hidden:false,querySelector:()=>null,querySelectorAll:()=>[],getElementsByClassName:()=>[],getElementById:el},window:{},
  petModel:{position:{x:0,y:0,z:2},rotation:{y:0}},spawnBusy:false,grabbed:false,dropping:false,bounceBack:0,
  anim:{state,birth:1,until:0,lastInteract:0},actionTransition:null,actions:{standUp:{}},
  catAgent:{acting:false,interrupt(){cancelled++;}},catLife:{cancel(){}},
  toyWorkshop:{held:held?{state:'held'}:null,cancel(){this.held=null;}},facePlay:{reset(){}},supplyCare:null,farmGarden:null,
  chatBusy:chat,voiceBusy:false,breathActive:false,gameOverlay:{hidden:true},gamesMask:{hidden:true},moodMask:{hidden:true},
  interactionBusy:()=>false,performing:()=>false,finishSupplyCare(){context.supplyCare=null;},updateRoamingButton(){},
  actionLabels:{},expressiveKeys:{},chainTimer:null,performingUntil:0,
  delay:()=>new Promise(resolve=>waiters.push(resolve)),playAction(){},playSleep(){},
  playOnceThen(key,next){context.actionTransition={};transition={end:now+900,next};},
 };
 context.locomotion=new Locomotion({navigation:new Navigation({...layout,bodyRadius:.3}),model:context.petModel,speed:.34,animate(key){context.anim.state=key;context.anim.until=0;},rest(){context.anim.state='idle';}});
 context.locomotion.enabled=enabled;context.locomotion.autonomous=false;
 vm.createContext(context);vm.runInContext(fs.readFileSync('static/js/den/portals.js','utf8'),context);
 const portals=Object.create(context.PetPortals.Controller.prototype);
 Object.assign(portals,{getPet:()=>({id:3,model:context.petModel}),root:{open:true},q:el,render(){},onArrive(){context.setAnim('wave',1800);},bubble(){},api:async()=>{requests++;return {};}});
 portals.view={positions:{desktop:context.locomotion.navigation.nearest({x:2.3,z:-.75}),neighbor:context.locomotion.navigation.nearest({x:4.6,z:-.75})},update(){}};
 context.portals=portals;
 vm.runInContext(between('        function setAnim(state, dur) {','        // ---------- 流畅动画链')+
  between('        function movementBlocked() {','        portalVisitors=new')+
  between('        async function actionWait(','        const actingDialog=')
    .replace("        document.getElementById('btn-action-stop').onclick=()=>{dialogueRunner.cancel('已停止');endDialogueHold();if(petModel)setAnim('idle',0);};",'')
    .replace('        const dialogueRunner=', '        let dialogueHeld=false,dialogueRestoreRoam=true; const dialogueRunner=')+
  '\nglobalThis.runner=dialogueRunner;',context);
 context.approach=vm.runInContext('('+between('            onApproach:async','            onArrive:').trim().replace(/^onApproach:/,'').replace(/,$/, '')+')',context);
 portals.onApproach=context.approach;
 async function tick(){now+=50;if(transition&&now>=transition.end){const t=transition;transition=null;context.actionTransition=null;t.next();}
  if(context.anim.until&&now>=context.anim.until)context.setAnim('idle',0);
  context.locomotion.update(.05,context.movementBlocked());portals.update(.05);
  const ready=waiters;waiters=[];for(const resolve of ready)resolve();await new Promise(r=>setImmediate(r));
 }
 async function settle(promise){let done=false;promise.finally(()=>done=true);for(let i=0;i<1600&&!done;i++)await tick();assert(done,'approach must settle');await promise;}
 return{context,portals,el,tick,settle,requests:()=>requests,cancelled:()=>cancelled};
}
(async()=>{
 // Old code starts a route while standing up, then movementBlocked discards it.
 const old=setup({state:'sit'});old.context.setAnim('idle',0);old.context.locomotion.goTo(old.portals.view.positions.desktop);await old.tick();
 assert.equal(old.context.locomotion.path.length,0,'reproduce lost route during stand-up');assert(!old.portals.holding);
 for(const state of ['idle','sit','sleep'])for(const kind of ['desktop','neighbor']){
  const x=setup({state,chat:true,enabled:false,held:true});
  const work=x.portals.choose(kind);assert(x.el('[data-confirm]').disabled,'no departure while approaching');
  if(state!=='idle'){await x.tick();assert.equal(x.context.locomotion.path.length,0,'wait for standing before route creation');}
  await x.settle(work);
  assert(x.portals.holding,`${state} reaches ${kind}`);assert(!x.portals.approachError,x.el('[data-status]').textContent);
  assert(!x.el('[data-confirm]').disabled);assert.match(x.el('[data-status]').textContent,/已到门口/);
  assert.equal(x.context.locomotion.enabled,false,'restore paused roaming');assert.equal(x.context.toyWorkshop.held,null);
  assert.equal(x.requests(),0,'approaching never authorizes travel');assert(x.cancelled()>0);
 }
 const swap=setup({state:'sleep'}),first=swap.portals.choose('desktop');await swap.tick();
 const second=swap.portals.choose('neighbor');await swap.settle(Promise.all([first,second]));
 assert.equal(swap.portals.intent,'neighbor');assert(swap.portals.holding);assert(!swap.portals.approachError,'stale callback cannot overwrite new destination');
 const blocked=setup();blocked.context.locomotion.navigation.route=()=>null;await blocked.settle(blocked.portals.choose('desktop'));
 assert(blocked.portals.approachError);assert.match(blocked.el('[data-status]').textContent,/安全路线/);assert(blocked.el('[data-confirm]').disabled);
 const interrupted=setup(),work=interrupted.portals.choose('desktop');await interrupted.tick();interrupted.context.runner.cancel('已停止');await interrupted.settle(work);
 assert(interrupted.portals.approachError);assert.equal(interrupted.context.locomotion.path.length,0);assert.equal(interrupted.requests(),0);
 const busy=setup();busy.context.grabbed=true;await busy.settle(busy.portals.choose('desktop'));assert.match(busy.el('[data-status]').textContent,/结束当前互动/);
 const loading=setup();loading.portals.view=null;await loading.settle(loading.portals.choose('desktop'));assert.match(loading.el('[data-status]').textContent,/还在加载/);
 assert(!DialogueActions.allowed.has('portal_desktop'),'portal UI commands stay out of default AI vocabulary');
 console.log('PASS portal approach: old stand-up route loss reproduced; both doors from idle/sit/sleep with chat, held toy and roaming paused; cancellation, target switch, blocked route, loading, no automatic departure');
})().catch(e=>{console.error(e);process.exitCode=1;});
