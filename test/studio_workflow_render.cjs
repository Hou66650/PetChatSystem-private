/* Isolated file fixture: real generated GLBs, mocked API, no paid requests. */
const {app,BrowserWindow}=require('electron'),fs=require('fs'),path=require('path'),os=require('os'),assert=require('assert'),{pathToFileURL}=require('url');
const root=path.resolve(__dirname,'..'),temp=fs.mkdtempSync(path.join(os.tmpdir(),'pait-cloud-workflow-'));
const result=path.join(root,'uploads/hunyuan-test-cat-20261015/paid-check-20261015/workflow-e2e');
assert(fs.existsSync(path.join(result,'adapted.glb')),'Run test_pet_generation live-query test first');
app.setPath('userData',path.join(temp,'profile'));app.disableHardwareAcceleration();
const file=p=>pathToFileURL(path.resolve(root,p)).href;
let body=fs.readFileSync(path.join(root,'templates/pet-studio.html'),'utf8').split('{% block body %}')[1].split('{% endblock %}')[0];
const row={id:'testcat',name:'云端测试橘猫',mode:'companion',status:'draft',notes:'',assets:['front','left','back'],updated:1};
const setup=`window.PET_STUDIO_SCOPE='test';window.row=${JSON.stringify(row)};window.calls=[];window.nativeFetch=fetch;
 window.fetch=async(url,options={})=>{if(url.startsWith('blob:'))return nativeFetch(url);if(url.includes('/assets/')){const name=url.split('/assets/')[1].split('?')[0];return nativeFetch(name==='adapted'?${JSON.stringify(file(path.join(result,'adapted.glb')))}:name==='model'?${JSON.stringify(file(path.join(result,'model.glb')))}:${JSON.stringify(file('uploads/hunyuan-test-cat-20261015/front.png'))});}
 if(options.method==='POST'){const op=url.split('/').pop();calls.push({op,body:JSON.parse(options.body)});
 if(op==='generate')row.generation={status:'running',message:'云端生成中'};
 if(op==='approve')row.status='approved';
 if(op==='adapt'){row.adaptation={id:'job',status:'review_motion',report:{warnings:['模板草稿需要人工核对']}};row.assets.push('adapted','blend');}
 if(op==='review-motion')row.adaptation.status='reviewed';if(op==='equip')row.equipped=true;if(op==='unequip')row.equipped=false;}
 return new Response(JSON.stringify({tasks:[row],scope:'test',generationAvailable:true}),{headers:{'Content-Type':'application/json'}});};`;
