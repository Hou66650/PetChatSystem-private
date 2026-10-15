const assert=require('assert'),fs=require('fs'),crypto=require('crypto'),flowers=require('../static/data/farm-flowers.json'),farm=require('../static/js/den/farm-garden');
const signatures=new Set();
for(const f of flowers){const growth=new Set();for(const variant of [false,true])for(let stage=variant?10:1;stage<=10;stage++)for(const far of [false,true]){
 const key=farm.modelKey(f.id+(variant?'-dream':''),stage,far),b=fs.readFileSync('static/models/petchat-farm-v1/'+key+'.glb');assert.equal(b.toString('ascii',0,4),'glTF');
 const j=JSON.parse(b.toString('utf8',20,20+b.readUInt32LE(12)));assert(j.meshes.length);assert(j.images?.length,'botanical pigment maps');
 if(!far&&!variant){growth.add(crypto.createHash('sha256').update(b).digest('hex'));if(stage===10)signatures.add(JSON.stringify(j.accessors.map(a=>a.count)));}
 for(const a of j.accessors)if(a.min){assert(a.min.every(Number.isFinite));assert(a.max.every(Number.isFinite));}
}
assert.equal(growth.size,10,f.id);const report=JSON.parse(fs.readFileSync('art/flower-collection-v1/'+f.id+'-report.json'));assert(report.at(-1).lodTriangles<report.at(-1).triangles*.5,f.id+' LOD must be lighter');}
assert.equal(signatures.size,10,'ten distinct species geometries');assert.throws(()=>farm.modelKey('unknown-dream',10,false));
console.log('PASS ten flower species, 100 stages, 10 dream cultivars, valid textures and lighter LODs');
