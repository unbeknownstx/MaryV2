import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { VRMLoaderPlugin, VRMUtils } from '@pixiv/three-vrm';
import './style.css';

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => Array.from(document.querySelectorAll(selector));

const app = $('#app');
const canvas = $('#avatar-canvas');
const fallback = $('#avatar-fallback');
const messages = $('#messages');
const composer = $('#composer');
const input = $('#message-input');
const sendButton = $('#send-button');
const micButton = $('#mic-button');
const thinking = $('#thinking');
const statusDot = $('#status-dot');
const statusText = $('#status-text');
const modelLabel = $('#model-label');
const workspaceOverlay = $('#workspace-overlay');
const workspaceBody = $('#workspace-body');
const commandPalette = $('#command-palette');
const commandInput = $('#command-input');
const commandResults = $('#command-results');
const musicAudio = $('#music-audio');
const musicPlayButton = $('#music-play-button');

let bridge = null;
let dashboardState = {};
let ecosystemState = {};
let searchResults = [];
let focusTicker = null;
let lastIdleActionAt = performance.now();
let integrationState = { creative_apps: [] };
let creativeWorkspaceState = { configured: false, files: [] };
let activeStudioFile = '';
let activeStudioDocument = '';
let studioDirty = false;
let runtimeStatus = {};
let currentScreen = 'chat';
let selectedCreativeFile = '';
let busy = false;
let conversationState = 'idle';
let activeSpeechAudio = null;
let speechAudioContext = null;
let speechAudioSource = null;
let speechAnalyser = null;
let speechWaveform = null;
let activeMouthExpression = null;
let lipSyncWeight = 0;
let currentVrm = null;
let modelBaseY = 0;
let modelBounds = null;
let avatarFraming = 'portrait';

function parsePayload(value) {
  if (typeof value === 'object' && value !== null) return value;
  try { return JSON.parse(value); } catch (_) { return {}; }
}

function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}

function titleCase(value) {
  return String(value || '')
    .replaceAll('_', ' ')
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function clamp(value, min = 0, max = 1) {
  const number = Number(value);
  if (!Number.isFinite(number)) return min;
  return Math.min(max, Math.max(min, number));
}

function percent(value) {
  return `${Math.round(clamp(value) * 100)}%`;
}

function toast(message, kind = 'info') {
  const stack = $('#toast-stack');
  const item = document.createElement('div');
  item.className = `toast ${kind}`;
  item.textContent = String(message || '');
  stack.append(item);
  window.setTimeout(() => item.remove(), 4300);
}

function playUiSound(id, volume = .18) {
  const audio = $(id);
  if (!audio) return;
  try { audio.volume = volume; audio.currentTime = 0; audio.play().catch(() => {}); } catch (_) {}
}

function finishBoot(message = 'Mary is ready.') {
  const boot = $('#boot-screen');
  if (!boot || boot.classList.contains('hidden')) return;
  $('#boot-progress-bar').style.width = '100%';
  $('#boot-status').textContent = message;
  playUiSound('#ui-startup-sound', .15);
  window.setTimeout(() => boot.classList.add('hidden'), 550);
}

function bootStep(percentValue, message) {
  const bar = $('#boot-progress-bar'); const label = $('#boot-status');
  if (bar) bar.style.width = `${percentValue}%`;
  if (label) label.textContent = message;
}

// ---------------------------------------------------------------------------
// VRM / character presentation
// ---------------------------------------------------------------------------

const renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true });
renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.shadowMap.enabled = true;

const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(28, 1, 0.1, 100);
camera.position.set(0, 1.35, 2.6);

const keyLight = new THREE.DirectionalLight(0xffffff, 2.35);
keyLight.position.set(1.5, 2.6, 2.2);
scene.add(keyLight);
const fillLight = new THREE.DirectionalLight(0x7aa5ff, 1.25);
fillLight.position.set(-2.2, 1.3, 1.0);
scene.add(fillLight);
const rimLight = new THREE.DirectionalLight(0xff4fa6, 1.05);
rimLight.position.set(1.7, 1.5, -1.5);
scene.add(rimLight);
scene.add(new THREE.HemisphereLight(0xffffff, 0x171124, 1.65));

let previousFrameMs = performance.now();
let blinkAt = performance.now() + 1800;
let blinkPhase = -1;

function resizeRenderer() {
  const rect = canvas.getBoundingClientRect();
  const width = Math.max(1, Math.floor(rect.width));
  const height = Math.max(1, Math.floor(rect.height));
  renderer.setSize(width, height, false);
  camera.aspect = width / height;
  camera.updateProjectionMatrix();
}

function quaternionArrayFromEuler(x = 0, y = 0, z = 0) {
  const q = new THREE.Quaternion().setFromEuler(new THREE.Euler(x, y, z, 'XYZ'));
  return [q.x, q.y, q.z, q.w];
}

const RELAXED_STANDING_POSE = {
  leftUpperArm: { rotation: quaternionArrayFromEuler(0, 0, -1.28) },
  rightUpperArm: { rotation: quaternionArrayFromEuler(0, 0, 1.28) },
  leftLowerArm: { rotation: quaternionArrayFromEuler(0, -0.10, -0.10) },
  rightLowerArm: { rotation: quaternionArrayFromEuler(0, 0.10, 0.10) },
};

function applyRelaxedStandingPose(vrm) {
  const humanoid = vrm?.humanoid;
  if (!humanoid?.setNormalizedPose) return;
  humanoid.setNormalizedPose(RELAXED_STANDING_POSE);
  vrm.update(0);
}

function setAvatarFraming(mode = 'portrait') {
  avatarFraming = mode;
  if (!currentVrm || !modelBounds) return;
  resizeRenderer();

  const { box, size, center } = modelBounds;
  let frameHeight = size.y;
  let targetY = center.y;
  let padding = 1.18;

  if (mode === 'portrait') {
    frameHeight = size.y * 0.72;
    targetY = box.min.y + size.y * 0.64;
    padding = 1.05;
  } else if (mode === 'close') {
    frameHeight = size.y * 0.48;
    targetY = box.min.y + size.y * 0.76;
    padding = 1.03;
  }

  const width = Math.max(size.x, 0.55);
  const verticalFov = THREE.MathUtils.degToRad(camera.fov);
  const horizontalFov = 2 * Math.atan(Math.tan(verticalFov / 2) * Math.max(camera.aspect, 0.1));
  const verticalDistance = (Math.max(frameHeight, .65) / 2) / Math.tan(verticalFov / 2);
  const horizontalDistance = (width / 2) / Math.tan(horizontalFov / 2);
  const distance = Math.max(verticalDistance, horizontalDistance) * padding;

  camera.position.set(center.x, targetY, center.z + distance);
  camera.lookAt(center.x, targetY, center.z);
}

async function loadMaryVrm() {
  const loader = new GLTFLoader();
  loader.register((parser) => new VRMLoaderPlugin(parser));

  try {
    const gltf = await loader.loadAsync('./models/MaryCosma.vrm');
    const vrm = gltf.userData.vrm;
    if (!vrm) throw new Error('No VRM object was found in MaryCosma.vrm.');

    if (currentVrm) scene.remove(currentVrm.scene);
    VRMUtils.removeUnnecessaryVertices(vrm.scene);
    VRMUtils.combineSkeletons(vrm.scene);
    currentVrm = vrm;
    VRMUtils.rotateVRM0(currentVrm);
    applyRelaxedStandingPose(currentVrm);
    scene.add(currentVrm.scene);

    const box = new THREE.Box3().setFromObject(vrm.scene);
    const size = box.getSize(new THREE.Vector3());
    const center = box.getCenter(new THREE.Vector3());
    modelBounds = { box, size, center };
    modelBaseY = vrm.scene.position.y;
    setAvatarFraming(avatarFraming);
    fallback.classList.add('hidden');
    applyAvatarState({ expression: 'neutral', emotion_intensity: 0 });
  } catch (error) {
    console.warn('MaryCosma.vrm was not loaded:', error);
    fallback.classList.remove('hidden');
  }
}

const PRESET_MAP = {
  happy: 'happy', excited: 'happy', loving: 'happy', affectionate: 'happy',
  gratitude: 'happy', grateful: 'happy', proud: 'happy', warmth: 'happy',
  sad: 'sad', lonely: 'sad', disappointed: 'sad', concerned: 'sad',
  angry: 'angry', frustrated: 'angry',
  surprised: 'surprised', afraid: 'surprised', confused: 'surprised',
  calm: 'relaxed', hopeful: 'relaxed', curious: 'relaxed', neutral: 'relaxed',
};

function resetKnownExpressions(manager) {
  for (const preset of ['happy', 'sad', 'angry', 'surprised', 'relaxed']) {
    try { manager.setValue(preset, 0); } catch (_) { /* optional preset */ }
  }
}

function applyAvatarState(state = {}) {
  if (!currentVrm?.expressionManager) return;
  const manager = currentVrm.expressionManager;
  resetKnownExpressions(manager);
  const emotionName = String(state.expression || state.emotion || 'neutral').toLowerCase();
  const preset = PRESET_MAP[emotionName] || 'relaxed';
  const intensity = Math.max(0.08, clamp(state.emotion_intensity ?? state.intensity ?? 0.3));
  try { manager.setValue(preset, intensity); } catch (_) { /* optional preset */ }
}

