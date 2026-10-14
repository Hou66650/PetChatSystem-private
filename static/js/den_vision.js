/* ============================================================
   宠物小窝 · 视觉互动模块（眼神对视 + 伸手抚摸）
   - MediaPipe FaceLandmarker（含虹膜）判定"用户是否看着屏幕/宠物"
   - MediaPipe HandLandmarker 判定"伸手靠近"，驱动屏幕虚拟手
   - 全部推理在本地 WASM 完成，摄像头画面不会上传（无任何网络发送）
   ============================================================ */
import { FilesetResolver, FaceLandmarker, HandLandmarker } from '/static/js/vendor/mediapipe/vision_bundle.mjs';

const WASM_PATH = '/static/js/vendor/mediapipe';
const FACE_MODEL = WASM_PATH + '/face_landmarker.task';
const HAND_MODEL = WASM_PATH + '/hand_landmarker.task';
const DETECT_MS = 100;          // 检测频率（10fps 足够，省 CPU）
const GAZE_HOLD_FRAMES = 12;    // 连续注视 ~1.2s 才算"对视"（防误触）
const GAZE_LOST_FRAMES = 8;     // 丢失 ~0.8s 结束对视
const HAND_REACH = 0.16;        // 掌距（腕→中指根）超过即视为"伸手靠近"（离摄像头近）
const PINCH_ON = 0.35;          // 捏合：拇指食指尖距 / 掌长 < 0.35（真捏合≈0.05-0.3，握拳搭指≈0.3-0.7）
const PINCH_OFF = 0.55;         // 松开：比值 > 0.55 才释放（滞后防抖）
const PALM_MIN = 0.06;          // 手掌过小（太远/未完全入镜）时忽略手势，防噪声误判

/* 纯计算：21 个关键点 → 手势指标。归一化到"掌长"（腕0→中指根9），
   使捏合/伸手判定与手离摄像头的距离无关 —— 这是误判率的核心修复。 */
function handMetrics(lms) {
    const d = (a, b) => Math.hypot(a.x - b.x, a.y - b.y);
    const palm = d(lms[0], lms[9]) || 1e-4;                    // 掌长 = 距离尺度
    const pinchDist = d(lms[4], lms[8]);                        // 拇指尖-食指尖
    const pinchRatio = pinchDist / palm;                        // 无量纲：≈0.1-0.3 捏合 / ≈1.0-1.6 张开
    const span = Math.max(
        d(lms[0], lms[4]), d(lms[0], lms[8]), d(lms[0], lms[12]),
        d(lms[0], lms[16]), d(lms[0], lms[20]),
    );
    return { palm, pinchDist, pinchRatio, span };
}

/* ============ 趣味手势检测（双手手势 + 动态手势）============
   update(landmarksArray, now) → 触发的手势名数组：
   - pray  双手合十作揖（掌心相对靠近 + 指尖朝上，保持 ~0.8s）
   - heart 双手比心（两食指尖 + 两拇指尖相触成心形，保持 ~0.6s）
   - wave  单手张开左右挥动（掌心 x 往复 ≥2 次换向）
   - thumb 竖大拇指（拇指伸展朝上 + 四指收拢，保持 ~0.6s）
   全部按"掌长"归一化，与离镜头远近无关；twoHandEngaged 供外部抑制单手捏合。 */
