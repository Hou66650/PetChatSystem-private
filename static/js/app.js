/* 全站公共 JS：toast + 顶栏汉堡（规范：docs/UI重构设计文档.md 二.6/二.7） */

// randomUUID is secure-context-only, while getRandomValues is also available on LAN HTTP.
// Keep native implementations; use cryptographic randomness for transaction/client IDs.
(function () {
  const c = globalThis.crypto;
  if (!c || typeof c.randomUUID === 'function' || typeof c.getRandomValues !== 'function') return;
  c.randomUUID = function () {
    const bytes = c.getRandomValues(new Uint8Array(16));
    bytes[6] = (bytes[6] & 15) | 64;
    bytes[8] = (bytes[8] & 63) | 128;
    const hex = Array.from(bytes, b => b.toString(16).padStart(2, '0'));
    return hex.slice(0, 4).join('') + '-' + hex.slice(4, 6).join('') + '-' +
      hex.slice(6, 8).join('') + '-' + hex.slice(8, 10).join('') + '-' + hex.slice(10).join('');
  };
})();

// ArkWeb 6.x may invalidate cached GL bindings between composited frames.
// Rebind state before drawing, without changing geometry, materials or page layout.
(function () {
  const prepared = new WeakSet();
  window.PaitWebCompat = {
    prepareRenderer(renderer) {
      if (!/ArkWeb\/6\./.test(globalThis.navigator?.userAgent || '') || prepared.has(renderer)) return renderer;
      prepared.add(renderer);
      const render = renderer.render;
      renderer.render = function (...args) {
        const target = this.getRenderTarget();
        const face = this.getActiveCubeFace();
        const level = this.getActiveMipmapLevel();
        this.resetState();
        this.setRenderTarget(target, face, level);
        return render.apply(this, args);
      };
      return renderer;
    }
  };
})();

// ---------- toast ----------
(function () {
  var container = null;

  function ensureContainer() {
    if (!container || !document.body.contains(container)) {
      container = document.createElement('div');
      container.className = 'toast-container';
      document.body.appendChild(container);
    }
    return container;
  }

  window.toast = function (msg, type, duration) {
    type = type || 'info';
    var box = ensureContainer();
    // 最多叠 3 条，超出挤掉最旧
    while (box.children.length >= 3) box.removeChild(box.firstChild);
    var el = document.createElement('div');
    el.className = 'toast ' + type;
    el.textContent = msg;
    el.setAttribute('role', 'status');
    el.addEventListener('click', function () { el.remove(); });
    box.appendChild(el);
    setTimeout(function () { el.remove(); },
      duration || (type === 'error' ? 4000 : 2500));
  };
})();

// ---------- 顶栏汉堡菜单 ----------
document.addEventListener('DOMContentLoaded', function () {
  var burger = document.getElementById('navbar-burger');
  var links = document.getElementById('navbar-links');
  if (burger && links) {
    burger.addEventListener('click', function () {
      links.classList.toggle('open');
      burger.setAttribute('aria-expanded', String(links.classList.contains('open')));
      burger.setAttribute('aria-label',
        links.classList.contains('open') ? '关闭菜单' : '打开菜单');
    });
    document.addEventListener('keydown', function (event) {
      if (event.key === 'Escape' && links.classList.contains('open')) {
        links.classList.remove('open');
        burger.setAttribute('aria-expanded', 'false');
        burger.setAttribute('aria-label', '打开菜单');
        burger.focus();
      }
    });
  }
});