function updateBlink(now) {
  const manager = currentVrm?.expressionManager;
  if (!manager) return;
  if (blinkPhase < 0 && now >= blinkAt) blinkPhase = 0;
  if (blinkPhase < 0) return;

  blinkPhase += 0.16;
  const amount = Math.sin(Math.min(Math.PI, blinkPhase * Math.PI));
  try { manager.setValue('blink', Math.max(0, amount)); } catch (_) { /* optional */ }

  if (blinkPhase >= 1) {
    try { manager.setValue('blink', 0); } catch (_) { /* optional */ }
    blinkPhase = -1;
    blinkAt = now + 2200 + Math.random() * 3200;
  }
}

function animate(now = performance.now()) {
  requestAnimationFrame(animate);
  resizeRenderer();
  const delta = Math.min(Math.max((now - previousFrameMs) / 1000, 0), 0.1);
  previousFrameMs = now;
  const elapsed = now / 1000;

  if (currentVrm) {
    updateLipSync();
    currentVrm.update(delta);
    currentVrm.scene.position.y = modelBaseY + Math.sin(elapsed * 1.25) * 0.006;
    const head = currentVrm.humanoid?.getNormalizedBoneNode?.('head');
    if (head) {
      head.rotation.y = Math.sin(elapsed * 0.22) * 0.035;
      head.rotation.z = Math.sin(elapsed * 0.31) * 0.012;
    }
    updateBlink(now);
  }
  renderer.render(scene, camera);
}

// ---------------------------------------------------------------------------
// Speech / lip sync
// ---------------------------------------------------------------------------

const MOUTH_PRESET_CANDIDATES = ['aa', 'oh', 'ou', 'ih', 'ee'];

function resolveMouthExpression() {
  const manager = currentVrm?.expressionManager;
  if (!manager) return null;
  for (const preset of MOUTH_PRESET_CANDIDATES) {
    try { if (manager.getExpression?.(preset)) return preset; } catch (_) { /* optional */ }
  }
  return null;
}

function resetLipSyncMouth() {
  const manager = currentVrm?.expressionManager;
  if (manager) {
    for (const preset of MOUTH_PRESET_CANDIDATES) {
      try { manager.setValue(preset, 0); } catch (_) { /* optional */ }
    }
  }
  activeMouthExpression = null;
  lipSyncWeight = 0;
}

function disconnectLipSyncGraph() {
  resetLipSyncMouth();
  try { speechAudioSource?.disconnect(); } catch (_) { /* best effort */ }
  try { speechAnalyser?.disconnect(); } catch (_) { /* best effort */ }
  speechAudioSource = null;
  speechAnalyser = null;
  speechWaveform = null;
}

function ensureSpeechAudioContext() {
  const AudioContextClass = window.AudioContext || window.webkitAudioContext;
  if (!AudioContextClass) return null;
  if (!speechAudioContext) speechAudioContext = new AudioContextClass();
  return speechAudioContext;
}

function attachLipSyncToAudio(audio) {
  disconnectLipSyncGraph();
  const context = ensureSpeechAudioContext();
  if (!context) return;
  try {
    const source = context.createMediaElementSource(audio);
    const analyser = context.createAnalyser();
    analyser.fftSize = 256;
    analyser.smoothingTimeConstant = 0.45;
    source.connect(analyser);
    analyser.connect(context.destination);
    speechAudioSource = source;
    speechAnalyser = analyser;
    speechWaveform = new Uint8Array(analyser.fftSize);
    activeMouthExpression = resolveMouthExpression();
    if (context.state === 'suspended') context.resume().catch(() => {});
  } catch (error) {
    console.warn('Lip sync analyser could not be attached:', error);
    disconnectLipSyncGraph();
  }
}

function updateLipSync() {
  const manager = currentVrm?.expressionManager;
  if (!manager || !speechAnalyser || !speechWaveform || !activeMouthExpression) return;
  let target = 0;
  if (activeSpeechAudio && !activeSpeechAudio.paused && !activeSpeechAudio.ended) {
    speechAnalyser.getByteTimeDomainData(speechWaveform);
    let sumSquares = 0;
    for (let index = 0; index < speechWaveform.length; index += 1) {
      const sample = (speechWaveform[index] - 128) / 128;
      sumSquares += sample * sample;
    }
    const rms = Math.sqrt(sumSquares / speechWaveform.length);
    const gated = Math.max(0, (rms - 0.018) * 7.5);
    target = Math.min(1, Math.sqrt(gated));
  }
  const response = target > lipSyncWeight ? 0.48 : 0.24;
  lipSyncWeight += (target - lipSyncWeight) * response;
  if (lipSyncWeight < 0.015 && target === 0) lipSyncWeight = 0;
  try { manager.setValue(activeMouthExpression, lipSyncWeight); } catch (_) { /* optional */ }
}

function stopVoicePlayback({ notifyBridge = true } = {}) {
  if (activeSpeechAudio) {
    try {
      activeSpeechAudio.pause();
      activeSpeechAudio.currentTime = 0;
    } catch (_) { /* best effort */ }
  }
  activeSpeechAudio = null;
  disconnectLipSyncGraph();
  if (notifyBridge && bridge?.voicePlaybackFinished) bridge.voicePlaybackFinished();
}

function playVoice(voice = {}) {
  if (!voice?.enabled || voice.status !== 'success' || !voice.audio_base64) return;
  stopVoicePlayback({ notifyBridge: false });
  const mimeType = voice.mime_type || 'audio/mpeg';
  const audio = new Audio(`data:${mimeType};base64,${voice.audio_base64}`);
  activeSpeechAudio = audio;
  attachLipSyncToAudio(audio);
  audio.addEventListener('play', () => {
    if (activeSpeechAudio === audio) bridge?.voicePlaybackStarted?.();
  });
  audio.addEventListener('ended', () => {
    if (activeSpeechAudio === audio) {
      activeSpeechAudio = null;
      disconnectLipSyncGraph();
      bridge?.voicePlaybackFinished?.();
    }
  });
  audio.addEventListener('error', () => {
    if (activeSpeechAudio === audio) activeSpeechAudio = null;
    disconnectLipSyncGraph();
    bridge?.voicePlaybackFinished?.();
    toast('Mary generated voice audio, but playback failed.', 'error');
  });
  audio.play().catch((error) => {
    if (activeSpeechAudio === audio) activeSpeechAudio = null;
    disconnectLipSyncGraph();
    bridge?.voicePlaybackFinished?.();
    toast(`Voice playback failed: ${error}`, 'error');
  });
}

// ---------------------------------------------------------------------------
// Conversation
// ---------------------------------------------------------------------------

function appendMessage(speaker, text, kind) {
  const article = document.createElement('article');
  article.className = `message ${kind}`;
  const meta = document.createElement('div');
  meta.className = 'message-meta';
  const label = document.createElement('span');
  label.textContent = speaker;
  const time = document.createElement('time');
  time.textContent = new Date().toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
  meta.append(label, time);
  const bubble = document.createElement('div');
  bubble.className = 'bubble';
  bubble.textContent = text;
  article.append(meta, bubble);
  messages.append(article);
  messages.scrollTop = messages.scrollHeight;
}

function setConnected(value, label = '') {
  statusDot.classList.toggle('connected', Boolean(value));
  statusText.textContent = label || (value ? 'Connection: Strong' : 'Disconnected');
}

function refreshConversationControls() {
  const listening = conversationState === 'listening';
  const transcribing = conversationState === 'transcribing';
  const thinkingNow = conversationState === 'thinking';
  const speaking = conversationState === 'speaking';
  const interrupted = conversationState === 'interrupted';

  input.disabled = listening || transcribing || thinkingNow || interrupted || busy;
  sendButton.disabled = input.disabled;
  micButton.disabled = transcribing || thinkingNow || interrupted || busy;
  micButton.classList.toggle('listening', listening);
  micButton.classList.toggle('transcribing', transcribing);
  micButton.classList.toggle('speaking', speaking);
  micButton.setAttribute('aria-pressed', listening ? 'true' : 'false');
  micButton.textContent = listening ? '■' : (transcribing ? '…' : (speaking ? '↯' : '◉'));
  micButton.title = listening ? 'Stop listening' : (speaking ? 'Interrupt Mary' : 'Push to talk');
  micButton.setAttribute('aria-label', listening ? 'Stop listening' : (speaking ? 'Interrupt' : 'Push to talk'));
  thinking.classList.toggle('hidden', !thinkingNow);

  const labels = {
    idle: 'Connection: Strong',
    listening: 'Listening…',
    transcribing: 'Transcribing…',
    thinking: 'Mary is thinking…',
    speaking: 'Mary speaking',
    interrupted: 'Interrupted…',
  };
  setConnected(true, labels[conversationState] || 'Connection: Strong');
  $('#avatar-live-state').textContent = `STATUS: ${String(conversationState || 'idle').toUpperCase()}`;
  $('#sidebar-activity').textContent = ({
    idle: 'Talking with you', listening: 'Listening to you', transcribing: 'Transcribing your voice',
    thinking: 'Thinking', speaking: 'Speaking', interrupted: 'Switching turns',
  })[conversationState] || 'Talking with you';
}

