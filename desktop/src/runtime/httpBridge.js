class Signal {
  constructor() { this.listeners = new Set(); }
  connect(callback) { if (typeof callback === 'function') this.listeners.add(callback); }
  disconnect(callback) { this.listeners.delete(callback); }
  emit(...args) {
    for (const callback of [...this.listeners]) {
      try { callback(...args); } catch (error) { console.error('[MaryMobile] signal listener failed', error); }
    }
  }
}

function tokenKey() { return 'mary.mobileToken'; }

function savedToken() {
  try { return localStorage.getItem(tokenKey()) || ''; } catch (_) { return ''; }
}

function saveToken(value) {
  try {
    if (value) localStorage.setItem(tokenKey(), value);
    else localStorage.removeItem(tokenKey());
  } catch (_) { /* storage is best effort */ }
}

function askForToken() {
  const value = window.prompt('Enter your Mary mobile access token. You only need to do this once on this device.');
  const token = String(value || '').trim();
  if (token) saveToken(token);
  return token;
}

async function apiRequest(path, options = {}, { retryAuth = true } = {}) {
  const headers = new Headers(options.headers || {});
  headers.set('Accept', 'application/json');
  if (options.body && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json');
  const token = savedToken();
  if (token) headers.set('Authorization', `Bearer ${token}`);

  const response = await fetch(path, { ...options, headers, cache: 'no-store' });
  if (response.status === 401 && retryAuth) {
    saveToken('');
    const supplied = askForToken();
    if (supplied) return apiRequest(path, options, { retryAuth: false });
  }
  let payload = {};
  try { payload = await response.json(); } catch (_) { /* handled below */ }
  if (!response.ok) {
    const message = payload?.error || `${response.status} ${response.statusText}`;
    throw new Error(message);
  }
  return payload;
}

function callbackResult(callback, value) {
  if (typeof callback !== 'function') return;
  if (typeof value === 'boolean') callback(value);
  else callback(JSON.stringify(value ?? {}));
}

function browserSpeechAvailable() {
  return Boolean(window.speechSynthesis && window.SpeechSynthesisUtterance);
}

function browserRecognitionConstructor() {
  return window.SpeechRecognition || window.webkitSpeechRecognition || null;
}

export async function createHttpBridge() {
  await apiRequest('/api/health');

  const bridge = {
    messageReady: new Signal(),
    avatarStateChanged: new Signal(),
    busyChanged: new Signal(),
    errorOccurred: new Signal(),
    listeningStateChanged: new Signal(),
    transcriptionReady: new Signal(),
    conversationStateChanged: new Signal(),
    characterStateChanged: new Signal(),
    dashboardStateChanged: new Signal(),
    voicePlaybackStopRequested: new Signal(),
  };

  let recognition = null;
  let speaking = false;

  const state = (name, reason = 'mobile') => {
    bridge.conversationStateChanged.emit(JSON.stringify({ state: name, reason }));
  };

  const refreshStateSignals = (payload = {}) => {
    if (payload.character) bridge.characterStateChanged.emit(JSON.stringify(payload.character));
    if (payload.dashboard) bridge.dashboardStateChanged.emit(JSON.stringify(payload.dashboard));
  };

  const speak = (text) => {
    if (!browserSpeechAvailable()) return false;
    if (localStorage.getItem('mary.mobileSpeak') === 'false') return false;
    try {
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(String(text || ''));
      utterance.rate = Number(localStorage.getItem('mary.mobileVoiceRate') || '1');
      utterance.pitch = Number(localStorage.getItem('mary.mobileVoicePitch') || '1');
      utterance.onstart = () => { speaking = true; state('speaking', 'browser_tts_started'); };
      utterance.onend = () => { speaking = false; state('idle', 'browser_tts_finished'); };
      utterance.onerror = () => { speaking = false; state('idle', 'browser_tts_failed'); };
      window.speechSynthesis.speak(utterance);
      return true;
    } catch (_) {
      return false;
    }
  };

  bridge.sendMessage = async (text) => {
    const value = String(text || '').trim();
    if (!value) return;
    bridge.busyChanged.emit(true);
    state('thinking', 'mobile_message_submitted');
    try {
      const payload = await apiRequest('/api/chat', {
        method: 'POST',
        body: JSON.stringify({ text: value }),
      });
      bridge.messageReady.emit(JSON.stringify(payload));
      if (payload.avatar) bridge.avatarStateChanged.emit(JSON.stringify(payload.avatar));
      refreshStateSignals(payload);
      bridge.busyChanged.emit(false);
      if (!speak(payload.text || '')) state('idle', 'mobile_turn_complete');
    } catch (error) {
      bridge.busyChanged.emit(false);
      state('idle', 'mobile_turn_failed');
      bridge.errorOccurred.emit(error?.message || String(error));
    }
  };

  bridge.startListening = () => {
    const Recognition = browserRecognitionConstructor();
    if (!Recognition) {
      bridge.errorOccurred.emit('Voice input is not available in this browser. You can still type to Mary.');
      return;
    }
    if (recognition) return;
    recognition = new Recognition();
    recognition.lang = navigator.language || 'en-US';
    recognition.interimResults = false;
    recognition.continuous = false;
    recognition.maxAlternatives = 1;
    recognition.onstart = () => {
      bridge.listeningStateChanged.emit('listening');
      state('listening', 'browser_stt_started');
    };
    recognition.onresult = (event) => {
      const text = event.results?.[0]?.[0]?.transcript || '';
      if (text.trim()) bridge.transcriptionReady.emit(text.trim());
    };
    recognition.onerror = (event) => {
      bridge.errorOccurred.emit(`Voice input failed: ${event.error || 'unknown error'}`);
    };
    recognition.onend = () => {
      recognition = null;
      bridge.listeningStateChanged.emit('idle');
      state('idle', 'browser_stt_finished');
    };
    try { recognition.start(); } catch (error) {
      recognition = null;
      bridge.errorOccurred.emit(`Could not start voice input: ${error}`);
    }
  };

  bridge.stopListening = () => {
    try { recognition?.stop(); } catch (_) { /* best effort */ }
  };

  bridge.voicePlaybackStage = () => {};
  bridge.voicePlaybackStarted = () => { speaking = true; state('speaking', 'audio_started'); };
  bridge.voicePlaybackFinished = () => { speaking = false; state('idle', 'audio_finished'); };

  const bridgeCall = async (method, args = [], callback = null) => {
    try {
      const payload = await apiRequest('/api/bridge', {
        method: 'POST',
        body: JSON.stringify({ method, args }),
      });
      callbackResult(callback, payload.result);
      if (!method.startsWith('get') && !method.startsWith('personalSearch') && !method.startsWith('playArcade')) {
        try {
          const dashboard = await bridgeCallRaw('getDashboardState', []);
          bridge.dashboardStateChanged.emit(JSON.stringify(dashboard));
        } catch (_) { /* non-critical refresh */ }
      }
      return payload.result;
    } catch (error) {
      bridge.errorOccurred.emit(error?.message || String(error));
      callbackResult(callback, { ok: false, error: error?.message || String(error) });
      return null;
    }
  };

  const bridgeCallRaw = async (method, args = []) => {
    const payload = await apiRequest('/api/bridge', {
      method: 'POST',
      body: JSON.stringify({ method, args }),
    });
    return payload.result;
  };

  const callbackMethods = [
    'getStatus', 'getAvatarState', 'getCharacterState', 'getDashboardState',
    'getEcosystemState', 'getMindStatus', 'rebuildCognitiveReservoir',
    'getLastTurnTrace', 'getIntegrationState', 'getYouTubeStatus',
    'chooseSearchRoot', 'chooseMediaFile', 'chooseCreativeFile',
    'getCreativeWorkspaceState', 'chooseCreativeWorkspace',
  ];
  callbackMethods.forEach((method) => {
    bridge[method] = (callback) => bridgeCall(method, [], callback);
  });

  bridge.addCommandItem = (title, kind, callback) => bridgeCall('addCommandItem', [title, kind], callback);
  bridge.updateCommandStatus = (id, statusValue, callback) => bridgeCall('updateCommandStatus', [id, statusValue], callback);
  bridge.startFocus = (minutes, task, callback) => bridgeCall('startFocus', [minutes, task], callback);
  bridge.stopFocus = (callback) => bridgeCall('stopFocus', [], callback);
  bridge.createStudyProject = (title, objective, callback) => bridgeCall('createStudyProject', [title, objective], callback);
  bridge.addStudyCard = (project, prompt, answer, callback) => bridgeCall('addStudyCard', [project, prompt, answer], callback);
  bridge.reviewStudyCard = (project, card, score, callback) => bridgeCall('reviewStudyCard', [project, card, score], callback);
  bridge.personalSearch = (query, callback) => bridgeCall('personalSearch', [query], callback);
  bridge.markNoticeRead = async (id) => Boolean(await bridgeCall('markNoticeRead', [id]));
  bridge.createResearchThread = (title, question, callback) => bridgeCall('createResearchThread', [title, question], callback);
  bridge.playArcade = (key, payload, unused, callback) => bridgeCall('playArcade', [key, payload, unused], callback);
  bridge.getIdleAction = (callback) => bridgeCall('getIdleAction', [], callback);
  bridge.searchYouTube = (query, callback) => bridgeCall('searchYouTube', [query], callback);
  bridge.saveYouTubeToResearch = (title, url, callback) => bridgeCall('saveYouTubeToResearch', [title, url], callback);
  bridge.readCreativeTextFile = (path, callback) => bridgeCall('readCreativeTextFile', [path], callback);
  bridge.saveCreativeTextFile = (path, content, callback) => bridgeCall('saveCreativeTextFile', [path, content], callback);
  bridge.openCreativeWorkspaceFolder = (callback) => bridgeCall('openCreativeWorkspaceFolder', [], callback);
  bridge.openDataFolder = (callback) => bridgeCall('openDataFolder', [], callback);
  bridge.openWorkspaceFolder = (callback) => bridgeCall('openWorkspaceFolder', [], callback);
  bridge.launchCreativeApp = (key, file, callback) => bridgeCall('launchCreativeApp', [key, file], callback);
  bridge.openExternalUrl = (url, callback) => {
    const parsed = String(url || '');
    if (/^https?:\/\//i.test(parsed)) {
      window.open(parsed, '_blank', 'noopener,noreferrer');
      if (typeof callback === 'function') callback(true);
      return true;
    }
    if (typeof callback === 'function') callback(false);
    return false;
  };

  bridge.minimizeWindow = () => {};
  bridge.maximizeWindow = () => {};
  bridge.closeWindow = () => {};
  bridge.startWindowMove = () => {};
  bridge.save = () => {};
  bridge._isHttpBridge = true;
  bridge._isSpeaking = () => speaking;

  return bridge;
}

export function installMaryPwa() {
  if (!('serviceWorker' in navigator)) return;
  if (!window.isSecureContext && location.hostname !== 'localhost' && location.hostname !== '127.0.0.1') return;
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js').catch((error) => {
      console.warn('[MaryMobile] service worker unavailable', error);
    });
  }, { once: true });
}
