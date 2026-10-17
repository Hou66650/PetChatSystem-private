/* Camera JPEG encoding only: no inference, networking or persistence in this worker. */
let canvas;
self.onmessage=async({data})=>{
    const image=data.image;
    try{
        const sourceWidth=image.displayWidth||image.width,sourceHeight=image.displayHeight||image.height;
        const scale=Math.min(1,640/sourceWidth,480/sourceHeight);
        const width=Math.max(1,Math.floor(sourceWidth*scale)),height=Math.max(1,Math.floor(sourceHeight*scale));
        canvas ||= new OffscreenCanvas(width,height);
        if(canvas.width!==width||canvas.height!==height){canvas.width=width;canvas.height=height;}
        canvas.getContext('2d',{alpha:false,willReadFrequently:true}).drawImage(image,0,0,width,height);
        image.close();
        // HTMLCanvasElement.toBlob waits for main-thread idle time on Harmony WebView.
        // Offscreen encoding here is independent of the busy 3D render thread.
        const blob=await canvas.convertToBlob({type:'image/jpeg',quality:.72});
        self.postMessage({blob});
    }catch(error){image?.close();self.postMessage({error:true});}
};