function setBusy(value) {
  busy = Boolean(value);
  refreshConversationControls();
}

function setConversationState(raw) {
  const payload = parsePayload(raw);
  const state = String(payload.state || raw || 'idle').toLowerCase();
  if (!['idle', 'listening', 'transcribing', 'thinking', 'speaking', 'interrupted'].includes(state)) return;
  conversationState = state;
  refreshConversationControls();
}

function submitPrompt(text) {
  const value = String(text || '').trim();
  if (!value || !bridge || busy) return;
  if (['listening', 'transcribing', 'thinking', 'interrupted'].includes(conversationState)) return;
  if (conversationState === 'speaking' || activeSpeechAudio) stopVoicePlayback({ notifyBridge: false });
  appendMessage('Unbe', value, 'user');
  bridge.sendMessage(value);
}

composer.addEventListener('submit', (event) => {
  event.preventDefault();
  const text = input.value.trim();
  if (!text) return;
  input.value = '';
  submitPrompt(text);
});

input.addEventListener('keydown', (event) => {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault();
    composer.requestSubmit();
  }
});

micButton.addEventListener('click', () => {
  if (!bridge || conversationState === 'transcribing' || conversationState === 'thinking') return;
  if (conversationState === 'listening') {
    bridge.stopListening();
    return;
  }
  if (conversationState === 'speaking' || activeSpeechAudio) stopVoicePlayback({ notifyBridge: false });
  bridge.startListening();
});

// ---------------------------------------------------------------------------
// Dashboard / live state
// ---------------------------------------------------------------------------

function renderMemoryHighlights(items = []) {
  const root = $('#memory-highlights');
  if (!items.length) {
    root.className = 'memory-list empty-state';
    root.textContent = 'No structured highlights yet.';
    return;
  }
  root.className = 'memory-list';
  root.innerHTML = items.slice(0, 5).map((item) => `
    <div class="memory-item">
      <span class="memory-icon">◇</span>
      <div class="memory-copy"><strong>${escapeHtml(item.title)}</strong><span>${escapeHtml(item.label || 'Memory')}</span></div>
      <span class="memory-tag">${escapeHtml(item.category || '')}</span>
    </div>
  `).join('');
}

function renderRecentActivities(items = []) {
  const root = $('#recent-activities');
  if (!items.length) {
    root.className = 'activity-list empty-state';
    root.textContent = 'No recent relationship activity yet.';
    return;
  }
  root.className = 'activity-list';
  root.innerHTML = items.slice(0, 5).map((item) => `
    <div class="activity-item">
      <span class="activity-icon">·</span>
      <div class="activity-copy"><strong>${escapeHtml(item.title)}</strong><span>${escapeHtml(titleCase(item.kind))}</span></div>
      <span class="activity-time">${escapeHtml(item.when || 'recently')}</span>
    </div>
  `).join('');
}

function renderProviderState(state = {}) {
  const route = state.effective_conversation_route || [];
  $('#provider-route').textContent = route.length
    ? `Conversation: ${route.join(' → ')}`
    : 'No effective conversation route reported yet.';
  const badges = $('#provider-badges');
  badges.innerHTML = (state.providers || []).map((provider) => `
    <span class="provider-badge ${provider.available ? 'ready' : ''}">${escapeHtml(provider.name)} · ${provider.available ? 'READY' : 'OFF'}</span>
  `).join('');
}

function applyCharacterState(raw) {
  const payload = parsePayload(raw);
  const character = payload.character || {};
  const memory = payload.memory || {};
  $('#state-name').textContent = String(character.name || 'Mary').toUpperCase();
  $('#state-continuity').textContent = character.continuity === 'persistent_capable' ? 'Persistent' : titleCase(character.continuity || 'Unknown');
  $('#state-mood').textContent = titleCase(character.mood || 'neutral');
  $('#state-energy').textContent = titleCase(character.energy || 'calm');
  $('#state-task').textContent = character.current_task || 'No active task';
  $('#avatar-mood-label').textContent = titleCase(character.mood || 'neutral');
  const total = character.memory_count ?? ((memory.episodic || 0) + (memory.semantic || 0));
  $('#app-version-label').title = `${total} represented durable memories`;
}

function applyDashboardState(raw) {
  const payload = parsePayload(raw);
  dashboardState = payload;
  ecosystemState = payload.ecosystem || ecosystemState || {};
  const live = payload.live || {};
  const character = live.character || {};
  const emotion = payload.emotion || {};
  const relationship = payload.relationship || {};

  applyCharacterState(live);
  renderMemoryHighlights(payload.memory_highlights || []);
  renderRecentActivities(payload.recent_activities || []);
  renderProviderState(payload.providers || {});
  const curiosities = payload.curiosities || [];
  const curiosity = curiosities[0] || {};
  if ($('#curiosity-headline')) $('#curiosity-headline').textContent = curiosity.description || curiosity.title || 'Nothing open right now';
  if ($('#curiosity-subline')) $('#curiosity-subline').textContent = curiosity.status ? `${titleCase(curiosity.status)} · ${Math.round(clamp(curiosity.importance ?? .5) * 100)}% importance` : 'Mary will only show curiosity actually represented in her agency state.';

  const mood = titleCase(emotion.primary || character.mood || 'neutral');
  const intensity = clamp(emotion.intensity || 0);
  const arousal = clamp(emotion.arousal || 0);
  $('#mood-headline').textContent = mood;
  $('#mood-subline').textContent = intensity > .65 ? 'Strong expressive state' : (intensity > .25 ? 'Present expressive state' : 'Quiet expressive state');
  $('#mood-intensity-label').textContent = titleCase(emotion.intensity_level || 'low');
  $('#state-mood').textContent = mood;
  $('#mood-meter').style.width = `${Math.max(12, intensity * 100)}%`;
  $('#energy-meter').style.width = `${Math.max(10, arousal * 100)}%`;
  $('#state-energy').textContent = titleCase(character.energy || (arousal > .7 ? 'high' : arousal > .35 ? 'engaged' : 'calm'));
  $$('#mood-blocks i').forEach((block, index) => block.classList.toggle('active', index < Math.max(1, Math.round(intensity * 10))));

  const score = Math.max(0, Math.min(100, Number(relationship.score || 0)));
  $('#relationship-score').textContent = `${score}%`;
  $('#relationship-headline').textContent = relationship.label || character.relationship || 'Beginning';
  $('#relationship-subline').textContent = `${relationship.milestones || 0} milestones · ${relationship.profile_records || 0} creator facts`;
  $('#connection-label').textContent = relationship.label || character.relationship || 'Beginning';
  $('#connection-meter').style.width = `${Math.max(5, score)}%`;
  $('#relationship-meter').style.width = `${Math.max(5, score)}%`;
  $('#relationship-ring').style.background = `conic-gradient(var(--pink) ${score * 3.6}deg, rgba(255,255,255,.07) 0deg)`;

  const moodTone = String(emotion.primary || character.mood || 'neutral').toLowerCase();
  app.dataset.mood = moodTone;
  $('#welcome-copy').innerHTML = `Mary is online · <strong>${escapeHtml(mood)}</strong> <span>♥</span>`;
  applyAvatarState({ expression: moodTone, emotion_intensity: intensity });

  const eco = ecosystemState || {};
  const study = eco.study || {}; const command = eco.command || {}; const inbox = eco.inbox || {}; const focus = eco.focus || {};
  if ($('#eco-study-due')) $('#eco-study-due').textContent = study.due ?? 0;
  if ($('#eco-task-count')) $('#eco-task-count').textContent = command.active ?? 0;
  if ($('#eco-inbox-count')) $('#eco-inbox-count').textContent = inbox.unread ?? 0;
  if ($('#eco-focus-state')) $('#eco-focus-state').textContent = focus.active ? 'Active' : 'Idle';

  if (currentScreen !== 'chat') renderWorkspace(currentScreen);
}

// ---------------------------------------------------------------------------
// Workspaces / game-like modes
// ---------------------------------------------------------------------------

const SCREEN_META = {
  memories: ['MEMORY ARCHIVE', 'Memories', 'Structured creator knowledge, shared history, and continuity.'],
  personality: ['MARY PROFILE', 'Personality', 'Mary’s authored and developed character state, separated from provider behavior.'],
  studio: ['CREATIVE MODE', 'Studio · Unbeknownst', 'A persistent creative workspace for chapters, lore, storyboards, and approved creative tools.'],
  study: ['LEARN WITH MARY', 'Study', 'Persistent study projects, due reviews, and spaced repetition around the same Mary.'],
  command: ['TODAY / PROJECTS', 'Command Center', 'Tasks, projects, goals, ideas, and waiting threads—kept intentionally lightweight.'],
  focus: ['CO-WORK', 'Focus With Mary', 'A quiet timer, local ambience, and lower-interruption companion mode.'],
  stream: ['PRESENCE', 'Stream & Presence', 'Initiative and idle context now; Twitch/OBS/vision remain optional until explicitly configured.'],
  gallery: ['VISUAL LIBRARY', 'Gallery', 'Character references, generated art, storyboards, screenshots, and project imagery.'],
  media: ['WATCH / LISTEN', 'Media', 'Local music now; richer media integrations remain explicit and opt-in.'],
  voice: ['VOICE / AVATAR', 'Voice & Avatar', 'VRM presentation, local-first voice, speech input, and live conversation state.'],
  search: ['PERSONAL SEARCH', 'Find That Thing', 'Bounded search over only the folders Mary has been allowed to inspect.'],
  research: ['RESEARCH', 'Research Notebook', 'Persistent research threads, notes, and conclusions without restarting from zero.'],
  arcade: ['PLAY', 'Mary Arcade', 'Small local games and creative sparks that do not require a cloud model.'],
  diagnostics: ['MARY DEV', 'Runtime & Latency', 'Grounded runtime metrics so performance problems can be measured instead of guessed.'],
  settings: ['SYSTEM', 'Settings', 'Provider availability, private state paths, skills, integrations, and desktop configuration.'],
};

