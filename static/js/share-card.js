/* MPC 分享卡片（S1-08）：
   点击分享 → 预览弹窗（1080×1350 Canvas 卡片）→ 保存图片 / 分享图片 / 仅复制文字。
   降级链：Web Share 文件分享 → 下载 PNG → 复制纯文本。
   只绘制单条消息：不含其他聊天、账号、地址、模型名。 */
(function () {
    'use strict';

    var W = 1080, H = 1350;
    var MARGIN = 96;
    var MAX_TEXT_W = 888;
    var MAX_CHARS = 220;
    var MAX_LINES = 7;      // 正文 y=720 起、行距 66：末行基线 1116，不压页脚（y≈1220）
    var FONT_BODY = '"Microsoft YaHei", "PingFang SC", "Heiti SC", sans-serif';

    var modal = null;
    var generating = false;
    var lastBlobUrl = null;
    var lastFile = null;

    // ---------- 文本工具 ----------
    function wrapCanvasText(ctx, text, maxWidth) {
        var lines = [];
        var line = '';
        var chars = Array.from(text);   // 按码点拆，emoji 不被拆代理对
        for (var i = 0; i < chars.length; i++) {
            var next = line + chars[i];
            if (line && ctx.measureText(next).width > maxWidth) {
                lines.push(line);
                line = chars[i];
            } else {
                line = next;
            }
        }
        if (line) lines.push(line);
        return lines;
    }
    function truncateChars(text, max) {
        var arr = Array.from(String(text));
        return arr.length > max ? arr.slice(0, max).join('') + '…' : arr.join('');
    }
    function pad(n) { return String(n).padStart(2, '0'); }

    // ---------- 头像 ----------
    function loadAvatar(url, timeoutMs) {
        return new Promise(function (resolve) {
            if (!url) { resolve(null); return; }
            var img = new Image();
            var done = false;
            var timer = setTimeout(function () { if (!done) { done = true; resolve(null); } }, timeoutMs || 3000);
            img.onload = function () { if (!done) { done = true; clearTimeout(timer); resolve(img); } };
            img.onerror = function () { if (!done) { done = true; clearTimeout(timer); resolve(null); } };
            img.src = url;
        });
    }

    // ---------- 卡片绘制 ----------
    function roundedRect(ctx, x, y, w, h, r) {
        ctx.beginPath();
        ctx.moveTo(x + r, y);
        ctx.arcTo(x + w, y, x + w, y + h, r);
        ctx.arcTo(x + w, y + h, x, y + h, r);
        ctx.arcTo(x, y + h, x, y, r);
        ctx.arcTo(x, y, x + w, y, r);
        ctx.closePath();
    }
    function drawCard(opts, avatarImg) {
        var canvas = document.createElement('canvas');
        canvas.width = W;
        canvas.height = H;
        var ctx = canvas.getContext('2d');

        // 背景渐变（暖米→浅橙），圆角 48
        var grad = ctx.createLinearGradient(0, 0, W, H);
        grad.addColorStop(0, '#FFF6E8');
        grad.addColorStop(1, '#FFE0BC');
        roundedRect(ctx, 0, 0, W, H, 48);
        ctx.fillStyle = grad;
        ctx.fill();
        ctx.save();
        roundedRect(ctx, 0, 0, W, H, 48);
        ctx.clip();

        // 柔和装饰圆
        ctx.fillStyle = 'rgba(255, 214, 165, .35)';
        ctx.beginPath(); ctx.arc(W - 90, 190, 150, 0, Math.PI * 2); ctx.fill();
        ctx.beginPath(); ctx.arc(110, H - 200, 130, 0, Math.PI * 2); ctx.fill();

        // 头像（失败画首字占位圆）
        var cx = W / 2, cy = 300, r = 110;
        if (avatarImg) {
            ctx.save();
            ctx.beginPath(); ctx.arc(cx, cy, r, 0, Math.PI * 2); ctx.clip();
            ctx.drawImage(avatarImg, cx - r, cy - r, r * 2, r * 2);
            ctx.restore();
        } else {
            ctx.fillStyle = '#FFD9A8';
            ctx.beginPath(); ctx.arc(cx, cy, r, 0, Math.PI * 2); ctx.fill();
            ctx.fillStyle = '#8A6248';
            ctx.font = 'bold 110px ' + FONT_BODY;
            ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
            var ch = Array.from(opts.displayName || '宠')[0];
            ctx.fillText(ch, cx, cy + 8);
        }
        ctx.strokeStyle = '#FFFFFF';
        ctx.lineWidth = 8;
        ctx.beginPath(); ctx.arc(cx, cy, r + 4, 0, Math.PI * 2); ctx.stroke();

        // 名称
        ctx.fillStyle = '#4A3B32';
        ctx.font = 'bold 56px ' + FONT_BODY;
        ctx.textAlign = 'center'; ctx.textBaseline = 'alphabetic';
        ctx.fillText(opts.displayName || '宠物伙伴', cx, 500);

        // 引号装饰
        ctx.fillStyle = 'rgba(214, 158, 94, .55)';
        ctx.font = 'bold 120px Georgia, serif';
        ctx.fillText('“', cx, 640);

        // 正文（逐字测量换行 + 双重截断）
        ctx.font = '44px ' + FONT_BODY;
        var text = truncateChars(opts.message || '', MAX_CHARS);
        var lines = wrapCanvasText(ctx, text, MAX_TEXT_W);
        if (lines.length > MAX_LINES) {
            lines = lines.slice(0, MAX_LINES);
            var lastLine = lines[MAX_LINES - 1];
            while (lastLine.length > 1 && ctx.measureText(lastLine + '…').width > MAX_TEXT_W) {
                lastLine = lastLine.slice(0, -1);
            }
            lines[MAX_LINES - 1] = lastLine + '…';
        }
        ctx.fillStyle = '#4A3B32';
        var y = 720;
        for (var i = 0; i < lines.length; i++) {
            ctx.fillText(lines[i], cx, y + i * 66);
        }

        // 页脚：日期 + 品牌
        var now = new Date();
        ctx.fillStyle = '#A89484';
        ctx.font = '30px ' + FONT_BODY;
        ctx.fillText(now.getFullYear() + '年' + (now.getMonth() + 1) + '月' + now.getDate() + '日  ·  派特岛', cx, H - 130);
        ctx.fillStyle = '#C4A98F';
        ctx.font = '26px ' + FONT_BODY;
        ctx.fillText('用陪伴传递温暖', cx, H - MARGIN + 20);

        ctx.restore();
        return canvas;
    }

    // ---------- 弹窗 ----------
    function canShareFiles() {
        try {
            if (!(navigator.share && navigator.canShare)) return false;
            var probe = new File([new Blob(['x'], { type: 'image/png' })], 'p.png', { type: 'image/png' });
            return navigator.canShare({ files: [probe] });
        } catch (e) { return false; }
    }
    var onKey = function (e) {
        if (e.key === 'Escape' && modal) finishClose(modal.backFocus);
    };
    function finishClose(focusEl) {
        document.removeEventListener('keydown', onKey);
        if (modal) modal.el.remove();
        modal = null;
        if (lastBlobUrl) { URL.revokeObjectURL(lastBlobUrl); lastBlobUrl = null; }
        if (focusEl && focusEl.focus) focusEl.focus();
    }

    function buildModal(opts, canvas) {
        var prevFocus = document.activeElement;
        var el = document.createElement('div');
        el.setAttribute('role', 'dialog');
        el.setAttribute('aria-modal', 'true');
        el.setAttribute('aria-label', '分享卡片预览');
        el.style.cssText = 'position:fixed;inset:0;z-index:400;background:rgba(60,45,35,.55);display:flex;' +
            'align-items:center;justify-content:center;padding:20px;';
        var box = document.createElement('div');
        box.style.cssText = 'background:#FFFDF8;border-radius:18px;max-width:min(92vw,420px);width:100%;' +
            'max-height:92vh;overflow:auto;padding:18px;box-shadow:0 18px 50px rgba(0,0,0,.35);';
        var title = document.createElement('h3');
        title.textContent = '分享这张卡片';
        title.tabIndex = -1;   // 焦点进入弹窗
        title.style.cssText = 'margin:0 0 12px;font-size:16px;color:#4A3B32;text-align:center;';
        var img = document.createElement('img');
        img.alt = '分享卡片预览';
        img.src = canvas.toDataURL('image/png');
        img.style.cssText = 'max-width:100%;border-radius:12px;display:block;margin:0 auto 14px;';
        var btns = document.createElement('div');
        btns.style.cssText = 'display:flex;flex-direction:column;gap:8px;';

        function mkBtn(text, primary, fn) {
            var b = document.createElement('button');
            b.type = 'button';
            b.textContent = text;
            b.style.cssText = 'padding:11px;border-radius:10px;border:' + (primary ? '0' : '1.5px solid #D8C7B4') +
                ';background:' + (primary ? '#FF9E58' : '#FFFDF8') + ';color:' + (primary ? '#4A2E14' : '#6F6055') +
                ';font:inherit;font-weight:600;cursor:pointer;';
            b.addEventListener('click', fn);
            btns.appendChild(b);
            return b;
        }

        // 保存图片（下载）
        mkBtn('保存图片', true, function () {
            if (!lastBlobUrl) return;
            var a = document.createElement('a');
            a.download = 'MPC-' + (opts.displayName || 'pet') + '-' + opts.dateKey + '.png';
            a.href = lastBlobUrl;
            a.click();
        });
        // 分享图片（仅支持文件分享的环境显示）
        if (canShareFiles()) {
            mkBtn('分享图片', false, function () {
                if (!lastFile) return;
                navigator.share({ files: [lastFile], title: '来自' + (opts.displayName || '宠物') + '的陪伴' })
                    .catch(function (e) { if (e && e.name === 'AbortError') return; });   // 用户取消不算错
            });
        }
        // 仅复制文字
        mkBtn('仅复制文字', false, function () {
            if (opts.copyText) opts.copyText();
        });
        var cancel = document.createElement('button');
        cancel.type = 'button';
        cancel.textContent = '关闭';
        cancel.style.cssText = 'padding:9px;border:0;background:transparent;color:#A89484;font:inherit;cursor:pointer;';
        cancel.addEventListener('click', function () { finishClose(prevFocus); });
        btns.appendChild(cancel);

        box.appendChild(title);
        box.appendChild(img);
        box.appendChild(btns);
        el.appendChild(box);
        el.addEventListener('click', function (e) { if (e.target === el) finishClose(prevFocus); });
        document.addEventListener('keydown', onKey);
        document.body.appendChild(el);
        modal = { el: el, backFocus: prevFocus };
        title.focus();
    }

    // ---------- 入口 ----------
    function open(opts) {
        if (modal || generating) return;   // 多次快速点击只保留一个任务
        generating = true;
        var d = new Date();
        var dateKey = d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate());
        loadAvatar(opts.avatarUrl, 3000).then(function (avatarImg) {
            var canvas = drawCard({
                displayName: opts.senderName,
                message: opts.message,
            }, avatarImg);
            return new Promise(function (resolve) {
                canvas.toBlob(function (blob) {
                    lastBlobUrl = URL.createObjectURL(blob);
                    lastFile = new File([blob], 'MPC-' + (opts.senderName || 'pet') + '-' + dateKey + '.png', { type: 'image/png' });
                    resolve(canvas);
                }, 'image/png', 0.92);
            });
        }).then(function (canvas) {
            generating = false;
            buildModal({ displayName: opts.senderName, copyText: opts.copyText, dateKey: dateKey }, canvas);
        }).catch(function () {
            generating = false;
            if (opts.copyText) opts.copyText();   // 卡片生成失败退回复制文字
        });
    }

    window.MPCShareCard = { open: open };
})();
