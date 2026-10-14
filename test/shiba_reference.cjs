const assert=require('node:assert/strict'),fs=require('node:fs');
const file=fs.readFileSync('static/models/petchat-shiba-v4/qiuqiu.glb');
const jsonSize=file.readUInt32LE(12),g=JSON.parse(file.toString('utf8',20,20+jsonSize)),bin=20+jsonSize+8;
function floats(index){
 const a=g.accessors[index],dims={SCALAR:1,VEC2:2,VEC3:3,VEC4:4}[a.type];assert.equal(a.componentType,5126);const values=new Array(a.count*dims).fill(0);
 if(a.bufferView!==undefined){const v=g.bufferViews[a.bufferView];for(let i=0;i<a.count;i++)for(let j=0;j<dims;j++)values[i*dims+j]=file.readFloatLE(bin+(v.byteOffset||0)+(a.byteOffset||0)+i*(v.byteStride||dims*4)+j*4);}
 if(a.sparse){const sp=a.sparse,iv=g.bufferViews[sp.indices.bufferView],vv=g.bufferViews[sp.values.bufferView],bytes={5121:1,5123:2,5125:4}[sp.indices.componentType];for(let i=0;i<sp.count;i++){const at=bin+(iv.byteOffset||0)+(sp.indices.byteOffset||0)+i*bytes;const target=bytes===1?file.readUInt8(at):bytes===2?file.readUInt16LE(at):file.readUInt32LE(at);for(let j=0;j<dims;j++)values[target*dims+j]=file.readFloatLE(bin+(vv.byteOffset||0)+(sp.values.byteOffset||0)+(i*dims+j)*4);}}
 return values;
}
const skin=g.meshes.find(m=>m.extras?.targetNames?.includes('Blink_L'));assert(skin);
assert.equal(g.skins[0].joints.length,45);
assert.equal(new Set(g.animations.map(a=>a.name)).size,35);
assert(file.length<18*1024*1024,'selected Shiba stays within the asset budget');
const page=fs.readFileSync('templates/den.html','utf8');
assert(page.includes("glb: '/static/models/petchat-shiba-v4/qiuqiu.glb?v={{ app_version }}'"));
for(const name of ['Blink_L','Blink_R']){
 const index=skin.extras.targetNames.indexOf(name);let moved=0;
 for(const p of skin.primitives){const values=floats(p.targets[index].POSITION);for(let i=0;i<values.length;i+=3){const d=Math.hypot(...values.slice(i,i+3));assert(Number.isFinite(d));assert(d<.055,'blink is a local eyelid deformation');if(d>.0001)moved++;}}
 assert(moved>20,'blink must actually deform the exported mesh');
}
for(const mesh of g.meshes)for(const p of mesh.primitives){
 const values=floats(p.attributes.WEIGHTS_0);for(let i=0;i<values.length;i+=4)assert(Math.abs(values.slice(i,i+4).reduce((a,b)=>a+b,0)-1)<1e-4,'normalized four-bone skin weights');
}
assert(g.meshes.length<=3,'fur and skin are batched');
assert(g.materials.some(m=>m.pbrMetallicRoughness?.baseColorTexture),'reference-based albedo is exported');
assert(g.images.some(im=>{const v=g.bufferViews[im.bufferView],start=bin+(v.byteOffset||0);return im.mimeType==='image/png'&&file.readUInt32BE(start+16)>=2048;}),'2K albedo embedded');
const poses=JSON.parse(fs.readFileSync('art/shiba-v4/pose-report.json'));
for(const [name,pose] of Object.entries(poses))assert(pose.bounds[2][0]>-.015,`${name}: exported skin must not penetrate the floor`);
console.log('PASS actual blink displacement, normalized skin weights, 2K source pigment, batched meshes, exported run/sit/play-bow ground clearance');

