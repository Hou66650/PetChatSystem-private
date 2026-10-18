/* Called inside the real Electron transfer test, never against a user database. */
const assert=require('node:assert/strict'),path=require('node:path');
module.exports=async function(control,petPage,output){
 const A=require('../desktop/actions'),errors=[];petPage.on('pageerror',e=>errors.push(e.message));
 await control.locator('#autonomous').uncheck();
 const state=await control.evaluate(()=>paitDesktop.command('state'));assert.equal(state.actions.length,25);
 assert((await control.evaluate(()=>paitDesktop.command('pose',{}))).error,'control cannot spoof standing pose');
 assert((await control.evaluate(()=>paitDesktop.command('action',{id:'unknown'}))).error);
 const observed=[];
 for(const a of A.catalog.filter(a=>a.id!=='walk')){
  await control.locator('#action-select').selectOption(a.id);await control.locator('#action-play').click();
  await petPage.waitForFunction(id=>animator.intent===id&&animator.phase===id&&!animator.blend,a.id,{timeout:10000});
  const result=await petPage.evaluate(()=>({intent:animator.intent,clip:animator.active.getClip().name,calls:renderer.info.render.calls,weights:[...animator.weights.values()]}));
  assert(A.find([{name:result.clip}],a.clips));assert(result.calls>0);assert(Math.abs(result.weights.reduce((a,b)=>a+b,0)-1)<1e-5);
  observed.push(result);
  if(['sleep','sit','bow','wave','affection'].includes(a.id)){await petPage.waitForFunction(()=>animator.clock>=animator.active.getClip().duration*.5);await petPage.screenshot({path:path.join(output,'action-'+a.id+'.png')});}
 }
 await control.locator('#action-select').selectOption('sleep');await control.locator('#action-play').click();
 await petPage.waitForFunction(()=>animator.phase==='sleep'&&!animator.blend);
 await control.locator('#action-select').selectOption('walk');await control.locator('#action-play').click();
 await petPage.waitForFunction(()=>animator.phase==='stand_up');
 const xy=await petPage.evaluate(()=>({x:window.screenX,y:window.screenY}));await petPage.waitForTimeout(200);
 assert.deepEqual(await petPage.evaluate(()=>({x:window.screenX,y:window.screenY})),xy,'window stays still while rising');
 await petPage.waitForFunction(()=>animator.locomotionReady);await petPage.waitForFunction(p=>Math.hypot(screenX-p.x,screenY-p.y)>10,xy);
 const performance=await petPage.evaluate(()=>new Promise(resolve=>{const times=[],start=performance.now(),first=renderedFrames;let last=start,frame=first;function sample(now){if(frame!==renderedFrames){times.push(now-last);last=now;frame=renderedFrames;}if(now-start<2500)requestAnimationFrame(sample);else{const sorted=times.slice(1).sort((a,b)=>a-b);resolve({fps:Math.round((renderedFrames-first)*1000/(now-start)),p95FrameMs:sorted[Math.floor(sorted.length*.95)],samples:times.length,clip:animator.active.getClip().name});}}requestAnimationFrame(sample);}));
 assert(performance.fps<=62,'render loop must respect the 60 FPS budget');

 await control.locator('#action-select').selectOption('idle');await control.locator('#action-play').click();
 assert.deepEqual(errors,[]);console.log(JSON.stringify({desktopActions:observed.length+1,performance,output}));
};
