/**
 * 实时会话唯一状态机（方案 §5.4）。
 *
 * IDLE → REQUESTING_PERMISSION → CONNECTING → READY
 * READY ⇄ USER_SPEAKING / AI_THINKING / AI_SPEAKING
 * 任意 → RECONNECTING / ERROR / STOPPED
 *
 * UI、字幕、按钮只读该状态，禁止各组件自行猜测。
 * 同时负责：麦克风采集（AudioWorklet 16kHz）、把 audio.delta 喂给播放器、
 * 收集性能埋点、断线状态展示与结束降级。
 */
class RealtimeController {
  /**
   * @param opts {petId, petGender?, onState(state,extra),
   *              onTranscripts({userText, assistantText, done}),
   *              onMetrics(metrics), onError(err)}
   */
  constructor(opts) {
    this.opts = opts || {};
    this.petId = opts.petId;
    this.petGender = opts.petGender || null;
    // synthetic=true：调试页合成语音注入模式——跳过麦克风/Worklet，
    // 由外部用 injectAudioChunk() 按 100ms 节奏喂 PCM16（含静音片）。
    this.synthetic = !!opts.synthetic;
    this.onState = opts.onState || function () {};
    this.onTranscripts = opts.onTranscripts || function () {};
    this.onMetrics = opts.onMetrics || function () {};
    this.onError = opts.onError || function () {};

    this.state = 'IDLE';
    this.muted = false;
    this.metrics = null;

    this._player = null;
    this._client = null;
    this._ctx = null;          // 16kHz AudioContext（采集）
    this._stream = null;       // MediaStream（保持整场会话打开，方案 §6）
    this._node = null;         // AudioWorkletNode
    this._watchTimer = null;
    this._tPermissionStart = 0;
  }

  _setState(s, extra) {
    this.state = s;
    this.onState(s, extra || {});
  }

  /** 启动整条链路：权限 → 采集 → 连接 → READY（synthetic 模式跳过权限与采集）。 */
  async start() {
    if (this.state !== 'IDLE' && this.state !== 'ERROR' && this.state !== 'STOPPED') return;
    let tPermission = 0;
    if (!this.synthetic) {
      this._setState('REQUESTING_PERMISSION');
      this._tPermissionStart = performance.now();
      try {
        // 麦克风约束（方案 §6）：AEC/NS/AGC 全开，单声道；sampleRate 仅作期望值
        this._stream = await navigator.mediaDevices.getUserMedia({
          audio: {
            channelCount: 1,
            echoCancellation: true,
            noiseSuppression: true,
            autoGainControl: true,
            sampleRate: 16000,
          },
          video: false,
        });
      } catch (e) {
        this._setState('ERROR', { reason: 'permission_denied', error: String(e) });
        this.onError({ code: 'permission_denied', message: '无法获得麦克风权限' });
        return;
      }
      tPermission = Math.round(performance.now() - this._tPermissionStart);

      try {
        // 采集上下文尽量运行在 16kHz；Worklet 内仍会真实重采样兜底
        const AC = window.AudioContext || window.webkitAudioContext;
        this._ctx = new AC({ sampleRate: 16000 });
        await this._ctx.audioWorklet.addModule('/static/js/realtime/audio-capture-worklet.js');
        const src = this._ctx.createMediaStreamSource(this._stream);
        this._node = new AudioWorkletNode(this._ctx, 'petchat-capture');
        this._node.port.onmessage = (e) => {
          if (e.data && e.data.type === 'chunk') this._client && this._client.sendAudio(e.data.buffer);
        };
        src.connect(this._node); // 不连 destination：避免把麦克风外放
      } catch (e) {
        this._setState('ERROR', { reason: 'capture_init_failed', error: String(e) });
        this.onError({ code: 'capture_init_failed', message: '音频采集初始化失败' });
        this.stop();
        return;
      }
    }

    this._setState('CONNECTING');
    this._player = new PCMPlayer({ sampleRate: 24000 });
    this._client = new RealtimeClient({
      petId: this.petId,
      petGender: this.petGender,
      player: this._player,
      onEvent: (type, data) => this._onClientEvent(type, data),
      onStatus: (status, info) => {
        if (status === 'reconnecting') this._setState('RECONNECTING', info);
      },
      onMetrics: (m) => { this.metrics = Object.assign({}, m); this.onMetrics(this.metrics); },
    });

    try {
      await this._client.fetchSession();
      await this._client.connect(); // resolve 于 session.updated
    } catch (e) {
      this._setState('ERROR', { reason: 'connect_failed', error: String(e) });
      this.onError({ code: 'connect_failed', message: `实时连接失败：${e.message || e}` });
      this.stop();
      return;
    }

    const ready = { t_permission_ms: tPermission, t_ws_connect_ms: this._client.metrics.t_ws_connect_ms,
                    t_session_ready_ms: this._client.metrics.t_session_ready_ms };
    this.metrics = Object.assign({}, this._client.metrics, ready);
    this.onMetrics(this.metrics);
    this._setState('READY');
    this._startWatch();
  }

