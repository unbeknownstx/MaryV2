function esc(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}

function title(value) {
  return String(value || '')
    .replaceAll('_', ' ')
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function formatFocus(seconds) {
  const value = Math.max(0, Number(seconds) || 0);
  const minutes = Math.floor(value / 60);
  const remainder = Math.floor(value % 60);
  return `${String(minutes).padStart(2, '0')}:${String(remainder).padStart(2, '0')}`;
}

function list(items, render, empty) {
  return Array.isArray(items) && items.length
    ? items.map(render).join('')
    : `<div class="presence-empty">${esc(empty)}</div>`;
}

export function renderPresenceHome(dashboard = {}, ecosystem = {}) {
  const pulse = ecosystem.companion || {};
  const counts = pulse.counts || {};
  const focus = { ...(pulse.focus || {}), ...(ecosystem.focus || {}) };
  const live = dashboard.live || {};
  const character = live.character || {};
  const emotion = dashboard.emotion || {};
  const relationship = dashboard.relationship || {};
  const provider = dashboard.providers || {};
  const primary = pulse.primary_action || { label: 'Talk to Mary', screen: 'chat' };
  const route = (provider.effective_conversation_route || []).join(' → ') || 'No route';
  const mood = title(emotion.primary || character.mood || 'neutral');

  const topTasks = pulse.top_tasks || [];
  const thoughts = pulse.pending_thoughts || [];
  const curiosities = pulse.curiosities || [];
  const notices = pulse.notices || [];

  return `
    <section class="presence-home">
      <article class="presence-hero workspace-panel">
        <img class="presence-hero-art" src="./assets/mary-reference.jpeg" alt="Mary Cosma portrait artwork" />
        <div class="presence-hero-shade"></div>
        <div class="presence-hero-copy">
          <span class="presence-kicker">MARY // LIVE PRESENCE</span>
          <h3>${esc(pulse.headline || 'Mary is here.')}</h3>
          <p>${esc(pulse.detail || 'Talk, create, study, focus, or just hang out.')}</p>
          <div class="presence-badges">
            <span>${esc(mood)}</span>
            <span>${esc(relationship.label || 'Continuity')}</span>
            <span>${esc(pulse.presence_mode || 'companion')} mode</span>
          </div>
          <div class="presence-hero-actions">
            <button class="presence-primary" data-screen-jump="${esc(primary.screen || 'chat')}">${esc(primary.label || 'Talk to Mary')}</button>
            <button class="presence-secondary" data-screen-jump="chat">Open Chat</button>
          </div>
        </div>
        <div class="presence-live-pill" id="presence-home-live"><i></i>${focus.active ? `FOCUS ${formatFocus(focus.remaining_seconds)}` : 'ONLINE'}</div>
      </article>

      <div class="presence-stat-grid">
        <button class="presence-stat" data-screen-jump="command"><span>COMMAND</span><strong>${Number(counts.active_tasks || 0)}</strong><small>active items</small></button>
        <button class="presence-stat" data-screen-jump="study"><span>STUDY</span><strong>${Number(counts.study_due || 0)}</strong><small>reviews due</small></button>
        <button class="presence-stat" data-screen-jump="stream"><span>INBOX</span><strong>${Number(counts.inbox_unread || 0)}</strong><small>quiet notices</small></button>
        <button class="presence-stat ${focus.active ? 'active' : ''}" data-screen-jump="focus"><span>FOCUS</span><strong id="presence-home-focus-value">${focus.active ? formatFocus(focus.remaining_seconds) : 'READY'}</strong><small id="presence-home-focus-detail">${focus.active ? esc(focus.task || 'co-working') : 'start a block'}</small></button>
      </div>

      <div class="presence-grid">
        <article class="workspace-panel presence-panel">
          <header><div><span class="presence-kicker">NOW</span><h3>Continue Together</h3></div><button class="micro-link" data-screen-jump="command">Command →</button></header>
          <div class="presence-list">
            ${list(topTasks, (item) => `<button class="presence-row" data-screen-jump="command"><span class="presence-row-icon">✓</span><span><strong>${esc(item.title)}</strong><small>${esc(title(item.kind))} · priority ${Number(item.priority || 0)}</small></span></button>`, 'No active command items. Mary is free to just be with you.')}
          </div>
        </article>

        <article class="workspace-panel presence-panel">
          <header><div><span class="presence-kicker">MARY NOTICED</span><h3>Held Thoughts</h3></div><button class="micro-link" data-screen-jump="stream">Presence →</button></header>
          <div class="presence-list">
            ${list(thoughts, (item) => `<div class="presence-row static"><span class="presence-row-icon">◇</span><span><strong>${esc(item.text)}</strong><small>${esc(item.context || 'presence')}</small></span></div>`, 'Nothing is waiting to interrupt you. Silence is valid.')}
          </div>
        </article>

        <article class="workspace-panel presence-panel">
          <header><div><span class="presence-kicker">CURIOSITY</span><h3>What Mary Is Exploring</h3></div><button class="micro-link" data-screen-jump="personality">Profile →</button></header>
          <div class="presence-list">
            ${list(curiosities, (item) => `<button class="presence-row" data-prompt="I noticed you are curious about ${esc(item.description)}. Want to explore that together?"><span class="presence-row-icon">?</span><span><strong>${esc(item.description)}</strong><small>${esc(title(item.status))}</small></span></button>`, 'No active curiosity is represented right now.')}
          </div>
        </article>

        <article class="workspace-panel presence-panel">
          <header><div><span class="presence-kicker">QUIET INBOX</span><h3>Waiting, Not Interrupting</h3></div><button class="micro-link" data-screen-jump="stream">Inbox →</button></header>
          <div class="presence-list">
            ${list(notices, (item) => `<div class="presence-row static"><span class="presence-row-icon">•</span><span><strong>${esc(item.title)}</strong><small>${esc(title(item.category))}</small></span></div>`, 'Mary Inbox is clear.')}
          </div>
        </article>
      </div>

      <article class="presence-runtime-strip workspace-panel">
        <div><span>CONVERSATION ROUTE</span><strong>${esc(route)}</strong></div>
        <div><span>PRESENCE POLICY</span><strong>Bounded · quiet by default</strong></div>
        <div><span>STATE</span><strong>${esc(character.continuity === 'persistent_capable' ? 'Persistent continuity' : title(character.continuity || 'unknown'))}</strong></div>
      </article>
    </section>`;
}
