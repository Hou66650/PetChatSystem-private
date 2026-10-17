const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const results=[],canvases=[];let fail=false;
class Canvas{
 constructor(w,h){this.width=w;this.height=h;canvases.push(this);}
 getContext(type,options){assert.equal(type,'2d');assert(options.willReadFrequently);return {drawImage:(image,x,y,w,h)=>{this.draw={image,w,h};}};}
 async convertToBlob(options){assert.equal(options.type,'image/jpeg');assert.equal(options.quality,.72);if(fail)throw Error('encoding failed');return {size:32};}
}
const context={self:{postMessage:data=>results.push(data)},OffscreenCanvas:Canvas};
vm.runInNewContext(fs.readFileSync('static/js/den/vision-encoder.js','utf8'),context);
const frame=(width,height)=>({width,height,close(){this.closed=true;}});
(async()=>{
 const wide=frame(1280,720);await context.self.onmessage({data:{image:wide}});
 assert(wide.closed);assert.equal(canvases[0].width,640);assert.equal(canvases[0].height,360);assert.equal(results[0].blob.size,32);
 const portrait=frame(480,640);await context.self.onmessage({data:{image:portrait}});
 assert.equal(canvases.length,1);assert.equal(canvases[0].width,360);assert.equal(canvases[0].height,480);assert(portrait.closed);
 const small=frame(160,120);await context.self.onmessage({data:{image:small}});assert.equal(canvases[0].width,160);
 const video={displayWidth:1280,displayHeight:720,codedWidth:1280,codedHeight:736,close(){this.closed=true;}};
 await context.self.onmessage({data:{image:video}});assert(video.closed);assert.equal(canvases[0].width,640);assert.equal(canvases[0].height,360,'use displayed aspect ratio, not padded video buffer');
 fail=true;const failed=frame(640,480);await context.self.onmessage({data:{image:failed}});assert(failed.closed);assert.equal(results.at(-1).error,true);
 console.log('PASS encoder: bounded aspect-preserving JPEG, reusable software canvas, bitmap disposal and error response');
})().catch(e=>{console.error(e);process.exitCode=1;});