function setScreen(screen) {
  const target = screen in SCREEN_META ? screen : 'chat';
  currentScreen = target;
  app.dataset.screen = target;
  $$('.nav-item').forEach((button) => button.classList.toggle('active', button.dataset.screen === target));
  if (target === 'chat') {
    workspaceOverlay.classList.add('hidden');
    input.focus();
  } else {
    workspaceOverlay.classList.remove('hidden');
    renderWorkspace(target);
    if (target === 'studio' && bridge?.getCreativeWorkspaceState) refreshCreativeWorkspace();
  }
}

function listOrEmpty(items, render, empty = 'Nothing represented here yet.') {
  return items?.length ? items.map(render).join('') : `<div class="workspace-empty">${escapeHtml(empty)}</div>`;
}

function renderMemories() {
  const highlights = dashboardState.memory_highlights || [];
  const activities = dashboardState.recent_activities || [];
  const memory = dashboardState.live?.memory || {};
  return `
    <div class="workspace-grid three">
      <div class="workspace-panel accent"><h3>Episodic</h3><div class="data-row"><span>Stored experiences</span><strong>${memory.episodic ?? 0}</strong></div></div>
      <div class="workspace-panel accent"><h3>Semantic</h3><div class="data-row"><span>Established knowledge</span><strong>${memory.semantic ?? 0}</strong></div></div>
      <div class="workspace-panel accent"><h3>Working</h3><div class="data-row"><span>Active context</span><strong>${memory.working ?? 0}</strong></div></div>
    </div>
    <div class="section-title">CURRENT CREATOR PROFILE HIGHLIGHTS</div>
    <div class="memory-browser">
      <div class="workspace-panel timeline">
        ${listOrEmpty(highlights, (item) => `
          <div class="data-row"><span>${escapeHtml(item.label)}</span><strong>${escapeHtml(item.title)}</strong></div>
        `, 'Mary does not have structured creator highlights to show yet.')}
      </div>
      <div class="workspace-panel memory-detail">
        <h3>Memory policy</h3>
        <p>This screen intentionally starts with source-aware creator profile items and counts instead of dumping raw episodic files. Raw-memory browsing can be added as an explicit advanced view without changing Mary's memory architecture.</p>
        <div class="data-row"><span>Backup recovered</span><strong>${memory.recovered_from_backup ? 'Yes' : 'No'}</strong></div>
        <div class="data-row"><span>Recent activity</span><strong>${activities.length}</strong></div>
      </div>
    </div>
  `;
}

function renderPersonality() {
  const profile = dashboardState.personality || {};
  const traits = profile.traits || [];
  const values = profile.values || [];
  const preferences = profile.preferences || [];
  return `
    <div class="workspace-grid">
      <div class="workspace-panel accent">
        <h3>Core / represented traits</h3>
        ${listOrEmpty(traits, (item) => `
          <div class="trait-row"><div class="trait-label"><span>${escapeHtml(titleCase(item.name))}</span><strong>${Math.round(clamp(item.value) * 100)}%</strong></div><div class="trait-bar"><i style="width:${Math.round(clamp(item.value) * 100)}%"></i></div></div>
        `, 'No trait snapshot available.')}
      </div>
      <div class="workspace-panel">
        <h3>Strong values</h3>
        ${listOrEmpty(values, (item) => `<div class="data-row"><span>${escapeHtml(titleCase(item.name))}</span><strong>${Math.round(clamp(item.strength) * 100)}%</strong></div>`, 'No values reported.')}
      </div>
    </div>
    <div class="section-title">PREFERENCES</div>
    <div class="workspace-panel"><div class="chip-row">${preferences.length ? preferences.map((item) => `<span class="chip">${item.polarity < 0 ? '−' : '+'} ${escapeHtml(titleCase(item.name))}</span>`).join('') : '<span class="chip">No represented preferences yet</span>'}</div></div>
  `;
}

function renderStudio() {
  const apps = integrationState.creative_apps || [];
  const workspace = creativeWorkspaceState || { configured: false, files: [] };
  const files = workspace.files || [];
  const appCards = apps.map((item) => `
    <div class="integration-item ${item.available ? '' : 'unavailable'}">
      <div class="integration-icon">${item.key === 'photoshop' ? 'Ps' : item.key === 'blender' ? '3D' : '✦'}</div>
      <div><strong>${escapeHtml(item.label)}</strong><small>${item.available ? 'Ready' : `Set ${escapeHtml(item.environment_variable)}`}</small></div>
      <button data-launch-app="${escapeHtml(item.key)}" ${item.available ? '' : 'disabled'}>Open</button>
    </div>
  `).join('');

  const fileRows = files.length ? files.map((item) => `
    <button class="project-file ${item.path === activeStudioFile ? 'active' : ''}" data-project-file="${escapeHtml(item.path)}" ${item.editable ? '' : 'data-reference-only="true"'}>
      <span>${item.editable ? '▤' : item.kind === 'image' ? '▧' : '◇'}</span>
      <span><strong>${escapeHtml(item.name)}</strong><small>${escapeHtml(item.path)}</small></span>
      <em>${escapeHtml(item.kind)}</em>
    </button>
  `).join('') : '<div class="workspace-empty compact">No supported project files found yet.</div>';

  const editor = activeStudioFile ? `
    <div class="studio-editor-head">
      <div><span>OPEN DOCUMENT</span><strong>${escapeHtml(activeStudioFile)}</strong></div>
      <div class="studio-editor-actions"><span id="studio-save-state">${studioDirty ? 'Unsaved' : 'Saved / loaded'}</span><button id="studio-save-file">Save</button></div>
    </div>
    <textarea id="studio-editor" spellcheck="true" aria-label="Creative text editor">${escapeHtml(activeStudioDocument)}</textarea>
    <div class="studio-editor-foot"><span>Edits are written only inside the selected creative workspace.</span><button class="text-link" data-prompt="Read the project excerpt I am working on in Studio and help me think through it without rewriting it unless I ask.">Work with Mary on this</button></div>
  ` : `
    <div class="editor-empty-state">
      <div class="editor-orb">M</div>
      <h3>${workspace.configured ? 'Choose a chapter or text file.' : 'Connect your Unbeknownst folder.'}</h3>
      <p>${workspace.configured ? 'Markdown, text, JSON, YAML, and CSV files can open directly in Studio. Creative/image assets remain available to external tools.' : 'Studio never scans your computer broadly. You choose one project folder, and Mary stays sandboxed to it.'}</p>
      <div class="action-grid">
        <button class="action-button" id="choose-project-folder"><strong>${workspace.configured ? 'Change Project Folder' : 'Choose Project Folder'}</strong><small>Connect Unbeknownst or another creative project</small></button>
        <button class="action-button" data-prompt="Help me plan the next Unbeknownst chapter. Start by asking only what you genuinely need from the current project state."><strong>Plan Chapter</strong><small>Structure and intent with Mary</small></button>
        <button class="action-button" data-prompt="Give me a continuity-focused critique of the Unbeknownst material we are currently working on."><strong>Continuity Pass</strong><small>Character, lore, and project consistency</small></button>
        <button class="action-button" data-prompt="Let's brainstorm this scene visually. Focus on composition, emotion, staging, and what should be shown rather than generic praise."><strong>Visual Brainstorm</strong><small>Scene and storyboard thinking</small></button>
      </div>
    </div>
  `;

  return `
    <div class="project-shell studio-live-shell">
      <div class="workspace-panel project-tree">
        <div class="project-tree-head"><div><span>PROJECT</span><h3>${escapeHtml(workspace.name || 'UNBEKNOWNST')}</h3></div><span class="tiny-badge">${workspace.configured ? `${files.length} FILES` : 'OFFLINE'}</span></div>
        <div class="project-path">${escapeHtml(workspace.root || 'No folder selected')}</div>
        <div class="project-files">${fileRows}</div>
        <div class="project-tree-actions">
          <button id="choose-project-folder">Choose Folder</button>
          <button id="open-project-folder" ${workspace.configured ? '' : 'disabled'}>Open Folder</button>
        </div>
      </div>
      <div class="studio-editor-panel">${editor}</div>
      <div class="workspace-panel studio-mary-panel">
        <h3>Mary · Creative Partner</h3>
        <p>Chat stays available below Studio. This is the same Mary and the same conversation/memory system—not a separate writing assistant.</p>
        <div class="action-grid studio-actions">
          <button class="action-button" data-prompt="Give me your actual opinion on the scene or chapter I'm currently working on. Focus on what is strongest and what you would push back on."><strong>Mary's Take</strong><small>Opinion, not automatic praise</small></button>
          <button class="action-button" data-prompt="Help me check the current chapter for continuity problems against what we already know about Unbeknownst."><strong>Continuity</strong><small>Look for contradictions</small></button>
        </div>
        <div class="section-title">EXTERNAL TOOLS</div>
        <div class="integration-grid" style="grid-template-columns:1fr">${appCards || '<div class="workspace-empty">Integrations load when the desktop bridge connects.</div>'}</div>
        <button class="text-link studio-file-pick" id="choose-creative-file">Choose PSD / KRA / CLIP / BLEND…</button>
        <small class="studio-safety-note">External app launches come from a finite allowlist and never execute arbitrary commands.</small>
      </div>
    </div>
  `;
}

