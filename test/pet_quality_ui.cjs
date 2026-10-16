/* Isolated studio UI: public checkboxes cannot unlock production quality gates. */
const fs=require('node:fs'),path=require('node:path'),http=require('node:http'),os=require('node:os'),assert=require('node:assert/strict');
const {chromium}=require('playwright');
const root=path.resolve(__dirname,'..');
const row={id:'fixture',name:'质量测试猫',mode:'companion',status:'review',notes:'',assets:['front'],quality:{},updated:1};
const body=fs.readFileSync(path.join(root,'templates/pet-studio.html'),'utf8').split('{% block body %}')[1].split('{% endblock %}')[0];
const html=`<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="/static/css/pet-studio.css">${body}<script>window.PET_STUDIO_SCOPE='test'</script><script src="/static/js/pet-studio.js"></script>`;
const server=http.createServer((req,res)=>{
 if(req.url.startsWith('/api/pet-studio')&&!req.url.includes('/assets/')){res.setHeader('Content-Type','application/json');return res.end(JSON.stringify({tasks:[row],scope:'test',generationAvailable:true}));}
 if(req.url==='/'){res.setHeader('Content-Type','text/html; charset=utf-8');return res.end(html);}
 const file=path.resolve(root,'.'+req.url.split('?')[0]);
 if(file.startsWith(root+path.sep)&&fs.existsSync(file)&&fs.statSync(file).isFile())return res.end(fs.readFileSync(file));
 res.statusCode=404;res.end();
});
(async()=>{let browser;try{
 await new Promise(r=>server.listen(0,'127.0.0.1',r));
 browser=await chromium.launch({headless:true,executablePath:process.env.PET_TEST_CHROME||'C:/Program Files/Google/Chrome/Application/chrome.exe'});
 const page=await browser.newPage({viewport:{width:1280,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto(`http://127.0.0.1:${server.address().port}`);await page.waitForSelector('#studio-quality li');
 assert(await page.locator('#studio-generate').isDisabled());assert(await page.locator('#studio-approve').isDisabled());
 async function refresh(){await page.locator('#studio-save').click();await page.waitForFunction(()=>!document.querySelector('#studio-save').disabled);}
 row.quality.inputs={status:'pass'};await refresh();assert(!(await page.locator('#studio-generate').isDisabled()));
 row.quality.geometry={status:'fail',reason:'疑似重复尾巴'};await refresh();assert(await page.locator('#studio-approve').isDisabled());
 assert((await page.locator('#studio-quality').innerText()).includes('疑似重复尾巴'));
 row.quality.geometry={status:'pass'};row.status='approved';row.adaptation={id:'job',status:'review_motion',report:{}};await refresh();
 for(const input of await page.locator('#studio-motion-checks input').all())await input.check();
 assert(await page.locator('#studio-motion-accept').isDisabled());
 row.quality.rig={status:'pass'};row.quality.motion={status:'pass'};await refresh();
 assert(!(await page.locator('#studio-motion-accept').isDisabled()));
 row.quality.motion={status:'unknown',reason:'重新绑定后需复核'};await refresh();assert(await page.locator('#studio-motion-accept').isDisabled());
 await page.setViewportSize({width:390,height:844});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
 const out=fs.mkdtempSync(path.join(os.tmpdir(),'pet-quality-ui-'));await page.screenshot({path:path.join(out,'mobile.png'),fullPage:true});
 assert.deepEqual(errors,[]);console.log('PASS quality gating, busy reset, all-checkbox bypass, stale status, mobile layout:',out);
 }finally{await browser?.close();server.close();}})().catch(e=>{console.error(e);process.exitCode=1;});
