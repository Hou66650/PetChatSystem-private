/**
 * GLM Realtime WebSocket 客户端（方案 §5.3）。
 *
 * - 先 POST /api/realtime/session 拿短期 JWT + 服务端会话配置；
 * - 浏览器 WS 不能自定义 Header，按官方 SDK 方式把 JWT 放在
 *   `?Authorization=<jwt>` query 参数直连 wss://open.bigmodel.cn；
 * - 收到 session.created 后发送完整 session.update（配置以服务端下发为准，
 *   前端不自行拼人设/音色）；
 * - 断线重连：1/2/4/8s、上限 15s + 0~300ms 抖动；重连一律重新取 JWT；
 *   重连后不重放旧音频缓存，避免重复回答；
 * - 每条客户端事件带唯一 event_id 与毫秒 client_timestamp。
 *
 * 依赖：外部传入 PCMPlayer 实例（audio.delta 直接喂给它，speech_started 时打断）。
 */
class RealtimeClient {
  /**
   * @param opts {petId, petGender?, player, onEvent(type,data), onStatus(status,info),
   *              onFatal(err), onMetrics(metrics)}
   */
  constructor(opts) {
    this.petId = opts.petId;
    this.petGender = opts.petGender || null;
    this.player = opts.player;
    this.onEvent = opts.onEvent || function () {};
    this.onStatus = opts.onStatus || function () {};
    this.onFatal = opts.onFatal || function () {};
    this.onMetrics = opts.onMetrics || function () {};

    this._ws = null;
    this._session = null;      // /api/realtime/session 响应
    this._sid = '';            // 服务端 session.id
    this._closedByUser = false;
    this._reconnectAttempts = 0;
    this._reconnectTimer = null;
    this._pendingAudio = [];   // 断线期间到达的采集片直接丢弃（不重放）

    // 一轮对话的累计器
    this._round = { userText: '', assistantText: '', responseId: '', itemId: '' };

    // 延迟埋点（方案 §8，只记耗时不记音频）
    this.metrics = {
      t_ws_connect_ms: null,
      t_session_ready_ms: null,
      t_speech_end_to_first_text_ms: null,
      t_speech_end_to_first_audio_ms: null,
      interrupt_latency_ms: null,
      reconnect_count: 0,
      error_code: null,
    };
    this._tConnectStart = 0;
    this._tSpeechEnd = 0;
    this._seenFirstText = false;
    this._seenFirstAudio = false;
  }

