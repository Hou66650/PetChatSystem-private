/**
 * 真实宠物叫声链路（v1.0.0）：
 * 1. split(text) —— 把 GLM 回复按拟声词拆成 [tts 片段 | pet_sound 事件] 序列；
 * 2. play(segments, petId) —— 顺序无缝播放：人声走 /api/tts，叫声走 /api/pet-sound
 *    （真实录音），叫声每次微变调（±1.5 半音内随机），声音库缺失时降级回人声 TTS。
 *
 * 设计要点（对应产品方案）：
 * - GLM 自然输出拟声词（"汪汪！主人回来啦"）→ 分段器转事件，不依赖 GLM 结构化；
 * - 叫声不进 TTS：彻底消除人声念"汪汪"的违和感；
 * - 微变化：playbackRate 0.91~1.09 + 音量 ±10%，同一叫声不再机械重复。
 */
(function () {
  'use strict';

  // 物种映射须与服务端 PET_SPECIES 一致（1柴犬/2哈士奇/4德牧=狗，3猫咪=猫）
  var SPECIES = { 1: 'dog', 2: 'dog', 3: 'cat', 4: 'dog' };

  // 拟声词 → 叫声类别。长词在前防止"嗷呜"被"嗷"截胡。
  var SOUND_RULES = [
    { re: /汪汪+|汪+|汪嗷+/g, kind: 'bark' },
    { re: /嗷呜+|呜呜+|呜+|哼唧+/g, kind: 'whine' },
    { re: /喵呜+|喵喵+|喵+/g, kind: 'meow' },
    { re: /呼噜+|咕噜+/g, kind: 'purr' },
  ];

  // 物种叫声合法性：狗只发 bark/whine，猫只发 meow/purr
  var SPECIES_KINDS = {
    dog: { bark: 1, whine: 1 },
    cat: { meow: 1, purr: 1 },
  };

  /**
   * 把文本拆成交替的 tts/sound 片段。
   * 返回 [{type:'tts',text}|{type:'sound',kind,raw}]；无拟声词时只有一条 tts。
   */
  function split(text, petId) {
    var species = SPECIES[petId] || 'dog';
    var allowed = SPECIES_KINDS[species] || SPECIES_KINDS.dog;
    var src = String(text || '');
    // 收集所有匹配（区间合并）
    var marks = [];
    src.replace(/汪汪+|汪+|汪嗷+|嗷呜+|呜呜+|呜+|哼唧+|喵呜+|喵喵+|喵+|呼噜+|咕噜+/g,
      function (m, idx) {
        marks.push({ s: idx, e: idx + m.length, raw: m });
        return m;
      });
    var out = [];
    var pos = 0;
    for (var i = 0; i < marks.length; i++) {
      var mk = marks[i];
      if (mk.s < pos) continue;                       // 被更长匹配覆盖
      var kind = kindOf(mk.raw);
      if (!kind || !allowed[kind]) continue;          // 该物种没有这类叫声 → 留给人声
      // 拟声词后面紧跟的标点一起吞掉（"汪汪！"的感叹号属于叫声）
      var e = mk.e;
      while (e < src.length && /[!！。~～，, ]/.test(src[e])) e++;
      var before = src.slice(pos, mk.s).trim();
      if (before) out.push({ type: 'tts', text: before });
      var last = out.length ? out[out.length - 1] : null;
      if (last && last.type === 'sound' && last.kind === kind) {
        last.raw += mk.raw;                        // 连续同类拟声词合并为一次叫声事件
      } else {
        out.push({ type: 'sound', kind: kind, raw: mk.raw });
      }
      pos = e;
    }
    var tail = src.slice(pos).trim();
    if (tail) out.push({ type: 'tts', text: tail });
    if (!out.length) out.push({ type: 'tts', text: src.trim() });
    return out;
  }

  function kindOf(raw) {
    var c = raw.charAt(0);
    if (c === '汪') return 'bark';
    if (c === '嗷' || c === '呜' || c === '哼') return 'whine';
    if (c === '喵') return 'meow';
    if (c === '呼' || c === '咕') return 'purr';
    return null;
  }

  // ---------- 播放序列器 ----------
  var _ctx = null;
  function ctx() {
    if (!_ctx) {
      var AC = window.AudioContext || window.webkitAudioContext;
      _ctx = new AC();
    }
    if (_ctx.state === 'suspended') _ctx.resume();
    return _ctx;
  }


  function fetchTTSBuffer(text, petId) {
    return fetch('/api/tts', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: text, petId: petId }),
    }).then(function (r) {
      if (!r.ok) throw new Error('tts ' + r.status);
      return r.arrayBuffer();
    });
  }

  function fetchPetSoundBuffer(petId, kind) {
    return fetch('/api/pet-sound?petId=' + petId + '&kind=' + kind,{cache:'no-store'})
      .then(async function(r){if(!r.ok)throw Error('pet-sound '+r.status);if(window.COMPANION_SCOPE&&r.headers.get('X-Profile-Scope')!==window.COMPANION_SCOPE)throw Error('account changed');return {bytes:await r.arrayBuffer(),original:r.headers.get('X-Pet-Original')==='true'};});
  }

  /**
   * 顺序播放分段。返回 {promise, stop()}；
   * 叫声段 404/解码失败时降级为该段人声 TTS，整体永不 reject 静默失败（除非全部失败）。
   */
  function play(segments, petId) {
    var stopped = false;
    var cur = null;
    var nextAt = 0;

    function playBuf(buf, rate) {
      var c = ctx();
      return c.decodeAudioData(buf.slice(0)).then(function (audio) {
        if (stopped) return 0;
        var when = Math.max(c.currentTime + 0.02, nextAt);
        var src = c.createBufferSource();
        src.buffer = audio;
        var gain = c.createGain();
        gain.gain.value = 0.9 + Math.random() * 0.15;
        src.playbackRate.value = rate;
        src.connect(gain).connect(c.destination);
        src.start(when);
        nextAt = when + audio.duration / rate + 0.09;   // 片间自然停顿 ~90ms
        cur = src;
        return new Promise(function (res) {
          src.onended = function () { cur = null; res(); };
        });
      });
    }

    var promise = (async function () {
      for (var i = 0; i < segments.length; i++) {
        if (stopped) break;
        var seg = segments[i];
        if (seg.type === 'tts') {
          try {
            var buf = await fetchTTSBuffer(seg.text, petId);
            await playBuf(buf, 1.0);
          } catch (e) { /* 单段失败跳过，不打断整体 */ }
        } else {
          var rate = 0.91 + Math.random() * 0.18;       // ±1.5 半音内微变调
          try {
            var sbuf = await fetchPetSoundBuffer(petId, seg.kind);
            await playBuf(sbuf.bytes, sbuf.original ? 1.0 : rate);
          } catch (e) {
            // 声音库缺失 → 降级：用 TTS 念出拟声词（好过无声）
            try {
              var fbuf = await fetchTTSBuffer(seg.raw, petId);
              await playBuf(fbuf, 1.0);
            } catch (e2) { /* 忽略 */ }
          }
        }
      }
    })();

    return {
      promise: promise,
      stop: function () {
        stopped = true;
        try { if (cur) cur.stop(); } catch (e) { /* 已结束 */ }
        cur = null;
      },
    };
  }

  window.PetSounds = {
    split: split,
    play: play,
    speciesOf: function (petId) { return SPECIES[petId] || 'dog'; },
    hasSound: function (segments) {
      return segments.some(function (s) { return s.type === 'sound'; });
    },
  };
})();