function refreshCreativeWorkspace() {
  if (!bridge?.getCreativeWorkspaceState) return;
  bridge.getCreativeWorkspaceState((raw) => {
    creativeWorkspaceState = parsePayload(raw);
    if (currentScreen === 'studio') renderWorkspace('studio');
  });
}

function openStudioTextFile(path) {
  if (!bridge?.readCreativeTextFile || !path) return;
  bridge.readCreativeTextFile(path, (raw) => {
    const result = parsePayload(raw);
    if (!result.ok) return;
    activeStudioFile = result.path || path;
    activeStudioDocument = result.content || '';
    studioDirty = false;
    selectedCreativeFile = creativeWorkspaceState.root ? `${creativeWorkspaceState.root}/${activeStudioFile}` : selectedCreativeFile;
    if (currentScreen === 'studio') renderWorkspace('studio');
  });
}

function saveStudioTextFile() {
  if (!bridge?.saveCreativeTextFile || !activeStudioFile) return;
  const editor = $('#studio-editor');
  const content = editor?.value ?? activeStudioDocument;
  bridge.saveCreativeTextFile(activeStudioFile, content, (raw) => {
    const result = parsePayload(raw);
    if (!result.ok) return;
    activeStudioDocument = content;
    studioDirty = false;
    const label = $('#studio-save-state');
    if (label) label.textContent = 'Saved';
    toast(`Saved ${activeStudioFile}`);
    refreshCreativeWorkspace();
  });
}


function renderStudy() {
  const study = ecosystemState.study || {}; const projects = study.project_list || []; const due = study.due_cards || [];
  return `
    <div class="eco-grid">
      <div class="eco-stat"><span>Study Projects</span><strong>${study.projects ?? 0}</strong><small>persistent learning tracks</small></div>
      <div class="eco-stat"><span>Due Reviews</span><strong>${study.due ?? 0}</strong><small>spaced repetition</small></div>
      <div class="eco-stat"><span>Voice Quiz</span><strong>Ready</strong><small>use Mary chat / microphone</small></div>
      <div class="eco-stat"><span>Mode</span><strong>Coach</strong><small>same Mary, study workspace</small></div>
    </div>
    <div class="workspace-grid" style="margin-top:12px">
      <div class="workspace-panel hero-panel"><h3>Create a study track</h3><div class="workspace-form"><input id="study-title" placeholder="CompTIA A+ 220-1201"/><button id="study-create">Create</button></div><p>Mary can keep a certification or subject alive across sessions instead of rebuilding a study plan each time.</p></div>
      <div class="workspace-panel"><h3>Projects</h3><div class="study-list">${listOrEmpty(projects,(p)=>`<div class="study-row"><span class="kind">◈</span><div><strong>${escapeHtml(p.title)}</strong><small>${p.cards} cards · ${p.due} due</small></div><span class="status-chip">ACTIVE</span></div>`,'No study project yet.')}</div></div>
    </div>
    <div class="section-title">DUE NOW</div><div class="workspace-panel"><div class="study-list">${listOrEmpty(due,(c)=>`<div class="study-row"><span class="kind">?</span><div><strong>${escapeHtml(c.prompt)}</strong><small>${escapeHtml(c.project_title || 'Study')}</small></div><span class="status-chip">DUE</span></div>`,'Nothing due right now. Nice.')}</div></div>`;
}

function renderCommand() {
  const command = ecosystemState.command || {}; const items = command.items || [];
  return `<div class="eco-grid"><div class="eco-stat"><span>Active</span><strong>${command.active ?? 0}</strong><small>current threads</small></div><div class="eco-stat"><span>Waiting</span><strong>${command.waiting ?? 0}</strong><small>not in your hands</small></div><div class="eco-stat"><span>Projects</span><strong>${command.projects ?? 0}</strong><small>longer work</small></div><div class="eco-stat"><span>Goals</span><strong>${command.goals ?? 0}</strong><small>direction</small></div></div>
  <div class="workspace-panel hero-panel" style="margin-top:12px"><h3>Add something we're doing</h3><div class="workspace-form triple"><select id="command-kind"><option value="task">Task</option><option value="project">Project</option><option value="goal">Goal</option><option value="waiting">Waiting</option><option value="idea">Idea</option></select><input id="command-title" placeholder="What do we need to remember?"/><button id="command-add">Add</button></div></div>
  <div class="section-title">OPEN THREADS</div><div class="workspace-panel"><div class="command-list">${listOrEmpty(items,(item)=>`<div class="command-row"><span class="kind">${item.kind==='project'?'◇':item.kind==='goal'?'☆':'✓'}</span><div><strong>${escapeHtml(item.title)}</strong><small>${escapeHtml(titleCase(item.kind))} · priority ${item.priority}</small></div><button class="status-chip" data-command-done="${escapeHtml(item.id)}">${escapeHtml(item.status)}</button></div>`,'Nothing open. Add a task, project, goal, idea, or waiting thread.')}</div></div>`;
}

function formatFocusTime(seconds) { const value=Math.max(0,Number(seconds||0)); const m=Math.floor(value/60); const s=Math.floor(value%60); return `${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}`; }
function renderFocus() {
  const focus=ecosystemState.focus || {}; const remaining=focus.remaining_seconds || 0; const total=Math.max(1,(focus.minutes||45)*60); const angle=Math.max(0,Math.min(360,(1-remaining/total)*360));
  return `<div class="workspace-grid"><div class="workspace-panel hero-panel"><h3>Focus With Mary</h3><div class="focus-clock" style="--focus-angle:${angle}deg"><strong id="focus-time">${formatFocusTime(remaining || (focus.minutes||45)*60)}</strong><span>${focus.active?'IN SESSION':'READY'}</span></div><div class="focus-actions">${focus.active?'<button id="focus-stop">Finish</button>':'<button data-focus-minutes="25">25 min</button><button data-focus-minutes="45">45 min</button><button data-focus-minutes="60">60 min</button>'}</div></div><div class="workspace-panel"><h3>Co-working policy</h3><p>Focus mode is designed to make Mary quieter, not absent. Idle animation and local ambience can continue while unnecessary initiative is suppressed.</p><div class="data-row"><span>Task</span><strong>${escapeHtml(focus.task || 'Choose a focus block')}</strong></div><div class="data-row"><span>Cloud required</span><strong>No</strong></div><div class="data-row"><span>Premium TTS required</span><strong>No</strong></div></div></div>`;
}

function renderStream() {
  const presence=ecosystemState.presence || {}; const skills=ecosystemState.skills || []; const byKey=Object.fromEntries(skills.map(x=>[x.key,x]));
  return `<div class="presence-status"><div class="presence-node ready"><strong>Presence Core</strong><span>${escapeHtml(titleCase(presence.mode || 'companion'))} · initiative + silence</span></div><div class="presence-node"><strong>Twitch</strong><span>${byKey.twitch?.enabled?'Enabled':'Optional · disabled for first boot'}</span></div><div class="presence-node"><strong>OBS / Vision</strong><span>${byKey.obs?.enabled||byKey.vision?.enabled?'Enabled':'Optional · disabled for first boot'}</span></div></div>
  <div class="workspace-grid" style="margin-top:12px"><div class="workspace-panel hero-panel"><h3>Mary Presence</h3><p>The part that moves Mary beyond prompt → response: typed live context, pending thoughts, cheap idle behavior, and a decision layer where staying quiet is valid.</p><div class="data-row"><span>Pending thoughts</span><strong>${(presence.pending_thoughts||[]).length}</strong></div><div class="data-row"><span>Recent context events</span><strong>${(presence.recent||[]).length}</strong></div><button class="primary-small" id="presence-idle-test" style="height:34px;margin-top:8px">Preview an idle behavior</button></div><div class="workspace-panel"><h3>External systems — later</h3><p>Twitch, OBS, and screen vision are deliberately present as skills but disabled by default. They cannot block getting Mary running on your PC.</p><div class="chip-row">${['twitch','obs','vision'].map(k=>`<span class="chip">${byKey[k]?.enabled?'●':'○'} ${escapeHtml(titleCase(k))}</span>`).join('')}</div></div></div>`;
}

