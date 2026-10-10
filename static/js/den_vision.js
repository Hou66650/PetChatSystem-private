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
const HAND_REACH = 0.24;        // 掌距（腕→中指根）超过即视为"伸手靠近"

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
        this.onError = () => {};
        this._smooth = { x: 0, y: 0, ok: false };   // 虚拟手平滑位置
        this._raf = null;
    }

    /* 启动：摄像头 → 模型 → 检测循环
       target：虚拟手/触摸判定所用主画布元素（坐标换算基准，勿传预览小窗） */
    async start(videoEl, callbacks = {}, target = null) {
        if (this.running) return true;
        this.onGaze = callbacks.onGaze || this.onGaze;
        this.onHand = callbacks.onHand || this.onHand;
        this.onError = callbacks.onError || this.onError;
        try {
            // 1) 摄像头（前置，低分辨率即可）
            this.stream = await navigator.mediaDevices.getUserMedia({
                video: { facingMode: 'user', width: { ideal: 640 }, height: { ideal: 480 } },
                audio: false,
            });
        } catch (e) {
            this.onError('camera', e);
            return false;
        }
        this.video = videoEl;
        try {
            videoEl.srcObject = this.stream;
            // play() 可能因空流/权限挂起：超时放行，检测循环自带 readyState 守卫
            await Promise.race([
                videoEl.play().catch(() => {}),
                new Promise((r) => setTimeout(r, 1500)),
            ]);
        } catch (e) { /* 出错不阻断：摄像头无帧时循环会安全跳过 */ }

        // 2) 模型（GPU 优先，失败回落 CPU）
        try {
            const fileset = await FilesetResolver.forVisionTasks(WASM_PATH);
            const delegate = navigator.gpu ? 'GPU' : 'CPU';
            try {
                this.face = await FaceLandmarker.createFromOptions(fileset, {
                    baseOptions: { modelAssetPath: FACE_MODEL, delegate },
                    runningMode: 'VIDEO', numFaces: 1, outputFaceBlendshapes: false,
                });
                this.hand = await HandLandmarker.createFromOptions(fileset, {
                    baseOptions: { modelAssetPath: HAND_MODEL, delegate },
                    runningMode: 'VIDEO', numHands: 1,
                });
            } catch (e) {
                // 个别机器 GPU 委托不兼容 → CPU 重试
                this.face = await FaceLandmarker.createFromOptions(fileset, {
                    baseOptions: { modelAssetPath: FACE_MODEL, delegate: 'CPU' },
                    runningMode: 'VIDEO', numFaces: 1,
                });
                this.hand = await HandLandmarker.createFromOptions(fileset, {
                    baseOptions: { modelAssetPath: HAND_MODEL, delegate: 'CPU' },
                    runningMode: 'VIDEO', numHands: 1,
                });
            }
        } catch (e) {
            this.stop();
            this.onError('model', e);
            return false;
        }

        this.running = true;
        this.target = target || videoEl;
        this.timer = setInterval(() => this._detect(), DETECT_MS);
        this._followLoop();
        return true;
    }

    stop() {
        this.running = false;
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
        try {
            this._detectGaze(ts);
            this._detectHand(ts);
            this._errStreak = 0;
        } catch (e) {
            // 推理异常（如 GPU 委托运行中失效）：连续多次则自动停止，避免每 100ms 报错
            this._errStreak = (this._errStreak || 0) + 1;
            if (this._errStreak >= 3) {
                this.stop();
                this.onError('runtime', e);
            }
        }
    }

    _detectGaze(ts) {
        const res = this.face.detectForVideo(this.video, ts);
        const lm = res.faceLandmarks && res.faceLandmarks[0];
        let looking = false;
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
            this.gazeStreak = 0;
            if (this.gazeContact && this.gazeLost >= GAZE_LOST_FRAMES) {
                this.gazeContact = false;
                this.onGaze(false);
            }
        }
    }

    _detectHand(ts) {
        this._syncCanvasSize();
        const res = this.hand.detectForVideo(this.video, ts);
        const lms = res.landmarks && res.landmarks[0];
        if (lms && lms.length >= 21) {
            const wrist = lms[0], mcp = lms[9];
            const palm = Math.hypot(mcp.x - wrist.x, mcp.y - wrist.y);
            const reaching = palm > HAND_REACH;
            // 归一化坐标 → 画布坐标（x 镜像，符合照镜子直觉）
            const sx = (1 - mcp.x) * this.canvasSize.w;
            const sy = mcp.y * this.canvasSize.h;
            const was = this.handState;
            this.handState = { present: true, reaching, sx, sy, palm };
            if (was.present !== true || was.reaching !== reaching) this.onHand(this.handState);
        } else if (this.handState.present) {
            this.handState = { present: false, reaching: false, sx: 0, sy: 0, palm: 0 };
            this.onHand(this.handState);
        }
    }

    /* ---------- 虚拟手平滑跟随（60fps 插值，检测帧间也不卡顿） ---------- */
    _followLoop() {
        if (!this.running) return;
        this._raf = requestAnimationFrame(() => this._followLoop());
        const h = this.handState;
        if (!h.present) { this._smooth.ok = false; return; }
        if (!this._smooth.ok) { this._smooth.x = h.sx; this._smooth.y = h.sy; this._smooth.ok = true; }
        this._smooth.x += (h.sx - this._smooth.x) * 0.25;
        this._smooth.y += (h.sy - this._smooth.y) * 0.25;
        this.onHand({ ...h, sx: this._smooth.x, sy: this._smooth.y, smooth: true });
    }

    get gaze() { return this.gazeContact; }
}

window.DenVision = DenVision;
