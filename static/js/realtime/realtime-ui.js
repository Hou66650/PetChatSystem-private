/**
 * 实时语音面板（方案 §5.5）：聊天页 gpt_me.html 的接入门面。
 *
 * - 自建面板 DOM（状态/字幕/静音/结束/切换文字），不侵入聊天页模板；
 * - 一轮结束（round.done）才回调 onRound 写历史：一条最终用户消息 + 一条最终宠物消息，
 *   增量字幕只在面板内展示，绝不重复落历史；
 * - 失败/停止提供"切换文字聊天"，不无限转圈；文字链路完全不受影响；
 * - 切换宠物：调用方在 pet 切换后调 restartForPet()，内部销毁旧 WS/播放器再重建
 *   （方案 §7）。
 */
(function () {
  'use strict';

  var STATE_TEXT = {
    IDLE: '未开始',
    REQUESTING_PERMISSION: '请授权麦克风…',
    CONNECTING: '连接中…',
    READY: '就绪，直接说话吧',
    USER_SPEAKING: '🎤 正在听你说…',
    AI_THINKING: '🐾 想一想…',
    AI_SPEAKING: '🔊 正在回答…（可随时插话）',
    RECONNECTING: '信号不好，重连中…',
    ERROR: '出错了，已停止',
    STOPPED: '已结束',
  };

  function RealtimeUI(opts) {
    this.getPet = opts.getPet || function () { return { id: 1, name: '宠物', avatar: '' }; };
    this.getGender = opts.getGender || function () { return null; };
    // onRound(userText, assistantText, pet)：仅在一轮完整结束时调用一次
    this.onRound = opts.onRound || function () {};
    this.onError = opts.onError || function () {};
    this.controller = null;
    this._panel = null;
    this._aiText = '';
    this._injectStyle();
  }

  RealtimeUI.prototype._injectStyle = function () {
    if (document.getElementById('rt-voice-style')) return;
    var css = [
      '#rt-panel{position:fixed;left:50%;transform:translateX(-50%);bottom:96px;z-index:320;',
      'width:min(560px,92vw);background:#fffdf8;border:1px solid #eadfd2;border-radius:16px;',
      'box-shadow:0 8px 30px rgba(74,59,50,.18);padding:14px 16px;font-size:14px;color:#4a3b32;}',
      '#rt-panel[hidden]{display:none;}',
      '#rt-head{display:flex;align-items:center;gap:8px;margin-bottom:8px;}',
      '#rt-dot{width:10px;height:10px;border-radius:50%;background:#f59e0b;flex:none;}',
      '#rt-dot.speak{background:#22c55e;animation:rt-pulse 1s infinite;}',
      '#rt-dot.think{background:#f59e0b;animation:rt-pulse 1.6s infinite;}',
      '#rt-dot.err{background:#ef4444;animation:none;}',
      '@keyframes rt-pulse{0%,100%{opacity:1}50%{opacity:.35}}',
      '#rt-state{font-weight:600;flex:1;}',
      '#rt-sub{background:#faf6ef;border-radius:10px;padding:8px 10px;min-height:20px;line-height:1.6;}',
      '#rt-user{color:#8a7666;font-size:13px;min-height:18px;}',
      '#rt-ai{color:#4a3b32;font-weight:500;}',
      '#rt-actions{display:flex;gap:8px;margin-top:10px;flex-wrap:wrap;}',
      '#rt-actions button{font-size:13px;padding:6px 14px;border-radius:999px;border:1px solid #eadfd2;',
      'background:#fff;cursor:pointer;color:#4a3b32;}',
      '#rt-actions button.primary{background:#f59e0b;border-color:#f59e0b;color:#fff;}',
      '#rt-actions button.danger{color:#b91c1c;border-color:#fecaca;}',
      '#rt-metrics{margin-top:8px;font-size:11px;color:#b0a294;font-family:Consolas,monospace;}',
    ].join('');
    var st = document.createElement('style');
    st.id = 'rt-voice-style';
    st.textContent = css;
    document.head.appendChild(st);
  };

  RealtimeUI.prototype._ensurePanel = function () {
    if (this._panel) return this._panel;
    var p = document.createElement('div');
    p.id = 'rt-panel';
    p.setAttribute('role', 'region');
    p.setAttribute('aria-label', '实时语音对话');
    p.hidden = true;
    p.innerHTML =
      '<div id="rt-head"><span id="rt-dot"></span><span id="rt-state"></span></div>' +
      '<div id="rt-sub"><div id="rt-user">—</div><div id="rt-ai">开启后直接说话，说完自动回答</div></div>' +
      '<div id="rt-actions">' +
      '<button type="button" id="rt-mute">🔇 静音</button>' +
      '<button type="button" id="rt-stop" class="danger">■ 结束对话</button>' +
      '</div>' +
      '<div id="rt-metrics"></div>';
    document.body.appendChild(p);
    var self = this;
    p.querySelector('#rt-mute').addEventListener('click', function () {
      if (!self.controller) return;
      self.controller.setMuted(!self.controller.muted);
      this.textContent = self.controller.muted ? '🔊 取消静音' : '🔇 静音';
    });
    p.querySelector('#rt-stop').addEventListener('click', function () { self.stop(); });
    this._panel = p;
    return p;
  };

  RealtimeUI.prototype._renderState = function (s, extra) {
    var p = this._panel;
    if (!p) return;
    var dot = p.querySelector('#rt-dot');
    var txt = STATE_TEXT[s] || s;
    if (extra && extra.attempt != null) txt += '（第' + (extra.attempt + 1) + '次）';
    p.querySelector('#rt-state').textContent = txt;
    dot.className = '';
    if (s === 'USER_SPEAKING' || s === 'AI_SPEAKING') dot.className = 'speak';
    else if (s === 'AI_THINKING' || s === 'RECONNECTING' || s === 'CONNECTING' || s === 'REQUESTING_PERMISSION') dot.className = 'think';
    else if (s === 'ERROR') dot.className = 'err';
  };

  RealtimeUI.prototype._renderMetrics = function (m) {
    if (!this._panel || !m) return;
    var parts = [];
    if (m.t_speech_end_to_first_text_ms != null) parts.push('首字 ' + m.t_speech_end_to_first_text_ms + 'ms');
    if (m.t_speech_end_to_first_audio_ms != null) parts.push('首音 ' + m.t_speech_end_to_first_audio_ms + 'ms');
    if (m.reconnect_count) parts.push('重连 ' + m.reconnect_count);
    this._panel.querySelector('#rt-metrics').textContent = parts.join(' · ');
  };

  RealtimeUI.prototype.isActive = function () {
    return !!(this.controller && this.controller._client);
  };

  RealtimeUI.prototype.start = async function () {
    if (this.isActive()) return;
    var self = this;
    var panel = this._ensurePanel();
    panel.hidden = false;
    this._aiText = '';
    panel.querySelector('#rt-user').textContent = '—';
    panel.querySelector('#rt-ai').textContent = '正在开启…';
    panel.querySelector('#rt-metrics').textContent = '';

    this.controller = new RealtimeController({
      petId: this.getPet().id,
      petGender: this.getGender(),
      onState: function (s, extra) {
        self._renderState(s, extra);
        if (s === 'ERROR') {
          var btn = panel.querySelector('#rt-stop');
          btn.textContent = '✍️ 切换文字聊天';
          panel.querySelector('#rt-ai').textContent =
            '实时语音不可用（麦克风权限或网络问题），文字聊天不受影响。';
        }
        if (s === 'STOPPED') panel.hidden = true;
      },
      onTranscripts: function (t) {
        if (t.assistantDelta != null) {
          self._aiText += t.assistantDelta;
          panel.querySelector('#rt-ai').textContent = self._aiText || '…';
        }
        if (t.userText) panel.querySelector('#rt-user').textContent = '你：' + t.userText;
        if (t.done) {
          // 一轮完整结束：增量字幕结算，交由页面写历史（一条用户 + 一条宠物）
          var pet = self.getPet();
          if (t.userText || t.assistantText) {
            try { self.onRound(t.userText || '', t.assistantText || '(……)', pet); }
            catch (e) { console.warn('onRound error', e); }
          }
          self._aiText = '';
        }
      },
      onMetrics: function (m) { self._renderMetrics(m); },
      onError: function (e) { self.onError(e); },
    });
    await this.controller.start();
  };

  RealtimeUI.prototype.stop = function () {
    if (this.controller) {
      this.controller.stop();
      this.controller = null;
    }
    if (this._panel) this._panel.hidden = true;
  };

  RealtimeUI.prototype.toggle = function () {
    if (this.isActive()) this.stop();
    else this.start();
  };

  /** 切换宠物后调用：销毁旧会话并按新宠物重建（方案 §7）。 */
  RealtimeUI.prototype.restartForPet = function () {
    if (!this.isActive()) return;
    this.stop();
    var self = this;
    setTimeout(function () { self.start(); }, 300);
  };

  window.RealtimeUI = RealtimeUI;
})();