function renderSearch() {
  const roots=ecosystemState.paths?.search_roots || [];
  return `<div class="workspace-panel hero-panel"><h3>Find That Thing</h3><div class="workspace-form"><input id="personal-search-query" class="search-box" placeholder="chapter, quote, filename, code phrase…"/><button id="personal-search-button">Search</button></div><div class="chip-row">${roots.map(r=>`<span class="chip">${escapeHtml(r)}</span>`).join('')||'<span class="chip">No approved roots</span>'}</div><button class="text-link" id="search-add-root">Add approved folder</button></div><div class="section-title">RESULTS</div><div class="workspace-panel"><div class="search-results">${listOrEmpty(searchResults,(r)=>`<div class="search-row"><span class="kind">⌕</span><div><strong>${escapeHtml(r.name)}</strong><small>${escapeHtml(r.relative_path)}${r.snippet?` · ${escapeHtml(r.snippet)}`:''}</small></div><span class="status-chip">${escapeHtml(r.match)}</span></div>`,'Search only runs when you ask. Mary does not broadly crawl your PC.')}</div></div>`;
}

function renderResearch() {
  const research=ecosystemState.research || {}; const threads=research.threads || [];
  return `<div class="workspace-grid"><div class="workspace-panel hero-panel"><h3>Research Notebook</h3><div class="workspace-form"><input id="research-title" placeholder="Local TTS engines"/><button id="research-create">Create thread</button></div><p>Keep a research question, notes and conclusions together instead of starting from scratch every time.</p></div><div class="workspace-panel"><h3>Open threads</h3>${listOrEmpty(threads,(t)=>`<div class="data-row"><span>${escapeHtml(t.title)}</span><strong>${(t.notes||[]).length} notes</strong></div>`,'No research threads yet.')}</div></div>`;
}

function renderArcade() {
  const games=ecosystemState.arcade?.games || [];
  return `<div class="workspace-panel hero-panel"><h3>Mary Arcade</h3><p>Small local games keep the app entertaining even when you didn't open Mary with a task.</p><div class="game-grid">${games.map(g=>`<button class="game-card" data-arcade="${escapeHtml(g.key)}"><strong>${escapeHtml(g.label)}</strong><small>${escapeHtml(g.description)}</small></button>`).join('')}</div><div id="arcade-result" class="workspace-empty compact" style="margin-top:12px">Pick something.</div></div>`;
}

function renderDiagnostics() {
  const metrics=ecosystemState.metrics || {}; const rows=Object.entries(metrics);
  return `<div class="workspace-panel hero-panel"><h3>Runtime & Latency</h3><p>This is how we'll decide whether a delay is Ollama, speech, rendering, or something else instead of guessing.</p><div class="metric-grid">${rows.length?rows.map(([k,v])=>`<div class="metric-card"><span>${escapeHtml(titleCase(k))}</span><strong>${escapeHtml(v.last_ms)} ms</strong><small>avg ${escapeHtml(v.avg_ms)} · max ${escapeHtml(v.max_ms)}</small></div>`).join(''):'<div class="workspace-empty">Metrics appear after live turns.</div>'}</div></div>`;
}

function renderGallery() {
  return `
    <div class="workspace-grid three">
      <div class="workspace-panel accent"><h3>Mary Reference</h3><img src="./assets/mary-reference.jpeg" style="width:100%;height:240px;object-fit:cover;object-position:center 38%;border-radius:10px;opacity:.9" alt="Mary reference" /></div>
      <div class="workspace-panel"><h3>VRM</h3><p>MaryCosma.vrm is connected to the live stage and remains the preferred interactive avatar.</p><div class="data-row"><span>Model</span><strong>MaryCosma.vrm</strong></div><div class="data-row"><span>Renderer</span><strong>Three.js + three-vrm</strong></div></div>
      <div class="workspace-panel"><h3>Project Gallery</h3><div class="workspace-empty">At home we can bind this to Unbeknownst references, storyboards, generated images, screenshots, and tagged creative assets.</div></div>
    </div>
  `;
}

function renderMedia() {
  return `
    <div class="media-hero">
      <div>
        <strong>Watch or listen with Mary</strong>
        <p>Local audio playback is connected now. YouTube/search can open explicitly through the system browser; an embedded watch-together surface is scaffolded for the next live PC pass.</p>
        <div class="media-search"><input id="youtube-query" placeholder="Search YouTube…" /><button id="youtube-search-button">Search</button></div>
        <div class="action-grid" style="margin-top:12px">
          <button class="action-button" id="media-choose-audio"><strong>Choose Local Music</strong><small>Plays through Mary's persistent mini-player</small></button>
          <button class="action-button" data-prompt="Find a song or video that fits what we're working on. Tell me what you would search for and why."><strong>Ask Mary</strong><small>Use her conversation/research layer first</small></button>
        </div>
      </div>
    </div>
    <div class="section-title">MEDIA ROADMAP</div>
    <div class="workspace-grid three"><div class="workspace-panel"><h3>YouTube</h3><p>Search/result selection → in-app watch panel → transcript metadata for grounded reactions.</p></div><div class="workspace-panel"><h3>Music</h3><p>Local playback now; service integrations can remain explicit and opt-in.</p></div><div class="workspace-panel"><h3>Watch Together</h3><p>Mary's VRM can shrink to a side panel while the media surface becomes the center stage.</p></div></div>
  `;
}

function renderVoice() {
  const voice = runtimeStatus.voice || {};
  const stt = runtimeStatus.speech_to_text || {};
  return `
    <div class="workspace-grid">
      <div class="workspace-panel accent">
        <h3>Voice</h3>
        <div class="data-row"><span>TTS</span><strong>${voice.enabled ? `ON · ${escapeHtml(voice.provider || 'configured')}` : 'OFF'}</strong></div>
        <div class="data-row"><span>Speech input</span><strong>${stt.enabled ? `ON · ${escapeHtml(stt.provider || 'configured')}` : 'OFF'}</strong></div>
        <div class="data-row"><span>Conversation state</span><strong>${escapeHtml(titleCase(conversationState))}</strong></div>
        <p>Text remains authoritative. Voice/STT can fail without swallowing Mary's response or corrupting state.</p>
      </div>
      <div class="workspace-panel">
        <h3>Avatar camera</h3>
        <div class="action-grid"><button class="action-button" data-avatar-frame="full"><strong>Full</strong><small>Whole-character framing</small></button><button class="action-button" data-avatar-frame="portrait"><strong>Portrait</strong><small>Default companion framing</small></button><button class="action-button" data-avatar-frame="close"><strong>Close</strong><small>Face / upper body</small></button></div>
        <p>Expression, blink, idle movement, and speech lip-sync are already wired to the live VRM.</p>
      </div>
    </div>
  `;
}

function renderSettings() {
  const providers = dashboardState.providers || {};
  const paths = dashboardState.paths || {};
  const apps = integrationState.creative_apps || [];
  return `
    <div class="workspace-grid">
      <div class="workspace-panel accent"><h3>Runtime</h3><div class="data-row"><span>Host</span><strong>${escapeHtml(providers.host || 'unknown')} / ${escapeHtml(providers.platform || 'unknown')}</strong></div><div class="data-row"><span>Conversation</span><strong>${escapeHtml((providers.effective_conversation_route || []).join(' → ') || 'none')}</strong></div><div class="data-row"><span>Task/general</span><strong>${escapeHtml((providers.effective_task_route || []).join(' → ') || 'none')}</strong></div></div>
      <div class="workspace-panel"><h3>Private state</h3><div class="data-row"><span>Data root</span><strong>${escapeHtml(paths.data_root || 'unknown')}</strong></div><div class="data-row"><span>Workspace</span><strong>${escapeHtml(paths.workspace_root || 'unknown')}</strong></div><div class="action-grid"><button class="action-button" id="settings-open-data"><strong>Open Data Folder</strong><small>Mary's persistent private state</small></button><button class="action-button" id="settings-open-workspace"><strong>Open Workspace</strong><small>Project/filesystem root</small></button></div></div>
    </div>
    <div class="section-title">CREATIVE APP INTEGRATIONS</div>
    <div class="workspace-panel"><div class="integration-grid">${apps.map((item) => `<div class="integration-item ${item.available ? '' : 'unavailable'}"><div class="integration-icon">✦</div><div><strong>${escapeHtml(item.label)}</strong><small>${item.available ? escapeHtml(item.path || 'Ready') : `Set ${escapeHtml(item.environment_variable)}`}</small></div></div>`).join('') || '<div class="workspace-empty">No integration state yet.</div>'}</div></div>
    <div class="section-title">UPDATES</div>
    <div class="workspace-panel"><h3>Mary Launcher</h3><p>The separate game-style launcher owns version checks and verified update staging. Persistent data stays outside replaceable program versions. Automatic apply/rollback is intentionally held behind the first personal-PC validation.</p></div>
  `;
}

