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
    const calls=[],body={scope:'test',islands:[{pet:'3',allow_visitors:0}],friends:[],trips:[],rewards:[]};
    globalThis.fetch=async(url,options)=>{if(options?.method==='POST'){calls.push({url,body:JSON.parse(options.body)});return {ok:true,json:async()=>({trip:'test-trip',code:'one-time-test-code'})};}return {ok:true,json:async()=>body};};
    const model=new THREE.Group();model.position.set(2.3,0,-.75);
    const c=new PetPortals.Controller({THREE,scene,scope:'test',getPet:()=>({id:3,model}),onApproach:()=>{},onReject:()=>{},onArrive:()=>{},onReturn:()=>{},bubble:()=>{}});
    c.attach({nearest:p=>({...p})},'room');await new Promise(r=>setTimeout(r,20));c.curious('desktop');c.update(.05);c.open('desktop');
    if(calls.length)throw Error('Curiosity must never authorize travel');
    await c.depart();if(calls.length!==1||calls[0].body.confirmed!==true||!c.q('[data-pair] code'))throw Error('Explicit confirmation did not create pairing UI');
    c.q('[data-decline]').click();if(calls.length!==1)throw Error('Rejection created travel');
    clearInterval(c.timer);c.view.dispose();c.root.remove();c.recall.remove();return 'PASS actual portal DOM: curiosity waits, explicit confirmation pairs, rejection never departs';
  })()`);
  console.log(consent);
  fs.writeFileSync(out,(await window.webContents.capturePage()).toPNG());console.log('PASS actual Electron transparent 3D render',stats,'preview',out);clearTimeout(timer);app.exit(0);
 }catch(error){console.error(error);app.exit(1);}},1800);return {ok:true};}
 return {ok:true};
});
app.whenReady().then(()=>{window=new BrowserWindow({width:280,height:300,show:false,transparent:true,frame:false,backgroundColor:'#00000000',webPreferences:{preload:path.join(__dirname,'../desktop/preload.js'),contextIsolation:true,nodeIntegration:false,sandbox:true,backgroundThrottling:false}});window.webContents.on('console-message',(_e,...args)=>console.log('renderer',...args));window.webContents.on('did-fail-load',(_e,code,text)=>console.error(code,text));window.loadFile(path.join(__dirname,'../desktop/pet.html'));timer=setTimeout(()=>{console.error('Desktop renderer timed out');app.exit(1);},30000);});
