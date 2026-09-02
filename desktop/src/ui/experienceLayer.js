/**
 * Passive desktop experience layer.
 *
 * It observes already-rendered Mary state and adds presentation polish. It does
 * not send commands, mutate Core state, infer new memories, or turn provider
 * metadata into identity.
 */

const textOf = (selector, fallback = '') => {
  const node = document.querySelector(selector);
  return (node?.textContent || fallback).trim();
};

const normalize = (value, fallback = 'neutral') =>
  String(value || fallback).trim().toLowerCase().replace(/\s+/g, '-');

const themeFrom = (mood, state) => {
  const m = normalize(mood);
  const s = normalize(state, 'idle');
  if (['thinking', 'transcribing', 'responding'].includes(s)) return 'focused';
  if (['angry', 'firm', 'serious', 'hurt'].includes(m)) return 'serious';
  if (['sad', 'soft', 'tender', 'shy'].includes(m)) return 'soft';
  if (['happy', 'excited', 'amused', 'playful', 'flirty'].includes(m)) return 'bright';
  return 'mary';
};

function installAmbient(app) {
  if (document.querySelector('.mary-xp-ambient')) return;
  const ambient = document.createElement('div');
  ambient.className = 'mary-xp-ambient';
  ambient.setAttribute('aria-hidden', 'true');
  ambient.innerHTML = '<i class="xp-orb"></i><i class="xp-orb"></i><i class="xp-grid"></i>';
  document.body.prepend(ambient);

  const stage = document.querySelector('.main-stage');
  if (stage && !stage.querySelector('.mary-xp-ribbon')) {
    const ribbon = document.createElement('div');
    ribbon.className = 'mary-xp-ribbon';
    ribbon.innerHTML = '<strong>MARY</strong><span class="xp-ribbon-text">persistent companion · core linked</span>';
    stage.appendChild(ribbon);
  }

  const corner = document.createElement('div');
  corner.className = 'mary-xp-corner';
  corner.setAttribute('aria-hidden', 'true');
  corner.innerHTML = '<img src="./assets/ui/mary-heart-core.svg" alt=""><span>identity · Mary Core</span>';
  document.body.appendChild(corner);

  window.addEventListener('pointermove', (event) => {
    if (!app || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    app.style.setProperty('--xp-pointer-x', `${(event.clientX / window.innerWidth) * 100}%`);
    app.style.setProperty('--xp-pointer-y', `${(event.clientY / window.innerHeight) * 100}%`);
  }, { passive: true });
}

function project(app) {
  if (!app) return;
  const state = textOf('#avatar-live-state', textOf('#status-text', 'idle'));
  const mood = textOf('#state-mood', textOf('#avatar-mood', 'neutral'));
  const provider = textOf('#model-label', '');
  app.dataset.xpState = normalize(state, 'idle');
  app.dataset.xpMood = normalize(mood, 'neutral');
  app.dataset.xpTheme = themeFrom(mood, state);

  const ribbon = document.querySelector('.mary-xp-ribbon .xp-ribbon-text');
  if (ribbon) {
    const base = `${state || 'Idle'} · ${mood || 'Neutral'}`;
    const nextText = provider && provider !== '—' ? `${base} · ${provider}` : base;
    if (ribbon.textContent !== nextText) ribbon.textContent = nextText;
  }
}

export function installExperienceLayer({ app } = {}) {
  if (!app || app.dataset.experienceLayerInstalled === 'true') return;
  app.dataset.experienceLayerInstalled = 'true';
  installAmbient(app);
  project(app);

  const observer = new MutationObserver(() => project(app));
  observer.observe(app, { subtree: true, childList: true, characterData: true });
  window.addEventListener('pagehide', () => observer.disconnect(), { once: true });
}
