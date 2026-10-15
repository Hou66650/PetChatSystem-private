const {app,BrowserWindow}=require('electron'),fs=require('node:fs'),path=require('node:path'),os=require('node:os'),{pathToFileURL}=require('node:url'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..'),temp=fs.mkdtempSync(path.join(os.tmpdir(),'cat-scene-monitor-'));app.setPath('userData',path.join(temp,'profile'));
let html=fs.readFileSync(path.join(root,'templates/cat-agent-monitor.html'),'utf8').replaceAll('{{ app_version }}','test').replace('{{ scope|tojson }}','"fixture"').replace(/(?:src|href)="(\/static\/[^"?]+)(?:\?[^\"]*)?"/g,(m,p)=>m.split('=')[0]+'="'+pathToFileURL(path.join(root,p)).href+'"');
const world={revision:'garden-new',asOf:100,beds:Array.from({length:8},(_,i)=>({name:'种植床'+(i+1),plant:i%2?null:{name:'波斯菊',stageName:'花苞初生',stage:7,wateredToday:true}})),decorations:[{place:'温室花盆',plant:'波斯菊'}],recentChanges:[{created:100,summary:'主人给波斯菊浇了水'}]};
const snap={phase:'walking',text:'想去种植园观察花苞',reason:'留意种植园变化',energy:.8,hunger:.2,pathLength:1,x:0,z:0,target:'farm_path',action:'observe',candidates:['farm_path'],route:[[1,1]],trail:[[0,0,100],[.5,0,500]],enabled:true};
const data={scope:'fixture',serverTime:100,streams:[{stream:'cat-one',updated:100,snapshot:snap},{stream:'cat-two',updated:100,snapshot:snap}],catalog:JSON.parse(fs.readFileSync(path.join(root,'static/data/cat-world.json'),'utf8')),events:[],memory:[],scene:{current:world,used:{'cat-one':{...world,revision:'garden-old'}},experiences:[{created:98,summary:'猫咪完成种植园观察；出发时场景记录：波斯菊（花苞初生）'}],decisions:[{stream:'cat-one',created:100,modelUsed:true,inputs:{scene:world},result:{source:'model',target:'farm_path',action:'observe'}}]}};
html=html.replace('<body>','<body><script>window.fixture='+JSON.stringify(data)+';window.fetch=async()=>({ok:true,json:async()=>fixture});</script>');fs.writeFileSync(path.join(temp,'index.html'),html);
app.whenReady().then(async()=>{
 const w=new BrowserWindow({show:false,width:1280,height:1100,webPreferences:{offscreen:true,backgroundThrottling:false,sandbox:true}}),errors=[];
 w.webContents.on('console-message',(_e,level,message)=>{if(level>=3)errors.push(message);});
 const run=s=>w.webContents.executeJavaScript(s),pause=ms=>new Promise(r=>setTimeout(r,ms));
 try{
  await w.loadFile(path.join(temp,'index.html'));await pause(200);
  assert(await run(`document.getElementById('scene-received').textContent.includes('后续选择')`));
  assert.equal(await run(`document.querySelectorAll('#scene-beds li').length`),9);
  assert(await run(`document.getElementById('scene-model-input').textContent.includes('garden-new')`));
  assert(await run(`document.getElementById('scene-experiences').textContent.includes('完成种植园观察')`));
  await run(`document.querySelector('.scene-context').scrollIntoView()`);await pause(100);
  fs.writeFileSync(path.join(os.tmpdir(),'pait-scene-monitor-desktop.png'),(await w.webContents.capturePage()).toPNG());
  w.setContentSize(390,844);await pause(100);
  assert(await run(`document.querySelector('.scene-context').scrollWidth<=document.querySelector('.scene-context').clientWidth+1`),'scene card fits mobile');
  fs.writeFileSync(path.join(os.tmpdir(),'pait-scene-monitor-mobile.png'),(await w.webContents.capturePage()).toPNG());
  await run(`document.getElementById('streams').value='cat-two';document.getElementById('streams').dispatchEvent(new Event('change'))`);
  assert(await run(`document.getElementById('scene-received').textContent.includes('尚未收到')`));
  assert.equal(await run(`document.getElementById('scene-model-input').textContent`),'');
  await run(`fixture.scope='changed'`);await pause(2200);
  assert(!await run(`document.querySelector('.scene-context').textContent.includes('波斯菊')`),'account change clears private scene data');
  assert.equal(errors.length,0,errors.join('\n'));
  console.log('PASS scene monitor browser: snapshot lag, model payload, completed observations, mobile fit, stream and account isolation');app.exit(0);
 }catch(e){console.error(e);app.exit(1);}
});