function renderWorkspace(screen) {
  if (screen === 'chat') return;
  const meta = SCREEN_META[screen] || ['MARY', titleCase(screen), ''];
  $('#workspace-eyebrow').textContent = meta[0];
  $('#workspace-title').textContent = meta[1];
  $('#workspace-description').textContent = meta[2];
  const renderers = {
    memories: renderMemories,
    personality: renderPersonality,
    studio: renderStudio,
    study: renderStudy,
    command: renderCommand,
    focus: renderFocus,
    stream: renderStream,
    search: renderSearch,
    research: renderResearch,
    arcade: renderArcade,
    diagnostics: renderDiagnostics,
    gallery: renderGallery,
    media: renderMedia,
    voice: renderVoice,
    settings: renderSettings,
  };
  workspaceBody.innerHTML = (renderers[screen] || (() => '<div class="workspace-empty">Coming soon.</div>'))();
  bindWorkspaceActions();
}

function bindWorkspaceActions() {
  $('#study-create')?.addEventListener('click', () => {
    const title=$('#study-title')?.value?.trim(); if(!title||!bridge?.createStudyProject)return;
    bridge.createStudyProject(title,'',(raw)=>{const r=parsePayload(raw);if(r.ok){toast('Study project created.');bridge.getDashboardState?.((x)=>applyDashboardState(x));}});
  });
  $('#command-add')?.addEventListener('click',()=>{const title=$('#command-title')?.value?.trim();const kind=$('#command-kind')?.value||'task';if(!title||!bridge?.addCommandItem)return;bridge.addCommandItem(title,kind,(raw)=>{const r=parsePayload(raw);if(r.ok){playUiSound('#ui-select-sound');bridge.getDashboardState?.((x)=>applyDashboardState(x));}});});
  $$('[data-command-done]').forEach((button)=>button.addEventListener('click',()=>bridge?.updateCommandStatus?.(button.dataset.commandDone,'done',(raw)=>{const r=parsePayload(raw);if(r.ok)bridge.getDashboardState?.((x)=>applyDashboardState(x));})));
  $$('[data-focus-minutes]').forEach((button)=>button.addEventListener('click',()=>{const minutes=Number(button.dataset.focusMinutes||45);bridge?.startFocus?.(minutes,'',(raw)=>{const r=parsePayload(raw);if(r.ok){toast(`Focus started · ${minutes} min`);bridge.getDashboardState?.((x)=>applyDashboardState(x));}});}));
  $('#focus-stop')?.addEventListener('click',()=>bridge?.stopFocus?.((raw)=>{const r=parsePayload(raw);if(r.ok){playUiSound('#ui-select-sound');bridge.getDashboardState?.((x)=>applyDashboardState(x));}}));
  $('#personal-search-button')?.addEventListener('click',()=>{const q=$('#personal-search-query')?.value?.trim();if(!q||!bridge?.personalSearch)return;bridge.personalSearch(q,(raw)=>{const r=parsePayload(raw);searchResults=r.results||[];renderWorkspace('search');});});
  $('#personal-search-query')?.addEventListener('keydown',(event)=>{if(event.key==='Enter'){event.preventDefault();$('#personal-search-button')?.click();}});
  $('#search-add-root')?.addEventListener('click',()=>bridge?.chooseSearchRoot?.((raw)=>{const r=parsePayload(raw);if(r.selected)bridge.getDashboardState?.((x)=>applyDashboardState(x));}));
  $('#research-create')?.addEventListener('click',()=>{const title=$('#research-title')?.value?.trim();if(!title||!bridge?.createResearchThread)return;bridge.createResearchThread(title,'',(raw)=>{const r=parsePayload(raw);if(r.ok)bridge.getDashboardState?.((x)=>applyDashboardState(x));});});
  $$('[data-arcade]').forEach((button)=>button.addEventListener('click',()=>bridge?.playArcade?.(button.dataset.arcade,'','',(raw)=>{const r=parsePayload(raw);const node=$('#arcade-result');if(node)node.textContent=r.message||r.result||r.error||'Done.';})));
  $('#presence-idle-test')?.addEventListener('click',()=>bridge?.getIdleAction?.((raw)=>{const r=parsePayload(raw);const a=r.action||{};toast(`Idle: ${a.name||'quiet'}`);if(a.sound){const audio=new Audio(`./assets/sounds/${a.sound}`);audio.volume=.12;audio.play().catch(()=>{});}}));
  $$('#workspace-body [data-project-file]').forEach((button) => button.addEventListener('click', () => {
    const path = button.dataset.projectFile || '';
    if (button.dataset.referenceOnly === 'true') {
      selectedCreativeFile = creativeWorkspaceState.root ? `${creativeWorkspaceState.root}/${path}` : selectedCreativeFile;
      toast(`Selected reference: ${path.split('/').pop()}`);
      return;
    }
    openStudioTextFile(path);
  }));
  $$('#workspace-body #choose-project-folder').forEach((button) => button.addEventListener('click', () => {
    bridge?.chooseCreativeWorkspace?.((raw) => {
      const result = parsePayload(raw);
      creativeWorkspaceState = result;
      if (result.selected) {
        activeStudioFile = '';
        activeStudioDocument = '';
        studioDirty = false;
        toast(`Studio connected: ${result.name || 'project'}`);
      }
      if (currentScreen === 'studio') renderWorkspace('studio');
    });
  }));
  $('#open-project-folder')?.addEventListener('click', () => bridge?.openCreativeWorkspaceFolder?.());
  $('#studio-save-file')?.addEventListener('click', saveStudioTextFile);
  $('#studio-editor')?.addEventListener('input', (event) => {
    activeStudioDocument = event.target.value;
    studioDirty = true;
    const label = $('#studio-save-state');
    if (label) label.textContent = 'Unsaved';
  });
  $('#studio-editor')?.addEventListener('keydown', (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 's') {
      event.preventDefault();
      saveStudioTextFile();
    }
  });
  $$('#workspace-body [data-prompt]').forEach((button) => button.addEventListener('click', () => {
    setScreen('chat');
    submitPrompt(button.dataset.prompt);
  }));
  $$('#workspace-body [data-avatar-frame]').forEach((button) => button.addEventListener('click', () => {
    setAvatarFraming(button.dataset.avatarFrame);
    toast(`Avatar framing: ${titleCase(button.dataset.avatarFrame)}`);
  }));
  $$('#workspace-body [data-launch-app]').forEach((button) => button.addEventListener('click', () => {
    if (!bridge?.launchCreativeApp) return;
    bridge.launchCreativeApp(button.dataset.launchApp, selectedCreativeFile || '', (ok) => {
      if (ok) toast('Creative application launched.');
    });
  }));

  $('#choose-creative-file')?.addEventListener('click', () => {
    bridge?.chooseCreativeFile?.((raw) => {
      const result = parsePayload(raw);
      if (!result.selected) return;
      selectedCreativeFile = result.path || '';
      toast(`Selected: ${selectedCreativeFile.split(/[\\/]/).pop()}`);
      renderWorkspace('studio');
    });
  });
  $('#open-workspace-folder')?.addEventListener('click', () => bridge?.openWorkspaceFolder?.());
  $('#settings-open-data')?.addEventListener('click', () => bridge?.openDataFolder?.());
  $('#settings-open-workspace')?.addEventListener('click', () => bridge?.openWorkspaceFolder?.());
  $('#media-choose-audio')?.addEventListener('click', chooseMusic);
  $('#youtube-search-button')?.addEventListener('click', () => {
    const query = $('#youtube-query')?.value?.trim();
    if (!query || !bridge?.openExternalUrl) return;
    bridge.openExternalUrl(`https://www.youtube.com/results?search_query=${encodeURIComponent(query)}`);
  });
  $('#youtube-query')?.addEventListener('keydown', (event) => {
    if (event.key === 'Enter') {
      event.preventDefault();
      $('#youtube-search-button')?.click();
    }
  });
}

$$('[data-screen]').forEach((button) => { button.addEventListener('click', () => { playUiSound('#ui-select-sound'); setScreen(button.dataset.screen); }); button.addEventListener('mouseenter',()=>playUiSound('#ui-hover-sound',.06)); });
$$('[data-screen-jump]').forEach((button) => button.addEventListener('click', () => setScreen(button.dataset.screenJump)));
$('#workspace-close').addEventListener('click', () => setScreen('chat'));
$$('#quick-actions [data-prompt]').forEach((button) => button.addEventListener('click', () => submitPrompt(button.dataset.prompt)));

// ---------------------------------------------------------------------------
// Local media mini-player
// ---------------------------------------------------------------------------

function chooseMusic() {
  if (!bridge?.chooseMediaFile) return;
  bridge.chooseMediaFile((raw) => {
    const result = parsePayload(raw);
    if (!result.selected || !result.url) return;
    musicAudio.src = result.url;
    $('#track-name').textContent = String(result.path || '').split(/[\\/]/).pop() || 'Local audio';
    $('#track-artist').textContent = 'Local file · playing with Mary';
    musicAudio.play().then(() => { musicPlayButton.textContent = '❚❚'; }).catch((error) => toast(`Could not play audio: ${error}`, 'error'));
  });
}

$('#choose-music-button').addEventListener('click', chooseMusic);
musicPlayButton.addEventListener('click', () => {
  if (!musicAudio.src) { chooseMusic(); return; }
  if (musicAudio.paused) musicAudio.play().then(() => { musicPlayButton.textContent = '❚❚'; }).catch(() => {});
  else { musicAudio.pause(); musicPlayButton.textContent = '▶'; }
});
musicAudio.addEventListener('ended', () => { musicPlayButton.textContent = '▶'; });
$('#music-volume-button').addEventListener('click', () => {
  musicAudio.muted = !musicAudio.muted;
  $('#music-volume-button').textContent = musicAudio.muted ? '×' : '♪';
});

