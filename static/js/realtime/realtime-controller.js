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
    this.surface = opts.surface || 'chat';
    this._generation = 0;
    this.petGender = opts.petGender || null;
    // synthetic=true：调试页合成语音注入模式——跳过麦克风/Worklet，
    // 由外部用 injectAudioChunk() 按 100ms 节奏喂 PCM16（含静音片）。
    this.synthetic = !!opts.synthetic;
    this.onState = opts.onState || function () {};
    this.onTranscripts = opts.onTranscripts || function () {};
    this.onMetrics = opts.onMetrics || function () {};
    this.onError = opts.onError || function () {};
    this.onWarning = opts.onWarning || function () {};
    this.onLevel = opts.onLevel || function () {};
    this.onPlayback = opts.onPlayback || function () {};
    this.lastLevel = null;
    // 指定输入设备（deviceId）：避开 ToDesk/OBS 等虚拟麦克风时使用
    this.micDeviceId = opts.micDeviceId || null;
    this.micLabel = '';

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
    const waiting={REQUESTING_PERMISSION:'正在等待麦克风授权',CONNECTING:'正在连接语音通话',RECONNECTING:'正在重新连接语音'};
    if(waiting[s]){if(!this._loadingProgress)this._loadingProgress=window.PaitLoading?.start(waiting[s],{timeout:90000});else this._loadingProgress.update(waiting[s]);}
    else if(this._loadingProgress){if(s==='ERROR')this._loadingProgress.fail('语音连接未完成，请查看通话提示');else if(s==='STOPPED')this._loadingProgress.cancel();else this._loadingProgress.done();this._loadingProgress=null;}
    this.onState(s, extra || {});
  }

  /** 麦克风申请失败 → 友好错误文案。 */
  _failPermission(e) {
    this.stop();
    const name = (e && e.name) || '';
    let msg = '无法获得麦克风权限';
    if (name === 'NotFoundError' || name === 'DevicesNotFoundError') {
      msg = '没有找到可用的麦克风设备';
    } else if (name === 'NotAllowedError' || name === 'SecurityError') {
      msg = '麦克风权限被拒绝：点浏览器地址栏的 🔒 图标，把麦克风设为允许后重试';
    } else if (name === 'NotReadableError') {
      msg = '麦克风被其他程序占用或系统层禁用，请检查 Windows 麦克风设置';
    }
    this._setState('ERROR', { reason: 'permission_denied', error: String(e) });
    this.onError({ code: name || 'permission_denied', message: msg });
  }

  /** 启动整条链路：权限 → 采集 → 连接 → READY（synthetic 模式跳过权限与采集）。 */
  async start() {
    if (this.state !== 'IDLE' && this.state !== 'ERROR' && this.state !== 'STOPPED') return;
    const remaining = Math.ceil(((RealtimeController.retryAfter || 0) - Date.now()) / 1000);
    if (remaining > 0) {
      this._setState('ERROR');
      this.onError({code:'rate_limit_error',message:`语音服务限流，请等待 ${remaining} 秒后手动开启；也可以先使用文字聊天。`});
      return;
    }
    const generation = ++this._generation;
    const current = () => generation === this._generation;
    let tPermission = 0;
    if (!this.synthetic) {
      // Preserve the user's activation: do this before the microphone promise.
      this._player = new PCMPlayer({sampleRate:24000});
      try { this._player.unlock(); } catch (e) {
        this.onPlayback({state:'error',message:'声音尚未开启，请点击“试听声音”重试。'});
      }
      this._setState('REQUESTING_PERMISSION');
      this._tPermissionStart = performance.now();
      try {
        // 麦克风约束（方案 §6）：AEC/NS/AGC 全开，单声道；sampleRate 仅作期望值；
        // 指定了 deviceId 时用 exact 强制（避开 ToDesk/OBS 等虚拟麦克风）
        const audioConstraints = {
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
          sampleRate: 16000,
        };
        if (this.micDeviceId) audioConstraints.deviceId = { exact: this.micDeviceId };
        const stream = await navigator.mediaDevices.getUserMedia({
          audio: audioConstraints,
          video: false,
        });
        if(!current()) { stream.getTracks().forEach(t=>t.stop()); return; }
        this._stream=stream;
        // 记录实际使用的设备名（诊断展示）
        try {
          const track = this._stream.getAudioTracks()[0];
          this.micLabel = (track && track.label) || '';
        } catch (e) { /* ignore */ }
      } catch (e) {
        if(!current()) return;
        // 指定设备失败时回退系统默认重试一次（设备可能被拔掉）
        if (this.micDeviceId) {
          this.micDeviceId = null;
          try {
            const stream = await navigator.mediaDevices.getUserMedia({
              audio: {
                channelCount: 1, echoCancellation: true, noiseSuppression: true,
                autoGainControl: true, sampleRate: 16000,
              },
              video: false,
            });
            if(!current()) { stream.getTracks().forEach(t=>t.stop()); return; }
        this._stream=stream;
          } catch (e2) {
            if(!current()) return;
            this._failPermission(e2);
            return;
          }
        } else {
          this._failPermission(e);
          return;
        }
      }
      tPermission = Math.round(performance.now() - this._tPermissionStart);

      try {
        // 采集上下文尽量运行在 16kHz；Worklet 内仍会真实重采样兜底
        const AC = window.AudioContext || window.webkitAudioContext;
        this._ctx = new AC({ sampleRate: 16000 });
        await this._ctx.audioWorklet.addModule('/static/js/realtime/audio-capture-worklet.js?v=2');
        if(!current()) return;
        const src = this._ctx.createMediaStreamSource(this._stream);
        this._node = new AudioWorkletNode(this._ctx, 'petchat-capture');
        this._node.port.onmessage = (e) => {
          const d = e.data;
          if (!d) return;
          if (d.type === 'chunk') this._captureChunk(d.buffer);
          else if (d.type === 'level') { this.lastLevel = d.level; this.onLevel(d.level); }
        };
        src.connect(this._node); // 不连 destination：避免把麦克风外放
      } catch (e) {
        if(!current()) return;
        this.stop();
        this._setState('ERROR', { reason: 'capture_init_failed', error: String(e) });
        this.onError({ code: 'capture_init_failed', message: '音频采集初始化失败' });
        return;
      }
    }

    this._setState('CONNECTING');
    if (!this._player) this._player = new PCMPlayer({ sampleRate: 24000 });
    this._client = this._makeClient();

    const client = this._client;
    try {
      await client.fetchSession();
      if(!current()) { client.close(); return; }
      // Block raw capture before opening a speaker-mode socket, including its handshake.
      this._speakerEnabled=!!client._session?.speakerEnabled;
      await client.connect(); // resolve 于 session.updated
    } catch (e) {
      if(!current()) return;
      if (e.status === 429) { this._onClientEvent('server.error',{code:'rate_limit_error',kind:'rate_limit'}); return; }
      this.stop();
      this._setState('ERROR', { reason: 'connect_failed', error: String(e) });
      this.onError({ code: 'connect_failed', message: `实时连接失败：${e.message || e}` });
      return;
    }
    if(!current()) return;

    const ready = { t_permission_ms: tPermission, t_ws_connect_ms: this._client.metrics.t_ws_connect_ms,
                    t_session_ready_ms: this._client.metrics.t_session_ready_ms };
    this.metrics = Object.assign({}, this._client.metrics, ready);
    this.onMetrics(this.metrics);
    this._enableSpeaker(client._session);
    this._setState('READY');
    this._startWatch();
  }

  _makeClient() {
    return new RealtimeClient({
      petId: this.petId,
      petGender: this.petGender,
      surface: this.surface,
      player: this._player,
      onEvent: (type, data) => this._onClientEvent(type, data),
      onStatus: (status, info) => {
        if (status === 'reconnecting') this._setState('RECONNECTING', info);
      },
      onMetrics: (m) => { this.metrics = Object.assign({}, m); this.onMetrics(this.metrics); },
    });
  }

  _captureChunk(buffer) {
    if(this.muted)return;
    if(this._speakerEnabled){this._speakerGate?.push(buffer);return;}
    this._client?.sendAudio(buffer);
  }

  _enableSpeaker(session) {
    this._speakerEnabled=!!session?.speakerEnabled;
    if(!this._speakerEnabled)return;
    this._speakerCounter=0;
    this._speakerGate=new SpeakerGate.Gate({
      onStart:()=>{this._speakerSource=this._client?._session;this._client?.close();this._player?.interrupt();this._setState('USER_SPEAKING');},
      onTurn:pcm=>this._speakerTurn(pcm),
      onError:e=>{this.stop();this._setState('ERROR');this.onError({code:'speaker_failed',message:e.message||'声纹辨认暂不可用，请关闭声纹模式后重试'});}
    });
    this.opts.onSpeaker?.({kind:'uncertain',name:null});
  }

  async _speakerTurn(pcm) {
    const generation=this._generation,epoch=this._speakerEpoch||0;
    const current=()=>generation===this._generation&&epoch===(this._speakerEpoch||0)&&!this.muted;
    this._setState('AI_THINKING');this.opts.onSpeaker?.({kind:'checking'});
    const abort=new AbortController();this._speakerAbort=abort;
    const timer=setTimeout(()=>abort.abort(),20000);
    try{
      const source=this._speakerSource;
      const q=new URLSearchParams({petId:this.petId,surface:this.surface,gender:this.petGender||''});
      const response=await fetch('/api/voiceprint/identify?'+q,{method:'POST',headers:{'Content-Type':'application/octet-stream','X-Profile-Scope':source.profileScope},body:pcm,signal:abort.signal});
      const result=await response.json();if(!current())return;
      if(!response.ok)throw Error(result.error||'声纹辨认失败');
      this.speaker=result;this.opts.onSpeaker?.(result);
      // A fresh conversation per utterance prevents one speaker inheriting another's transcript.
      const client=this._makeClient();this._client=client;
      if(source.expiresAt*1000<Date.now()+30000)await client.fetchSession();else client._session={...source,config:{...source.config}};
      if(!current()){client.close();return;}
      client._session.config.instructions=result.instructions;
      client._turnId=++this._speakerCounter*100;
      let connectTimer;
      try{await Promise.race([client.connect(),new Promise((_,reject)=>{connectTimer=setTimeout(()=>reject(Error('语音连接超时，请重新开始通话')),10000);})]);}finally{clearTimeout(connectTimer);}
      if(!current()){client.close();return;}
      // Complete PCM turn plus trailing silence is sent only after session.updated.
      for(let i=0;i<pcm.byteLength;i+=3200)client.sendAudio(pcm.slice(i,i+3200));
      client.sendAudio(new Int16Array(16000).buffer);
    }catch(e){if(current()){
      if(e.status===429)this._onClientEvent('server.error',{code:'rate_limit_error',kind:'rate_limit'});
      else throw e;
    }}finally{clearTimeout(timer);if(this._speakerAbort===abort)this._speakerAbort=null;}
  }

  /** 由播放器/客户端事件驱动的状态观察。 */
  _startWatch() {
    this._watchTimer = setInterval(() => {
      this._reportPlayback();
      if (this.state === 'AI_SPEAKING' && this._player && !this._player.playing) {
        this._setState('READY');
      }
      if(this.state==='READY'&&!this._player?.playing&&this._client?.needsContextRenewal)void this._client.renewContext();
    }, 250);
  }

  _reportPlayback() {
    if (!this._player) return;
    const state=this._player.outputState, received=this._player.receivedChunks || 0;
    this.onPlayback({state,received,message:state==='running'
      ? (received ? '已收到回复声音；听不到时请检查浏览器是否静音及电脑输出设备。' : '声音已开启，可以点击“试听声音”检查耳机或扬声器。')
      : '浏览器尚未开启声音，请点击“试听声音”。'});
  }

  testPlayback() {
    if (!this._player) return;
    try { this._player.testTone(); this._reportPlayback(); }
    catch (e) { this.onPlayback({state:'error',message:'无法播放声音，请检查浏览器声音权限或输出设备。'}); }
  }

  _onClientEvent(type, data) {
    switch (type) {
      case 'input_audio_buffer.speech_started':
        this._setState('USER_SPEAKING');
        this.onTranscripts({ userText: '', assistantText: '', done: false, reset:true, turnId:data.turnId });
        break;
      case 'input_audio_buffer.speech_stopped':
        if (this.state === 'USER_SPEAKING') this._setState('AI_THINKING');
        break;
      case 'response.created':
        this._roundAudioChunks = 0;
        this._playbackResponseId = data.response?.id;
        if (this.state !== 'USER_SPEAKING') this._setState('AI_THINKING');
        break;
      case 'response.audio.delta':
        if (!data.response_id || data.response_id === this._playbackResponseId)
          this._roundAudioChunks = (this._roundAudioChunks || 0) + (data.delta ? 1 : 0);
        if (this.state === 'AI_THINKING' || this.state === 'READY') this._setState('AI_SPEAKING');
        break;
      case 'response.done':
        if (!data.customVoice && data.response?.id === this._playbackResponseId && !this._roundAudioChunks && data.response?.status !== 'cancelled')
          this.onWarning({code:'reply_audio_missing',message:'这轮没有收到回复音频，请再说一次。'});
        break;
      case 'custom.audio.ready':
        this._roundAudioChunks=1;this._setState('AI_SPEAKING');this._reportPlayback();break;
      case 'custom.audio.error':
        this.onWarning({code:'custom_voice_failed',message:data.message});
        if(this.state==='AI_THINKING')this._setState('READY');break;
      case 'playback.error':
        this.onPlayback({state:'error',message:'回复声音播放失败，请点击“试听声音”检查播放。'});
        break;
      case 'conversation.item.input_audio_transcription.completed':
        this.onTranscripts({ userText: data.transcript || '', assistantText: '', done: false, finalUserText:true, turnId:data.turnId });
        break;
      case 'response.audio_transcript.delta':
        // 增量字幕：由页面累积，这里只保证状态
        this.onTranscripts({ assistantDelta: data.delta || '', done: false });
        break;
      case 'round.done':
        this.onTranscripts({ ...data, done: true });
        break;
      case 'session.updated':
        if (this.state === 'RECONNECTING') this._setState('READY');
        break;
      case 'server.error': {
        const code = String(data.code || 'unknown').replace(/[^a-zA-Z0-9_.-]/g, '').slice(0,64);
        if(code==='context_length_exceeded'){
          this.stop();this._setState('ERROR',{reason:'context_limit',code});
          this.onTranscripts({reset:true,userText:'',assistantText:'',done:false});
          this.onError({code,message:'这次语音携带的信息超过服务上限，通话已停止。请重新开启语音；已保存的记忆和岛屿数据不会删除。'});break;
        }
        if(code==='downstream_reconnect_exceeded'){
          this.stop();
          this._setState('ERROR',{reason:'provider_unavailable',code});
          this.onError({code,message:'语音供应商的内部连接暂时失败，本次通话已停止。请稍后重新开启，也可以先用文字聊天。'});
          break;
        }
        if (code === 'rate_limit_error' || data.kind === 'rate_limit') {
          RealtimeController.retryAfter = Date.now() + 30000;
          this.stop();
          this._setState('ERROR', {reason:'rate_limit',code});
          this.onPlayback({state:'error',message:'语音服务限流，本轮未正常完成；无需调整扬声器。'});
          this.onError({code:'rate_limit_error',message:'语音服务请求过于频繁，已停止本次通话。请至少等待30秒后手动开启，或先切换文字聊天；如果持续出现，需要检查服务端并发或额度限制。'});
          break;
        }
        if (data.recoverable) {
          // A config rejection does not invalidate the reply currently playing.
          this.onWarning({code, kind:data.kind, message:data.kind === 'profile_update'
            ? '记忆已保存；语音陪伴设置将在下次通话生效。当前可以继续聊。'
            : '这一轮语音暂时出错，可以直接再说一次。（' + code + '）'});
          if (data.kind !== 'profile_update' && this.state === 'AI_THINKING') this._setState('READY');
          break;
        }
        this.stop();
        this._setState('ERROR', {reason:'server_error',code});
        this.onError({code, message:'语音连接已停止（错误码：' + code + '），请重新开启语音。'});
        break;
      }
      default:
        break;
    }
  }

  /** 静音开关：Worklet 停止产出（麦克风保持打开，可随时恢复/插话）。 */
  setMuted(m) {
    this.muted = !!m;
    if(this.muted&&this._speakerGate){this._speakerEpoch=(this._speakerEpoch||0)+1;this._speakerAbort?.abort();this._speakerGate.reset();}
    if (this._node) this._node.port.postMessage({ type: 'mute', value: this.muted });
  }

  /** 调试页合成注入：绕过麦克风直接把 PCM16 片喂给客户端。 */
  injectAudioChunk(arrayBuffer) {
    this._captureChunk(arrayBuffer);
  }

  /** 结束会话：销毁 WS、播放器、采集。 */
  stop() {
    ++this._generation;
    this._speakerGate?.close();this._speakerGate=null;this._speakerAbort?.abort();
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
