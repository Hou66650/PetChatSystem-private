/* 登录/注册页背景轮换：每次进入从已有图中选一张与上次不同的，预加载成功后再切换。
   sessionStorage 记忆上次图片，避免同一次会话连续重复；加载失败回退 c.jpg。 */
(function () {
    'use strict';

    var BACKGROUNDS = [
        '/static/images/a.jpg',
        '/static/images/b.jpg',
        '/static/images/c.jpg',
    ];
    var LAST_KEY = 'mpc_auth_bg_last';

    var last = null;
    try { last = sessionStorage.getItem(LAST_KEY); } catch (e) {}

    var candidates = BACKGROUNDS.filter(function (url) { return url !== last; });
    var selected = candidates[Math.floor(Math.random() * candidates.length)] || BACKGROUNDS[0];

    var preload = new Image();
    preload.onload = function () {
        document.documentElement.style.setProperty('--auth-bg-url', 'url("' + selected + '")');
        document.body.classList.add('auth-bg-ready');
        try { sessionStorage.setItem(LAST_KEY, selected); } catch (e) {}
    };
    preload.onerror = function () {
        document.documentElement.style.setProperty('--auth-bg-url', 'url("/static/images/c.jpg")');
        document.body.classList.add('auth-bg-ready');
    };
    preload.src = selected;
})();