class HandGestures {
    constructor() {
        this.hold = {};        // 手势保持起始时间
        this.cool = {};        // 手势冷却截止
        this.waveHist = [];    // 挥手轨迹 {t, x}
        this.twoHandEngaged = false;
    }
    static palmC(l) {
        return {
            x: (l[0].x + l[5].x + l[9].x + l[13].x + l[17].x) / 5,
            y: (l[0].y + l[5].y + l[9].y + l[13].y + l[17].y) / 5,
        };
    }
    static palmR(l) {
        const c = HandGestures.palmC(l);
        return Math.hypot(l[9].x - c.x, l[9].y - c.y) || 1e-4;
    }
    static dist(a, b) { return Math.hypot(a.x - b.x, a.y - b.y); }
    // 指尖比近端指节离腕更远 = 该指伸展
    static ext(l, tip, pip) {
        const w = l[0];
        return HandGestures.dist(l[tip], w) > HandGestures.dist(l[pip], w) * 1.08;
    }
    // 食~小指伸展计数
    static openness(l) {
        let n = 0;
        [[8, 6], [12, 10], [16, 14], [20, 18]].forEach((p) => { if (HandGestures.ext(l, p[0], p[1])) n++; });
        return n;
    }
    _trackHold(name, cond, now, needMs, coolMs) {
        if (this.cool[name] && now < this.cool[name]) return false;
        if (cond) {
            if (!this.hold[name]) this.hold[name] = now;
            if (now - this.hold[name] >= needMs) {
                this.hold[name] = 0;
                this.cool[name] = now + coolMs;
                return true;
            }
        } else this.hold[name] = 0;
        return false;
    }
    update(hands, now) {
        const fired = [];
        const H = HandGestures;
        // 尺度统一用「掌长」= 腕(0)→中指根(9)，比掌心半径大 ~4 倍，
        // 真手几何下的合理阈值：并掌掌心距≈1掌长、折叠指尖距掌心≈0.5掌长
        const PL = (l) => H.dist(l[0], l[9]) || 1e-4;
        if (hands.length >= 2) {
            const A = hands[0], B = hands[1];
            const ca = H.palmC(A), cb = H.palmC(B);
            const pl = (PL(A) + PL(B)) / 2;
            const dPalm = H.dist(ca, cb);
            const dThumb = H.dist(A[4], B[4]);
            const dIndex = H.dist(A[8], B[8]);
            const tipsUp = A[8].y < ca.y - 0.3 * pl && B[8].y < cb.y - 0.3 * pl;
            const openEnough = H.openness(A) >= 2 && H.openness(B) >= 2;
            // 比心（更特异，先判）：两食指尖相触 + 两拇指尖相触，触点位于掌心上方
            const heart = dIndex < 0.32 * pl && dThumb < 0.38 * pl && dPalm < 2.6 * pl &&
                (A[8].y + B[8].y) / 2 < Math.min(ca.y, cb.y) - 0.05 * pl;
            // 作揖：两掌并拢（掌心距≈1掌长）+ 拇指/食指彼此接近 + 指尖朝上（非比心形态）
            const pray = !heart && dPalm < 1.35 * pl && dThumb < 0.85 * pl && dIndex < 0.65 * pl &&
                tipsUp && openEnough;
            this.twoHandEngaged = pray || heart || !!this.hold.pray || !!this.hold.heart;
            this.waveHist.length = 0;   // 双手时不判挥手
            this.hold.thumb = 0;
            if (this._trackHold('heart', heart, now, 600, 4000)) fired.push('heart');
            if (this._trackHold('pray', pray, now, 800, 4000)) fired.push('pray');
        } else if (hands.length === 1) {
            this.twoHandEngaged = false;
            this.hold.pray = this.hold.heart = 0;
            const l = hands[0];
            const c = H.palmC(l), pl = PL(l);
            const open = H.openness(l) >= 4;
            // 大拇指：四指收拢（指尖距掌心 < 1 掌长）+ 拇指尖高于掌心 0.4 掌长 + 拇指伸展到位
            const folded = H.openness(l) === 0 &&
                [8, 12, 16, 20].every((t) => H.dist(l[t], c) < 1.0 * pl);
            const thumbUp = folded && l[4].y < c.y - 0.4 * pl &&
                H.dist(l[4], l[0]) > pl * 1.05;
            if (this._trackHold('thumb', thumbUp, now, 600, 4000)) fired.push('thumb');
            // 挥手：手掌张开 + 掌心 x 在 ~1.6s 内往复换向 ≥2 次且有幅度
            if (open) {
                this.waveHist.push({ t: now, x: c.x });
                while (this.waveHist.length && now - this.waveHist[0].t > 1600) this.waveHist.shift();
                if (this.waveHist.length >= 6) {
                    let reversals = 0, lastDx = 0, path = 0;
                    for (let i = 1; i < this.waveHist.length; i++) {
                        const dx = this.waveHist[i].x - this.waveHist[i - 1].x;
                        path += Math.abs(dx);
                        if (lastDx !== 0 && Math.sign(dx) !== Math.sign(lastDx) &&
                            Math.abs(dx) > 0.0015 && Math.abs(lastDx) > 0.0015) reversals++;
                        if (Math.abs(dx) > 0.0015) lastDx = dx;
                    }
                    if (reversals >= 2 && path > 0.12 && (!this.cool.wave || now >= this.cool.wave)) {
                        this.cool.wave = now + 4000;
                        this.waveHist.length = 0;
                        fired.push('wave');
                    }
                }
            } else this.waveHist.length = 0;
        } else {
            this.twoHandEngaged = false;
            this.hold = {};
            this.waveHist.length = 0;
        }
        return fired;
    }
}

