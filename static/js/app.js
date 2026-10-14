/* 全站公共 JS：toast + 顶栏汉堡（规范：docs/UI重构设计文档.md 二.6/二.7） */

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
