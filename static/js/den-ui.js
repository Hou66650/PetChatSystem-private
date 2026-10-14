/* Nonmodal disclosure panels: one open at a time; all existing action IDs survive. */
document.addEventListener('DOMContentLoaded', () => {
  const triggers = Array.from(document.querySelectorAll('[data-dock-panel]'));
  const dock = document.querySelector('.glass-dock');
  let active = null;
  function close(restoreFocus = false) {
    if (!active) return;
    const trigger = active;
    document.getElementById(trigger.dataset.dockPanel).hidden = true;
    trigger.setAttribute('aria-expanded', 'false');
    active = null;
    if (restoreFocus) trigger.focus();
  }
  triggers.forEach(trigger => {
    const panel = document.getElementById(trigger.dataset.dockPanel);
    trigger.addEventListener('click', () => {
      const wasOpen = active === trigger;
      close();
      if (!wasOpen) {
        active = trigger;
        panel.hidden = false;
        trigger.setAttribute('aria-expanded', 'true');
        panel.querySelector('.dock-close').focus();
      }
    });
    panel.querySelector('.dock-close').addEventListener('click', () => close(true));
    // Close before the action opens another dialog, so its focus is not stolen.
    panel.addEventListener('click', event => {
      const button = event.target.closest('.action-btn');
      if (button && !button.disabled && !button.hasAttribute('aria-pressed')) close(true);
    }, true);
    panel.addEventListener('focusout', event => {
      if (event.relatedTarget && !panel.contains(event.relatedTarget) && event.relatedTarget !== trigger) close();
    });
  });
  document.addEventListener('pointerdown', event => {
    if (active && !event.target.closest('.dock-panel') && !event.target.closest('.glass-dock')) close();
  });
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && active) { event.preventDefault(); close(true); }
  });
  dock?.addEventListener('click', event => {
    if (event.target.closest('.action-btn') && !event.target.closest('[data-dock-panel]')) close();
  });
});
