/* MPC 日记页逻辑（S1-05）：
   - 新记录按本地日期分组；旧记录（无 createdAt）进"历史记录（日期未保存）"，不伪造日期
   - 宠物 / 日期 / 关键词组合筛选 + 单条删除（按 localId）
   - PDF：可视区外 794px 固定宽导出容器，含标题/导出时间/筛选说明/分组日期/页脚 */
(function () {
    'use strict';

    var HISTORY_KEY = 'chatHistory';
    var PET_NAMES = { 1: '球球', 2: '雪球', 3: '团子', 4: '大壮' };
    var PET_SPECIES = { 1: '柴犬', 2: '哈士奇', 3: '猫', 4: '德牧' };   // 旧记录 sender 兜底推断
    var DATE_LABELS = { all: '全部日期', '7': '最近 7 天', '30': '最近 30 天', legacy: '历史未知日期' };
    var WEEK = ['日', '一', '二', '三', '四', '五', '六'];

    var $ = function (id) { return document.getElementById(id); };
    var contentEl = $('diary-content');
    var countEl = $('diary-count');
    var petSel = $('f-pet');
    var dateSel = $('f-date');
    var kwInput = $('f-kw');
    var exportBtn = $('btn-export-pdf');

    function pad(n) { return String(n).padStart(2, '0'); }
    function localDateKey(d) { return d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate()); }
    function dateKeyToUtcDay(key) {
        var p = key.split('-').map(Number);
        return Math.floor(Date.UTC(p[0], p[1] - 1, p[2]) / 86400000);
    }
    function entryDateKey(e) {
        if (!e.createdAt) return 'legacy';
        var d = new Date(e.createdAt);
        if (Number.isNaN(d.getTime())) return 'legacy';
        return localDateKey(d);   // 按本地时区分组，不用 ISO.slice（UTC 午夜会错一天）
    }
    function fmtDateTitle(key) {
        var p = key.split('-').map(Number);
        var wd = WEEK[new Date(p[0], p[1] - 1, p[2]).getDay()];
        return p[0] + '年' + p[1] + '月' + p[2] + '日 · 星期' + wd;
    }
    function inferPetId(e) {
        if (e.petId != null) return e.petId;
        var s = String(e.sender || '');
        var names = Object.keys(PET_NAMES);
        for (var i = 0; i < names.length; i++) {
            if (s.indexOf(PET_NAMES[names[i]]) >= 0) return Number(names[i]);
        }
        var sp = Object.keys(PET_SPECIES);
        for (var j = 0; j < sp.length; j++) {
            if (s.indexOf(PET_SPECIES[sp[j]]) >= 0) return Number(sp[j]);
        }
        return null;
    }
    function nameOf(e) {
        if (e.role === 'user') return '我';
        var pid = inferPetId(e);
        return String(e.sender || (pid != null ? PET_SPECIES[pid] : '') || '宠物');
    }

    function loadHistory() {
        try {
            var arr = JSON.parse(localStorage.getItem(HISTORY_KEY) || '[]');
            return Array.isArray(arr) ? arr : [];
        } catch (e) { return []; }
    }
    function saveHistory(arr) {
        try { localStorage.setItem(HISTORY_KEY, JSON.stringify(arr)); } catch (e) {}
    }

    // ---------- 筛选 ----------
    function currentFilters() {
        return {
            pet: petSel.value,
            date: dateSel.value,
            kw: kwInput.value.trim().toLocaleLowerCase(),
        };
    }
    function filterEntries(list, f) {
        var today = dateKeyToUtcDay(localDateKey(new Date()));
        return list.filter(function (e) {
            if (!e || !e.message || !String(e.message).trim()) return false;
            if (f.pet !== 'all' && String(inferPetId(e)) !== f.pet) return false;
            var dk = entryDateKey(e);
            if (f.date === 'legacy') { if (dk !== 'legacy') return false; }
            else if (f.date !== 'all') {
                if (dk === 'legacy') return false;
                if (today - dateKeyToUtcDay(dk) >= Number(f.date)) return false;   // 7/30 天含今天
            }
            if (f.kw && String(e.message).toLocaleLowerCase().indexOf(f.kw) < 0) return false;
            return true;
        });
    }

    // ---------- 渲染 ----------
    var lastGrouped = [];   // [{key, entries}] 供 PDF 使用
    function render() {
        var all = loadHistory();
        // 旧记录缺 localId：补齐后只保存一次
        var patched = false;
        all.forEach(function (e) {
            if (e && e.message && !e.localId) {
                patched = true;
                e.localId = 'msg-' + Date.now() + '-' + Math.random().toString(36).slice(2, 8);
            }
        });
        if (patched) saveHistory(all);

        var rows = filterEntries(all, currentFilters());

        var groups = new Map();
        rows.forEach(function (e) {
            var k = entryDateKey(e);
            if (!groups.has(k)) groups.set(k, []);
            groups.get(k).push(e);
        });
        // legacy 视为最老放最前，其余日期升序
        var keys = Array.from(groups.keys()).sort(function (a, b) {
            if (a === 'legacy') return -1;
            if (b === 'legacy') return 1;
            return a < b ? -1 : (a > b ? 1 : 0);
        });
        lastGrouped = keys.map(function (k) { return { key: k, entries: groups.get(k) }; });

        countEl.textContent = rows.length ? ('共 ' + rows.length + ' 条') : '';
        exportBtn.disabled = rows.length === 0;

        contentEl.innerHTML = '';
        if (!rows.length) {
            var empty = document.createElement('div');
            empty.className = 'diary-empty';
            empty.textContent = all.length ? '当前筛选条件下没有日记，试试重置筛选。' : '还没有聊天记录。去和宠物聊两句，再回来翻开这页日记吧。';
            contentEl.appendChild(empty);
            return;
        }
        lastGrouped.forEach(function (g) {
            var sec = document.createElement('section');
            sec.className = 'diary-day';
            var h = document.createElement('h3');
            h.className = 'diary-day-title';
            h.textContent = g.key === 'legacy' ? '历史记录（日期未保存）' : fmtDateTitle(g.key);
            sec.appendChild(h);
            g.entries.forEach(function (e) { sec.appendChild(entryEl(e)); });
            contentEl.appendChild(sec);
        });
    }

    function entryEl(e) {
        var art = document.createElement('article');
        art.className = 'diary-entry';
        var main = document.createElement('div');
        main.className = 'diary-entry-main';
        var strong = document.createElement('strong');
        strong.textContent = (e.ts ? e.ts + '  ' : '') + nameOf(e) + '：';
        main.appendChild(strong);
        main.appendChild(document.createTextNode(String(e.message).trim()));
        var del = document.createElement('button');
        del.type = 'button';
        del.className = 'diary-del';
        del.textContent = '删除';
        del.setAttribute('aria-label', '删除这条记录');
        del.addEventListener('click', function () {
            if (!confirm('确定删除这条日记吗？删除后无法恢复。')) return;
            var arr = loadHistory();
            var idx = -1;
            for (var i = 0; i < arr.length; i++) {
                if (arr[i] && arr[i].localId === e.localId) { idx = i; break; }
            }
            if (idx >= 0) { arr.splice(idx, 1); saveHistory(arr); }
            render();
            toast('已删除', 'success');
        });
        art.appendChild(main);
        art.appendChild(del);
        return art;
    }

    // ---------- PDF ----------
    function filterDesc(f) {
        var pet = f.pet === 'all' ? '全部宠物' : (PET_NAMES[f.pet] || '未知宠物');
        var kw = f.kw ? ('｜关键词：' + kwInput.value.trim()) : '';
        return '宠物：' + pet + '｜范围：' + (DATE_LABELS[f.date] || '全部日期') + kw;
    }
    function buildPdf() {
        var box = document.createElement('div');
        box.setAttribute('style',
            'position:fixed;left:-9999px;top:0;width:794px;background:#FFFDF8;color:#3c342c;' +
            'font-family:"Microsoft YaHei","PingFang SC",sans-serif;padding:44px 48px;box-sizing:border-box;');
        var now = new Date();
        var title = document.createElement('h1');
        title.textContent = '我的陪伴日记';
        title.setAttribute('style', 'margin:0 0 8px;font-size:26px;color:#2f2620;');
        var meta = document.createElement('p');
        meta.textContent = '导出时间：' + localDateKey(now) + ' ' + pad(now.getHours()) + ':' + pad(now.getMinutes()) +
            '　·　' + filterDesc(currentFilters());
        meta.setAttribute('style', 'margin:0 0 20px;font-size:13px;color:#8a7a6c;');
        box.appendChild(title);
        box.appendChild(meta);

        lastGrouped.forEach(function (g) {
            var h = document.createElement('h3');
            h.textContent = g.key === 'legacy' ? '历史记录（日期未保存）' : fmtDateTitle(g.key);
            h.setAttribute('style', 'margin:20px 0 8px;font-size:16px;color:#4a3b32;border-bottom:1px solid #e8dcc8;padding-bottom:4px;');
            box.appendChild(h);
            g.entries.forEach(function (e) {
                var p = document.createElement('p');
                p.textContent = (e.ts ? e.ts + '  ' : '') + nameOf(e) + '：' + String(e.message).trim();
                p.setAttribute('style', 'margin:0 0 8px;font-size:13px;line-height:1.7;');
                box.appendChild(p);
            });
        });

        var foot = document.createElement('p');
        foot.textContent = 'MPC 宠物聊天 · 用陪伴传递温暖';
        foot.setAttribute('style', 'margin-top:28px;font-size:12px;color:#a89a8a;text-align:center;');
        box.appendChild(foot);

        document.body.appendChild(box);
        return html2canvas(box, { scale: 2, backgroundColor: '#FFFDF8' }).then(function (canvas) {
            document.body.removeChild(box);
            var jsPDF = window.jspdf.jsPDF;
            var pdf = new jsPDF('p', 'mm', 'a4');
            var pdfW = pdf.internal.pageSize.getWidth();
            var pdfH = pdf.internal.pageSize.getHeight();
            var pxPerMm = canvas.width / pdfW;
            var pageHpx = Math.floor(pdfH * pxPerMm);
            var y = 0;
            var first = true;
            while (y < canvas.height) {
                var sliceH = Math.min(pageHpx, canvas.height - y);
                var pc = document.createElement('canvas');
                pc.width = canvas.width;
                pc.height = sliceH;
                pc.getContext('2d').drawImage(canvas, 0, y, canvas.width, sliceH, 0, 0, canvas.width, sliceH);
                if (!first) pdf.addPage();
                // 每页只画本页切片的实际高度（旧实现把切片拉伸到整图高度 → 页页重复整图）
                pdf.addImage(pc.toDataURL('image/png'), 'PNG', 0, 0, pdfW, sliceH / pxPerMm);
                first = false;
                y += sliceH;
            }
            pdf.save('MPC陪伴日记_' + localDateKey(now) + '.pdf');
        }).catch(function (err) {
            if (box.parentNode) box.parentNode.removeChild(box);
            throw err;
        });
    }
    exportBtn.addEventListener('click', function () {
        if (!lastGrouped.length) { toast('当前筛选条件下没有日记', 'info'); return; }
        var old = exportBtn.textContent;
        exportBtn.disabled = true;
        exportBtn.textContent = '生成中…';
        setTimeout(function () {
            buildPdf()
                .then(function () { toast('PDF 已导出', 'success'); })
                .catch(function () { toast('PDF 生成失败', 'error'); })
                .then(function () { exportBtn.disabled = false; exportBtn.textContent = old; });
        }, 30);
    });

    // ---------- 事件 ----------
    petSel.addEventListener('change', render);
    dateSel.addEventListener('change', render);
    var kwTimer = null;
    kwInput.addEventListener('input', function () {
        clearTimeout(kwTimer);
        kwTimer = setTimeout(render, 150);   // 防抖：避免每个按键重建大段 DOM
    });
    $('btn-reset-filters').addEventListener('click', function () {
        petSel.value = 'all';
        dateSel.value = 'all';
        kwInput.value = '';
        render();
    });

    render();
})();
