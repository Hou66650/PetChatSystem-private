const assert=require('node:assert/strict'),fs=require('node:fs');
const {Controller}=require('../static/js/den/waterfall-flow.js');
const b=fs.readFileSync('static/models/petchat-waterfalls-v1/sakura.glb');
const glb=JSON.parse(b.toString('utf8',20,20+b.readUInt32LE(12)));
assert.equal(glb.nodes.filter(n=>n.extras?.waterfall_role==='curtain').length,14);
for(const n of glb.nodes.filter(n=>n.extras?.waterfall_role==='curtain')){
    for(const p of glb.meshes[n.mesh].primitives){assert(p.attributes.TEXCOORD_0!==undefined);assert.equal(glb.materials[p.material].alphaMode,'BLEND');}
}
let disposed=0;const tex={dispose(){disposed++}},water={map:tex,alphaMap:tex},mist={map:tex},untouched={depthWrite:true};
const node=(role,m)=>({isMesh:true,userData:role?{waterfall_role:role}:{},material:m,castShadow:true});
const objects=[node('curtain',water),node('curtain',water),node('mist',mist),node(null,untouched)];
const ctl=new Controller({traverse(fn){objects.forEach(fn)}});
const shader={uniforms:{},vertexShader:'#include <begin_vertex>',fragmentShader:'#include <color_fragment>'};
water.onBeforeCompile(shader);assert.equal(shader.uniforms.waterfallTime,ctl.time);
assert(shader.vertexShader.includes('vFallUv=uv'));assert(shader.fragmentShader.includes('smoothstep(0.68,1.06'));
ctl.update(5);assert.equal(shader.uniforms.waterfallTime.value,5);
ctl.update(NaN);assert.equal(ctl.time.value,0);
assert.equal(water.depthWrite,false);assert.equal(objects[0].castShadow,false);
assert.equal(untouched.depthWrite,true);assert.equal(untouched.onBeforeCompile,undefined);
ctl.dispose();ctl.dispose();assert.equal(disposed,1,'Shared mist texture disposed exactly once');
console.log('PASS: exported UV/alpha metadata, animation clock, isolated materials, texture lifecycle');