  /** 由播放器/客户端事件驱动的状态观察。 */
  _startWatch() {
    this._watchTimer = setInterval(() => {
      if (this.state === 'AI_SPEAKING' && this._player && !this._player.playing) {
        this._setState('READY');
      }
    }, 250);
  }

  _onClientEvent(type, data) {
    switch (type) {
      case 'input_audio_buffer.speech_started':
        this._setState('USER_SPEAKING');
        this.onTranscripts({ userText: '', assistantText: '', done: false });
        break;
      case 'input_audio_buffer.speech_stopped':
        if (this.state === 'USER_SPEAKING') this._setState('AI_THINKING');
        break;
      case 'response.created':
        if (this.state !== 'USER_SPEAKING') this._setState('AI_THINKING');
        break;
      case 'response.audio.delta':
        if (this.state === 'AI_THINKING' || this.state === 'READY') this._setState('AI_SPEAKING');
        break;
      case 'conversation.item.input_audio_transcription.completed':
        this.onTranscripts({ userText: data.transcript || '', assistantText: '', done: false });
        break;
      case 'response.audio_transcript.delta':
        // 增量字幕：由页面累积，这里只保证状态
        this.onTranscripts({ assistantDelta: data.delta || '', done: false });
        break;
      case 'round.done':
        this.onTranscripts({ userText: data.userText, assistantText: data.assistantText, done: true });
        break;
      case 'session.updated':
        if (this.state === 'RECONNECTING') this._setState('READY');
        break;
      case 'server.error':
        break;
      default:
        break;
    }
  }

  /** 静音开关：Worklet 停止产出（麦克风保持打开，可随时恢复/插话）。 */
  setMuted(m) {
    this.muted = !!m;
    if (this._node) this._node.port.postMessage({ type: 'mute', value: this.muted });
  }

  /** 调试页合成注入：绕过麦克风直接把 PCM16 片喂给客户端。 */
  injectAudioChunk(arrayBuffer) {
    this._client && this._client.sendAudio(arrayBuffer);
  }

  /** 结束会话：销毁 WS、播放器、采集。 */
  stop() {
    if (this._watchTimer) { clearInterval(this._watchTimer); this._watchTimer = null; }
    if (this._client) { this._client.close(); this._client = null; }
    if (this._player) { this._player.destroy(); this._player = null; }
    if (this._node) { try { this._node.disconnect(); } catch (e) {} this._node = null; }
    if (this._ctx) { const c = this._ctx; this._ctx = null; c.close().catch(() => {}); }
    if (this._stream) { this._stream.getTracks().forEach((t) => t.stop()); this._stream = null; }
    this._setState('STOPPED');
  }

  get finalMetrics() {
    const underruns = this._player ? this._player.underrunCount : 0;
    return Object.assign({}, this.metrics, {
      audio_underrun_count: underruns,
      reconnect_count: this._client ? this._client.metrics.reconnect_count : 0,
    });
  }
}

window.RealtimeController = RealtimeController;
