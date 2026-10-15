const assert=require('node:assert/strict'),{Controller}=require('../static/js/den/cat-agent'),catalog=require('../static/data/cat-world.json');
(async()=>{
 const saved=new Map(),storage={getItem:k=>saved.get(k),setItem:(k,v)=>saved.set(k,v)};
 function create(){const model={position:{x:0,z:0}},locomotion={autonomous:true,enabled:true,path:[],navigation:{isWalkable:p=>Math.abs(p.x)<5&&Math.abs(p.z)<5},interrupt(){this.path=[];}};return new Controller({model,locomotion,life:{cancel(){}},scope:'return-test',storage,animate(){},fetcher:async()=>({ok:true,json:async()=>({scope:'return-test',catalog,memory:[]})})});}
 const first=create();await first.ready;Object.assign(first.model.position,{x:1,z:2});first.energy=.72;first.hunger=.3;first.thirst=.4;first.dispose();
 const second=create();await second.ready;assert.deepEqual(second.model.position,{x:1,z:2});assert.equal(second.energy,.72);assert.equal(second.hunger,.3);assert.equal(second.thirst,.4);second.dispose();
 saved.set('pait-cat-exploration:return-test:needs',JSON.stringify({position:{x:999,z:999},energy:.7}));const third=create();await third.ready;assert.deepEqual(third.model.position,{x:0,z:0});third.dispose();
 console.log('PASS leave/return: safe position and needs restored, no offline decay, invalid location ignored');
})().catch(e=>{console.error(e);process.exitCode=1});
