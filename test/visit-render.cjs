/* Isolated local-file fixture: no network, account, or existing browser access. */
const {app,BrowserWindow,ipcMain}=require('electron'),fs=require('node:fs'),path=require('node:path'),os=require('node:os'),{pathToFileURL}=require('node:url');
const root=path.resolve(__dirname,'..'),folder=fs.mkdtempSync(path.join(os.tmpdir(),'pait-visit-test-')),assets=new Set();let samples=0,snapshot={},firstSnapshot=null,moved=false,window;
app.setPath('userData',path.join(folder,'profile'));
const data={id:'fixture',pet:'2',mine:true,status:'active',kind:'neighbor',created:Date.now()/1000,petSpec:{id:'2',name:'哈士奇',height:1.05,model:'/static/models/petchat-husky-v3/xueqiu.glb'},hostPet:{id:'3',name:'猫咪',height:.85,theme:'room',model:'/static/models/petchat-cat-v2/cat.glb',stage:'/static/models/petchat-mistwood-v1/mistwood.glb'},messages:[],snapshot};
ipcMain.handle('fixture',(_e,url,body)=>{
 if(url.startsWith('/static/')){const p=path.resolve(root,'.'+url);if(!p.startsWith(path.join(root,'static')+path.sep)||!p.endsWith('.glb'))throw Error('Unexpected asset');assets.add(url);const b=fs.readFileSync(p);return b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength);}
 if(url.endsWith('/sample')){samples++;snapshot=body.snapshot;if(!firstSnapshot)firstSnapshot=JSON.parse(JSON.stringify(snapshot));else moved ||= Math.hypot(snapshot.visitor.x-firstSnapshot.visitor.x,snapshot.visitor.z-firstSnapshot.visitor.z)>.05||Math.hypot(snapshot.host.x-firstSnapshot.host.x,snapshot.host.z-firstSnapshot.host.z)>.05;return {ok:true};}
 if(url.endsWith('/plan'))return {visitor:'wander',host:'wander',source:'local'};
 return {...data,snapshot};
});
app.whenReady().then(()=>{
 let html=fs.readFileSync(path.join(root,'templates/portal-visit.html'),'utf8').replace(/\?v={{ app_version }}/g,'').replace(/window.VISIT={{[\s\S]*?}};/,'window.VISIT={trip:"fixture",scope:"fixture"};').replace(/(["'])\/static\//g,(_,q)=>q+pathToFileURL(path.join(root,'static')).href+'/');
 const bootstrap=`<script>const originalFetch=fetch.bind(window);window.fetch=async(url,options)=>{if(typeof url!=='string'||!url.startsWith('/'))return originalFetch(url,options);const d=await visitFixture.request(url,options?.body?JSON.parse(options.body):undefined);return {ok:true,json:async()=>d,arrayBuffer:async()=>d};};</script>`;
 html=html.replace('<script src=',bootstrap+'<script src=');fs.writeFileSync(path.join(folder,'visit.html'),html);
 window=new BrowserWindow({width:1200,height:800,show:false,webPreferences:{preload:path.join(__dirname,'visit-preload.cjs'),contextIsolation:true,nodeIntegration:false,sandbox:true,backgroundThrottling:false,offscreen:true}});
 window.webContents.setFrameRate(30);window.webContents.on('console-message',(_e,level,message)=>{if(level>=2)console.log('renderer',message);});window.loadFile(path.join(folder,'visit.html'));
 const start=Date.now(),timer=setInterval(async()=>{if(samples>=6&&moved){clearInterval(timer);try{if(assets.size!==3||!snapshot.visitor||!snapshot.host)throw Error('Incorrect selected-asset or pet state count');const out=path.join(os.tmpdir(),'pait-visit-render.png');fs.writeFileSync(out,(await window.webContents.capturePage()).toPNG());console.log('PASS real two-pet visit render',JSON.stringify({samples,assets:[...assets],snapshot}),out);app.exit(0);}catch(e){console.error(e);app.exit(1);}}else if(Date.now()-start>45000){console.error('Visit renderer timed out',JSON.stringify({samples,snapshot,firstSnapshot}),await window.webContents.executeJavaScript('document.getElementById("visit-status").textContent'));app.exit(1);}},1000);
});