class DenVision {
    constructor() {
        this.running = false;
        this.face = null;      // FaceLandmarker
        this.hand = null;      // HandLandmarker
        this.video = null;
        this.stream = null;
        this.timer = null;
        this.lastTs = -1;
        this.gazeStreak = 0;
        this.gazeLost = 0;
        this.gazeContact = false;
        this.handState = { present: false, reaching: false, sx: 0, sy: 0, palm: 0 };
        this.canvasSize = { w: 0, h: 0 };
        this._errStreak = 0;
        this.onGaze = () => {};
        this.onHand = () => {};
        this.onGesture = () => {};
        this.onError = () => {};
        this.gestures = new HandGestures();
        this._smooth = { x: 0, y: 0, px: 0, py: 0, ok: false };   // 虚拟手 + 捏合点平滑位置
        this._raf = null;
        this.options = { face:true, hands:true, gestures:true, mirror:true, sensitivity:1.3, centerX:.5, centerY:.5 };
        this.generation = 0;
        this.worker = null;
        this.pending = false;
        this.starting = false;
    }

    configure(options = {}) {
        this.options = {...this.options, ...options};
        this.options.sensitivity = Math.min(2.5, Math.max(.6, Number(this.options.sensitivity) || 1.3));
    }
    calibrate() {
        if (!this.handState.present || !this.lastRaw) return false;
        this.configure({centerX:this.lastRaw.x, centerY:this.lastRaw.y});
        this._smooth.ok = false;
        return {centerX:this.lastRaw.x, centerY:this.lastRaw.y};
    }
    _point(x, y) {
        const o=this.options, direction=o.mirror ? -1 : 1;
        return {x:Math.max(0,Math.min(1,.5+direction*(x-o.centerX)*o.sensitivity))*this.canvasSize.w,
                y:Math.max(0,Math.min(1,.5+(y-o.centerY)*o.sensitivity))*this.canvasSize.h};
    }
    async _models(epoch) {
        // Worker keeps the 3D render thread responsive. Older browsers use a slower fallback.
        if (typeof Worker !== 'undefined' && typeof createImageBitmap === 'function' && typeof OffscreenCanvas !== 'undefined') {
            let worker;
            try {
                worker = new Worker('/static/js/den/vision-worker.js');
                this.worker=worker;
                await new Promise((resolve,reject)=>{
                    const done=(error)=>{clearTimeout(this.initTimeout);this.initCancel=null;error?reject(error):resolve();};
                    this.initCancel=()=>done(new Error('cancelled'));
                    this.initTimeout=setTimeout(()=>done(new Error('Worker initialization timed out')),30000);
                    worker.onmessage=({data})=>{if(data.type==='ready'){this.delegate=data.delegate||'CPU';done();}else if(data.type==='error')done(new Error(data.message));};
                    worker.onerror=()=>done(new Error('Worker unavailable'));
                    worker.postMessage({type:'init',face:this.options.face,hands:this.options.hands});
                });
                if(epoch!==this.generation) {worker.terminate();return;}
                worker.onmessage=({data})=>{
                    clearTimeout(this.frameTimeout);this.pending=false;
                    if(!this.running || epoch!==this.generation)return;
                    if(data.type==='error'){this._runtimeError();return;}
                    this._consume(data.ts,data.face,data.hand);
                };
                worker.onerror=()=>{if(epoch===this.generation)this._runtimeError();};
                this.backend='worker'; return;
            } catch(error) {
                worker?.terminate();if(this.worker===worker)this.worker=null;
                if(epoch!==this.generation) return;
            }
        }
        const fileset=await FilesetResolver.forVisionTasks(WASM_PATH);
        if(epoch!==this.generation)return;
        const delegates=[];
        const make=async(Task,path,extra)=>{
            let model,gpuContext;
            try {
                const canvas=document.createElement('canvas');
                gpuContext=canvas.getContext('webgl2',{powerPreference:'high-performance'});
                if(!gpuContext)throw Error('GPU unavailable');
                model=await Task.createFromOptions(fileset,{canvas,baseOptions:{modelAssetPath:path,delegate:'GPU'},runningMode:'VIDEO',...extra});
                delegates.push('GPU');
            } catch(error){gpuContext?.getExtension?.('WEBGL_lose_context')?.loseContext();if(epoch!==this.generation)return null;model=await Task.createFromOptions(fileset,{baseOptions:{modelAssetPath:path,delegate:'CPU'},runningMode:'VIDEO',...extra});delegates.push('CPU');}
            if(epoch!==this.generation){model.close();return null;}return model;
        };
        if(this.options.face){const model=await make(FaceLandmarker,FACE_MODEL,{numFaces:1});if(epoch===this.generation)this.face=model;}
        if(epoch!==this.generation)return;
        if(this.options.hands){const model=await make(HandLandmarker,HAND_MODEL,{numHands:2});if(epoch===this.generation)this.hand=model;}
        this.delegate=[...new Set(delegates)].join(' + ');this.backend='main';
    }
    _runtimeError() {
        if(++this._errStreak>=3){this.stop();this.onError('runtime',new Error('Inference failed'));}
    }
    _consume(ts, face, hand) {
        try {
            if(this.options.face)this._detectGaze(ts,face);
            if(this.options.hands)this._detectHand(ts,hand);
            this._errStreak=0;
        } catch(error) {this._runtimeError();}
    }

