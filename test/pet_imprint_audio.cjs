const assert=require('node:assert/strict');
const {Controller}=require('../static/js/den/pet-care-runtime.js');
global.document=new EventTarget();document.hidden=false;
global.localStorage={getItem:()=>null};
let played=0,paused=0,voice=false,resolve,paths=[];
global.Audio=class{play(){played++;return Promise.resolve();}pause(){paused++;}};
URL.createObjectURL=()=> 'blob:test';URL.revokeObjectURL=()=>{};
const settled=()=>new Promise(r=>setImmediate(r));
(async()=>{
 const c=new Controller({scope:'a',pet:()=>({id:1}),available:()=>false,noticeAvailable:()=>false,cancelComfort:()=>{},voiceActive:()=>voice,
  fetcher:async path=>({ok:true,json:async()=>({scope:'a',signedIn:true,settings:{emotion:false},enabled:false,clips:[]})})});
 try{await settled();c.unlocked=true;
  const imprint={revision:7,originalCalls:{enabled:true,clips:[]},policy:{vocality:'quiet',calls:{greeting:{id:'original',duration:1}}}};
  c.fetcher=path=>{paths.push(path);return new Promise(r=>resolve=r);};
  const response={ok:true,headers:{get:()=> 'a'},blob:async()=>new Blob(['test'])};
  const late=c.call('greeting',{explicit:true,imprint});c.stopAudio();resolve(response);await late;assert.equal(played,0);
  const live=c.call('greeting',{explicit:true,imprint});resolve(response);await live;assert.equal(played,1);assert(paths.at(-1).endsWith('?revision=7'));
  const count=paths.length;await c.call('greeting',{imprint});assert.equal(paths.length,count,'quiet cooldown prevents repeated automatic sound');
  c.stopAudio();assert.equal(paused,1);
  const speaking=c.call('greeting',{explicit:true,imprint});voice=true;resolve(response);await speaking;assert.equal(played,1,'late sound cannot interrupt voice');
  voice=false;const other=c.call('greeting',{explicit:true,imprint});resolve({...response,headers:{get:()=> 'other'}});await other;assert.equal(played,1);
  console.log('PASS bound original revision, quiet cooldown, manual cancellation, voice priority and account isolation');
 }finally{c.dispose();}
})().catch(e=>{console.error(e);process.exitCode=1;});
