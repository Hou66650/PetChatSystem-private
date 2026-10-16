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
    this.onState = opts.onState || function () {};
    this.onTurnStart = opts.onTurnStart || function () {};
    this.onUserTranscript = opts.onUserTranscript || function () { return false; };
    this.onSaved = opts.onSaved || function () {};
    this.surface = opts.surface || 'chat';
    this._generation = 0;
    this._restartTimer = null;
    this._saveQueue = Promise.resolve();
    this.controller = null;
    this._panel = null;
    this._aiText = '';
    this._injectStyle();
    document.addEventListener?.('voiceprint-settings-open',()=>this.stop());
    document.addEventListener?.('pet-voice-settings-open',()=>this.stop());
    document.addEventListener?.('pet-voice-changed',e=>{if(Number(e.detail?.petId)===Number(this.getPet().id)&&this.isActive())this._restart();});
  }

  RealtimeUI.prototype._injectStyle = function () {
    if (document.getElementById('rt-voice-style')) return;
    var css = [
      '#rt-panel{position:fixed;left:50%;transform:translateX(-50%);bottom:96px;z-index:320;',
      'width:min(560px,92vw);background:#fffdf8;border:1px solid #eadfd2;border-radius:16px;',
      'box-shadow:0 8px 30px rgba(74,59,50,.18);padding:14px 16px;font-size:14px;color:#4a3b32;}',
      '#rt-panel[data-surface=den]{left:18px;transform:none;width:min(360px,92vw);}',
      '@media(max-width:760px){#rt-panel[data-surface=den]{left:50%;transform:translateX(-50%);max-height:42vh;overflow:auto;}}',
      '#rt-panel[hidden]{display:none;}',
      '#rt-head{display:flex;align-items:center;gap:8px;margin-bottom:8px;}',
      '#rt-dot{width:10px;height:10px;border-radius:50%;background:#f59e0b;flex:none;}',
      '#rt-lv{margin-left:auto;display:flex;align-items:center;gap:5px;flex:none;}',
      '#rt-lvbar{width:64px;height:6px;border-radius:3px;background:#efe7db;overflow:hidden;}',
      '#rt-lvbar i{display:block;height:100%;width:0;background:#22c55e;border-radius:3px;',
      'transition:width .25s linear;}',
      '#rt-lvdb{font-size:11px;color:#b0a294;min-width:42px;text-align:right;font-family:Consolas,monospace;}',
      '#rt-dot.speak{background:#22c55e;animation:rt-pulse 1s infinite;}',
      '#rt-dot.think{background:#f59e0b;animation:rt-pulse 1.6s infinite;}',
      '#rt-dot.err{background:#ef4444;animation:none;}',
      '@keyframes rt-pulse{0%,100%{opacity:1}50%{opacity:.35}}',
      '#rt-state{font-weight:600;flex:1;}',
      '#rt-sub{background:#faf6ef;border-radius:10px;padding:8px 10px;min-height:20px;line-height:1.6;}',
      '#rt-devrow{display:flex;align-items:center;gap:8px;margin-top:8px;}',
      '#rt-devrow label{font-size:12px;color:#8a7666;flex:none;}',
      '#rt-dev{flex:1;font-size:12px;padding:4px 8px;border-radius:8px;border:1px solid #eadfd2;',
      'background:#fff;color:#4a3b32;min-width:0;}',
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
    p.dataset.surface=this.surface;
    p.setAttribute('role', 'region');
    p.setAttribute('aria-label', '实时语音对话');
    p.hidden = true;
    p.innerHTML =
      '<div id="rt-head"><span id="rt-dot"></span><span id="rt-state"></span>' +
      '<span id="rt-lv"><span id="rt-lvbar"><i></i></span><span id="rt-lvdb">— dB</span></span></div>' +
      '<div id="rt-sub"><div id="rt-user">—</div><div id="rt-ai">开启后直接说话，说完自动回答</div></div>' +
      '<div id="rt-devrow"><label for="rt-dev">🎤 输入设备</label><select id="rt-dev"><option>正在识别…</option></select></div>' +
      '<div id="rt-speaker" role="status" style="margin-top:8px"></div>' +
      '<div id="rt-actions">' +
      '<button type="button" id="rt-voiceprint">声纹设置</button>' +
      '<button type="button" id="rt-mute">🔇 静音</button>' +
      '<button type="button" id="rt-sound-test">试听声音</button>' +
      '<button type="button" id="rt-stop" class="danger">■ 结束对话</button>' +
      '</div>' +
      '<div id="rt-output" role="status" style="margin-top:8px;font-size:12px;color:#8a7666"></div>' +
      '<div id="rt-notice" role="status" style="margin-top:8px;font-size:12px;color:#8a7666"></div>' +
      '<div id="rt-memory" role="status" style="margin-top:8px;font-size:12px;color:#8a7666"></div>' +
      '<div id="rt-metrics"></div>';
    document.body.appendChild(p);
    var self = this;
    p.querySelector('#rt-mute').addEventListener('click', function () {
      if (!self.controller) return;
      self.controller.setMuted(!self.controller.muted);
      this.textContent = self.controller.muted ? '🔊 取消静音' : '🔇 静音';
    });
    p.querySelector('#rt-stop').addEventListener('click', function () { self.stop(); });
    p.querySelector('#rt-sound-test').addEventListener('click', function () {
      if (self.controller) self.controller.testPlayback();
    });
    p.querySelector('#rt-dev').addEventListener('change', function () {
      if (!this.value) return;
      try { localStorage.setItem('rt_mic_id', this.value); } catch (e) { /* ignore */ }
      p.querySelector('#rt-ai').textContent = '正在切换到 ' + (this.options[this.selectedIndex] || {}).textContent + ' …';
      self._restart(this.value);
    });
    p.querySelector('#rt-voiceprint').onclick=()=>window.VoiceprintUI?.open();
    this._panel = p;
    return p;
  };

  // 虚拟麦克风特征（ToDesk/Voicemeeter/各类 Virtual Audio）：录不到人声的常见元凶
  RealtimeUI._VIRTUAL_MIC = /virtual|todesk|voicemeeter|虚拟/i;

  /** 权限到位后枚举输入设备填充下拉；默认设备是虚拟麦克风时自动切换到真实麦克风。 */
  RealtimeUI.prototype._populateDevices = async function () {
    var generation = this._generation;
    var panel = this._panel;
    var sel = panel && panel.querySelector('#rt-dev');
    if (!sel) return;
    var devs;
    try {
      devs = (await navigator.mediaDevices.enumerateDevices())
        .filter(function (d) { return d.kind === 'audioinput'; });
    } catch (e) {
      sel.innerHTML = '<option>设备列表不可用</option>';
      return;
    }
    if(generation !== this._generation || !this.isActive()) return;
    sel.innerHTML = '';
    var V = RealtimeUI._VIRTUAL_MIC;
    devs.forEach(function (d) {
      var o = document.createElement('option');
      o.value = d.deviceId;
      o.textContent = (d.label || '未命名输入设备') + (V.test(d.label || '') ? ' ⚠️虚拟' : '');
      sel.appendChild(o);
    });
    // 当前实际使用的设备高亮
    var curLabel = this.controller ? (this.controller.micLabel || '') : '';
    var curId = null;
    try {
      var track = this.controller._stream && this.controller._stream.getAudioTracks()[0];
      var settings = track && track.getSettings();
      curId = settings && settings.deviceId;
    } catch (e) { /* ignore */ }
    if (curId) {
      for (var i = 0; i < sel.options.length; i++) {
        if (sel.options[i].value === curId) { sel.selectedIndex = i; break; }
      }
    }
    // 未手动选过设备 且 当前正在用虚拟麦克风 → 自动切到第一块真实麦克风并记住
    var saved = null;
    try { saved = localStorage.getItem('rt_mic_id'); } catch (e) { /* ignore */ }
    if (!saved && curLabel && V.test(curLabel)) {
      var real = devs.filter(function (d) { return !V.test(d.label || ''); })[0];
      if (real) {
        try { localStorage.setItem('rt_mic_id', real.deviceId); } catch (e) { /* ignore */ }
        panel.querySelector('#rt-ai').textContent =
          '检测到浏览器默认用了虚拟麦克风（' + curLabel + '），已自动切换到「' +
          real.label + '」。现在可以直接说话了。';
        var self2 = this;
        self2._restart(real.deviceId);
      }
    }
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

  RealtimeUI.prototype._renderLevel = function (db) {
    if (!this._panel) return;
    var bar = this._panel.querySelector('#rt-lvbar i');
    var txt = this._panel.querySelector('#rt-lvdb');
    if (!bar || !txt) return;
    var pct = Math.max(2, Math.min(100, Math.round(((db + 70) / 70) * 100)));
    bar.style.width = pct + '%';
    bar.style.background = db > -60 ? '#22c55e' : '#d6cabb';
    txt.textContent = db <= -99 ? '无声' : db + ' dB';
    // 静默检测：开麦状态下连续 5 秒接近无声 → 给出排查指引（只提示一次，恢复后重置）
    var now = Date.now();
    if (db > -55) {
      this._silentFrom = 0;
      this._silentHinted = false;
    } else if (!this._silentHinted) {
      if (!this._silentFrom) this._silentFrom = now;
      else if (now - this._silentFrom > 5000 && !this.controller.muted) {
        this._silentHinted = true;
        this._panel.querySelector('#rt-ai').textContent =
          '🎤 麦克风一直没收到声音，请检查：① 系统麦克风是否被静音（键盘静音键/任务栏音量-输入设备）' +
          '② 输入设备是否选对（Windows 设置→系统→声音→输入）③ Windows 设置→隐私和安全性→麦克风，' +
          '允许桌面应用访问。改完后点"结束"再重新开启。';
      }
    }
  };

  RealtimeUI.prototype.isActive = function () {
    return !!(this.controller && !['IDLE','ERROR','STOPPED'].includes(this.controller.state));
  };

  RealtimeUI.prototype.start = async function (deviceId) {
    if (this.isActive()) return;
    this.stop();
    var generation = ++this._generation;
    var pet = Object.assign({}, this.getPet());
    var gender = this.getGender();
    var turnContexts = new Map();
    var transcriptTurns = new Set();
    var handledActionTurns = new Set();
    var latestTurn = 0;
    var self = this;
    var current = function(){return generation === self._generation;};
    var panel = this._ensurePanel();
    // 设备优先级：手动切换 > 记忆选择 > 系统默认
    var micId = deviceId || null;
    if (!micId) {
      try { micId = localStorage.getItem('rt_mic_id') || null; } catch (e) { /* ignore */ }
    }
    panel.hidden = false;
    panel.querySelector('#rt-stop').textContent='■ 结束对话';
    panel.querySelector('#rt-mute').textContent='🔇 静音';
    this._aiText = '';
    this._silentFrom = 0;
    this._silentHinted = false;
    this._lastErrMsg = '';
    panel.querySelector('#rt-user').textContent = '—';
    panel.querySelector('#rt-ai').textContent = '正在开启…';
    panel.querySelector('#rt-metrics').textContent = '';
    panel.querySelector('#rt-memory').textContent = '';
    panel.querySelector('#rt-speaker').textContent = '';
    panel.querySelector('#rt-notice').textContent = '';
    panel.querySelector('#rt-output').textContent = '';
    panel.querySelector('#rt-lvdb').textContent = '— dB';
    panel.querySelector('#rt-lvbar i').style.width = '0';

    var controller = new RealtimeController({
      petId: pet.id,
      petGender: gender,
      surface: this.surface,
      micDeviceId: micId,
      onSpeaker: function(info){if(!current())return;panel.querySelector('#rt-speaker').textContent=info.kind==='checking'?'正在本机辨认声音，请稍候…':info.kind==='familiar'?'听起来像 '+info.name+' · 亲近回应':info.kind==='unfamiliar'?'尚不熟悉的声音 · 礼貌回应':'声音不确定 · '+(info.message||'请连续说话3–6秒后再试');},
      onLevel: function (db) { if(current()) self._renderLevel(db); },
      onPlayback: function (info) {
        if(!current()) return;
        var output=panel.querySelector('#rt-output');
        if(output.textContent!==info.message) output.textContent=info.message;
      },
      onState: function (s, extra) {
        if(!current()) return;
        self._renderState(s, extra);
        self.onState(s, extra, pet);
        if(s === 'USER_SPEAKING') self._aiText='';
        if (s === 'ERROR') {
          panel.hidden=false;
          var btn = panel.querySelector('#rt-stop');
          btn.textContent = '✍️ 切换文字聊天';
          panel.querySelector('#rt-ai').textContent =
            (self._lastErrMsg || '实时语音不可用（麦克风权限或网络问题），文字聊天不受影响。');
        }
        if (s === 'STOPPED') panel.hidden = true;
      },
      onTranscripts: function (t) {
        if(!current()) return;
        if(t.reset) {
          latestTurn=t.turnId;
          turnContexts.set(t.turnId,self.onTurnStart(pet));
          if(turnContexts.size>40){
            var oldest=turnContexts.keys().next().value;
            turnContexts.delete(oldest);transcriptTurns.delete(oldest);handledActionTurns.delete(oldest);
          }
          panel.querySelector('#rt-user').textContent='正在听…';
          panel.querySelector('#rt-ai').textContent='';
        }
        if (t.assistantDelta != null) {
          self._aiText += t.assistantDelta;
          panel.querySelector('#rt-ai').textContent = self._aiText || '…';
        }
        if (t.userText && (t.turnId == null || t.turnId === latestTurn)) panel.querySelector('#rt-user').textContent = '你：' + t.userText;
        if (t.userText && (t.finalUserText || t.done) && t.turnId === latestTurn &&
            turnContexts.has(t.turnId) && !transcriptTurns.has(t.turnId)) {
          transcriptTurns.add(t.turnId);
          // Explicit scene commands act on finalized ASR, before reply/memory work.
          try {
            if(controller.speaker?.kind!=='unfamiliar' && self.onUserTranscript(t.userText,pet,turnContexts.get(t.turnId)) === true)
              handledActionTurns.add(t.turnId);
          } catch(e) { console.warn('onUserTranscript error', e); }
        }
        if (t.done) {
          // 一轮完整结束：增量字幕结算，交由页面写历史（一条用户 + 一条宠物）
          var context = turnContexts.get(t.turnId);
          if (!controller._speakerEnabled && (t.userText || t.assistantText)) {
            try { self.onRound(t.userText || '', t.assistantText || '', pet); }
            catch (e) { console.warn('onRound error', e); }
          }
          if(t.userText && !controller._speakerEnabled) {
            var completedAt=performance.now();
            panel.querySelector('#rt-memory').textContent='正在整理这一轮的记忆'+(self.surface==='den'?'与动作':'')+'…';
            var revision=controller._client?controller._client._session.profileRevision:null;
            var scope=controller._client?controller._client._session.profileScope:null;
            var requestId=crypto.randomUUID();
            self._saveQueue=self._saveQueue.catch(function(){}).then(async function(){
              // Completed turns still persist after hang-up; scope/revision guard forgotten or changed accounts.
              var r=await fetch('/api/companion/voice-round',{
                method:'POST',headers:{'Content-Type':'application/json'},
                body:JSON.stringify({message:t.userText,assistantText:t.assistantText||'…',petId:pet.id,
                  petGender:gender,surface:self.surface,requestId,profileRevision:revision,profileScope:scope})
              });
              var data=await r.json();
              if(!r.ok){
                if(r.status===409 && current()){
                  self.stop();self.onError({code:'profile_changed',message:data.error});return;
                }
                throw Error(data.error||'这轮语音暂未保存');
              }
              if(!current()) return;
              if(controller._client){
                if(data.profile.revision!==revision){
                  // Forget requires a fresh server conversation, not just new instructions.
                  self._restart();
                } else controller._client.updateInstructions(data.instructions);
              }
              var timely=performance.now()-completedAt<30000;
              if(t.turnId===latestTurn){
                panel.querySelector('#rt-memory').textContent=!handledActionTurns.has(t.turnId)&&!timely&&data.actions?.length?'这轮动作等待过久，已取消。可以再说一次。':data.memorySaved?'已记住你的偏好，陪伴方式已更新':data.profile.enabled===false?'长期记忆已暂停':'这轮对话已保存';
              }
              self.onSaved(data,pet,context,t.turnId===latestTurn && current() && timely && !handledActionTurns.has(t.turnId));
            }).catch(function(e){if(current()){panel.querySelector('#rt-memory').textContent='这轮语音暂未保存，请稍后再试';self.onError({code:'archive_failed',message:e.message});}});
          }
          self._aiText = '';
        }
      },
      onMetrics: function (m) { if(current())self._renderMetrics(m); },
      onWarning: function (e) {
        if(!current()) return;
        // Inline status avoids a repeated service-error toast for a recoverable event.
        panel.querySelector('#rt-notice').textContent = e.message;
      },
      onError: function (e) {
        if(!current()) return;
        self._lastErrMsg = (e && e.message) || '';
        panel.querySelector('#rt-ai').textContent=self._lastErrMsg;
        self.onError(e);
      },
    });
    this.controller=controller;
    await controller.start();
    if(!current()) return;
    // 开启完成后把占位文案换掉，避免一直显示"正在开启…"
    var aiEl = panel.querySelector('#rt-ai');
    if (aiEl.textContent === '正在开启…') aiEl.textContent = '我在听——直接说话就好，说完它自动回答';
    // 权限到位后（label 可见）填充设备下拉；默认设备是虚拟麦克风时自动切换
    if (this.controller._stream) this._populateDevices();
  };

  RealtimeUI.prototype.stop = function () {
    clearTimeout(this._restartTimer);this._restartTimer=null;
    if (this.controller) {
      this.controller.stop();
      this.controller = null;
    }
    ++this._generation;
    if (this._panel) this._panel.hidden = true;
  };

  RealtimeUI.prototype.toggle = function () {
    if (this.isActive()) this.stop();
    else this.start();
  };

  /** 切换宠物后调用：销毁旧会话并按新宠物重建（方案 §7）。 */
  RealtimeUI.prototype.restartForPet = function () {
    if (!this.isActive()) return;
    this._restart();
  };

  RealtimeUI.prototype._restart = function(deviceId){
    this.stop();
    var self=this;
    this._restartTimer=setTimeout(function(){self._restartTimer=null;self.start(deviceId);},300);
  };

  window.RealtimeUI = RealtimeUI;
})();