let js=fs.readFileSync(path.join(root,'static/js/pet-studio.js'),'utf8').replace('renderer.render(scene,camera);','renderer.render(scene,camera);window.__previewCheck={draws:renderer.info.render.calls,triangles:renderer.info.render.triangles,action:activeAction?.getClip().name};');
fs.writeFileSync(path.join(temp,'studio.js'),js);
fs.writeFileSync(path.join(temp,'index.html'),`<meta charset="utf-8"><style>body{margin:0;font-family:Arial,sans-serif}</style><link rel="stylesheet" href="${file('static/css/pet-studio.css')}">${body}<script>${setup}</script><link rel="stylesheet" href="${file('static/css/glass-loading.css')}"><script src="${file('static/js/glass-loading.js')}"></script><script src="${file('static/js/vendor/three.min.js')}"></script><script src="${file('static/js/vendor/GLTFLoader.js')}"></script><script src="${file('static/js/vendor/OrbitControls.js')}"></script><script src="${file('static/js/den/pet-model-bounds.js')}"></script><script src="studio.js"></script>`);
app.whenReady().then(async()=>{const w=new BrowserWindow({show:false,width:1260,height:1000,webPreferences:{offscreen:true,sandbox:true}});const errors=[];w.webContents.on('console-message',(_,level,message)=>{if(level===3&&!message.includes('Failed to load resource'))errors.push(message);});
const run=s=>w.webContents.executeJavaScript(s),wait=async(test)=>{for(let n=0;n<150;n++){if(await run(test))return;await new Promise(r=>setTimeout(r,100));}throw Error('Timed out: '+test);};
try{
 await w.loadFile(path.join(temp,'index.html'));await wait(`document.querySelectorAll('.studio-photo').length===5`);
 await run(`document.getElementById('studio-generate').click()`);assert.equal(await run('calls.length'),0);
 await run(`document.getElementById('studio-cloud-consent').checked=true;document.getElementById('studio-generate').click()`);
 await wait(`calls.length===1 && document.getElementById('studio-generate').disabled`);
 assert(await run(`PaitLoading.activeCount()>0`));assert(await run(`calls[0].body.consent===true`));
 await run(`row.generation={status:'done',message:'生成完成',credits:50};row.status='review';row.assets.push('model');document.getElementById('studio-save').click()`);
 await wait(`window.__previewCheck?.triangles>90000`);
 await run(`document.getElementById('studio-approve').click()`);await wait(`row.status==='approved'&&!document.getElementById('studio-adapt-start').disabled`);
 assert.equal(await run(`document.getElementById('studio-adapt-mode').value`),'template-skin');
 await run(`document.getElementById('studio-adapt-start').click()`);await wait(`document.querySelectorAll('#studio-motion-buttons button').length===12`);
 for(const name of ['走路','跑动','坐下','睡觉','吃饭']){await run(`[...document.querySelectorAll('#studio-motion-buttons button')].find(b=>b.textContent===${JSON.stringify(name)}).click()`);await new Promise(r=>setTimeout(r,300));assert(await run(`__previewCheck.draws>0`));}
 await run(`document.getElementById('studio-motion-accept').click()`);assert(await run(`document.getElementById('studio-message').textContent.includes('8 项')`));
 await run(`document.querySelectorAll('#studio-motion-checks input').forEach(c=>c.checked=true);document.getElementById('studio-motion-accept').click()`);
 await wait(`!document.getElementById('studio-equip-controls').hidden`);await run(`document.getElementById('studio-equip').click()`);await wait(`row.equipped===true`);
 await wait(`document.querySelectorAll('#studio-motion-buttons button').length===12`);
 await run(`document.querySelector('#studio-motion-buttons button').click();document.getElementById('studio-preview-wrap').scrollIntoView()`);await new Promise(r=>setTimeout(r,600));
 fs.writeFileSync(path.join(result,'studio-desktop.png'),(await w.webContents.capturePage()).toPNG());
 w.setContentSize(390,844);await new Promise(r=>setTimeout(r,500));assert(await run(`document.documentElement.scrollWidth<=innerWidth`));
 fs.writeFileSync(path.join(result,'studio-mobile.png'),(await w.webContents.capturePage()).toPNG());
 // A failed unrigged cloud model must not revert to compatible-rig mode.
 await run(`row.adaptation={id:'failed-rig',status:'needs_manual',report:{mode:'auto',error:'未发现骨骼：请选择模板蒙皮'}};row.assets=['front'];document.getElementById('studio-save').click()`);
 await wait(`document.getElementById('studio-adapt-status').textContent.includes('不需要重新云端生成')`);
 assert.equal(await run(`document.getElementById('studio-adapt-mode').value`),'template-skin');
 await run(`document.getElementById('studio-adapt-mode').value='auto';document.getElementById('studio-adapt-mode').dispatchEvent(new Event('change'));document.getElementById('studio-save').click()`);
 await new Promise(r=>setTimeout(r,150));assert.equal(await run(`document.getElementById('studio-adapt-mode').value`),'auto','explicit user choice survives repaint');
 await run(`row.id='other-cat';row.generation=null;row.adaptation={status:'needs_manual',report:{mode:'template-skin'}};document.getElementById('studio-save').click()`);
 await new Promise(r=>setTimeout(r,150));assert.equal(await run(`document.getElementById('studio-adapt-mode').value`),'template-skin','choice cannot leak between cats');
 assert.deepEqual(errors,[]);console.log('PASS: consent, paid-click guard, glass progress, real GLB rendering, 12 action controls, review gate, equip, mobile bounds');app.exit(0);
}catch(e){console.error(e,errors);app.exit(1);}});
