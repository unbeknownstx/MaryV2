import './launcher.css';

const $ = (selector) => document.querySelector(selector);
let bridge = null;

function parse(value) {
  if (typeof value === 'object' && value !== null) return value;
  try { return JSON.parse(value); } catch (_) { return {}; }
}

function toast(message, error = false) {
  const node = $('#launcher-toast');
  node.textContent = String(message || '');
  node.classList.remove('hidden', 'error');
  if (error) node.classList.add('error');
  window.clearTimeout(toast.timer);
  toast.timer = window.setTimeout(() => node.classList.add('hidden'), 4500);
}

function applyState(raw) {
  const state = parse(raw);
  const update = state.update || {};
  $('#installed-version').textContent = state.version || update.current_version || 'unknown';
  $('#release-channel').textContent = state.channel || 'private-v2';
  $('#desktop-phase').textContent = state.desktop_phase || 'desktop';

  if (!update.enabled) {
    $('#update-state').textContent = 'Manual / local';
    $('#update-notes').textContent = 'Set MARY_UPDATE_MANIFEST_URL later to enable verified remote update checks.';
    $('#stage-update-button').classList.add('hidden');
  } else if (update.update_available) {
    $('#update-state').textContent = `v${update.latest_version} available`;
    $('#update-notes').textContent = update.notes || 'A verified update is available.';
    $('#stage-update-button').classList.remove('hidden');
  } else if (update.latest_version) {
    $('#update-state').textContent = 'Up to date';
    $('#update-notes').textContent = update.notes || 'Mary is current.';
    $('#stage-update-button').classList.add('hidden');
  } else if (update.last_error) {
    $('#update-state').textContent = 'Check failed';
    $('#update-notes').textContent = update.last_error;
  } else {
    $('#update-state').textContent = 'Ready to check';
  }

  if (update.staged) {
    $('#update-state').textContent = `v${update.latest_version} staged`;
    $('#update-notes').textContent = update.apply_policy || 'Verified package staged for the future apply/rollback flow.';
  }
}

function connect() {
  if (!window.qt?.webChannelTransport || typeof QWebChannel === 'undefined') {
    $('#launcher-status').textContent = 'Open with Mary Launcher';
    return;
  }
  new QWebChannel(window.qt.webChannelTransport, (channel) => {
    bridge = channel.objects.launcherBridge;
    $('#launcher-status').textContent = 'Ready to launch';
    bridge.stateChanged.connect(applyState);
    bridge.errorOccurred.connect((message) => toast(message, true));
    bridge.appLaunched.connect(() => { $('#launcher-status').textContent = 'Launching Mary…'; });
    bridge.getState(applyState);
  });
}

$('#play-button').addEventListener('click', () => {
  if (!bridge) return;
  $('#launcher-status').textContent = 'Launching Mary…';
  bridge.play();
});
$('#check-update-button').addEventListener('click', () => {
  if (!bridge) return;
  $('#update-state').textContent = 'Checking…';
  bridge.checkForUpdates();
});
$('#stage-update-button').addEventListener('click', () => {
  if (!bridge) return;
  $('#update-state').textContent = 'Downloading / verifying…';
  bridge.stageUpdate();
});
$('#launcher-minimize').addEventListener('click', () => bridge?.minimizeWindow?.());
$('#launcher-close').addEventListener('click', () => bridge?.closeWindow?.());
$('#launcher-titlebar').addEventListener('pointerdown', (event) => {
  if (event.button !== 0 || event.target.closest('button')) return;
  bridge?.startWindowMove?.();
});

connect();