    /* 启动：摄像头 → 模型 → 检测循环
       target：虚拟手/触摸判定所用主画布元素（坐标换算基准，勿传预览小窗） */
    async start(videoEl, callbacks = {}, target = null) {
        if (this.running) return true;
        if (this.starting) return false;
        this.starting=true;
        const epoch=++this.generation;
        for(const name of ['onBlink','onSnap','onFace']) this[name]=callbacks[name] || (()=>{});
        this.onGaze = callbacks.onGaze || this.onGaze;
        this.onHand = callbacks.onHand || this.onHand;
        this.onGrab = callbacks.onGrab || this.onGrab;
        this.onGesture = callbacks.onGesture || this.onGesture;
        this.onError = callbacks.onError || this.onError;
        try {
            // 1) 摄像头（前置，低分辨率即可）
            const stream = await navigator.mediaDevices.getUserMedia({
                video: { facingMode: 'user', width: { ideal: 640 }, height: { ideal: 480 } },
                audio: false,
            });
            if(epoch!==this.generation){stream.getTracks().forEach(t=>t.stop());return false;}
            this.stream=stream;
        } catch (e) {
            if(epoch===this.generation){this.starting=false;this.onError('camera', e);}
            return false;
        }
        if(epoch!==this.generation){this.stream?.getTracks().forEach(t=>t.stop());this.stream=null;return false;}
        this.video = videoEl;
        try {
            videoEl.srcObject = this.stream;
            // play() 可能因空流/权限挂起：超时放行，检测循环自带 readyState 守卫
            await Promise.race([
                videoEl.play().catch(() => {}),
                new Promise((r) => setTimeout(r, 1500)),
            ]);
        } catch (e) { /* 出错不阻断：摄像头无帧时循环会安全跳过 */ }

        if(epoch!==this.generation)return false;
        try { await this._models(epoch); }
        catch(error){if(epoch===this.generation){this.stop();this.onError('model',error);}return false;}
        if(epoch!==this.generation || !this.stream || !this.stream.getVideoTracks().some(t=>t.readyState==='live')) {
            if(epoch===this.generation)this.stop();return false;
        }
        this.starting=false;
        this.running = true;
        this.target = target || videoEl;
        this.timer = setInterval(() => this._detect(), this.backend==='worker'?DETECT_MS:180);
        this._followLoop();
        return true;
    }

