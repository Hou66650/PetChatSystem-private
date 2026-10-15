/* Render a saved test-account den template with local assets and no server access. */
const {app,BrowserWindow,session}=require('electron'),fs=require('fs'),path=require('path'),os=require('os'),assert=require('assert'),{pathToFileURL}=require('url');
const root=path.resolve(__dirname,'..'),temp=fs.mkdtempSync(path.join(os.tmpdir(),'pait-private-island-'));
const result=path.join(root,'uploads/hunyuan-test-cat-20261015/paid-check-20261015/workflow-e2e');
const file=p=>pathToFileURL(path.resolve(root,p)).href;
app.setPath('userData',path.join(temp,'profile'));app.disableHardwareAcceleration();
let html=fs.readFileSync(path.join(result,'den-fixture.html'),'utf8');
const scope=JSON.parse(html.match(/window.COMPANION_SCOPE\s*=\s*("[^"]*")/)[1]);
const coat=JSON.parse(html.match(/let catAppearanceId\s*=\s*("[^"]*")/)[1]);
html=html.replace(/(["'`])(\/(?:static|images|js|css)\/)/g,(_,q,p)=>q+file(p.startsWith('/static/')?p.slice(1):'templates'+p)+'/');
const setup=`window.__fixtureErrors=[];addEventListener('error',e=>{if(e.error)__fixtureErrors.push(e.message)});window.__requested=[];const nativeFetch=window.fetch;
window.fetch=async(url,options)=>{url=String(url);__requested.push(url);if(url.startsWith('file:')||url.startsWith('blob:')||url.startsWith('data:'))return nativeFetch(url,options);
 if(url.includes('/api/pet-studio/')&&url.includes('/assets/adapted'))return nativeFetch(${JSON.stringify(file(path.join(result,'adapted.glb')))},options);
 if(url.startsWith('/api/cat-market'))return new Response(JSON.stringify({scope:${JSON.stringify(scope)},active:'tabby',catalog:[],effectiveAppearance:{id:${JSON.stringify(coat)},custom:true,name:'测试猫',model:'/api/pet-studio/fixture/assets/adapted'}}),{headers:{'Content-Type':'application/json'}});
 return new Response(JSON.stringify({error:'Isolated UI fixture: background services disabled'}),{status:503,headers:{'Content-Type':'application/json'}});};`;
html=html.replace('<head>','<head><script>'+setup+'</script>');
fs.writeFileSync(path.join(temp,'island.html'),html);
app.whenReady().then(async()=>{
 session.defaultSession.webRequest.onBeforeRequest({urls:['http://*/*','https://*/*']},(_,cb)=>cb({cancel:true}));
 const w=new BrowserWindow({show:false,width:1280,height:900,webPreferences:{offscreen:true,sandbox:true}});const run=s=>w.webContents.executeJavaScript(s);
 try{
  await w.loadFile(path.join(temp,'island.html'),{query:{pet:'3'}});
  let state;for(let n=0;n<240;n++){await new Promise(r=>setTimeout(r,250));state=await run(`window.__denLocomotionDebug?.()`);if(state?.petId===3)break;}
  assert(state?.petId===3,JSON.stringify(await run('__fixtureErrors')));assert(state.clips.includes('walk')&&state.clips.includes('run')&&state.clips.includes('sleep'));
  assert(Math.abs(state.originalHeight-.693124)<.002,'Skinned rest bounds must preserve generated model proportions: '+state.originalHeight);
  assert(await run(`__requested.some(u=>u.includes('/api/pet-studio/')&&u.includes('/assets/adapted'))`));
  await run(`document.getElementById('btn-run').click()`);await new Promise(r=>setTimeout(r,1500));
  const after=await run('__denLocomotionDebug()');assert(after.headLook!==false);
  assert.deepEqual(await run('__fixtureErrors'),[]);
  fs.writeFileSync(path.join(result,'island.png'),(await w.webContents.capturePage()).toPNG());
  fs.writeFileSync(path.join(result,'island-render.json'),JSON.stringify({state,after,errors:await run('__fixtureErrors')},null,2));
  console.log('PASS: private GLB in real island template, walk/run/sleep actions, run control, no uncaught JavaScript errors');app.exit(0);
 }catch(e){console.error(e);console.error(await run('__fixtureErrors'));app.exit(1);}
});
