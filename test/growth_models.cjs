const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const root=path.resolve(__dirname,'..'),manifest=JSON.parse(fs.readFileSync(path.join(root,'static/data/pet-growth-models.json'),'utf8'));
const expected=Number(process.env.PET_GROWTH_EXPECT||12);assert.equal(manifest.stages.length,expected,'complete pet/stage resource coverage');
const budgets={1:160839,2:169146,3:154155,4:163530};
const hash=data=>crypto.createHash('sha256').update(data).digest('hex');
function parse(file){
 const raw=fs.readFileSync(file);assert(raw.length>=28);assert.equal(raw.readUInt32LE(0),0x46546c67);assert.equal(raw.readUInt32LE(4),2);assert.equal(raw.readUInt32LE(8),raw.length);
 const length=raw.readUInt32LE(12),g=JSON.parse(raw.subarray(20,20+length).toString('utf8')),binary=raw.subarray(28+length),accessors=g.accessors||[];let triangles=0;const positions=[];
 for(const mesh of g.meshes||[])for(const primitive of mesh.primitives||[]){
  const position=accessors[primitive.attributes.POSITION];triangles+=(primitive.indices===undefined?position.count:accessors[primitive.indices].count)/3;
  const view=g.bufferViews[position.bufferView],start=(view.byteOffset||0)+(position.byteOffset||0),bytes=binary.subarray(start,start+view.byteLength);positions.push(hash(bytes));
 }
 return {g,triangles,positionSignature:hash(positions.sort().join(':'))};
}
const signatures=new Map();
for(const item of manifest.stages){
 for(const [appearance,asset] of Object.entries(item.assets)){
  const file=path.join(root,asset.path.slice(1));assert(fs.existsSync(file),asset.path);assert.equal(hash(fs.readFileSync(file)),asset.sha256,asset.path+' hash');
  const {g,triangles,positionSignature}=parse(file);assert.deepEqual(g.skins.map(s=>s.joints.length),[45],asset.path+' joints');assert.equal(g.animations.length,35,asset.path+' clips');assert.equal(triangles,budgets[item.pet],asset.path+' triangle budget');assert(fs.statSync(file).size<=32*1024*1024);
  const key=item.pet+':'+appearance;if(!signatures.has(key))signatures.set(key,new Set());signatures.get(key).add(positionSignature);
  console.log(item.pet,item.stage,appearance,'triangles',triangles,'clips',g.animations.length,'bytes',fs.statSync(file).size);
 }
}
for(const [key,values] of signatures)assert.equal(values.size,3,'independent stage geometry for '+key);
console.log('Growth models: GLB hashes, rigs, clips, budgets and independent POSITION signatures passed');