    stop() {
        ++this.generation;
        this.starting=false;
        this.running = false;
        this.initCancel?.();this.initCancel=null;
        clearTimeout(this.initTimeout);clearTimeout(this.frameTimeout);
        this.worker?.terminate();this.worker=null;this.pending=false;
        this.face?.close();this.hand?.close();this.face=this.hand=null;
        this.lastTs=-1;this._prevSnapRatio=undefined;this._eyesClosedFrames=0;
        this.lastRaw=null;this.gestures=new HandGestures();
        this.onFace?.({present:false});
        if (this.timer) { clearInterval(this.timer); this.timer = null; }
        if (this._raf) { cancelAnimationFrame(this._raf); this._raf = null; }
        if (this.stream) { this.stream.getTracks().forEach(t => t.stop()); this.stream = null; }
        if (this.video) this.video.srcObject = null;
        this.gazeContact = false;
        this.gazeStreak = 0;          // 状态完全复位，重启需重新累计
        this.gazeLost = 0;
        this._errStreak = 0;
        this.handState = { present: false, reaching: false, sx: 0, sy: 0, palm: 0 };
        this._smooth.ok = false;
        // 停止时显式通知：捏合释放 + 对视结束 + 手消失（页面据此取消手势喂食等清理）
        if (this._pinching) { this._pinching = false; this.onGrab && this.onGrab(false, null, 'stop'); }
        this.onGaze(false);
        this.onHand(this.handState);
    }

    /* ---------- 每帧检测 ---------- */
    _syncCanvasSize() {
        // 坐标换算基准 = 主画布（虚拟手与触摸判定所在空间）
        const el = this.target || this.video;
        if (el) {
            this.canvasSize.w = el.clientWidth || this.canvasSize.w || 640;
            this.canvasSize.h = el.clientHeight || this.canvasSize.h || 480;
        }
    }
    _detect() {
        const v = this.video;
        if (!this.running || !v || v.readyState < 2) return;
        const ts = performance.now();
        if (v.currentTime === this.lastTs) return;      // 无新帧则跳过
        this.lastTs = v.currentTime;
        this._syncCanvasSize();
        if(this.worker){
            if(this.pending)return;
            this.pending=true;
            const worker=this.worker,epoch=this.generation;
            createImageBitmap(v).then(image=>{
                if(epoch!==this.generation || !this.running){image.close();return;}
                this.frameTimeout=setTimeout(()=>{if(epoch===this.generation){this.stop();this.onError('runtime',new Error('Frame timed out'));}},5000);
                try{worker.postMessage({type:'frame',image,ts},[image]);}catch(error){image.close();throw error;}
            }).catch(()=>{if(epoch===this.generation){this.pending=false;this._runtimeError();}});
        } else {
            try {this._consume(ts,this.face?.detectForVideo(v,ts),this.hand?.detectForVideo(v,ts));}
            catch(error){this._runtimeError();}
        }
    }

