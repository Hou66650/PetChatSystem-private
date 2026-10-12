/**
 * AudioWorklet 采集处理器：单声道 Float32 → 16kHz 重采样 → little-endian PCM16。
 *
 * 方案 §5.1：
 * - 禁止使用已废弃的 ScriptProcessorNode；
 * - 不能相信 getUserMedia({sampleRate:16000}) 必然生效：无论 AudioContext 实际
 *   运行在什么采样率（常见 48kHz），都在 Worklet 内用线性插值真实重采样到 16kHz；
 * - 每 100ms 一片（1600 采样），通过 transferable ArrayBuffer 回传主线程。
 *
 * 主线程消息：
 *   worklet → 主线程 {type:'chunk', buffer:ArrayBuffer(PCM16 LE), sampleRate:16000}
 *   主线程 → worklet {type:'mute', value:boolean}   静音=不再产出音频片
 */
class CaptureProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this._targetRate = 16000;
    this._chunkSamples = Math.round(this._targetRate * 0.1); // 1600 ≈ 100ms
    this._buf = new Float32Array(this._chunkSamples);
    this._filled = 0;
    // 重采样状态：输入侧浮点游标（相对上一帧末尾样本的相位）
    this._lastSample = 0;
    this._frac = 0; // 上一帧消费到的分数位置
    this._muted = false;
    this.port.onmessage = (e) => {
      const d = e.data;
      if (d && d.type === 'mute') this._muted = !!d.value;
    };
  }

  /** 线性插值重采样：input(任意率) → 16kHz Float32Array，跨 process() 调用保持相位。 */
  _resample(input, inRate) {
    if (inRate === this._targetRate) return input;
    const step = inRate / this._targetRate; // 每产出 1 个样本消耗的输入样本数
    const out = [];
    let pos = this._frac; // 相对 input[-1]（即上一帧最后一个样本）的位置，从 1.0 起有效
    while (pos < input.length) {
      const i = Math.floor(pos);
      const t = pos - i;
      const s0 = i === -1 ? this._lastSample : input[i];
      const s1 = input[Math.min(i + 1, input.length - 1)];
      out.push(s0 + (s1 - s0) * t);
      pos += step;
    }
    this._frac = pos - input.length; // 留给下一帧的剩余相位（1..1+step）
    this._lastSample = input[input.length - 1];
    return out;
  }

  process(inputs) {
    const ch = inputs[0] && inputs[0][0];
    if (!ch || !ch.length) return true;
    if (this._muted) return true; // 静音期间不产出（不向服务端发帧）
    const resampled = this._resample(ch, sampleRate);
    for (let i = 0; i < resampled.length; i++) {
      this._buf[this._filled++] = resampled[i];
      if (this._filled === this._chunkSamples) {
        const pcm = new Int16Array(this._filled);
        for (let j = 0; j < this._filled; j++) {
          let s = this._buf[j];
          if (s > 1) s = 1; else if (s < -1) s = -1;
          pcm[j] = s < 0 ? s * 0x8000 : s * 0x7fff;
        }
        this.port.postMessage(
          { type: 'chunk', buffer: pcm.buffer, sampleRate: this._targetRate },
          [pcm.buffer],
        );
        this._buf = new Float32Array(this._chunkSamples);
        this._filled = 0;
      }
    }
    return true;
  }
}

registerProcessor('petchat-capture', CaptureProcessor);
