/* No windows/network: exercise the shared desktop/visitor adapter with a posed skin. */
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),THREE=require('../static/js/vendor/three.min.js');
const ctx={};vm.createContext(ctx);for(const f of ['pet-model-bounds','portal-pets'])vm.runInContext(fs.readFileSync('static/js/den/'+f+'.js','utf8'),ctx);
const geometry=new THREE.BoxGeometry(.5,1,.6);geometry.translate(0,10,0);const n=geometry.attributes.position.count;
geometry.setAttribute('skinIndex',new THREE.Uint16BufferAttribute(new Uint16Array(n*4),4));const weights=new Float32Array(n*4);for(let i=0;i<n;i++)weights[i*4]=1;geometry.setAttribute('skinWeight',new THREE.Float32BufferAttribute(weights,4));
const skin=new THREE.SkinnedMesh(geometry,new THREE.MeshBasicMaterial()),joint=new THREE.Bone();joint.name='joint';skin.add(joint);skin.bind(new THREE.Skeleton([joint]));joint.position.y=2;
const scene=new THREE.Group();scene.add(skin);const clips=['idle_breathe','walk','run','sniff','sleep_loop'].map(name=>new THREE.AnimationClip(name,1,[new THREE.NumberKeyframeTrack('joint.position[x]',[0,.5,1],[0,.1,0])]));
const pet=new ctx.PortalPets.Pet(THREE,{scene,animations:clips},{height:.85,custom:true});const bounds=ctx.PetModelBounds.measure(THREE,pet.root);
assert(Math.abs(bounds.min.y)<1e-5,'private skin must stand on the floor');assert(Math.abs(bounds.max.y-.85)<1e-5,'private skin height must use actual bone transforms');
for(const [action,clip] of [['walk','walk'],['trot','walk'],['run','run'],['sleep','sleep_loop'],['petting','sniff']]){pet.play(action);assert.equal(pet.active.getClip().name,clip);pet.update(.04);assert(ctx.PetModelBounds.measure(THREE,pet.root).min.toArray().every(Number.isFinite));}
console.log('PASS private desktop/visitor rest-skin bounds, scale, walk/run/sleep/petting mappings');
