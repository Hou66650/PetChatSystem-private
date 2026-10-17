const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const root=path.resolve(__dirname,'..'),assets=require('../static/js/den/growth-assets.js');
const manifest=assets.validate(JSON.parse(fs.readFileSync(path.join(root,'static/data/pet-growth-models.json'),'utf8')));
for(const stage of ['幼年','少年','成年']){
 for(const coat of ['tabby','ginger','tuxedo','calico','ragdoll']){
  const selected=assets.resolve(manifest,{petId:3,stage,appearance:coat});
  assert(selected.supported);assert.equal(selected.stage,stage);assert.equal(selected.appearance,coat);
  assert(selected.path.endsWith('.glb'));assert(fs.existsSync(path.join(root,selected.path.slice(1))));
 }
}
assert.equal(assets.resolve(manifest,{petId:3,stage:'幼年',appearance:'tabby'}).height,.58);
assert.equal(assets.resolve(manifest,{petId:3,stage:'少年',appearance:'tabby'}).height,.72);
assert.equal(assets.resolve(manifest,{petId:3,stage:'成年',appearance:'tabby'}).height,.85);
assert.deepEqual(assets.resolve(manifest,{petId:3,stage:'幼年',appearance:'studio-1',custom:true}),{supported:false,reason:'private-preserved'});
assert.equal(assets.resolve(manifest,{petId:3,stage:'幼年',appearance:'unknown'}).reason,'appearance-unsupported');
assert.equal(manifest.stages.length,12);
for(const [petId,heights] of [[1,[.64,.82,.95]],[2,[.72,.91,1.05]],[4,[.76,.96,1.12]]]){
 ['幼年','少年','成年'].forEach((stage,index)=>{
  const selected=assets.resolve(manifest,{petId,stage});assert(selected.supported);assert.equal(selected.height,heights[index]);
 });
}
const selected=assets.resolve(manifest,{petId:3,stage:'幼年',appearance:'tabby'});
assert(!('scale' in selected),'stage height must not be combined with the legacy scale');
console.log('Growth assets: stage/appearance resolution, private preservation and single-resource selection passed');
