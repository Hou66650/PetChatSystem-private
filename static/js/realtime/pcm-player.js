/**
 * PCM 流式播放器：response.audio.delta 的 base64 PCM（24kHz 单声道 s16le）
 * 顺序调度播放（方案 §5.2）。
 *
 * - Web Audio 顺序调度：维护 nextPlayTime，append 时排到队列末尾；
 *   AudioBuffer 声明 24000 采样率，由 AudioContext 自动重采样到硬件率；
 * - interrupt()：用户插话（speech_started）时立即停掉全部已调度未播完的源并清空
 *   队列，避免旧回复拖尾（方案 §6）；
 * - 统计 underrun：追加时若调度点已落后于当前时间（网络抖动导致断流）计数。
 */
class PCMPlayer {
  constructor(opts) {
    opts = opts || {};
    this.sampleRate = opts.sampleRate || 24000; // GLM Realtime PCM 输出为 24kHz
    this._ctx = null;
    this._gain = null;
    this._sources = new Set();
    this._nextTime = 0;
    this._volume = opts.volume != null ? opts.volume : 1.0;
    this.underrunCount = 0;
    this.queuedDuration = 0; // 已调度未播完的秒数（近似）
  }

  /** 惰性创建（必须在用户手势后 resume）。 */
  ensureContext() {
    if (!this._ctx) {
      const AC = window.AudioContext || window.webkitAudioContext;
      this._ctx = new AC();
      this._gain = this._ctx.createGain();
      this._gain.gain.value = this._volume;
      this._gain.connect(this._ctx.destination);
    }
    if (this._ctx.state === 'suspended') this._ctx.resume();
    return this._ctx;
  }

  /** base64 → Int16 PCM → Float32 AudioBuffer。 */
  static base64ToFloat32(b64) {
    const bin = atob(b64);
    const n = bin.length >> 1;
    const f32 = new Float32Array(n);
    for (let i = 0; i < n; i++) {
      const lo = bin.charCodeAt(i * 2);
      const hi = bin.charCodeAt(i * 2 + 1);
      let v = (hi << 8) | lo;
      if (v >= 0x8000) v -= 0x10000;
      f32[i] = v / 32768;
    }
    return f32;
  }

  /** 追加一片 base64 PCM；返回本片调度时长（秒）。 */
  append(b64) {
    const ctx = this.ensureContext();
    const f32 = PCMPlayer.base64ToFloat32(b64);
    if (!f32.length) return 0;
    const now = ctx.currentTime;
    let when = this._nextTime;
    if (when < now + 0.02) {
      if (this._nextTime > 0 && now - this._nextTime > 0.05) this.underrunCount++;
      when = now + 0.02; // 最小启动缓冲
    }
    const buf = ctx.createBuffer(1, f32.length, this.sampleRate);
    buf.copyToChannel(f32, 0);
    const src = ctx.createBufferSource();
    src.buffer = buf;
    src.connect(this._gain);
    src.start(when);
    const dur = buf.duration;
    this._nextTime = when + dur;
    this.queuedDuration = Math.max(0, this._nextTime - now);
    src.onended = () => {
      this._sources.delete(src);
      this.queuedDuration = Math.max(0, this._nextTime - ctx.currentTime);
    };
    this._sources.add(src);
    return dur;
  }

  /**
   * 插话打断：立即停掉全部已调度的音频并清空未播放队列。
   * 返回被打断时剩余的近似秒数（供打断延迟观测）。
   */
  interrupt() {
    let remain = this.queuedDuration;
    this._sources.forEach((s) => {
      try { s.stop(); } catch (e) { /* 已结束 */ }
    });
    this._sources.clear();
    this._nextTime = 0;
    this.queuedDuration = 0;
    return remain;
  }

  pause() { if (this._ctx && this._ctx.state === 'running') this._ctx.suspend(); }
  resume() { if (this._ctx && this._ctx.state === 'suspended') this._ctx.resume(); }
  get playing() { return this.queuedDuration > 0.03; }

  reset() { this.interrupt(); }

  destroy() {
    this.interrupt();
    if (this._ctx) {
      const c = this._ctx;
      this._ctx = null;
      c.close().catch(() => {});
    }
  }
}

window.PCMPlayer = PCMPlayer;
