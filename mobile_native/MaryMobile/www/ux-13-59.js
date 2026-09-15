/* MaryV2 13.59 — LU-inspired quick workspace navigation.
   Presentation-only: filters and activates existing Mary workspace controls. */
(() => {
  'use strict';
  const sheet = document.getElementById('workspace-sheet');
  if (!sheet || sheet.querySelector('[data-mary-quick-switch]')) return;

  const style = document.createElement('style');
  style.textContent = `
    .mary-quick-switch{padding:0 16px 12px;position:sticky;top:0;z-index:2;background:linear-gradient(180deg,rgba(7,8,24,.98),rgba(7,8,24,.82),transparent)}
    .mary-quick-switch label{display:flex;align-items:center;gap:9px;padding:10px 12px;border:1px solid rgba(255,111,181,.25);border-radius:13px;background:rgba(255,255,255,.035);box-shadow:inset 0 1px 0 rgba(255,255,255,.025)}
    .mary-quick-switch label:focus-within{border-color:var(--mary-accent,#ff5aaa);box-shadow:0 0 0 2px color-mix(in srgb,var(--mary-accent,#ff5aaa) 14%,transparent)}
    .mary-quick-switch span{font-size:13px;color:var(--mary-glow,#5fe7ff)}
    .mary-quick-switch input{min-width:0;flex:1;border:0;outline:0;background:transparent;color:var(--mary-text,#f7f2ff);font:inherit;font-size:14px}
    .mary-quick-switch input::placeholder{color:rgba(238,237,255,.42)}
    .mary-quick-switch kbd{font:600 9px/1 system-ui;padding:4px 6px;border:1px solid rgba(255,255,255,.12);border-radius:6px;color:rgba(238,237,255,.5);background:rgba(255,255,255,.04)}
    .workspace-grid section[data-filter-empty="true"]{display:none}
    .workspace-grid button[data-filter-hidden="true"]{display:none}
    .workspace-grid button[data-quick-active="true"]{outline:2px solid color-mix(in srgb,var(--mary-accent,#ff5aaa) 48%,transparent);outline-offset:1px}
    .mary-quick-empty{display:none;padding:14px 16px 20px;text-align:center;color:rgba(238,237,255,.5);font-size:12px}
    .mary-quick-empty[data-visible="true"]{display:block}
  `;
  document.head.appendChild(style);

  const wrap = document.createElement('div');
  wrap.className = 'mary-quick-switch';
  wrap.dataset.maryQuickSwitch = 'true';
  wrap.innerHTML = '<label><span>⌕</span><input type="search" inputmode="search" autocomplete="off" placeholder="Find a Mary workspace…" aria-label="Find a Mary workspace"><kbd>⌘K</kbd></label>';
  const head = sheet.querySelector('.sheet-head');
  head?.insertAdjacentElement('afterend', wrap);
  const empty = document.createElement('div');
  empty.className = 'mary-quick-empty';
  empty.textContent = 'No matching workspace.';
  sheet.querySelector('.workspace-grid')?.insertAdjacentElement('afterend', empty);

  const input = wrap.querySelector('input');
  const buttons = [...sheet.querySelectorAll('.workspace-grid button[data-open]')];
  const sections = [...sheet.querySelectorAll('.workspace-grid section')];
  let active = -1;

  function visibleButtons(){ return buttons.filter(button => button.dataset.filterHidden !== 'true'); }
  function markActive(index){
    const visible = visibleButtons();
    visible.forEach(button => delete button.dataset.quickActive);
    if (!visible.length){ active = -1; return; }
    active = Math.max(0, Math.min(index, visible.length - 1));
    visible[active].dataset.quickActive = 'true';
    visible[active].scrollIntoView?.({block:'nearest'});
  }
  function filter(){
    const query = String(input.value || '').trim().toLowerCase();
    buttons.forEach(button => {
      const searchable = `${button.dataset.open || ''} ${button.textContent || ''}`.toLowerCase();
      button.dataset.filterHidden = query && !searchable.includes(query) ? 'true' : 'false';
    });
    sections.forEach(section => { section.dataset.filterEmpty = section.querySelector('button[data-open]:not([data-filter-hidden="true"])') ? 'false' : 'true'; });
    empty.dataset.visible = visibleButtons().length ? 'false' : 'true';
    markActive(0);
  }
  function focusSearch(){
    if (!sheet.open) document.getElementById('workspace-button')?.click();
    window.setTimeout(() => { input.focus(); input.select(); filter(); }, 0);
  }

  input.addEventListener('input', filter);
  input.addEventListener('keydown', event => {
    if (event.key === 'ArrowDown'){ event.preventDefault(); markActive(active + 1); }
    else if (event.key === 'ArrowUp'){ event.preventDefault(); markActive(active - 1); }
    else if (event.key === 'Enter'){
      const target = visibleButtons()[active < 0 ? 0 : active];
      if (target){ event.preventDefault(); target.click(); }
    } else if (event.key === 'Escape' && input.value){ event.stopPropagation(); input.value=''; filter(); }
  });
  document.addEventListener('keydown', event => {
    const editable = /^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement?.tagName || '');
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k'){
      event.preventDefault(); focusSearch();
    } else if (!editable && event.key === '/' && sheet.open){ event.preventDefault(); focusSearch(); }
  });
  sheet.addEventListener('close', () => { input.value=''; filter(); });
  filter();
})();
