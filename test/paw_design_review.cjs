// Run scripts/review_paw_commons.py first. Uses only isolated design assets.
const {chromium}=require('playwright'),assert=require('node:assert/strict'),fs=require('node:fs');
(async()=>{
const browser=await chromium.launch({headless:true,executablePath:process.env.PET_TEST_CHROME||'C:/Program Files/Google/Chrome/Application/chrome.exe',args:['--enable-webgl','--ignore-gpu-blocklist']});
try{
const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
await page.goto('http://127.0.0.1:5089/art/paw-commons-v2/index.html');
await page.locator('#load').click();await page.waitForFunction(()=>!!window.reviewModel,null,{timeout:120000});
const data=await page.evaluate(()=>{let triangles=0,meshes=0,finite=true;reviewModel.updateMatrixWorld(true);reviewModel.traverse(o=>{if(!o.isMesh)return;meshes++;const a=o.geometry.attributes.position.array;for(const n of a)finite=finite&&Number.isFinite(n);triangles+=(o.geometry.index?.count||a.length/3)/3;});const b=new THREE.Box3().setFromObject(reviewModel);return {triangles,meshes,finite,min:b.min.toArray(),max:b.max.toArray()}});
assert(data.finite);assert(data.triangles>300000&&data.triangles<4000000);assert(data.min[1]<-4.5);assert(data.max[1]>4);assert(data.max[0]-data.min[0]<33);
assert(await page.evaluate(()=>Array.from(document.images).every(i=>i.complete&&i.naturalWidth>0)));
await page.locator('#viewer').screenshot({path:'uploads/park-review/design-viewer.png'});
await page.locator('img[src$="03-dimensions.svg"]').screenshot({path:'uploads/park-review/dimensions.png'});
await page.setViewportSize({width:390,height:844});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
assert.equal((await page.request.get('http://127.0.0.1:5089/.env')).status(),404);
assert.equal((await page.request.get('http://127.0.0.1:5089/art/paw-commons-v2/')).status(),200); // index only
assert.deepEqual(errors,[]);
fs.writeFileSync('art/paw-commons-v2/review/browser-validation.json',JSON.stringify({status:'pass',...data,checks:['real GLB browser load','finite vertices','model bounds','all review images loaded','narrow layout','private path denied'],notTested:['HarmonyOS frame rate','multiplayer play','physical facility interaction']},null,2));
console.log('PASS detailed model browser and review:',data);
}finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