// ---------------------------------------------------------------------------
// Command palette
// ---------------------------------------------------------------------------

const commands = [
  { label: 'Talk to Mary', hint: 'Chat', action: () => setScreen('chat') },
  { label: 'Open Memories', hint: 'Archive', action: () => setScreen('memories') },
  { label: 'Open Personality', hint: 'Profile', action: () => setScreen('personality') },
  { label: 'Open Unbeknownst Studio', hint: 'Creative mode', action: () => setScreen('studio') },
  { label: 'Study with Mary', hint: 'Study', action: () => setScreen('study') },
  { label: 'Command Center', hint: 'Tasks / projects', action: () => setScreen('command') },
  { label: 'Focus With Mary', hint: 'Co-work', action: () => setScreen('focus') },
  { label: 'Find That Thing', hint: 'Personal search', action: () => setScreen('search') },
  { label: 'Research Notebook', hint: 'Research', action: () => setScreen('research') },
  { label: 'Mary Arcade', hint: 'Play', action: () => setScreen('arcade') },
  { label: 'Stream & Presence', hint: 'Presence', action: () => setScreen('stream') },
  { label: 'Runtime & Latency', hint: 'Diagnostics', action: () => setScreen('diagnostics') },
  { label: 'Open Gallery', hint: 'Visual library', action: () => setScreen('gallery') },
  { label: 'Music / YouTube', hint: 'Media', action: () => setScreen('media') },
  { label: 'Voice & Avatar', hint: 'Presence', action: () => setScreen('voice') },
  { label: 'Settings', hint: 'System', action: () => setScreen('settings') },
  { label: 'Brainstorm with Mary', hint: 'Prompt', action: () => submitPrompt("Let's brainstorm together. Pick up from what we actually know, not a generic topic.") },
  { label: 'Ask Mary for her take', hint: 'Opinion', action: () => submitPrompt("What's your actual take on where we are right now?") },
];

function renderCommands(filter = '') {
  const normalized = filter.trim().toLowerCase();
  const visible = commands.filter((item) => !normalized || `${item.label} ${item.hint}`.toLowerCase().includes(normalized));
  commandResults.innerHTML = visible.map((item, index) => `<button class="command-result ${index === 0 ? 'active' : ''}" data-command-index="${commands.indexOf(item)}"><span>${escapeHtml(item.label)}</span><small>${escapeHtml(item.hint)}</small></button>`).join('') || '<div class="workspace-empty">No matching command.</div>';
  $$('#command-results [data-command-index]').forEach((button) => button.addEventListener('click', () => {
    commandPalette.close();
    commands[Number(button.dataset.commandIndex)]?.action();
  }));
}

function openCommandPalette() {
  renderCommands('');
  commandPalette.showModal();
  commandInput.value = '';
  window.setTimeout(() => commandInput.focus(), 20);
}

$('#command-palette-button').addEventListener('click', openCommandPalette);
commandInput.addEventListener('input', () => renderCommands(commandInput.value));
commandInput.addEventListener('keydown', (event) => {
  if (event.key === 'Enter') {
    event.preventDefault();
    $('#command-results .command-result.active')?.click();
  }
});
window.addEventListener('keydown', (event) => {
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
    event.preventDefault();
    openCommandPalette();
  }
  if (event.key === 'Escape' && !commandPalette.open && currentScreen !== 'chat') setScreen('chat');
});

// ---------------------------------------------------------------------------
// Window chrome
// ---------------------------------------------------------------------------

$('#window-minimize').addEventListener('click', () => bridge?.minimizeWindow?.());
$('#window-maximize').addEventListener('click', () => bridge?.maximizeWindow?.());
$('#window-close').addEventListener('click', () => bridge?.closeWindow?.());
$('#titlebar').addEventListener('pointerdown', (event) => {
  if (event.button !== 0) return;
  if (event.target.closest('button')) return;
  bridge?.startWindowMove?.();
});

// ---------------------------------------------------------------------------
// Qt bridge
// ---------------------------------------------------------------------------

function connectBridge() {
  if (!window.qt?.webChannelTransport || typeof QWebChannel === 'undefined') {
    setConnected(false, 'Open through MaryV2 Desktop');
    renderWorkspace(currentScreen);
    return;
  }

  new QWebChannel(window.qt.webChannelTransport, (channel) => {
    bridge = channel.objects.maryBridge;
    bootStep(58, 'Connected to Mary core…');
    setConnected(true, 'Connection: Strong');

    bridge.messageReady.connect((raw) => {
      const payload = parsePayload(raw);
      appendMessage('Mary', payload.text || '[No response]', 'mary');
      applyAvatarState(payload.avatar || {});
      playVoice(payload.voice || {});
    });
    bridge.avatarStateChanged.connect((raw) => applyAvatarState(parsePayload(raw)));
    bridge.busyChanged.connect((value) => setBusy(value));
    bridge.conversationStateChanged.connect((raw) => setConversationState(raw));
    bridge.characterStateChanged?.connect((raw) => applyCharacterState(raw));
    bridge.dashboardStateChanged?.connect((raw) => applyDashboardState(raw));
    bridge.voicePlaybackStopRequested.connect(() => stopVoicePlayback({ notifyBridge: false }));
    bridge.errorOccurred.connect((message) => {
      setBusy(false);
      toast(message, 'error');
      appendMessage('System', message, 'system');
    });
    bridge.listeningStateChanged.connect((state) => {
      const value = String(state || '').toLowerCase();
      if (['listening', 'transcribing'].includes(value)) setConversationState(value);
    });
    bridge.transcriptionReady.connect((text) => {
      const transcript = String(text || '').trim();
      if (!transcript || busy) return;
      appendMessage('Unbe', transcript, 'user');
      bridge.sendMessage(transcript);
    });

    bridge.getStatus((raw) => {
      runtimeStatus = parsePayload(raw);
      const voiceLabel = runtimeStatus.voice?.enabled ? ` · voice:${runtimeStatus.voice.provider}` : '';
      const sttLabel = runtimeStatus.speech_to_text?.enabled ? ` · mic:${runtimeStatus.speech_to_text.provider}` : '';
      modelLabel.textContent = `${runtimeStatus.provider || 'runtime'} · ${runtimeStatus.model || 'MaryV2'}${voiceLabel}${sttLabel}`;
      if (runtimeStatus.conversation) setConversationState(runtimeStatus.conversation);
    });
    bridge.getAvatarState((raw) => applyAvatarState(parsePayload(raw)));
    bridge.getCharacterState?.((raw) => applyCharacterState(raw));
    bridge.getDashboardState?.((raw) => { applyDashboardState(raw); bootStep(86, 'Loading memory, state, and ecosystem…'); window.setTimeout(()=>finishBoot('Mary is ready.'), 280); });
    bridge.getIntegrationState?.((raw) => {
      integrationState = parsePayload(raw);
      if (currentScreen === 'studio' || currentScreen === 'settings') renderWorkspace(currentScreen);
    });
    bridge.getCreativeWorkspaceState?.((raw) => {
      creativeWorkspaceState = parsePayload(raw);
      if (currentScreen === 'studio') renderWorkspace('studio');
    });
  });
}


window.setInterval(() => {
  const now=new Date();
  const time=$('#clock-time'); const date=$('#clock-date');
  if(time) time.textContent=now.toLocaleTimeString([], {hour:'numeric', minute:'2-digit'});
  if(date) date.textContent=now.toLocaleDateString([], {weekday:'short', month:'short', day:'numeric'});
},1000);

window.setInterval(() => {
  const focus=ecosystemState.focus||{};
  if(focus.active && focus.ends_at){
    const remaining=Math.max(0,Math.floor(Number(focus.ends_at)-Date.now()/1000));
    focus.remaining_seconds=remaining;
    const node=$('#focus-time'); if(node) node.textContent=formatFocusTime(remaining);
    if(remaining===0 && !focus._notified){ focus._notified=true; const audio=new Audio('./assets/sounds/focus_complete.wav'); audio.volume=.16; audio.play().catch(()=>{}); toast('Focus block complete.'); }
  }
  if(bridge && conversationState==='idle' && performance.now()-lastIdleActionAt>90000){
    lastIdleActionAt=performance.now();
    bridge.getIdleAction?.((raw)=>{const r=parsePayload(raw);const a=r.action||{};if(a.kind==='sound'&&a.sound){const audio=new Audio(`./assets/sounds/${a.sound}`);audio.volume=.06;audio.play().catch(()=>{});} if(a.kind==='animation'&&currentVrm){currentVrm.scene.rotation.y=(Math.random()-.5)*.035;}});
  }
},1000);

window.addEventListener('resize', () => {
  resizeRenderer();
  setAvatarFraming(avatarFraming);
});

bootStep(28, 'Loading character renderer…');
loadMaryVrm();
window.setTimeout(()=>{ if(!bridge) finishBoot('Desktop preview mode.'); }, 2800);
connectBridge();
refreshConversationControls();
animate();