    _detectGaze(ts, result) {
        const res = result || {};
        const lm = res.faceLandmarks && res.faceLandmarks[0];
        let looking = false;
        if(!lm){this._eyesClosedFrames=0;this.onFace?.({present:false});}
        if (lm && lm.length >= 478) {
            // 虹膜中心：468=右眼，473=左眼；眼角：33/133 右眼，362/263 左眼
            const gazeOf = (iris, o, i) => {
                const cx = (lm[o].x + lm[i].x) / 2, w = Math.abs(lm[i].x - lm[o].x) || 1e-4;
                return (lm[iris].x - cx) / w;
            };
            // 竖直分量：虹膜相对上下眼睑中点（159上/145下 右眼，386上/374下 左眼）
            const gazeYOf = (iris, up, dn) => {
                const cy = (lm[up].y + lm[dn].y) / 2, h = Math.abs(lm[dn].y - lm[up].y) || 1e-4;
                return (lm[iris].y - cy) / h;
            };
            const gaze = (gazeOf(468, 33, 133) + gazeOf(473, 362, 263)) / 2;
            const gazeY = (gazeYOf(468, 159, 145) + gazeYOf(473, 386, 374)) / 2;
            // 头部偏转代理：鼻尖相对两颊中点
            const faceCx = (lm[234].x + lm[454].x) / 2;
            const faceW = Math.abs(lm[454].x - lm[234].x) || 1e-4;
            const yaw = (lm[1].x - faceCx) / faceW;
            const faceCenterX = faceCx;
            const roll=Math.atan2(lm[263].y-lm[33].y,Math.abs(lm[263].x-lm[33].x));
            this.onFace?.({present:true,x:(this.options.mirror?1-faceCx:faceCx),y:lm[1].y,roll,yaw,gaze,gazeY});
            // 注视屏幕 ≈ 视线水平+竖直都居中 + 头基本正对 + 人坐在画面中部
            looking = Math.abs(gaze) < 0.17 && Math.abs(gazeY) < 0.4 && Math.abs(yaw) < 0.25
                && faceCenterX > 0.2 && faceCenterX < 0.8;
        }
        if (looking) {
            this.gazeStreak++;
            this.gazeLost = 0;
            if (!this.gazeContact && this.gazeStreak >= GAZE_HOLD_FRAMES) {
                this.gazeContact = true;
                this.onGaze(true);
            }
        } else {
            this.gazeLost++;
            // 单帧宽限：眨眼（~1-4 检测帧）时 gazeY 会短暂超阈，streak 衰减而非清零
            this.gazeStreak = Math.max(0, this.gazeStreak - 1);
            if (this.gazeContact && this.gazeLost >= GAZE_LOST_FRAMES) {
                this.gazeContact = false;
                this.onGaze(false);
            }
        }

        // ---- 眨眼检测（EAR：上下眼睑间距 / 眼宽，闭眼时骤降）----
        if (lm && lm.length >= 478) {
            const earR = Math.abs(lm[159].y - lm[145].y) / (Math.abs(lm[133].x - lm[33].x) || 1e-4);
            const earL = Math.abs(lm[386].y - lm[374].y) / (Math.abs(lm[263].x - lm[362].x) || 1e-4);
            const ear = (earR + earL) / 2;
            const closed = ear < 0.13;                    // 阈值：闭眼 EAR 约 0.05-0.1，睁眼 0.25-0.35
            if (closed) {
                this._eyesClosedFrames = (this._eyesClosedFrames || 0) + 1;
            } else if (this._eyesClosedFrames >= 1) {
                // 闭→睁 = 一次完整眨眼；节流防重复触发
                const now = performance.now();
                if (now - (this._lastBlinkAt || 0) > 450) {
                    this._lastBlinkAt = now;
                    this.onBlink && this.onBlink();
                }
                this._eyesClosedFrames = 0;
            } else {
                this._eyesClosedFrames = 0;
            }
        }
    }

