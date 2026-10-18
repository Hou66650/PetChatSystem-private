/* Presentation preferences only: never change pet behaviour or active call controls. */
document.addEventListener('DOMContentLoaded', () => {
  const wrap = document.getElementById('den-wrap');
  if (!wrap) return;
  const groups = [
    ['navigation', '顶部网站导航', 'body > .navbar'],
    ['pets', '宠物切换', '#den-pets'],
    ['info', '宠物信息与陪伴菜单', '#intimacy-panel, .cat-companion-standalone'],
    ['fullscreen', '全屏按钮', '#scene-fullscreen'],
    ['dock', '底部操作栏', '.glass-dock'],
  ];
  const buttons = [
    ['call', '叫它过来', '.glass-dock > .cat-call-button'],
    ['voice', '语音对话', '.glass-dock > #btn-voice'],
    ['pet', '摸摸', '.glass-dock > #btn-pet'],
    ['food', '喂食', '.glass-dock > [data-dock-panel="dock-food"]'],
    ['actions', '动作', '.glass-dock > [data-dock-panel="dock-actions"]'],
    ['chat', '聊天', '.glass-dock > #btn-chat'],
    ['more', '更多', '.glass-dock > [data-dock-panel="dock-more"]'],
  ];
  const options = [...groups, ...buttons];
  const key = 'pait-interface-v1:' + window.COMPANION_SCOPE;
  let preferences = {};
  function read(raw) {
    try {
      const data = JSON.parse(raw);
      return Object.fromEntries(options.map(([id]) => [id, data?.[id] !== false]));
    } catch { return {}; }
  }
  try { preferences = read(localStorage.getItem(key)); } catch { /* Private mode. */ }
  const rules = document.createElement('style');
  rules.textContent = options.map(([id, , selectors]) => selectors.split(',').map(selector =>
    `html.pait-hide-${id} ${selector.trim()}{display:none!important}`).join('\n')).join('\n');
  document.head.append(rules);
  const launcher = document.createElement('button');
  launcher.id = 'interface-toggle';
  launcher.type = 'button';
  launcher.textContent = '界面';
  launcher.setAttribute('aria-label', '界面显示设置');
  launcher.setAttribute('aria-haspopup', 'dialog');
  launcher.setAttribute('aria-controls', 'interface-settings');
  const dialog = document.createElement('dialog');
  dialog.id = 'interface-settings';
  // Scene downloads stay with the scene, not inside this instant settings panel.
  dialog.dataset.loadingOverlay = 'outside';
  dialog.setAttribute('aria-labelledby', 'interface-title');
  dialog.innerHTML = `<header><h2 id="interface-title">留下你需要的按钮</h2><button type="button" data-close aria-label="关闭界面设置">✕</button></header>
    <p>取消勾选即可隐藏。右上角「界面」随时可以找回它们。</p>
    <fieldset data-groups><legend>画面区域</legend></fieldset>
    <details><summary>单独选择底部按钮</summary><fieldset data-buttons><legend class="sr-only">底部按钮</legend></fieldset></details>
    <p class="interface-note">仅记住当前浏览器、当前账号的选择。不同宠物会保留各自可用的功能；通话与正在进行的互动不受影响。</p>
    <footer><button type="button" data-clean>全部隐藏</button><button type="button" data-reset>恢复默认</button><button type="button" data-done>完成</button></footer>
    <span class="interface-status" role="status"></span>`;
  for (const [list, selector] of [[groups, '[data-groups]'], [buttons, '[data-buttons]']]) {
    const fieldset = dialog.querySelector(selector);
    for (const [id, label] of list) {
      const row = document.createElement('label');
      const checkbox = document.createElement('input');
      checkbox.type = 'checkbox';
      checkbox.dataset.option = id;
      row.append(checkbox, document.createTextNode(label));
      fieldset.append(row);
    }
  }
  wrap.append(launcher, dialog);
  function apply() {
    for (const [id] of options) {
      document.documentElement.classList.toggle('pait-hide-' + id, preferences[id] === false);
      dialog.querySelector(`[data-option="${id}"]`).checked = preferences[id] !== false;
    }
    dialog.querySelector('[data-buttons]').disabled = preferences.dock === false;
    document.documentElement.classList.toggle('pait-custom-dock', buttons.some(([id]) => preferences[id] === false));
    // Close orphaned disclosures through their normal close handlers.
    for (const name of ['food', 'actions', 'more']) {
      if (preferences.dock === false || preferences[name] === false) {
        const panel = document.getElementById('dock-' + name);
        if (panel && !panel.hidden) panel.querySelector('.dock-close')?.click();
      }
    }
    requestAnimationFrame(() => window.dispatchEvent(new Event('resize')));
  }
  function save() {
    apply();
    const status = dialog.querySelector('[role="status"]');
    try { localStorage.setItem(key, JSON.stringify(preferences)); status.textContent = '已保存'; }
    catch { status.textContent = '本次已生效，浏览器未允许保存偏好'; }
  }
  launcher.addEventListener('click', () => dialog.showModal());
  dialog.addEventListener('change', event => {
    const id = event.target.dataset.option;
    if (!options.some(option => option[0] === id)) return;
    preferences[id] = event.target.checked;
    save();
  });
  dialog.querySelector('[data-clean]').onclick = () => {
    preferences = Object.fromEntries(options.map(([id]) => [id, false])); save();
  };
  dialog.querySelector('[data-reset]').onclick = () => { preferences = {}; save(); };
  dialog.querySelector('[data-close]').onclick = dialog.querySelector('[data-done]').onclick = () => dialog.close();
  dialog.addEventListener('close', () => launcher.focus({preventScroll: true}));
  window.addEventListener('storage', event => {
    if (event.key === key || event.key === null) { preferences = read(event.newValue); apply(); }
  });
  apply();
});
