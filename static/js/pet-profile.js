/* MPC 宠物资料（S1-09）：每只宠物可选 男孩子/女孩子/暂不设定。
   只影响称呼与资料展示，不影响模型/亲密度/动画/TTS。
   存储 key：petProfilesV1（独立于 denState/chatHistory，损坏时回退 unspecified 不阻塞页面）。 */
(function () {
    'use strict';

    var KEY = 'petProfilesV1:' + (window.COMPANION_SCOPE || 'legacy');
    var VALID = ['male', 'female', 'unspecified'];
    var voiceVersion = document.currentScript?.src ? new URL(document.currentScript.src).search : '';
    var voiceLoad;

    function loadAll() {
        try {
            var o = JSON.parse(localStorage.getItem(KEY) || '{}');
            return (o && typeof o === 'object' && !Array.isArray(o)) ? o : {};
        } catch (e) { return {}; }
    }
    function saveAll(obj) {
        try { localStorage.setItem(KEY, JSON.stringify(obj)); } catch (e) {}
    }

    var PetProfile = {
        loadAll: loadAll,
        get: function (petId) {
            var p = loadAll()[String(petId)];
            var g = p && p.gender;
            return { gender: VALID.indexOf(g) >= 0 ? g : 'unspecified' };
        },
        setGender: function (petId, gender) {
            if (VALID.indexOf(gender) < 0) return false;
            var all = loadAll();
            all[String(petId)] = Object.assign({}, all[String(petId)] || {},
                { gender: gender, updatedAt: new Date().toISOString() });
            saveAll(all);
            return true;
        },
        // 展示名：未设定返回空串（调用方拼 " · 男孩子" 时自然省略）
        label: function (gender) {
            return gender === 'male' ? '男孩子' : gender === 'female' ? '女孩子' : '';
        },
        // 送后端的值：只有 male/female 白名单内才送，未设定送 null
        promptValue: function (gender) {
            return (gender === 'male' || gender === 'female') ? gender : null;
        },

        /* ---------- 资料弹窗（小窝与聊天页共用） ---------- */
        openDialog: function (opts) {
            var petId = opts.petId, petName = opts.petName, onChange = opts.onChange || function () {};
            var prevFocus = document.activeElement;
            if (document.getElementById('pet-profile-dialog')) return;

            var mask = document.createElement('div');
            mask.id = 'pet-profile-dialog';
            mask.setAttribute('role', 'dialog');
            mask.setAttribute('aria-modal', 'true');
            mask.setAttribute('aria-label', petName + '的资料');
            mask.style.cssText = 'position:fixed;inset:0;z-index:420;background:rgba(60,45,35,.5);' +
                'display:flex;align-items:center;justify-content:center;padding:16px;';
            var card = document.createElement('div');
            card.style.cssText = 'background:#FFFDF8;border-radius:16px;width:min(92vw,340px);padding:22px;' +
                'box-shadow:0 16px 40px rgba(0,0,0,.3);font-family:inherit;';
            var h = document.createElement('h3');
            h.textContent = petName + '的资料';
            h.style.cssText = 'margin:0 0 6px;font-size:17px;color:#4A3B32;';
            var sub = document.createElement('p');
            sub.textContent = '性别只影响称呼，不会改变模型和声音';
            sub.style.cssText = 'margin:0 0 14px;font-size:12px;color:#A89484;';
            card.appendChild(h);
            card.appendChild(sub);

            var current = PetProfile.get(petId).gender;
            var firstRadio = null;
            [['male', '男孩子'], ['female', '女孩子'], ['unspecified', '暂不设定']].forEach(function (pair) {
                var val = pair[0], txt = pair[1];
                var label = document.createElement('label');
                label.style.cssText = 'display:flex;align-items:center;gap:10px;padding:11px 12px;border-radius:10px;' +
                    'cursor:pointer;font-size:15px;color:#4A3B32;';
                label.onmouseenter = function () { label.style.background = 'rgba(255,158,88,.12)'; };
                label.onmouseleave = function () { label.style.background = 'transparent'; };
                var radio = document.createElement('input');
                radio.type = 'radio';
                radio.name = 'pet-gender';
                radio.value = val;
                radio.checked = current === val;
                radio.style.accentColor = '#FF9E58';
                label.appendChild(radio);
                label.appendChild(document.createTextNode(txt));
                card.appendChild(label);
                if (!firstRadio) firstRadio = radio;
            });

            var btns = document.createElement('div');
            btns.style.cssText = 'display:flex;gap:10px;justify-content:flex-end;margin-top:16px;';
            function mkBtn(text, primary, fn) {
                var b = document.createElement('button');
                b.type = 'button';
                b.textContent = text;
                b.style.cssText = 'padding:9px 20px;border-radius:10px;border:' + (primary ? '0' : '1.5px solid #D8C7B4') +
                    ';background:' + (primary ? '#FF9E58' : '#FFFDF8') + ';color:' + (primary ? '#4A2E14' : '#6F6055') +
                    ';font:inherit;font-weight:600;cursor:pointer;min-height:44px;';
                b.addEventListener('click', fn);
                btns.appendChild(b);
            }
            function close() {
                document.removeEventListener('keydown', onKey);
                mask.remove();
                if (prevFocus && prevFocus.focus) prevFocus.focus();
            }
            var onKey = function (e) { if (e.key === 'Escape') close(); };
            var voiceButton = document.createElement('button');
            voiceButton.type = 'button';voiceButton.textContent = '专属声音 · 上传录音';
            voiceButton.style.cssText = 'width:100%;padding:12px;margin-top:12px;border:1px solid #b8cec7;border-radius:12px;background:#eef7f2;color:#315c51;cursor:pointer;font:inherit;';
            voiceButton.onclick = async function () {
                voiceButton.disabled=true;
                try {
                    if(!window.PetVoiceUI){
                        if(!voiceLoad)voiceLoad=new Promise(function(resolve,reject){var s=document.createElement('script');s.src='/static/js/realtime/pet-voice-ui.js'+voiceVersion;s.onload=resolve;s.onerror=function(){voiceLoad=null;reject(Error('声音设置加载失败，请重试'));};document.head.append(s);});
                        await voiceLoad;
                    }
                    close();window.PetVoiceUI.open(petId,petName);
                } catch(e) {voiceButton.textContent=e.message;} finally {voiceButton.disabled=false;}
            };
            card.appendChild(voiceButton);
            mkBtn('取消', false, close);
            mkBtn('保存', true, function () {
                var sel = card.querySelector('input[name="pet-gender"]:checked');
                var val = sel ? sel.value : 'unspecified';
                PetProfile.setGender(petId, val);   // 保存前不动 localStorage，点保存才写
                close();
                var t = (typeof toast === 'function') ? toast : (window.toast || function () {});
                t(petName + '的资料已保存', 'success');
                onChange(val);
            });
            card.appendChild(btns);
            mask.appendChild(card);
            mask.addEventListener('click', function (e) { if (e.target === mask) close(); });
            document.addEventListener('keydown', onKey);
            document.body.appendChild(mask);
            if (firstRadio) firstRadio.focus();   // 焦点进入第一个单选项
        },
    };

    window.PetProfile = PetProfile;
})();
