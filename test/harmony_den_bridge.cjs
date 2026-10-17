const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const {stripTypeScriptTypes}=require('node:module');
const THREE=require('../static/js/vendor/three.min.js');
const path='/static/models/petchat-cat-v3/cat.glb';
let time=0, renders=[], throws=false;
const events=[], parent={insertBefore(node){this.node=node;}};
const context={THREE,URL,performance:{now:()=>time},crypto:{randomUUID:()=> 'session-one'},
 location:{href:'http://192.168.1.2:5005/den',origin:'http://192.168.1.2:5005'},
 addEventListener:(...a)=>events.push(a),removeEventListener(){},
 document:{hidden:false,addEventListener:(...a)=>events.push(a),removeEventListener(){},
 createElement:()=>({style:{},setAttribute(){},remove(){this.removed=true;}})}};
vm.runInNewContext(fs.readFileSync('static/js/den/native-den.js','utf8'),context);
const scene=new THREE.Scene(),camera=new THREE.PerspectiveCamera(42,1,.1,100);
camera.position.set(0,1,5);camera.lookAt(0,.5,0);camera.updateMatrixWorld();
const pet=new THREE.Group();pet.add(new THREE.Mesh(new THREE.BoxGeometry(.5,1,.5),new THREE.MeshBasicMaterial()));
pet.userData.height=1;scene.add(pet);scene.updateMatrixWorld(true);
let state={scene,camera,petModel:pet,spec:{glb:path},busy:false,special:false,
 action:{getClip:()=>({name:'Armature|idle_breathe',duration:2}),time:.5,getEffectiveTimeScale:()=>1,loop:THREE.LoopRepeat}};
const bridge=new context.NativeDenBridge.Bridge({canvas:{parentElement:parent},
 renderer:{render(){renders.push(pet.visible);if(throws)throw Error('render failure');}},read:()=>state});
bridge.render(scene,camera);assert.equal(renders.at(-1),true);assert.equal(parent.node,undefined,'desktop path must not insert native UI');
bridge.exchange(null);bridge.render(scene,camera);assert.equal(renders.at(-1),true,'keep original until native acknowledges');
assert.equal(bridge.packet.clip,'idle_breathe');assert.equal(bridge.packet.phase,.25);
const ack=()=>({session:bridge.session,key:bridge.packet.key,ready:true});
bridge.exchange(ack());bridge.render(scene,camera);assert.equal(renders.at(-1),false);assert.equal(pet.visible,true);
assert.equal(parent.node.style.opacity,'1');
throws=true;assert.throws(()=>bridge.render(scene,camera));throws=false;assert.equal(pet.visible,true,'restore raycast model even on draw errors');
bridge.exchange({...ack(),session:'previous-page'});bridge.render(scene,camera);assert.equal(renders.at(-1),true);
bridge.exchange(ack());time+=1001;bridge.render(scene,camera);assert.equal(renders.at(-1),true,'lost heartbeat restores original');
bridge.exchange(ack());state.special=true;bridge.render(scene,camera);assert.equal(renders.at(-1),true);state.special=false;
pet.userData.accessories=[{visible:true}];bridge.render(scene,camera);assert.equal(renders.at(-1),true);pet.userData.accessories=[];
state.spec.glb='https://evil.test'+path;bridge.render(scene,camera);assert.equal(bridge.packet.key,'');state.spec.glb=path;
bridge.render(scene,camera);bridge.exchange(ack());bridge.render(scene,camera);assert.equal(renders.at(-1),false);
const wall=new THREE.Mesh(new THREE.BoxGeometry(3,3,.3),new THREE.MeshBasicMaterial());wall.position.set(0,.7,2);
scene.add(wall);scene.updateMatrixWorld(true);time+=200;bridge.render(scene,camera);
assert.equal(bridge.packet.visible,false);assert.equal(renders.at(-1),true,'scenery occlusion returns to shared WebGL depth buffer');
scene.remove(wall);time+=200;bridge.render(scene,camera);bridge.exchange(ack());
const previousKey=bridge.packet.key;pet.uuid='next-pet';bridge.render(scene,camera);
assert.notEqual(bridge.packet.key,previousKey);assert.equal(renders.at(-1),true,'switch cannot display stale native pet');
context.document.hidden=true;bridge.render(scene,camera);assert.equal(bridge.packet.visible,false);
const embed=parent.node;bridge.dispose();assert(embed.removed);assert.equal(bridge.enabled,false);
bridge.enable();bridge.unavailable();bridge.exchange(null);assert.equal(bridge.enabled,false);assert.equal(bridge.embed,null);
assert.match(bridge.mode(),/不可用/);
assert(events.every(e=>['pagehide','visibilitychange'].includes(e[0])),'does not replace original business event handlers');

const source=fs.readFileSync('harmony/entry/src/main/ets/model/NativeDenProtocol.ets','utf8').replace(/^import .*;\r?\n/gm,'').replace(/export /g,'');
const protocol={NATIVE_PETS:[{path}]};
vm.runInNewContext(stripTypeScriptTypes(source)+'\nglobalThis.parse=parseDenFrame;globalThis.trusted=isDenPage;',protocol);
const frame={version:1,session:'one',key:'pet-one',path,visible:true,position:{x:0,y:0,z:0},rotation:{x:0,y:0,z:0,w:1},scale:{x:1,y:1,z:1},
 cameraPosition:{x:0,y:1,z:5},cameraRotation:{x:0,y:0,z:0,w:1},fov:.7,near:.1,far:100,clip:'idle_breathe',phase:.2,speed:1,loop:true};
assert(protocol.parse(JSON.stringify(frame)));assert(protocol.parse(JSON.stringify(JSON.stringify(frame))));
for(const changes of [{path:'https://evil.test/model.glb'},{path:'/../secret'},{speed:Infinity},{phase:-1},{near:0},{far:.01},
 {scale:{x:-1,y:1,z:1}},{rotation:{x:0,y:0,z:0,w:9}},{session:{}},{visible:'true'},{clip:'x'.repeat(101)}]) {
 assert.equal(protocol.parse(JSON.stringify({...frame,...changes})),null);
}
assert.equal(protocol.parse('x'.repeat(8193)),null);assert.equal(protocol.parse('null'),null);
assert(protocol.parse(JSON.stringify({version:1,session:'one',key:'',visible:false})));
const origin='http://192.168.1.2:5005';
assert(protocol.trusted(origin+'/den?pet=3',origin));assert(protocol.trusted(origin+'/den/',origin));
for(const url of [origin+'.evil/den',origin+'/den-other',origin+'/chat','https://evil/den'])assert(!protocol.trusted(url,origin));
console.log('PASS den bridge: unchanged desktop/UI handlers, ack gating, stale sessions, fallback, occlusion, model switching and protocol limits');
