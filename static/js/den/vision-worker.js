/* Dedicated inference thread; one transferred frame at a time, never any uploads. */
// MediaPipe's WASM loader calls importScripts, which needs a classic worker.
const tasks = import('/static/js/vendor/mediapipe/vision_bundle.mjs');
let face = null, hand = null;
self.onmessage = async ({data}) => {
  if (data.type === 'init') {
    try {
      const {FilesetResolver, FaceLandmarker, HandLandmarker} = await tasks;
      const fileset = await FilesetResolver.forVisionTasks('/static/js/vendor/mediapipe');
      const delegates=[];
      async function create(Task,name,extra){
        const modelAssetPath='/static/js/vendor/mediapipe/'+name+'_landmarker.task';
        let gpuContext;
        try {
          const canvas=new OffscreenCanvas(640,480);
          gpuContext=canvas.getContext('webgl2',{powerPreference:'high-performance'});
          if(!gpuContext)throw Error('GPU context unavailable');
          const model=await Task.createFromOptions(fileset,{canvas,baseOptions:{modelAssetPath,delegate:'GPU'},runningMode:'VIDEO',...extra});
          delegates.push('GPU');return model;
        } catch(error) {
          gpuContext?.getExtension?.('WEBGL_lose_context')?.loseContext();
          const model=await Task.createFromOptions(fileset,{baseOptions:{modelAssetPath,delegate:'CPU'},runningMode:'VIDEO',...extra});
          delegates.push('CPU');return model;
        }
      }
      if (data.face) face=await create(FaceLandmarker,'face',{numFaces:1});
      if (data.hands) hand=await create(HandLandmarker,'hand',{numHands:2});
      self.postMessage({type:'ready',delegate:[...new Set(delegates)].join(' + ')});
    } catch (error) { face?.close(); hand?.close(); self.postMessage({type:'error', message:String(error)}); }
  } else if (data.type === 'frame') {
    try {
      const faceResult = face ? face.detectForVideo(data.image, data.ts) : null;
      const handResult = hand ? hand.detectForVideo(data.image, data.ts) : null;
      self.postMessage({type:'result', face:faceResult, hand:handResult, ts:data.ts});
    } catch (error) { self.postMessage({type:'error', message:String(error)}); }
    finally { data.image.close(); }
  }
};
