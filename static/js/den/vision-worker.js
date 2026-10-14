/* Dedicated inference thread; one transferred frame at a time, never any uploads. */
// MediaPipe's WASM loader calls importScripts, which needs a classic worker.
const tasks = import('/static/js/vendor/mediapipe/vision_bundle.mjs');
let face = null, hand = null;
self.onmessage = async ({data}) => {
  if (data.type === 'init') {
    try {
      const {FilesetResolver, FaceLandmarker, HandLandmarker} = await tasks;
      const fileset = await FilesetResolver.forVisionTasks('/static/js/vendor/mediapipe');
      const base = name => ({modelAssetPath: '/static/js/vendor/mediapipe/' + name + '_landmarker.task', delegate: 'CPU'});
      if (data.face) face = await FaceLandmarker.createFromOptions(fileset, {baseOptions: base('face'), runningMode:'VIDEO', numFaces:1});
      if (data.hands) hand = await HandLandmarker.createFromOptions(fileset, {baseOptions: base('hand'), runningMode:'VIDEO', numHands:2});
      self.postMessage({type:'ready'});
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
