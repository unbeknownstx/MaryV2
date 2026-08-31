/* MaryV2 13.2 — passive experience renderer.
   This file can decorate Mary; it never owns Mary. */
(() => {
  'use strict';

  const STORAGE_SERVER = 'mary.mobileServer';
  const STORAGE_TOKEN = 'mary.mobileToken';
  const app = document.getElementById('app');
  if (!app) return;

  const rail = document.getElementById('mary-presence-rail');
  const context = document.getElementById('mary-presence-context');
  const relation = document.getElementById('mary-presence-relationship');
  const continuity = document.getElementById('mary-continuity-chip');
  let timer = 0;
  let unsupported = false;
  let latest = null;

  function endpoint() {
    const stored = (localStorage.getItem(STORAGE_SERVER) || '').trim();
    return (stored || window.location.origin).replace(/\/$/, '');
  }

  async function getExperience() {
    if (unsupported || document.hidden || app.dataset.connection === 'offline') return;
    const token = (localStorage.getItem(STORAGE_TOKEN) || '').trim();
    const headers = token ? { Authorization: `Bearer ${token}` } : {};
    try {
      const response = await fetch(`${endpoint()}/api/experience`, { headers, cache: 'no-store' });
      if (response.status === 404) {
        unsupported = true; // graceful compatibility with an older Core.
        return;
      }
      if (!response.ok) return;
      apply(await response.json());
    } catch (_) {
      // The canonical app owns connection UX; this optional layer stays quiet.
    }
  }

  function clean(value, fallback = '') {
    const text = String(value ?? '').trim();
    return text || fallback;
  }

  function apply(snapshot) {
    latest = snapshot || {};
    const theme = snapshot?.theme || {};
    const root = document.documentElement.style;
    if (theme.accent) root.setProperty('--mary-accent', theme.accent);
    if (theme.accent_2) root.setProperty('--mary-accent-2', theme.accent_2);
    if (theme.glow) root.setProperty('--mary-glow', theme.glow);
    if (theme.surface) root.setProperty('--mary-surface', theme.surface);
    if (theme.text) root.setProperty('--mary-text', theme.text);

    app.dataset.maryState = clean(snapshot?.interaction_state, 'idle').toLowerCase();
    app.dataset.maryMood = clean(snapshot?.mood, 'neutral').toLowerCase();
    app.dataset.maryEnergy = clean(snapshot?.energy, 'calm').toLowerCase();
    app.dataset.maryTheme = clean(theme?.name, 'mary').toLowerCase();

    if (rail) rail.dataset.state = app.dataset.maryState;
    if (context) {
      const task = clean(snapshot?.active_task);
      const label = clean(snapshot?.conversation_label, 'Main');
      context.textContent = task ? `${label} · ${task}` : `${label} · ${clean(snapshot?.lane, 'adaptive')}`;
    }
    if (relation) relation.textContent = clean(snapshot?.relationship_label, 'Developing');
    if (continuity) {
      const count = Number(snapshot?.memory_count || 0);
      continuity.querySelector('span').textContent = count > 0 ? `${count} memories indexed` : 'continuity online';
      continuity.title = `Identity: ${clean(snapshot?.identity_owner, 'mary_core')} · provider: ${clean(snapshot?.provider, '—')}`;
    }
    renderExperienceCards();
  }

  function renderExperienceCards() {
    if (!latest) return;
    const home = document.getElementById('home-content');
    if (home && home.childElementCount && !home.querySelector('.mary-experience-card')) {
      const card = document.createElement('article');
      card.className = 'card mary-experience-card';
      const latency = Number(latest.latency_ms);
      const latencyText = Number.isFinite(latency) ? `${Math.round(latency)} ms` : 'live';
      card.innerHTML = `
        <span class="eyebrow">EXPERIENCE LENS · PRESENTATION ONLY</span>
        <div class="xp-home-grid">
          <div><small>STATE</small><strong>${clean(latest.interaction_state, 'idle')}</strong></div>
          <div><small>MOOD</small><strong>${clean(latest.mood, 'neutral')}</strong></div>
          <div><small>CONTINUITY</small><strong>${Number(latest.memory_count || 0)}</strong></div>
          <div><small>LATENCY</small><strong>${latencyText}</strong></div>
        </div>
        <p>${clean(latest.active_task, 'Mary Core is linked. Surface state is being projected without owning identity or memory.')}</p>`;
      home.appendChild(card);
    }
  }

  function compactForKeyboard() {
    const viewport = window.visualViewport;
    if (!viewport) return;
    const keyboardLikely = window.innerHeight - viewport.height > 150;
    app.dataset.compact = keyboardLikely ? 'true' : 'false';
  }

  const surfaceObserver = new MutationObserver(() => renderExperienceCards());
  surfaceObserver.observe(document.getElementById('screen-stack') || app, { subtree: true, childList: true });

  document.addEventListener('visibilitychange', () => {
    if (!document.hidden) getExperience();
  });
  window.visualViewport?.addEventListener('resize', compactForKeyboard);
  window.visualViewport?.addEventListener('scroll', compactForKeyboard);

  getExperience();
  compactForKeyboard();
  timer = window.setInterval(getExperience, 3500);
  window.addEventListener('pagehide', () => {
    window.clearInterval(timer);
    surfaceObserver.disconnect();
  }, { once: true });
})();
