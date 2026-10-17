const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const {stripTypeScriptTypes}=require('node:module');
const source=fs.readFileSync('harmony/entry/src/main/ets/components/NativeDenNode.ets','utf8');
const js=stripTypeScriptTypes(source.slice(source.indexOf('export class NativeDenNode')).replace('export class','class'))+'\nglobalThis.DenNode=NativeDenNode;';
const behavior=stripTypeScriptTypes(fs.readFileSync('harmony/entry/src/main/ets/model/NativePetController.ets','utf8').replace(/^import .*;\r?\n/gm,'').replace(/export /g,''));
function glb(){const b=new ArrayBuffer(20),d=new DataView(b);d.setUint32(0,0x46546c67,true);d.setUint32(4,2,true);d.setUint32(8,20,true);return b;}
function harness(response, unsupported=false){
 const events=[],models=[];
 const animations=['idle_breathe','motion_walk','touch_head'].map(name=>({name,progress:0,enabled:false,speed:1,
  stop(){},restart(){},pause(){},seek(p){this.progress=p;},onFinished(fn){this.done=fn;}}));
 const content={destroy(){events.push('contentDestroyed');}};
 const scene={animations,environment:{},destroy(){events.push('sceneDestroyed');},
  importScene(){const model={};models.push(model);return model;},getResourceFactory(){return{
   async createScene(){return content;},async createNode(){return{};},async createCamera(){return{};},async createLight(){return{};}
  };}};
 const ctx={NodeController:class{},BuilderNode:class{build(){}getFrameNode(){return{};}update(){}dispose(){events.push('builderDestroyed');}},
  wrapBuilder:x=>x,denView(){},ModelType:{TEXTURE:0},NodeRenderType:{RENDER_TYPE_TEXTURE:0},
  Scene:{async load(){events.push('sceneLoad');if(unsupported)throw Error("graphics.scene does not provide an export name 'Scene'");return scene;}},LightType:{DIRECTIONAL:1},EnvironmentBackgroundType:{BACKGROUND_NONE:0},
  http:{RequestMethod:{GET:1},HttpDataType:{ARRAY_BUFFER:1},createHttp(){return{async request(url){events.push(url);return response();},destroy(){events.push('requestDestroyed');}};}},
  fs:{OpenMode:{CREATE:1,TRUNC:2,WRITE_ONLY:4},openSync(){return{fd:1};},writeSync(){events.push('write');},closeSync(){},unlinkSync(){events.push('unlink');}},console,Date,DataView,ArrayBuffer};
 vm.runInNewContext(behavior+'\n'+js,ctx);
 const node=new ctx.DenNode('surface',500,300,'http://192.168.1.2:5005','/cache');node.makeNode({});
 return{node,events,models,animations};
}
const frame={session:'one',key:'cat',path:'/static/models/petchat-cat-v3/cat.glb',visible:true,position:{x:2,y:.2,z:3},
 rotation:{x:0,y:0,z:0,w:1},scale:{x:.85,y:.85,z:.85},cameraPosition:{x:0,y:2,z:5},cameraRotation:{x:0,y:0,z:0,w:1},
 fov:.7,near:.1,far:100,clip:'motion_walk',phase:.3,speed:1,loop:true};
const flush=async()=>{for(let i=0;i<25;i++)await Promise.resolve();};
(async()=>{
 const a=harness(async()=>({responseCode:200,result:glb()}));a.node.accept(frame);assert(!a.node.ack().ready);await flush();
 assert(a.node.ack().ready);assert.equal(a.node.ack().session,'one');assert.equal(a.models[0].scale.x,.85);
 assert.equal(a.models[0].position.x,2);assert.equal(a.animations[1].progress,.3);
 a.node.setActive(false);assert(!a.node.ack().ready);assert.equal(a.models[0].visible,false);
 a.node.setActive(true);assert(a.node.ack().ready);
 a.node.accept({...frame,visible:false});assert(!a.node.ack().ready);
 a.node.accept({...frame,clip:'missing'});assert(!a.node.ack().ready,'unknown clip must preserve the web rendering');
 a.node.dispose();assert.equal(a.events.filter(e=>e==='sceneDestroyed').length,1);assert(a.events.includes('unlink'));
 let done;const pending=harness(()=>new Promise(r=>done=r));pending.node.accept(frame);await flush();pending.node.dispose();
 done({responseCode:200,result:glb()});await flush();assert(!pending.events.includes('write'));assert(!pending.node.ack().ready);
 const bad=harness(async()=>({responseCode:200,result:new ArrayBuffer(20)}));bad.node.accept(frame);await flush();
 assert(!bad.node.ack().ready);assert.equal(bad.events.filter(e=>e==='sceneDestroyed').length,1);const count=bad.events.length;
 bad.node.accept(frame);await flush();assert.equal(bad.events.length,count,'do not retry a failed model on every frame');
 const switched=harness(async()=>({responseCode:200,result:glb()}));switched.node.accept(frame);
 switched.node.accept({session:'two',key:'',visible:false});await flush();assert(!switched.node.ack().ready);assert(!switched.events.includes('write'));
 const unsupported=harness(()=>{throw Error('must not download');},true);unsupported.node.accept(frame);await flush();
 assert.match(unsupported.node.ack().status,/^unavailable:/);assert(!unsupported.events.some(e=>e.startsWith('http')));
 console.log('PASS embedded scene: transform/animation sync, pause, unknown animation fallback, cancellation, corruption and owned-resource cleanup');
})().catch(e=>{console.error(e);process.exitCode=1;});
