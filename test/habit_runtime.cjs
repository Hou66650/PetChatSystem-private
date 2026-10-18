const assert=require('node:assert/strict');
const {Controller}=require('../static/js/den/pet-imprint-runtime.js');
(async()=>{
 let played=[],supported=['come','sit','curious'],data={scope:'a',petId:3,enabled:true,policy:{responses:{recall:{plan:['curious','come','sit'],evidence:{quote:'经主人核对'}}},calls:{}}};
 const a={scope:'a',pet:()=>3,hidden:()=>false,available:()=>true,supports:k=>supported.includes(k),status:()=>{},cancel:()=>{},play:async p=>{played.push(p);return true;},call:async()=>{},fetcher:async()=>({ok:true,json:async()=>data})};
 const c=new Controller(a);assert(await c.trigger('recall',true));assert.deepEqual(played,[['curious','come','sit']]);
 supported=['come','sit'];assert.equal(await c.trigger('recall',true),false);assert.equal(played.length,1);
 data.policy.responses={rest:{plan:['sit'],evidence:{quote:'坐下休息'}}};assert(await c.trigger('rest',true));assert.deepEqual(played[1],['sit']);
 data.policy.responses={};assert.equal(await c.trigger('rest',true),false);assert.equal(played.length,2);
 console.log('PASS confirmed ordered recall/rest recipes; absent clips and withdrawn rules never execute');
})().catch(e=>{console.error(e);process.exitCode=1});
