const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {chromium}=require('playwright');
const root=path.resolve(__dirname,'..'),manifest=JSON.parse(fs.readFileSync(path.join(root,'art/wardrobe-v1/manifest.json')));
for(const item of manifest){
 const raw=fs.readFileSync(path.join(root,item.model));assert.equal(raw.readUInt32LE(0),0x46546c67);
 const g=JSON.parse(raw.subarray(20,20+raw.readUInt32LE(12)).toString());
 assert.equal(g.meshes.length,3);assert(g.images.length>=2);assert(g.images.every(x=>x.bufferView!==undefined),'textures are embedded');
 assert(g.materials.some(x=>x.normalTexture),'woven normal map');assert(raw.length<600000);
 const triangles=g.meshes.reduce((n,m)=>n+m.primitives.reduce((sum,p)=>sum+g.accessors[p.indices].count/3,0),0);
 assert.equal(triangles,item.triangles);assert(fs.statSync(path.join(root,item.source)).size>100000);
}
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.PET_TEST_CHROME||'C:/Program Files/Google/Chrome/Application/chrome.exe'});
 try{
  const page=await browser.newPage();await page.goto((process.env.PET_TEST_BASE||'http://127.0.0.1:5091')+'/pet-shop');
  const report=await page.evaluate(async()=>{
   const manifest=await(await fetch('/static/data/pet-growth-models.json')).json();let count=0;
   const items=[{id:'daisy',slot:'head',design:'flower'},{id:'blue-beret',slot:'head',design:'beret'},{id:'moss-bow',slot:'neck',design:'bow'},{id:'coral-bow',slot:'neck',design:'bow'}];
   for(const entry of manifest.stages){
    const asset=entry.assets.default||entry.assets.tabby;
    const gltf=await new Promise((resolve,reject)=>new THREE.GLTFLoader().load(asset.path,resolve,undefined,reject));
    const p=new PortalPets.Pet(THREE,gltf,{height:entry.height});await p.wardrobeReady;
    for(const item of items){
     if(await p.wardrobe.apply([item])!==1)throw Error('Unsupported '+entry.pet+entry.stage+item.id);
     p.play('run');for(let i=0;i<10;i++)p.update(.05);
     p.root.updateMatrixWorld(true);
     const object=p.root.userData.accessories[0],box=new THREE.Box3().setFromObject(object),size=box.getSize(new THREE.Vector3());
     if(!box.min.toArray().every(Number.isFinite)||size.length()<.015||size.length()>entry.height*.6)throw Error('Invalid accessory bounds');
     count++;
    }
    const pending=p.wardrobe.apply(items);SelectedAssets.disposeTree(p.root);await pending;
    if(p.root.userData.accessories.length)throw Error('Late attachment after disposal');
   }
   return count;
  });
  assert.equal(report,48);console.log('PASS four independent GLBs, packed PBR textures, editable sources, 48 model/item fits and pending-load disposal');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1});
