/* Real Electron/WebGL rendering smoke test, isolated from user browser sessions. */
const {app,BrowserWindow,ipcMain}=require('electron');
const fs=require('node:fs'),path=require('node:path'),os=require('node:os');
const out=path.join(os.tmpdir(),'pait-desktop-render.png');let window,timer;
app.setPath('userData',path.join(os.tmpdir(),'pait-desktop-render-profile'));
const spec={id:'3',name:'猫咪',height:.85};
ipcMain.handle('desktop:command',async(e,command)=>{
 console.log('IPC',command);
 if(command==='state')return {connected:true,action:'walk',pet:spec};
 if(command==='model'){const b=fs.readFileSync(path.join(__dirname,'../static/models/petchat-cat-v2/cat.glb'));return {bytes:b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength),pet:spec};}
 if(command==='ready'){setTimeout(async()=>{try{
  const stats=await window.webContents.executeJavaScript('JSON.stringify({calls:renderer.info.render.calls,triangles:renderer.info.render.triangles,animation:pet.action,clip:pet.active?.getClip().name,bones:pet.model.getObjectByProperty("isBone",true)!==undefined})');
  const d=JSON.parse(stats);if(!d.calls||!d.triangles||!d.bones)throw Error('No animated pet rendered');
  await window.webContents.executeJavaScript(fs.readFileSync(path.join(__dirname,'../static/js/den/portals.js'),'utf8'));
  const consent=await window.webContents.executeJavaScript(`(async()=>{
    const calls=[],body={scope:'test',userId:'1',islands:[{pet:'3',allow_visitors:0}],friends:[{id:'island-private-key',userId:'2',allow:true,petSpec:{name:'柴犬'}}],trips:[],rewards:[]};
    let generation=0;
    globalThis.fetch=async(url,options)=>{if(options?.method==='POST'){calls.push({url,body:JSON.parse(options.body)});if(url.endsWith('/depart')){generation++;const id='test-trip-'+generation;body.trips=[{id,pet:'3',mine:true,status:'pairing',kind:'desktop'}];return {ok:true,json:async()=>({trip:id,code:'one-time-test-code-'+generation})};}if(url.endsWith('/return'))body.trips=[];return {ok:true,json:async()=>({ok:true})};}return {ok:true,json:async()=>body};};
    const model=new THREE.Group();model.position.set(2.3,0,-.75);
    const c=new PetPortals.Controller({THREE,scene,scope:'test',getPet:()=>({id:3,model}),onApproach:()=>{},onReject:()=>{},onArrive:()=>{},onReturn:()=>{},bubble:()=>{}});
    c.attach({nearest:p=>({...p})},'room');await new Promise(r=>setTimeout(r,20));c.curious('desktop');c.update(.05);c.open('desktop');
    if(calls.length)throw Error('Curiosity must never authorize travel');
    c.choose('neighbor');if(!c.q('[data-friends]').textContent.includes('好友 ID 2')||!c.q('[data-my-id]').textContent.includes('1')||c.q('[data-friends]').textContent.includes('island-private-key'))throw Error('Friend IDs are not shown correctly');c.choose('desktop');
    await c.depart();if(calls.length!==1||calls[0].body.confirmed!==true||!c.q('[data-pair] code'))throw Error('Explicit confirmation did not create pairing UI');
    c.choose('desktop');c.update(.05);if(!c.q('[data-pair] code')||c.q('[data-reissue]').hidden||c.q('[data-confirm]').textContent!=='等待桌面配对')throw Error('Reopening lost pairing code or recovery controls');
    await c.depart();if(calls.length!==1)throw Error('Duplicate departure sent');
    c.pairCodes.clear();c.renderJourney();if(c.q('[data-pair] code')||!c.q('[data-pair]').textContent.includes('重新生成'))throw Error('Reloaded pending journey lacks recovery instructions');
    await c.reissue();if(generation!==2||c.q('[data-pair] code')?.textContent!=='one-time-test-code-2')throw Error('Regeneration failed');
    await c.recallPet();c.choose('desktop');if(c.q('[data-confirm]').disabled)throw Error('Cancelled pairing still blocks confirmation');
    const before=calls.length;c.q('[data-decline]').click();if(calls.length!==before)throw Error('Rejection created travel');
    c.choose('desktop');await c.depart();body.trips=[];await c.poll();if(c.q('[data-confirm]').disabled||c.q('[data-pair] code'))throw Error('Expired pairing did not unlock confirmation');
    clearInterval(c.timer);c.view.dispose();c.root.remove();c.recall.remove();return 'PASS actual portal DOM: curiosity waits, explicit confirmation pairs, rejection never departs; reopen, reload recovery, regeneration, cancellation and expiry';
  })()`);
  console.log(consent);
  fs.writeFileSync(out,(await window.webContents.capturePage()).toPNG());console.log('PASS actual Electron transparent 3D render',stats,'preview',out);clearTimeout(timer);app.exit(0);
 }catch(error){console.error(error);app.exit(1);}},1800);return {ok:true};}
 return {ok:true};
});
app.whenReady().then(()=>{window=new BrowserWindow({width:280,height:300,show:false,transparent:true,frame:false,backgroundColor:'#00000000',webPreferences:{preload:path.join(__dirname,'../desktop/preload.js'),contextIsolation:true,nodeIntegration:false,sandbox:true,backgroundThrottling:false}});window.webContents.on('console-message',(_e,...args)=>console.log('renderer',...args));window.webContents.on('did-fail-load',(_e,code,text)=>console.error(code,text));window.loadFile(path.join(__dirname,'../desktop/pet.html'));timer=setTimeout(()=>{console.error('Desktop renderer timed out');app.exit(1);},30000);});