    _detectHand(ts, result) {
        this._syncCanvasSize();
        const res = result || {};
        const allHands = (res.landmarks || []).filter((l) => l && l.length >= 21);
        // 趣味手势（作揖/比心/挥手/点赞）：事件驱动，内部带保持时长与冷却
        try {
            this.gestures.update(this.options.gestures?allHands.filter(l=>handMetrics(l).palm>=PALM_MIN):[], ts).forEach((g) => this.onGesture && this.onGesture(g));
        } catch (e) { /* 手势失败不影响基础视觉 */ }
        const lms = allHands[0];
        if (lms && lms.length >= 21) {
            const wrist = lms[0], mcp = lms[9];
            const m = handMetrics(lms);
            const palm = m.palm;
            // 掌长太小 = 手太远/不完整：不判手势（防噪声），但保留虚拟手位置反馈
            const quality = palm >= PALM_MIN;
            const reaching = palm > Math.min(HAND_REACH, .10);
            this.lastRaw={x:mcp.x,y:mcp.y};
            // 捏合：按掌长归一化后滞后判定（张开≈1.0-1.6，捏合≈0.1-0.3）
            // 捏合判定：只看指尖距比值（食指弯曲姿态不影响——真捏合时食指就是弯的）；
            // 与握拳的区分交给收紧的阈值：拳 thumb-index tip ≈0.3-0.7掌长 > PINCH_ON
            let pinching = false;
            if (quality && !this.gestures.twoHandEngaged) {
                if (this._pinching) pinching = m.pinchRatio < PINCH_OFF;
                else pinching = m.pinchRatio < PINCH_ON;
            }
            // 捏合点 = 拇指尖与食指尖中点（拿食物用精确坐标；x 镜像与掌心一致）
            const thumbTip = lms[4], indexTip = lms[8];
            const mapped=this._point((thumbTip.x+indexTip.x)/2,(thumbTip.y+indexTip.y)/2);
            const handPoint=this._point(mcp.x,mcp.y);
            const pinchX=mapped.x,pinchY=mapped.y;
            // 捏合状态变化时通知（附捏合点；保留 sx/sy 兼容旧调用方）
            if (pinching !== this._pinching) {
                this._pinching = pinching;
                this.onGrab && this.onGrab(pinching, {
                    sx:handPoint.x, sy:handPoint.y,
                    pinchX, pinchY, palm,
                });
            }

            // 打响指检测：拇指尖(4)-中指尖(12)距离从很小→骤增（弹开动作，同样按掌长归一化）
            const midTip = lms[12];
            const snapDist = Math.hypot(lms[4].x - midTip.x, lms[4].y - midTip.y) / palm;
            if (quality && this.options.gestures && this._prevSnapRatio !== undefined) {
                const snapSpeed = snapDist - this._prevSnapRatio;
                if (this._prevSnapRatio < 0.30 && snapSpeed > 0.22) {
                    const now = performance.now();
                    if (now - (this._lastSnapAt || 0) > 800) {
                        this._lastSnapAt = now;
                        this.onSnap && this.onSnap();
                    }
                }
            }
            this._prevSnapRatio = snapDist;
            // 归一化坐标 → 画布坐标（x 镜像，符合照镜子直觉）
            const sx=handPoint.x,sy=handPoint.y;
            const was = this.handState;
            this.handState = {
                present: true, reaching, sx, sy, palm, pinching,
                pinchX, pinchY, pinchDist: m.pinchDist, pinchRatio: m.pinchRatio,
                quality,
            };
            if (was.present !== true || was.reaching !== reaching) this.onHand(this.handState);
        } else {
            this._prevSnapRatio=undefined;this.lastRaw=null;
            // 手消失时释放捏合（无坐标：调用方只能按"取消"处理，不能当成功）
            if (this._pinching) {
                this._pinching = false;
                this.onGrab && this.onGrab(false, null, 'lost');
            }
            if (this.handState.present) {
                this.handState = { present: false, reaching: false, sx: 0, sy: 0, palm: 0 };
                this.onHand(this.handState);
            }
        }
    }

    /* ---------- 虚拟手平滑跟随（60fps 插值，检测帧间也不卡顿；捏合点同步平滑） ---------- */
    _followLoop() {
        if (!this.running) return;
        this._raf = requestAnimationFrame(() => this._followLoop());
        const h = this.handState;
        if (!h.present) { this._smooth.ok = false; return; }
        if (!this._smooth.ok) {
            this._smooth.x = h.sx; this._smooth.y = h.sy;
            this._smooth.px = h.pinchX || h.sx; this._smooth.py = h.pinchY || h.sy;
            this._smooth.ok = true;
        }
        this._smooth.x += (h.sx - this._smooth.x) * 0.25;
        this._smooth.y += (h.sy - this._smooth.y) * 0.25;
        // 捏合点独立平滑（系数略高：拿食物要跟手但不过冲）
        this._smooth.px += ((h.pinchX || h.sx) - this._smooth.px) * 0.30;
        this._smooth.py += ((h.pinchY || h.sy) - this._smooth.py) * 0.30;
        this.onHand({ ...h, sx: this._smooth.x, sy: this._smooth.y,
                      pinchX: this._smooth.px, pinchY: this._smooth.py, smooth: true });
    }

    get gaze() { return this.gazeContact; }
}

window.DenVision = DenVision;
DenVision.metrics = handMetrics;         // 调试/测试：21 关键点 → 归一化手势指标
DenVision.HandGestures = HandGestures;  // 调试/测试：趣味手势检测器（纯逻辑可注入）
