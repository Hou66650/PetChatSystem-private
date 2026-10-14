const assert = require('node:assert/strict');
const fs = require('node:fs');
const THREE = require('../static/js/vendor/three.min.js');
function read(path) {
  const b=fs.readFileSync(path); return JSON.parse(b.subarray(20,20+b.readUInt32LE(12)));
}
const old=read('static/models/petchat-toys-v1/sakura.glb');
const scene=read('static/models/petchat-sakura-grand-v1/sakura.glb');
const tree=n=>n.extras?.asset_role==='grand_cherry_tree';
assert.equal(scene.nodes.filter(tree).length,8);
assert(!scene.nodes.some(n=>n.name?.startsWith('Sakura_v2_')));
function bounds(g,nodes) {
  const result=new THREE.Box3();
  for(const n of nodes) {
    const m=new THREE.Matrix4();
    if(n.matrix)m.fromArray(n.matrix);
    else m.compose(new THREE.Vector3().fromArray(n.translation||[0,0,0]),new THREE.Quaternion().fromArray(n.rotation||[0,0,0,1]),new THREE.Vector3().fromArray(n.scale||[1,1,1]));
    for(const p of g.meshes[n.mesh].primitives) {
      const a=g.accessors[p.attributes.POSITION];
      result.union(new THREE.Box3(new THREE.Vector3().fromArray(a.min),new THREE.Vector3().fromArray(a.max)).applyMatrix4(m));
    }
  }
  return result;
}
const oldTree=old.nodes.filter(n=>n.name?.startsWith('Sakura_v2_'));
const oldSize=bounds(old,oldTree).getSize(new THREE.Vector3());
const newSize=bounds(scene,scene.nodes.filter(tree)).getSize(new THREE.Vector3());
assert(newSize.x>oldSize.x*1.3,'Crown must be substantially broader');
assert(newSize.y>oldSize.y*1.2,'Tree must be taller');
for(const n of old.nodes.filter(n=>n.mesh!==undefined&&!oldTree.includes(n))) {
  const replacement=scene.nodes.find(x=>x.name===n.name);
  assert(replacement,`Preserve ${n.name}`);
  assert.deepEqual(replacement.extras,n.extras);
  const before=bounds(old,[n]),after=bounds(scene,[replacement]);
  assert(before.min.distanceTo(after.min)<.0001&&before.max.distanceTo(after.max)<.0001,`Preserve placement: ${n.name}`);
}
const curtains=scene.nodes.filter(n=>n.extras?.waterfall_role==='curtain');
assert.equal(curtains.length,14);
for(const n of curtains)for(const p of scene.meshes[n.mesh].primitives) {
  assert(p.attributes.TEXCOORD_0!==undefined);
  assert.equal(scene.materials[p.material].alphaMode,'BLEND');
}
assert(scene.nodes.some(n=>n.extras?.toy_id==='ball'));
const report=JSON.parse(fs.readFileSync('art/sakura-grand-v1/build-report.json'));
assert.equal(report.flowers,4929);
assert(report.tree_triangles<460000);
assert(report.glb_bytes<45*1024*1024);
const html=fs.readFileSync('templates/den.html','utf8');
assert(html.includes('/static/models/petchat-sakura-grand-v1/sakura.glb'));
const nav=JSON.parse(html.match(/const SAKURA_NAV = (.*);/)[1]);
assert(nav.obstacles.find(x=>x.x===-2.1&&x.z===-1.5).r>=.55);
console.log('PASS: grand crown bounds, 8 batches, scene preservation, water/toy metadata and root clearance',newSize.toArray());
