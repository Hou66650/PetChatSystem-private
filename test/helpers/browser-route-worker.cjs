const path=require('node:path'),{Worker:Thread}=require('node:worker_threads');
class BrowserWorker{
 constructor(url){
  this.thread=new Thread(`
   const {parentPort,workerData}=require('node:worker_threads'),fs=require('node:fs'),path=require('node:path');
   global.self=globalThis;global.location={search:''};global.postMessage=data=>parentPort.postMessage(data);
   // Browser imports have no CommonJS module. Keep native globals in this isolated
   // thread; VM context proxy lookups otherwise distort navigation timing heavily.
   global.importScripts=(...urls)=>urls.forEach(url=>Function('module','exports',fs.readFileSync(path.join(workerData.root,url.split('?')[0]),'utf8'))(undefined,undefined));
   importScripts(workerData.url);parentPort.on('message',data=>self.onmessage({data}));
  `,{eval:true,workerData:{root:path.resolve(__dirname,'../..'),url}});
  this.thread.on('message',data=>this.onmessage?.({data}));this.thread.on('error',e=>this.onerror?.(e));
 }
 postMessage(data){this.thread.postMessage(data);}
 terminate(){void this.thread.terminate();}
}
module.exports=BrowserWorker;