  /** 拉取短期会话（JWT 过期/重连时也会重新调用）。 */
  async fetchSession() {
    const r = await fetch('/api/realtime/session', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ petId: this.petId, petGender: this.petGender }),
      cache: 'no-store',
    });
    if (!r.ok) {
      let msg = `session http ${r.status}`;
      try { const j = await r.json(); if (j && j.error) msg = j.error; } catch (e) {}
      const err = new Error(msg);
      err.status = r.status;
      throw err;
    }
    this._session = await r.json();
    return this._session;
  }

  /** 建立 WS 连接并完成 session.update。resolve 于 session.updated。 */
  connect() {
    return new Promise((resolve, reject) => {
      let settled = false;
      const done = (err) => {
        if (settled) return;
        settled = true;
        if (err) reject(err); else resolve();
      };
      const s = this._session;
      const url = `${s.wsBaseUrl}?Authorization=${encodeURIComponent(s.token)}`;
      this._tConnectStart = performance.now();
      this.onStatus('connecting');
      const ws = new WebSocket(url);
      this._ws = ws;

      ws.onopen = () => {
        this.metrics.t_ws_connect_ms = Math.round(performance.now() - this._tConnectStart);
      };
      ws.onmessage = (ev) => {
        let data;
        try { data = JSON.parse(ev.data); } catch (e) { return; }
        this._dispatch(data, done);
      };
      ws.onerror = () => { /* onclose 会跟进 */ };
      ws.onclose = (ev) => {
        this._ws = null;
        if (this._closedByUser) { done(new Error('closed')); return; }
        done(new Error(`ws closed (${ev.code})`));
        this._scheduleReconnect();
      };
    });
  }

  /** 服务端事件分发：协议机制内部消化，业务通过 onEvent 透出。 */
  _dispatch(data, connectDone) {
    const type = data.type || '';
    this.onEvent(type, data);
    switch (type) {
      case 'session.created':
        this._sid = (data.session && data.session.id) || '';
        this._sendSessionUpdate();
        break;
      case 'session.updated':
        this.metrics.t_session_ready_ms = Math.round(performance.now() - this._tConnectStart);
        this.onStatus('ready');
        connectDone && connectDone(null);
        break;
      case 'input_audio_buffer.speech_started': {
        // Server VAD 模式下打断由服务端托管，客户端只需清空本地播放（方案 §6）。
        // interrupt_latency_ms = 收到 speech_started → 本地旧音频全部停止的实测耗时；
        // interrupt_cleared_ms = 被清掉未播完的音频量（毫秒）。
        const t0 = performance.now();
        const remainSec = this.player.interrupt();
        this.metrics.interrupt_latency_ms = Math.round(performance.now() - t0);
        this.metrics.interrupt_cleared_ms = Math.round(remainSec * 1000);
        this.onMetrics(this.metrics);
        this._resetRound();
        break;
      }
      case 'input_audio_buffer.speech_stopped':
        this._tSpeechEnd = performance.now();
        this._seenFirstText = false;
        this._seenFirstAudio = false;
        break;
      case 'input_audio_buffer.committed':
        this._round.itemId = data.item_id || '';
        break;
      case 'conversation.item.input_audio_transcription.completed':
        this._round.userText = data.transcript || '';
        break;
      case 'response.created':
        this._round.responseId = (data.response && data.response.id) || '';
        break;
      case 'response.audio.delta': {
        if (!this._seenFirstAudio) {
          this._seenFirstAudio = true;
          if (this._tSpeechEnd) {
            this.metrics.t_speech_end_to_first_audio_ms =
              Math.round(performance.now() - this._tSpeechEnd);
            this.onMetrics(this.metrics);
          }
        }

        this.player.append(data.delta);

        break;
      }
      case 'response.audio_transcript.delta': {
        if (!this._seenFirstText) {
          this._seenFirstText = true;
          if (this._tSpeechEnd) {
            this.metrics.t_speech_end_to_first_text_ms =
              Math.round(performance.now() - this._tSpeechEnd);
            this.onMetrics(this.metrics);
          }
        }
        this._round.assistantText += data.delta || '';
        break;
      }
      case 'response.done': {
        const final = {
          userText: this._round.userText,
          assistantText: this._round.assistantText,
          itemId: this._round.itemId,
          responseId: this._round.responseId,
        };
        this.onEvent('round.done', final);

        // 播完队列里的余量即回到 READY（由 controller 观察 player 状态）
        break;
      }
      case 'error': {
        const code = (data.error && data.error.code) || 'unknown';
        this.metrics.error_code = code;
        console.warn('[realtime] server error:', code, data.error && data.error.message);
        this.onEvent('server.error', data.error || {});
        break;
      }
      default:
        break;
    }
  }

  /** session.update：配置全部来自服务端下发的 config（方案 §4.2 返回结构）。 */
  _sendSessionUpdate() {
    const c = this._session.config;
    this._send({
      type: 'session.update',
      session: {
        turn_detection: c.turn_detection || { type: 'server_vad' },
        instructions: c.instructions || '',
        input_audio_format: c.input_audio_format || 'pcm16',
        output_audio_format: c.output_audio_format || 'pcm',
        beta_fields: { chat_mode: c.chat_mode || 'audio', tts_source: 'e2e' },
        voice: c.voice || 'default',
      },
    });
  }

  _send(obj) {
    if (!this._ws || this._ws.readyState !== 1) return false;
    obj.event_id = obj.event_id || (crypto.randomUUID ? crypto.randomUUID()
      : `evt-${Date.now()}-${Math.random().toString(36).slice(2)}`);
    obj.client_timestamp = Date.now();
    this._ws.send(JSON.stringify(obj));
    return true;
  }

  /** 发送一片 PCM16 16kHz ArrayBuffer（由采集 Worklet / 调试注入产生）。 */
  sendAudio(arrayBuffer) {
    if (!arrayBuffer || !arrayBuffer.byteLength) return;
    if (!this._ws || this._ws.readyState !== 1) return; // 断线期间直接丢弃，不缓存重放
    const u8 = new Uint8Array(arrayBuffer);
    let bin = '';
    const CH = 0x8000;
    for (let i = 0; i < u8.length; i += CH) {
      bin += String.fromCharCode.apply(null, u8.subarray(i, i + CH));
    }
    this._send({ type: 'input_audio_buffer.append', audio: btoa(bin) });
  }

  /** 断线重连：退避 1/2/4/8…15s + 0~300ms 抖动；重新取 JWT；不重放旧音频。 */
  _scheduleReconnect() {
    if (this._closedByUser) return;
    if (this._reconnectTimer) return;
    const attempt = this._reconnectAttempts++;
    const delay = Math.min(Math.pow(2, attempt), 15) * 1000 + Math.random() * 300;
    this.metrics.reconnect_count++;
    this.onStatus('reconnecting', { attempt, delayMs: Math.round(delay) });
    this._reconnectTimer = setTimeout(async () => {
      this._reconnectTimer = null;
      try {
        await this.fetchSession();          // 重新取 JWT（旧的可能已过期）
        await this.connect();               // session.created → session.update → ready
        this._reconnectAttempts = 0;
      } catch (e) {
        if (!this._closedByUser) this._scheduleReconnect();
      }
    }, delay);
  }

  /** 用户主动结束：停重连、关 WS。 */
  close() {
    this._closedByUser = true;
    if (this._reconnectTimer) { clearTimeout(this._reconnectTimer); this._reconnectTimer = null; }
    this._pendingAudio = [];
    if (this._ws) {
      try { this._ws.close(); } catch (e) { /* ignore */ }
      this._ws = null;
    }
  }

  _resetRound() {
    this._round = { userText: '', assistantText: '', responseId: '', itemId: '' };
  }
}

window.RealtimeClient = RealtimeClient;
