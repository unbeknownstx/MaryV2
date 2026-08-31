import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { VRMLoaderPlugin, VRMUtils } from '@pixiv/three-vrm';
import './style.css';
import './uplift.css';
import './presence.css';
import './neon-street.css';
import { renderPresenceHome } from './ui/presenceHome.js';
import { formatMilliseconds, normalizeTurnTrace, providerAttemptSummary, timingValue } from './runtime/turnTrace.js';
import { createHttpBridge, installMaryPwa } from './runtime/httpBridge.js';
import './mobile.css';
import './experience-v2.css';
import { installExperienceLayer } from './ui/experienceLayer.js';

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => Array.from(document.querySelectorAll(selector));


// 12.11.2: surface the exact browser-side source location when a frontend
// exception occurs. Qt's default console forwarding can otherwise collapse
// useful information into only "Uncaught TypeError".
window.addEventListener('error', (event) => {
  const location = [event.filename, event.lineno, event.colno].filter(Boolean).join(':');
  const stack = event.error?.stack ? `\n${event.error.stack}` : '';
  console.error(`[MaryUI] ${event.message || 'frontend error'}${location ? ` @ ${location}` : ''}${stack}`);
});

const app = $('#app');
installExperienceLayer({ app });
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
const ambientAudio = $('#ambient-audio');
const screenLauncher = $('#screen-launcher');

let bridge = null;
let dashboardState = {};
let ecosystemState = {};
let searchResults = [];
let youtubeResults = [];
let youtubeStatus = {};
let focusTicker = null;
let lastIdleActionAt = performance.now();
let lastPresencePulseAt = performance.now();
let integrationState = { creative_apps: [] };
let creativeWorkspaceState = { configured: false, files: [] };
let activeStudioFile = '';
let activeStudioDocument = '';
let studioDirty = false;
let runtimeStatus = {};
let lastTurnTrace = {};
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
const BASE_DELIVERY_PLAN = { profile: 'neutral', energy: .4, gesture_energy: .3, avatar_expression: 'neutral', gesture_style: 'natural', gaze_style: 'engaged', head_style: 'natural', performance_beats: [] };
let currentDeliveryPlan = { ...BASE_DELIVERY_PLAN };
let currentPerformanceBeatIndex = -1;
let currentPerformancePacket = {};
let ambientAvatarState = { expression: 'neutral', emotion_intensity: 0 };
let preReactionCue = null;
let preReactionUntil = 0;
let performanceSettleTimer = null;
let idleCue = null;
let idleCueTimer = null;
let modelBaseY = 0;
let modelBounds = null;
let avatarFraming = 'portrait';
let avatarPresentation = localStorage.getItem('mary.avatarPresentation') === 'art' ? 'art' : 'live';

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

function syncAvatarPresentation() {
  const stage = $('#avatar-stage');
  if (!stage || !fallback) return;
  const showArt = avatarPresentation === 'art' || !currentVrm;
  stage.classList.toggle('presentation-art', avatarPresentation === 'art');
  stage.classList.toggle('presentation-live', avatarPresentation !== 'art');
  fallback.classList.toggle('hidden', !showArt);
  const caption = $('#avatar-fallback-caption');
  if (caption) caption.textContent = avatarPresentation === 'art'
    ? 'Portrait presentation · local reference art'
    : (currentVrm ? 'Live VRM active' : 'VRM unavailable · local reference art');
  $$('[data-avatar-presentation]').forEach((button) => {
    button.classList.toggle('active', button.dataset.avatarPresentation === avatarPresentation);
  });
}

function setAvatarPresentation(mode = 'live') {
  avatarPresentation = mode === 'art' ? 'art' : 'live';
  localStorage.setItem('mary.avatarPresentation', avatarPresentation);
  syncAvatarPresentation();
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
    currentVrm.scene.updateMatrixWorld(true);

    const box = new THREE.Box3().setFromObject(vrm.scene);
    const size = box.getSize(new THREE.Vector3());
    const center = box.getCenter(new THREE.Vector3());
    if (![size.x, size.y, size.z, center.x, center.y, center.z].every(Number.isFinite) || size.y < 0.1) {
      throw new Error(`Mary VRM produced invalid bounds: ${JSON.stringify({ size, center })}`);
    }
    modelBounds = { box, size, center };
    modelBaseY = vrm.scene.position.y;
    setAvatarFraming(avatarFraming);
    // Qt may settle the stage geometry one frame after the model finishes loading.
    window.requestAnimationFrame(() => setAvatarFraming(avatarFraming));
    syncAvatarPresentation();
    applyAvatarState({ expression: 'neutral', emotion_intensity: 0 });
  } catch (error) {
    console.warn('MaryCosma.vrm was not loaded:', error);
    currentVrm = null;
    syncAvatarPresentation();
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

function performanceBeatState() {
  const beats = Array.isArray(currentDeliveryPlan.performance_beats) ? currentDeliveryPlan.performance_beats : [];
  if (!activeSpeechAudio || !beats.length || !Number.isFinite(activeSpeechAudio.duration) || activeSpeechAudio.duration <= 0) {
    return { index: -1, beat: null };
  }
  const progress = clamp(activeSpeechAudio.currentTime / activeSpeechAudio.duration);
  const index = beats.findIndex((beat) => progress >= Number(beat.start ?? 0) && progress <= Number(beat.end ?? 1));
  const resolved = index >= 0 ? index : Math.max(0, Math.min(beats.length - 1, Math.floor(progress * beats.length)));
  return { index: resolved, beat: beats[resolved] || null };
}

function applyPerformanceExpression(beat) {
  const manager = currentVrm?.expressionManager;
  if (!manager || !beat) return;
  resetKnownExpressions(manager);
  const expression = String(beat.expression || currentDeliveryPlan.avatar_expression || 'neutral').toLowerCase();
  const preset = PRESET_MAP[expression] || 'relaxed';
  const beatEnergy = clamp(beat.energy ?? currentDeliveryPlan.energy ?? .4);
  const intensity = Math.max(.08, Math.min(.82, .18 + beatEnergy * .62));
  try { manager.setValue(preset, intensity); } catch (_) { /* optional preset */ }
}

function updatePerformanceBeat() {
  const { index, beat } = performanceBeatState();
  if (index === currentPerformanceBeatIndex) return beat;
  currentPerformanceBeatIndex = index;
  if (beat) applyPerformanceExpression(beat);
  return beat;
}

function applyPerformancePacket(packet = {}) {
  if (performanceSettleTimer) {
    window.clearTimeout(performanceSettleTimer);
    performanceSettleTimer = null;
  }
  currentPerformancePacket = packet && typeof packet === 'object' ? packet : {};
  const delivery = currentPerformancePacket.delivery || {};
  if (delivery && typeof delivery === 'object' && Object.keys(delivery).length) {
    currentDeliveryPlan = { ...BASE_DELIVERY_PLAN, ...delivery };
  }
  const reaction = currentPerformancePacket.pre_reaction || {};
  const style = String(reaction.style || 'none').toLowerCase();
  const duration = Math.max(0, Math.min(420, Number(reaction.duration_ms) || 0));
  if (style === 'none' || duration <= 0) {
    preReactionCue = null;
    preReactionUntil = 0;
    return 0;
  }
  preReactionCue = {
    style,
    expression: String(reaction.expression || currentDeliveryPlan.avatar_expression || 'neutral'),
    gaze_style: String(reaction.gaze_style || currentDeliveryPlan.gaze_style || 'engaged'),
    head_style: String(reaction.head_style || currentDeliveryPlan.head_style || 'natural'),
    intensity: clamp(reaction.intensity ?? .28),
  };
  preReactionUntil = performance.now() + duration;
  applyAvatarState({
    expression: preReactionCue.expression,
    emotion_intensity: preReactionCue.intensity,
  });
  return duration;
}

function rememberAmbientAvatarState(state = {}) {
  if (state && typeof state === 'object' && Object.keys(state).length) {
    ambientAvatarState = { ...ambientAvatarState, ...state };
  }
  applyAvatarState(state);
}

function settlePerformanceState(delay = 320) {
  if (performanceSettleTimer) window.clearTimeout(performanceSettleTimer);
  performanceSettleTimer = window.setTimeout(() => {
    currentPerformancePacket = {};
    currentDeliveryPlan = { ...BASE_DELIVERY_PLAN };
    currentPerformanceBeatIndex = -1;
    preReactionCue = null;
    preReactionUntil = 0;
    applyAvatarState(ambientAvatarState);
    performanceSettleTimer = null;
  }, Math.max(0, Number(delay) || 0));
}

function applyIdleAction(raw, { preview = false } = {}) {
  const payload = parsePayload(raw);
  const action = payload.action || {};
  const kind = String(action.kind || '').toLowerCase();
  const name = String(action.name || 'quiet').toLowerCase();
  if (preview) toast(`Idle: ${name || 'quiet'}`);

  if (kind === 'sound' && action.sound && !payload.focus_quiet) {
    const audio = new Audio(`./assets/sounds/${action.sound}`);
    audio.volume = preview ? .12 : .06;
    audio.play().catch(() => {});
    return;
  }

  // Phrases are never emitted directly from the renderer. Spoken initiative
  // belongs to canonical Presence -> TurnMind -> CharacterMind/LLM.
  if (kind !== 'animation' || !currentVrm || conversationState !== 'idle' || activeSpeechAudio) return;

  if (idleCueTimer) window.clearTimeout(idleCueTimer);
  const durations = {
    blink_slow: 900, look_side: 2200, glance_down: 1800, head_tilt: 2100,
    shift_weight: 2600, shoulder_settle: 1800, stretch_small: 2400, smile_soft: 2200,
  };
  idleCue = { name, started_at: performance.now(), until: performance.now() + (durations[name] || 1800) };

  if (name === 'blink_slow') { blinkPhase = 0; }
  if (name === 'smile_soft') {
    applyAvatarState({ expression: 'happy', emotion_intensity: .18 });
  }

  const token = idleCue;
  idleCueTimer = window.setTimeout(() => {
    if (idleCue === token) {
      idleCue = null;
      if (!activeSpeechAudio && conversationState === 'idle') applyAvatarState(ambientAvatarState);
    }
    idleCueTimer = null;
  }, durations[name] || 1800);
}

function applyAvatarState(state = {}) {
  const delivery = state?.metadata?.delivery_plan || state?.delivery_plan || {};
  if (delivery && typeof delivery === 'object' && Object.keys(delivery).length) {
    currentDeliveryPlan = { ...currentDeliveryPlan, ...delivery };
  }
  if (!currentVrm?.expressionManager) return;
  const manager = currentVrm.expressionManager;
  resetKnownExpressions(manager);
  const directedExpression = String(currentDeliveryPlan.avatar_expression || '').toLowerCase();
  const emotionName = directedExpression || String(state.expression || state.emotion || 'neutral').toLowerCase();
  const preset = PRESET_MAP[emotionName] || PRESET_MAP[String(state.expression || state.emotion || 'neutral').toLowerCase()] || 'relaxed';
  const deliveryEnergy = clamp(currentDeliveryPlan.energy ?? 0.4);
  const intensity = Math.max(0.08, clamp(Math.max(state.emotion_intensity ?? state.intensity ?? 0.3, deliveryEnergy * .58)));
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
    const activeBeat = updatePerformanceBeat();
    currentVrm.update(delta);
    const reactionActive = preReactionCue && now < preReactionUntil;
    let gestureEnergy = clamp(activeBeat?.energy ?? currentDeliveryPlan.gesture_energy ?? .3);
    let gestureStyle = String(activeBeat?.gesture_style || currentDeliveryPlan.gesture_style || 'natural');
    let headStyle = String(reactionActive ? preReactionCue.head_style : (activeBeat?.head_style || currentDeliveryPlan.head_style || 'natural'));
    let gazeStyle = String(reactionActive ? preReactionCue.gaze_style : (activeBeat?.gaze_style || currentDeliveryPlan.gaze_style || 'engaged'));

    // Realtime lifecycle is also body language. These local cues never decide
    // what Mary thinks; they make listening/thinking/turn-taking visible while
    // the richer turn-specific performance score takes over during speech.
    if (!activeSpeechAudio && !reactionActive) {
      if (conversationState === 'listening') {
        gestureEnergy = .12; gestureStyle = 'soft'; headStyle = 'tilt'; gazeStyle = 'direct';
      } else if (conversationState === 'transcribing') {
        gestureEnergy = .09; gestureStyle = 'soft'; headStyle = 'still'; gazeStyle = 'direct';
      } else if (conversationState === 'thinking' || conversationState === 'responding') {
        gestureEnergy = .13; gestureStyle = 'soft'; headStyle = 'thoughtful'; gazeStyle = 'glance_away';
      } else if (conversationState === 'interrupted') {
        gestureEnergy = .10; gestureStyle = 'soft'; headStyle = 'still'; gazeStyle = 'direct';
      }
    }

    const idleName = (!activeSpeechAudio && !reactionActive && conversationState === 'idle' && idleCue && now < idleCue.until) ? idleCue.name : '';
    if (idleName === 'look_side') { headStyle = 'thoughtful'; gazeStyle = 'glance_away'; gestureStyle = 'soft'; gestureEnergy = .11; }
    else if (idleName === 'glance_down') { headStyle = 'quiet'; gazeStyle = 'soft'; gestureStyle = 'soft'; gestureEnergy = .08; }
    else if (idleName === 'head_tilt') { headStyle = 'tilt'; gazeStyle = 'direct'; gestureStyle = 'soft'; gestureEnergy = .10; }
    else if (idleName === 'shift_weight') { gestureStyle = 'tease'; gestureEnergy = .10; headStyle = 'soft'; gazeStyle = 'engaged'; }
    else if (idleName === 'shoulder_settle') { gestureStyle = 'soft'; gestureEnergy = .07; headStyle = 'soft'; }
    else if (idleName === 'stretch_small') { gestureStyle = 'animated'; gestureEnergy = .16; headStyle = 'soft'; gazeStyle = 'engaged'; }
    else if (idleName === 'smile_soft') { gestureStyle = 'soft'; gestureEnergy = .08; gazeStyle = 'soft'; headStyle = 'tilt'; }

    const speakingBoost = conversationState === 'speaking' ? .55 + gestureEnergy * .65 : .45;
    const bounceGain = ['animated','celebrate'].includes(gestureStyle) ? 1.65 : gestureStyle === 'firm' ? .58 : gestureStyle === 'soft' ? .72 : 1.0;
    currentVrm.scene.position.y = modelBaseY + Math.sin(elapsed * (1.15 + gestureEnergy * .22)) * (0.0045 + .003 * speakingBoost) * bounceGain;

    const head = currentVrm.humanoid?.getNormalizedBoneNode?.('head');
    if (head) {
      let motion = conversationState === 'speaking' ? (0.028 + gestureEnergy * .035) : 0.028;
      let yawRate = .22;
      let roll = .009 + gestureEnergy * .012;
      let pitch = conversationState === 'speaking' ? gestureEnergy * .012 : 0;
      let yawOffset = 0;
      let rollOffset = 0;
      if (headStyle === 'still') { motion *= .22; roll *= .30; pitch *= .25; }
      if (headStyle === 'thoughtful') { yawRate *= .62; motion *= .72; roll *= .70; }
      if (headStyle === 'quiet' || headStyle === 'soft') { yawRate *= .70; motion *= .55; roll *= .58; pitch *= .55; }
      if (headStyle === 'tilt') { rollOffset = .045; motion *= .70; }
      if (headStyle === 'flustered') { yawOffset = -.045; rollOffset = .025; yawRate *= 1.28; }
      if (headStyle === 'amused') { rollOffset = .025; yawRate *= 1.15; }
      if (headStyle === 'animated') { motion *= 1.30; roll *= 1.35; pitch *= 1.5; yawRate *= 1.22; }
      if (gazeStyle === 'direct') { motion *= .58; yawOffset *= .35; }
      if (gazeStyle === 'glance_away') yawOffset -= .065;
      if (gazeStyle === 'soft') motion *= .70;
      if (idleName === 'look_side') yawOffset -= .04;
      if (idleName === 'glance_down') pitch += .035;
      if (idleName === 'head_tilt') rollOffset += .025;
      if (idleName === 'stretch_small') { pitch -= .018; rollOffset -= .015; }
      head.rotation.y = yawOffset + Math.sin(elapsed * yawRate) * motion;
      head.rotation.z = rollOffset + Math.sin(elapsed * .31 * (headStyle === 'thoughtful' ? .72 : 1.0)) * roll;
      head.rotation.x = Math.sin(elapsed * (headStyle === 'animated' ? 1.75 : 1.4)) * pitch;
    }

    const chest = currentVrm.humanoid?.getNormalizedBoneNode?.('upperChest');
    if (chest) {
      const speaking = conversationState === 'speaking';
      let chestYaw = speaking ? Math.sin(elapsed * .42) * gestureEnergy * .012 : 0;
      let chestRoll = speaking ? Math.sin(elapsed * .36) * gestureEnergy * .009 : 0;
      if (gestureStyle === 'tease') chestRoll += .014;
      if (gestureStyle === 'firm') { chestYaw *= .35; chestRoll *= .35; }
      if (gestureStyle === 'soft') { chestYaw *= .55; chestRoll *= .55; }
      if (gestureStyle === 'animated' || gestureStyle === 'celebrate') { chestYaw *= 1.55; chestRoll *= 1.45; }
      if (idleName === 'shift_weight') chestRoll += Math.sin((now - idleCue.started_at) / 700) * .018;
      if (idleName === 'shoulder_settle') chestRoll += .008 * Math.max(0, 1 - (now - idleCue.started_at) / 1800);
      if (idleName === 'stretch_small') chestYaw += Math.sin((now - idleCue.started_at) / 500) * .012;
      chest.rotation.y = chestYaw;
      chest.rotation.z = chestRoll;
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
      activeSpeechAudio._maryCleanup?.();
    } catch (_) { /* best effort */ }
  }
  activeSpeechAudio = null;
  currentPerformanceBeatIndex = -1;
  disconnectLipSyncGraph();
  restoreAmbientVolume();
  settlePerformanceState(120);
  if (notifyBridge && bridge?.voicePlaybackFinished) bridge.voicePlaybackFinished();
}

function audioSourceFromVoice(voice = {}) {
  if (voice.audio_url) return { source: String(voice.audio_url), revoke: null };
  if (!voice.audio_base64) return { source: '', revoke: null };
  try {
    const binary = atob(String(voice.audio_base64));
    const bytes = new Uint8Array(binary.length);
    for (let index = 0; index < binary.length; index += 1) bytes[index] = binary.charCodeAt(index);
    const blob = new Blob([bytes], { type: voice.mime_type || 'audio/mpeg' });
    const source = URL.createObjectURL(blob);
    return { source, revoke: () => URL.revokeObjectURL(source) };
  } catch (_) {
    return { source: `data:${voice.mime_type || 'audio/mpeg'};base64,${voice.audio_base64}`, revoke: null };
  }
}

function playVoice(voice = {}) {
  if (!voice?.enabled || voice.status !== 'success' || (!voice.audio_url && !voice.audio_base64)) return;
  const packet = voice?.performance_packet && typeof voice.performance_packet === 'object' ? voice.performance_packet : currentPerformancePacket;
  const delivery = packet.delivery || voice.delivery_plan || {};
  if (delivery && typeof delivery === 'object' && Object.keys(delivery).length) {
    currentDeliveryPlan = { ...currentDeliveryPlan, ...delivery };
  }
  applyAvatarState({ expression: currentDeliveryPlan.avatar_expression || 'neutral', emotion_intensity: currentDeliveryPlan.energy || .3 });
  stopVoicePlayback({ notifyBridge: false });
  bridge?.voicePlaybackStage?.('payload_received');
  const prepared = audioSourceFromVoice(voice);
  if (!prepared.source) return;
  const audio = new Audio();
  audio.preload = 'auto';
  audio.src = prepared.source;
  activeSpeechAudio = audio;
  currentPerformanceBeatIndex = -1;
  let lipSyncAttached = false;
  const cleanupSource = () => {
    if (typeof prepared.revoke === 'function') {
      try { prepared.revoke(); } catch (_) { /* best effort */ }
      prepared.revoke = null;
    }
  };
  audio._maryCleanup = cleanupSource;
  audio.addEventListener('canplay', () => bridge?.voicePlaybackStage?.('audio_ready'), { once: true });
  audio.addEventListener('playing', () => {
    duckAmbientVolume();
    if (!lipSyncAttached) {
      // Do not make AudioContext/lip-sync graph setup sit in front of play().
      // Attach only once the browser has actually started playback.
      attachLipSyncToAudio(audio);
      lipSyncAttached = true;
    }
    if (activeSpeechAudio === audio) bridge?.voicePlaybackStarted?.();
  }, { once: true });
  audio.addEventListener('ended', () => {
    cleanupSource();
    if (activeSpeechAudio === audio) {
      activeSpeechAudio = null;
      currentPerformanceBeatIndex = -1;
      disconnectLipSyncGraph();
      restoreAmbientVolume();
      settlePerformanceState(360);
      bridge?.voicePlaybackFinished?.();
    }
  });
  audio.addEventListener('error', () => {
    cleanupSource();
    if (activeSpeechAudio === audio) activeSpeechAudio = null;
    disconnectLipSyncGraph();
    restoreAmbientVolume();
    settlePerformanceState(120);
    bridge?.voicePlaybackFinished?.();
    toast('Mary generated voice audio, but playback failed.', 'error');
  });
  audio.load();
  bridge?.voicePlaybackStage?.('play_requested');
  audio.play().catch((error) => {
    cleanupSource();
    if (activeSpeechAudio === audio) activeSpeechAudio = null;
    disconnectLipSyncGraph();
    restoreAmbientVolume();
    settlePerformanceState(120);
    bridge?.voicePlaybackFinished?.();
    toast(`Voice playback failed: ${error}`, 'error');
  });
}

function configuredAmbientVolume() {
  const stored = Number(localStorage.getItem('mary.ambientVolume'));
  return Number.isFinite(stored) ? clamp(stored, 0, .22) : .08;
}

function restoreAmbientVolume() {
  if (!ambientAudio) return;
  ambientAudio.volume = configuredAmbientVolume();
}

function duckAmbientVolume() {
  if (!ambientAudio) return;
  ambientAudio.volume = Math.min(.018, configuredAmbientVolume());
}

function ensureAmbientMusic() {
  if (!ambientAudio || localStorage.getItem('mary.ambientEnabled') === 'false') return;
  restoreAmbientVolume();
  if (ambientAudio.paused) ambientAudio.play().catch(() => {});
}

// ---------------------------------------------------------------------------
// Conversation
// ---------------------------------------------------------------------------

function appendMessage(speaker, text, kind) {
  if (kind === 'mary') $$('.message-feedback').forEach((node) => node.remove());
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
  if (kind === 'mary') {
    const feedback = document.createElement('footer');
    feedback.className = 'message-feedback';
    feedback.innerHTML = '<span>TRAIN MARY · OPTIONAL</span><button type="button" data-response-feedback="positive" title="This felt like Mary">♡</button><button type="button" data-response-feedback="negative" title="This did not feel like Mary">×</button>';
    article.append(feedback);
  }
  messages.append(article);
  messages.scrollTop = messages.scrollHeight;
}

function recordDesktopFeedback(button) {
  if (!bridge?.recordResponseFeedback) return;
  const rating = String(button?.dataset?.responseFeedback || 'neutral');
  const tags = [rating === 'positive' ? 'felt_like_mary' : 'did_not_feel_like_mary'];
  let chosen = '';
  if (rating === 'negative') {
    const correction = window.prompt('Optional: what should Mary have said instead?', '');
    if (correction === null) return;
    chosen = String(correction || '').trim();
    if (chosen) tags.push('correction_supplied');
  }
  bridge.recordResponseFeedback(
    rating,
    JSON.stringify(tags),
    '',
    chosen,
    (raw) => {
      const result = parsePayload(raw);
      if (result.ok === false) {
        console.warn('Mary feedback was not saved:', result.error || result);
        return;
      }
      const footer = button.closest('.message-feedback');
      if (footer) footer.innerHTML = `<span>${rating === 'positive' ? 'SAVED · FELT LIKE MARY' : (chosen ? 'SAVED · CORRECTION ADDED' : 'SAVED · NEEDS REFINEMENT')}</span>`;
    },
  );
}

messages?.addEventListener('click', (event) => {
  const button = event.target.closest?.('[data-response-feedback]');
  if (button) recordDesktopFeedback(button);
});

function setConnected(value, label = '') {
  statusDot.classList.toggle('connected', Boolean(value));
  statusText.textContent = label || (value ? 'Connection: Strong' : 'Disconnected');
}

function refreshConversationControls() {
  const listening = conversationState === 'listening';
  const transcribing = conversationState === 'transcribing';
  const responding = conversationState === 'responding';
  const thinkingNow = conversationState === 'thinking';
  const speaking = conversationState === 'speaking';
  const interrupted = conversationState === 'interrupted';

  input.disabled = listening || transcribing || responding || thinkingNow || interrupted || busy;
  sendButton.disabled = input.disabled;
  micButton.disabled = transcribing || responding || thinkingNow || interrupted || busy;
  micButton.classList.toggle('listening', listening);
  micButton.classList.toggle('transcribing', transcribing);
  micButton.classList.toggle('speaking', speaking);
  micButton.setAttribute('aria-pressed', listening ? 'true' : 'false');
  micButton.textContent = listening ? '■' : (transcribing ? '…' : (speaking ? '↯' : '◉'));
  micButton.title = listening ? 'Stop listening' : (speaking ? 'Interrupt Mary' : 'Push to talk');
  micButton.setAttribute('aria-label', listening ? 'Stop listening' : (speaking ? 'Interrupt' : 'Push to talk'));
  thinking.classList.toggle('hidden', !(responding || thinkingNow));
  const thinkingLabel = thinking.querySelector('em');
  if (thinkingLabel) thinkingLabel.textContent = responding ? 'Mary is responding' : 'Mary is thinking';

  const labels = {
    idle: 'Connection: Strong',
    listening: 'Listening…',
    transcribing: 'Transcribing…',
    responding: 'Mary is responding…',
    thinking: 'Mary is thinking…',
    speaking: 'Mary speaking',
    interrupted: 'Interrupted…',
  };
  setConnected(true, labels[conversationState] || 'Connection: Strong');
  $('#avatar-live-state').textContent = `STATUS: ${String(conversationState || 'idle').toUpperCase()}`;
  $('#sidebar-activity').textContent = ({
    idle: 'Talking with you', listening: 'Listening to you', transcribing: 'Transcribing your voice',
    responding: 'Responding', thinking: 'Thinking', speaking: 'Speaking', interrupted: 'Switching turns',
  })[conversationState] || 'Talking with you';
}

function setBusy(value) {
  busy = Boolean(value);
  refreshConversationControls();
}

function setConversationState(raw) {
  const payload = parsePayload(raw);
  const state = String(payload.state || raw || 'idle').toLowerCase();
  if (!['idle', 'listening', 'transcribing', 'responding', 'thinking', 'speaking', 'interrupted'].includes(state)) return;
  conversationState = state;
  const stage = $('#main-stage');
  if (stage) stage.dataset.interactionState = state;
  refreshConversationControls();
}

function submitPrompt(text) {
  const value = String(text || '').trim();
  if (!value || !bridge || busy) return;
  if (['listening', 'transcribing', 'responding', 'thinking', 'interrupted'].includes(conversationState)) return;
  if (conversationState === 'speaking' || activeSpeechAudio) stopVoicePlayback({ notifyBridge: false });
  appendMessage('Unbe', value, 'user');
  bridge.sendMessage(value);
}

composer?.addEventListener('submit', (event) => {
  event.preventDefault();
  const text = input.value.trim();
  if (!text) return;
  input.value = '';
  submitPrompt(text);
});

input?.addEventListener('keydown', (event) => {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault();
    composer?.requestSubmit();
  }
});

micButton?.addEventListener('click', () => {
  if (!bridge || conversationState === 'transcribing' || conversationState === 'responding' || conversationState === 'thinking') return;
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

function applyTurnTrace(raw) {
  lastTurnTrace = normalizeTurnTrace(raw);
  const provider = lastTurnTrace.provider || 'Waiting';
  const model = lastTurnTrace.model || 'No completed turn';
  const timings = lastTurnTrace.timings || {};
  const setText = (selector, value) => { const node = $(selector); if (node) node.textContent = value; };
  setText('#runtime-last-provider', provider);
  setText('#runtime-last-model', model);
  setText('#runtime-pipeline', formatMilliseconds(timings.pipeline_ms));
  setText('#runtime-tts', formatMilliseconds(timings.tts_synthesis_ms));
  setText('#runtime-perceived', formatMilliseconds(timings.perceived_ms ?? timings.text_ready_ms));
  setText('#runtime-attempts', providerAttemptSummary(lastTurnTrace));
}

function applyCompanionPulse(ecosystem = ecosystemState) {
  const pulse = ecosystem?.companion || {};
  const counts = pulse.counts || {};
  const focus = { ...(pulse.focus || {}), ...(ecosystem?.focus || {}) };
  const setText = (selector, value) => { const node = $(selector); if (node) node.textContent = value; };
  setText('#pulse-headline', pulse.headline || 'Mary is here.');
  setText('#pulse-detail', pulse.detail || 'Talk, create, study, focus, or just hang out.');
  setText('#pulse-command', counts.active_tasks ?? 0);
  setText('#pulse-study', counts.study_due ?? 0);
  setText('#pulse-inbox', counts.inbox_unread ?? 0);
  setText('#pulse-focus', focus.active ? 'ON' : '—');
  app.dataset.focus = focus.active ? 'active' : 'idle';
}

function applyDashboardState(raw) {
  const payload = parsePayload(raw);
  dashboardState = payload;
  ecosystemState = payload.ecosystem || ecosystemState || {};
  if (ecosystemState.last_turn) applyTurnTrace(ecosystemState.last_turn);
  applyCompanionPulse(ecosystemState);
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
  home: ['MARY HOME', 'Companion Pulse', 'A read-only live view across Mary, your workspaces, quiet notices, focus, and represented curiosity.'],
  memories: ['MEMORY ARCHIVE', 'Memories', 'Structured creator knowledge, shared history, and continuity.'],
  growth: ['INNER LIFE', 'Growth', 'Grounded experience, learning, milestones, and Mary’s developing self.'],
  personality: ['MARY PROFILE', 'Personality', 'Mary’s authored and developed character state, separated from provider behavior.'],
  mind: ['LOCAL MIND', 'Cognitive Reservoir', 'Mary’s fast rebuildable local mind: hot state, structured retrieval, dialogue policy, escalation, and model roles.'],
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

function renderHome() {
  return renderPresenceHome(dashboardState, ecosystemState);
}

function renderMind() {
  const mind = dashboardState.mind || {};
  const reservoir = mind.reservoir || {};
  const hot = mind.hot || {};
  const last = mind.last_local_decision || {};
  const plan = last.plan || {};
  const models = mind.local_model_catalog || [];
  const sizeMb = Number(reservoir.size_bytes || 0) / (1024 * 1024);
  const modelRows = models.map((item) => `
    <div class="command-row">
      <span class="kind">${item.role === 'embeddings' ? '◇' : item.role.includes('dialogue') || item.role.includes('character') ? '◉' : '⌁'}</span>
      <div><strong>${escapeHtml(item.model)}</strong><small>${escapeHtml(titleCase(item.role))} · ~${escapeHtml(item.approx_size_gb)} GB · ${escapeHtml(item.notes)}</small></div>
      <span class="status-chip">P${escapeHtml(item.priority)}</span>
    </div>`).join('');
  return `
    <div class="workspace-grid three">
      <div class="workspace-panel accent"><h3>Local Mind</h3><div class="data-row"><span>Status</span><strong>${mind.enabled ? 'Running' : 'Off'}</strong></div><div class="data-row"><span>Dialogue reflex</span><strong>${mind.local_dialogue_enabled ? 'Enabled' : 'Off'}</strong></div><div class="data-row"><span>Hot state</span><strong>${hot.loaded ? 'In RAM' : 'Cold'}</strong></div><p>Fast character decisions happen before a provider call. This layer is a projection over Mary—not a replacement identity.</p></div>
      <div class="workspace-panel"><h3>Cognitive Reservoir</h3><div class="data-row"><span>Records</span><strong>${reservoir.records ?? 0}</strong></div><div class="data-row"><span>Search</span><strong>${reservoir.fts5 ? 'SQLite FTS5' : 'SQLite fallback'}</strong></div><div class="data-row"><span>Disk</span><strong>${sizeMb.toFixed(2)} MB / ${reservoir.max_megabytes || 512} MB</strong></div><button class="primary-small" id="mind-rebuild" style="height:34px;margin-top:8px">Rebuild derived index</button></div>
      <div class="workspace-panel"><h3>Last Local Decision</h3><div class="data-row"><span>Act</span><strong>${escapeHtml(titleCase(plan.act || '—'))}</strong></div><div class="data-row"><span>Local</span><strong>${plan.local ? 'Yes' : 'Escalated'}</strong></div><div class="data-row"><span>Decision</span><strong>${escapeHtml(formatMilliseconds(last.elapsed_ms))}</strong></div><p>${escapeHtml(plan.rationale || 'Complete a conversation turn to see local-mind decisions.')}</p></div>
    </div>
    <div class="section-title">COGNITIVE SPEEDS</div>
    <div class="workspace-grid">
      <div class="workspace-panel hero-panel"><h3>Mary first, models second</h3><div class="trace-stack">
        <div class="trace-row"><span>Reflex / local dialogue</span><i style="width:8%"></i><strong>&lt; 200 ms target</strong></div>
        <div class="trace-row"><span>Reservoir retrieval</span><i style="width:14%"></i><strong>local</strong></div>
        <div class="trace-row"><span>Fast language cortex</span><i style="width:42%"></i><strong>Groq / small local</strong></div>
        <div class="trace-row"><span>Thinking / expert</span><i style="width:100%"></i><strong>only when warranted</strong></div>
      </div></div>
      <div class="workspace-panel"><h3>Escalation rule</h3><p>Known represented state can be answered locally. Novel open-ended language escalates to a fast language model. Hard reasoning can visibly enter Thinking. OpenAI stays an explicit expert instead of Mary's heartbeat.</p><div class="chip-row"><span class="chip">LOCAL STATE</span><span class="chip">RESERVOIR</span><span class="chip">FAST LLM</span><span class="chip">THINKING</span><span class="chip">EXPERT</span></div></div>
    </div>
    <div class="section-title">LOCAL MODEL LAB</div>
    <div class="workspace-panel"><p>These are candidates sized for the current 32 GB RAM / 4 GB VRAM machine. They are not auto-downloaded. Run <code>scripts\benchmark_local_models_windows.ps1</code> after pulling whichever models you want to test.</p><div class="command-list">${modelRows || '<div class="workspace-empty">No model catalog.</div>'}</div></div>`;
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

function renderGrowth() {
  const growth = dashboardState.growth || {};
  const journal = growth.journal || {};
  const engagement = dashboardState.engagement || {};
  const session = engagement.active_session || {};
  const candidates = growth.preference_candidates || [];
  const milestones = growth.recent_milestones || [];
  return `
    <div class="workspace-grid three">
      <div class="workspace-panel accent"><h3>Experience</h3><div class="data-row"><span>Retained</span><strong>${journal.records ?? 0}</strong></div><div class="data-row"><span>Meaningful</span><strong>${journal.meaningful_records ?? 0}</strong></div><p>Observable turn outcomes only. No hidden chain-of-thought is stored.</p></div>
      <div class="workspace-panel accent"><h3>Development</h3><div class="data-row"><span>Semantic promotions</span><strong>${growth.semantic_promotions ?? 0}</strong></div><div class="data-row"><span>Developed preferences</span><strong>${growth.preference_promotions ?? 0}</strong></div><div class="data-row"><span>Milestones</span><strong>${growth.milestones_created ?? 0}</strong></div></div>
      <div class="workspace-panel"><h3>Conversation</h3><div class="data-row"><span>Mode</span><strong>${escapeHtml(titleCase(session.mode || engagement.mode || 'adaptive'))}</strong></div><div class="data-row"><span>Thread turns</span><strong>${session.turns_remaining ?? 0}</strong></div><p>Intentional Talk/Deep sessions trade some latency for continuity, initiative, and room to think.</p></div>
    </div>
    <div class="section-title">DEVELOPING</div><div class="workspace-panel"><div class="command-list">${listOrEmpty(candidates,(item)=>`<div class="command-row"><span class="kind">↟</span><div><strong>${escapeHtml(titleCase(item.name))}</strong><small>${item.observations || 0} grounded observations · confidence ${Math.round(Number(item.confidence || 0)*100)}%</small></div><span class="status-chip">${item.eligible?'ELIGIBLE':'WATCH'}</span></div>`,'No development candidates yet.')}</div></div>
    <div class="section-title">MILESTONES</div><div class="workspace-panel timeline">${listOrEmpty(milestones,(item)=>`<div class="timeline-row"><span></span><div><strong>${escapeHtml(item.title || 'Milestone')}</strong><small>${escapeHtml(item.description || '')}</small></div></div>`,'No development milestones yet.')}</div>
    <div class="workspace-panel"><h3>Protected growth boundary</h3><p>Model dialogue cannot become durable self-evidence. Canonical values/personality stay protected while repeated grounded experience can produce safe semantic learning and strict preference development.</p></div>`;
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
  const stage=dashboardState.performance_context || runtimeStatus.performance_context || {}; const mode=stage.mode || 'private'; const modes=['private','casual','focus','stream','performance'];
  return `<div class="presence-status"><div class="presence-node ready"><strong>Presence Core</strong><span>${escapeHtml(titleCase(presence.mode || 'companion'))} · initiative + silence</span></div><div class="presence-node ready"><strong>Character Stage</strong><span>${escapeHtml(titleCase(mode))} · same Mary, different projection</span></div><div class="presence-node"><strong>Twitch / OBS</strong><span>${byKey.twitch?.enabled||byKey.obs?.enabled?'Connected':'Optional adapters'}</span></div></div>
  <div class="workspace-grid" style="margin-top:12px"><div class="workspace-panel hero-panel"><h3>Mary Presence</h3><p>The part that moves Mary beyond prompt → response: live context, pending thoughts, cheap idle behavior, and a decision layer where staying quiet is valid.</p><div class="data-row"><span>Pending thoughts</span><strong>${(presence.pending_thoughts||[]).length}</strong></div><div class="data-row"><span>Recent context events</span><strong>${(presence.recent||[]).length}</strong></div><button class="primary-small" id="presence-idle-test" style="height:34px;margin-top:8px">Preview an idle behavior</button></div><div class="workspace-panel accent"><h3>Social Stage</h3><p>These are performance contexts, not alternate personas. Public modes project Mary more clearly while keeping private creator/relationship context out of the room.</p><div class="chip-row">${modes.map(x=>`<button class="chip ${x===mode?'active':''}" data-performance-context="${x}">${escapeHtml(titleCase(x))}</button>`).join('')}</div><div class="data-row"><span>Audience</span><strong>${escapeHtml(titleCase(stage.audience||'creator'))}</strong></div><div class="data-row"><span>Privacy</span><strong>${stage.public?'PUBLIC GUARD':'PRIVATE'}</strong></div></div></div>
  <div class="workspace-panel" style="margin-top:12px"><h3>External performer adapters</h3><p>Twitch, OBS and vision remain optional inputs/outputs. They never own Mary; they publish context or render actions through Core.</p><div class="chip-row">${['twitch','obs','vision'].map(k=>`<span class="chip">${byKey[k]?.enabled?'●':'○'} ${escapeHtml(titleCase(k))}</span>`).join('')}</div></div>`;
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
  const metrics = ecosystemState.metrics || {};
  const rows = Object.entries(metrics);
  const trace = normalizeTurnTrace(ecosystemState.last_turn || lastTurnTrace);
  const timings = trace.timings || {};
  const realtime = dashboardState.realtime || runtimeStatus.realtime || {};
  const realtimeStats = realtime.stats || {};
  const attention = realtime.attention || {};
  const nextAttention = attention.next || {};
  const nodes = dashboardState.nodes || runtimeStatus.nodes || {};
  const nodeItems = nodes.nodes || [];
  const retrieval = dashboardState.retrieval || runtimeStatus.retrieval || {};
  const vectorIndex = retrieval.vector_index || {};
  const perception = dashboardState.perception || runtimeStatus.perception || {};
  const feedback = dashboardState.training_feedback || runtimeStatus.training_feedback || {};
  const timeline = [
    ['Provider call', timingValue(trace, 'provider_call_ms')],
    ['Reasoning', timingValue(trace, 'reasoning_ms')],
    ['Reflection', timingValue(trace, 'reflection_ms')],
    ['Speech render', timingValue(trace, 'speech_render_ms')],
    ['TTS synthesis', timingValue(trace, 'tts_synthesis_ms')],
    ['Text ready', timingValue(trace, 'text_ready_ms')],
    ['UI payload received', timingValue(trace, 'ui_payload_ms')],
    ['Audio ready', timingValue(trace, 'audio_ready_ms')],
    ['Play requested', timingValue(trace, 'play_request_ms')],
    ['Playback / perceived', timingValue(trace, 'perceived_ms')],
  ].filter(([,value]) => value !== null);
  const max = Math.max(1, ...timeline.map(([,value]) => value || 0));
  return `<div class="trace-hero">
    <div class="workspace-panel hero-panel"><h3>Last Turn Trace</h3><p>Measured from the real runtime: provider, cognition, reflection, speech, and perceived response timing. This telemetry is ephemeral and never becomes Mary memory.</p>
      <div class="trace-stack">${timeline.length ? timeline.map(([label,value]) => `<div class="trace-row"><span>${escapeHtml(label)}</span><i style="width:${Math.max(2,(value/max)*100)}%"></i><strong>${escapeHtml(formatMilliseconds(value))}</strong></div>`).join('') : '<div class="workspace-empty">Complete one desktop turn to populate the trace.</div>'}</div>
    </div>
    <div class="workspace-panel accent"><h3>Route</h3><div class="data-row"><span>Provider</span><strong>${escapeHtml(trace.provider || '—')}</strong></div><div class="data-row"><span>Model</span><strong>${escapeHtml(trace.model || '—')}</strong></div><div class="data-row"><span>Purpose</span><strong>${escapeHtml(trace.generation_purpose || '—')}</strong></div><div class="data-row"><span>Lane</span><strong>${escapeHtml(titleCase(trace.conversation_lane || '—'))}</strong></div><div class="data-row"><span>Response class</span><strong>${escapeHtml(titleCase(trace.response_class || trace.local_mind?.response_class || '—'))}</strong></div><div class="data-row"><span>Engine</span><strong>${escapeHtml(trace.response_engine || trace.local_mind?.response_engine || '—')}</strong></div><div class="data-row"><span>Escalation</span><strong>${escapeHtml(trace.escalation_reason || trace.local_mind?.escalation_reason || '—')}</strong></div><div class="data-row"><span>Shadow</span><strong>${trace.local_mind?.shadow_enabled ? 'ON' : 'OFF'}</strong></div><div class="data-row"><span>Shadow latency</span><strong>${escapeHtml(formatMilliseconds(timings.shadow_ms))}</strong></div><div class="data-row"><span>Classification</span><strong>${escapeHtml(formatMilliseconds(timings.classification_ms))}</strong></div><div class="data-row"><span>Local composer</span><strong>${escapeHtml(formatMilliseconds(timings.local_composer_ms))}</strong></div><div class="data-row"><span>Local audit</span><strong>${escapeHtml(formatMilliseconds(timings.local_audit_ms))}</strong></div><div class="data-row"><span>Reflection</span><strong>${escapeHtml(trace.reflection_mode || '—')}</strong></div><div class="data-row"><span>Voice delivery</span><strong>${escapeHtml(titleCase(trace.delivery_plan?.profile || '—'))}</strong></div><div class="data-row"><span>Local act</span><strong>${escapeHtml(titleCase(trace.local_mind?.plan?.act || '—'))}</strong></div><p>${escapeHtml(providerAttemptSummary(trace))}</p></div>
  </div>
  <div class="section-title">REALTIME COGNITIVE INFRASTRUCTURE</div>
  <div class="workspace-grid three">
    <div class="workspace-panel accent"><h3>Interaction</h3><div class="data-row"><span>Phase</span><strong>${escapeHtml(titleCase(realtime.phase || 'idle'))}</strong></div><div class="data-row"><span>Anti-echo</span><strong>${realtime.anti_echo === false ? 'OFF' : 'ON'}</strong></div><div class="data-row"><span>Interruptions</span><strong>${realtimeStats.interruptions ?? 0}</strong></div><div class="data-row"><span>Echo suppressions</span><strong>${realtimeStats.suppressed_echo_inputs ?? 0}</strong></div><p>One shared lifecycle coordinates text, speech, interruption and future streaming clients without owning character state.</p></div>
    <div class="workspace-panel"><h3>Attention Bus</h3><div class="data-row"><span>Pending</span><strong>${attention.pending ?? 0}</strong></div><div class="data-row"><span>Published / claimed</span><strong>${attention.published ?? 0} / ${attention.claimed ?? 0}</strong></div><div class="data-row"><span>Dropped</span><strong>${attention.dropped ?? 0}</strong></div><div class="data-row"><span>Next</span><strong>${escapeHtml(titleCase(nextAttention.source || 'none'))}</strong></div><p>Urgency controls what Mary should consider first; provenance and truth remain separate.</p></div>
    <div class="workspace-panel"><h3>Perception Boundary</h3><div class="data-row"><span>Recent observations</span><strong>${(perception.recent || []).length}</strong></div><p>Perception providers describe objective observations. Mary interprets them through her own represented state; raw media is not stored here.</p></div>
  </div>
  <div class="workspace-grid">
    <div class="workspace-panel"><h3>Hybrid Memory Retrieval</h3><div class="data-row"><span>Mode</span><strong>${escapeHtml(retrieval.mode || 'auto')}</strong></div><div class="data-row"><span>Embedding model</span><strong>${escapeHtml(retrieval.embedding_model || '—')}</strong></div><div class="data-row"><span>Vector records</span><strong>${vectorIndex.records ?? vectorIndex.count ?? 0}</strong></div><div class="data-row"><span>Last query used vectors</span><strong>${retrieval.last_query_used_vectors ? 'YES' : 'NO'}</strong></div><p>Lexical and semantic similarity retrieve candidates. Existing canonical memory/provenance still decides what is true.</p></div>
    <div class="workspace-panel"><h3>Compute Nodes</h3>${nodeItems.length ? nodeItems.map((node) => `<div class="data-row"><span>${escapeHtml(node.node_id || 'node')}</span><strong>${node.connected ? 'ONLINE' : 'OFFLINE'}</strong></div><small>${escapeHtml(Object.entries(node.capabilities || {}).filter(([,info]) => info?.available).map(([name]) => name).slice(0,8).join(' · ') || 'No active capabilities')}</small>`).join('') : '<div class="workspace-empty">No compute nodes registered.</div>'}<p>13.1 starts with the current host; future cloud/home agents can register through the same capability model.</p></div>
  </div>
  <div class="workspace-panel"><h3>Mary Evaluation Set</h3><div class="data-row"><span>Explicit ratings</span><strong>${feedback.records ?? 0}</strong></div><div class="data-row"><span>Positive / negative</span><strong>${feedback.ratings?.positive ?? 0} / ${feedback.ratings?.negative ?? 0}</strong></div><p>Only explicit creator feedback belongs here. It is private future evaluation/training data and never character-state authority.</p></div>
  <div class="section-title">ROLLING METRICS</div>
  <div class="workspace-panel"><div class="metric-grid">${rows.length ? rows.map(([k,v])=>`<div class="metric-card"><span>${escapeHtml(titleCase(k))}</span><strong>${escapeHtml(v.last_ms)} ms</strong><small>avg ${escapeHtml(v.avg_ms)} · max ${escapeHtml(v.max_ms)}</small></div>`).join('') : '<div class="workspace-empty">Metrics appear after live turns.</div>'}</div></div>`;
}

function renderGallery() {
  return `
    <div class="workspace-grid three">
      <div class="workspace-panel accent"><h3>Mary Reference</h3><img src="./assets/mary-reference.jpeg" style="width:100%;height:240px;object-fit:cover;object-position:center 38%;border-radius:10px;opacity:.9" alt="Mary reference" /></div>
      <div class="workspace-panel"><h3>Neon Reference Study</h3><img src="./assets/gallery/mary-neon-reference-sheet.png" style="width:100%;height:240px;object-fit:cover;object-position:center;border-radius:10px;opacity:.94" alt="Mary neon reference sheet" /><small>Generated concept/reference sheet · visual evidence only.</small></div>
      <div class="workspace-panel"><h3>Gala Visual Study</h3><img src="./assets/gallery/mary-gala-reference.png" style="width:100%;height:240px;object-fit:cover;object-position:center 30%;border-radius:10px;opacity:.92" alt="Mary gala visual study" /><small>Optional generated visual reference · not autobiographical memory or automatic canon.</small></div>
      <div class="workspace-panel"><h3>Neon Night Manga Study</h3><img src="./assets/gallery/mary-neon-night-manga.png" style="width:100%;height:240px;object-fit:cover;object-position:center;border-radius:10px;opacity:.92" alt="Mary neon night manga study" /><small>Library visual study preserving Mary's beanie/jacket/skirt palette.</small></div>
      <div class="workspace-panel"><h3>Stream Room Study</h3><img src="./assets/gallery/mary-stream-room-reference.png" style="width:100%;height:240px;object-fit:cover;object-position:center;border-radius:10px;opacity:.92" alt="Mary stream room visual study" /><small>Library visual study for the streamer/companion environment.</small></div>
      <div class="workspace-panel"><h3>VRM</h3><p>MaryCosma.vrm is connected to the live stage and remains the preferred interactive avatar.</p><div class="data-row"><span>Model</span><strong>MaryCosma.vrm</strong></div><div class="data-row"><span>Renderer</span><strong>Three.js + three-vrm</strong></div></div>
      <div class="workspace-panel"><h3>Project Gallery</h3><div class="workspace-empty">Bind this to Unbeknownst references, storyboards, approved generated images, screenshots, and tagged creative assets while preserving provenance.</div></div>
    </div>
  `;
}

function renderMedia() {
  const configured = Boolean(youtubeStatus.configured);
  const enabled = Boolean(youtubeStatus.enabled);
  const youtubeRows = youtubeResults.length ? youtubeResults.map((item) => `
    <article class="youtube-result">
      ${item.thumbnail ? `<img src="${escapeHtml(item.thumbnail)}" alt="" />` : '<div class="youtube-thumb-fallback">▶</div>'}
      <div><strong>${escapeHtml(item.title)}</strong><small>${escapeHtml(item.channel)} · ${escapeHtml(item.published_at || '')}</small><p>${escapeHtml(item.description || '')}</p></div>
      <div class="youtube-actions"><button data-youtube-open="${escapeHtml(item.url)}">Watch</button><button data-youtube-save="${escapeHtml(item.video_id)}">Save to Research</button></div>
    </article>`).join('') : `<div class="workspace-empty">${enabled && configured ? 'Search only runs when you ask. Results stay ephemeral until you explicitly save one to Research.' : 'YouTube API search is optional. Enable MARY_YOUTUBE_ENABLED and set YOUTUBE_API_KEY, or use Open YouTube to search in your browser.'}</div>`;
  return `
    <div class="media-hero">
      <div>
        <strong>Watch or listen with Mary</strong>
        <p>Ambient audio, your local music, and explicit YouTube search share one media surface. Mary does not browse YouTube in the background.</p>
        <div class="media-search"><input id="youtube-query" placeholder="Search YouTube…" /><button id="youtube-search-button">Search</button><button id="youtube-browser-button">Open YouTube</button></div>
        <div class="media-policy"><span class="status-chip">${enabled && configured ? 'API READY' : 'API OPTIONAL'}</span><small>Public metadata search only · no arbitrary transcript scraping · save intentionally to Research.</small></div>
        <div class="action-grid" style="margin-top:12px">
          <button class="action-button" id="media-choose-audio"><strong>Choose Local Music</strong><small>Plays through Mary's persistent mini-player</small></button>
          <button class="action-button" id="ambient-toggle"><strong>Ambient Bed</strong><small>${localStorage.getItem('mary.ambientEnabled') === 'false' ? 'Off' : 'On'} · ducks when Mary speaks</small></button>
        </div>
      </div>
    </div>
    <div class="section-title">YOUTUBE RESULTS</div>
    <div class="workspace-panel youtube-results">${youtubeRows}</div>`;
}

function renderVoice() {
  const voice = runtimeStatus.voice || {};
  const stt = runtimeStatus.speech_to_text || {};
  const trace = normalizeTurnTrace(ecosystemState.last_turn || lastTurnTrace);
  const plan = trace.delivery_plan || {};
  const timings = trace.timings || {};
  const textReady = timingValue(trace, 'text_ready_ms');
  const uiReceived = timingValue(trace, 'ui_payload_ms');
  const audioReady = timingValue(trace, 'audio_ready_ms');
  const perceived = timingValue(trace, 'perceived_ms');
  const transportMs = textReady !== null && uiReceived !== null ? Math.max(0, uiReceived - textReady) : null;
  const decodeMs = uiReceived !== null && audioReady !== null ? Math.max(0, audioReady - uiReceived) : null;
  const schedulerMs = audioReady !== null && perceived !== null ? Math.max(0, perceived - audioReady) : null;
  return `
    <div class="workspace-grid">
      <div class="workspace-panel accent">
        <h3>Voice</h3>
        <div class="data-row"><span>TTS</span><strong>${voice.enabled ? `ON · ${escapeHtml(voice.provider || 'configured')}` : 'OFF'}</strong></div>
        <div class="data-row"><span>Speech input</span><strong>${stt.enabled ? `ON · ${escapeHtml(stt.provider || 'configured')}` : 'OFF'}</strong></div>
        <div class="data-row"><span>Conversation state</span><strong>${escapeHtml(titleCase(conversationState))}</strong></div>
        <div class="data-row"><span>Delivery mode</span><strong>${escapeHtml(titleCase(plan.metadata?.performance_mode || 'natural conversation'))}</strong></div>
        <p>Stage 12 keeps neutral conversation natural, but represented Mary character modes now become audible and visible performance instead of being flattened back to one baseline.</p>
      </div>
      <div class="workspace-panel">
        <h3>Last delivery plan</h3>
        <div class="data-row"><span>Profile</span><strong>${escapeHtml(titleCase(plan.profile || '—'))}</strong></div>
        <div class="data-row"><span>Energy / warmth</span><strong>${escapeHtml(`${plan.energy ?? '—'} / ${plan.warmth ?? '—'}`)}</strong></div>
        <div class="data-row"><span>Stability / style</span><strong>${escapeHtml(`${plan.stability ?? '—'} / ${plan.style ?? '—'}`)}</strong></div>
        <div class="data-row"><span>Pace / emphasis</span><strong>${escapeHtml(`${plan.pace ?? '—'} / ${plan.emphasis ?? '—'}`)}</strong></div>
        <div class="data-row"><span>Gesture</span><strong>${escapeHtml(`${plan.gesture_energy ?? '—'} · ${titleCase(plan.gesture_style || 'natural')}`)}</strong></div>
        <div class="data-row"><span>Gaze / head</span><strong>${escapeHtml(`${titleCase(plan.gaze_style || 'engaged')} / ${titleCase(plan.head_style || 'natural')}`)}</strong></div>
        <div class="data-row"><span>Performance beats</span><strong>${escapeHtml(String(Array.isArray(plan.performance_beats) ? plan.performance_beats.length : 0))}</strong></div>
        <p>${escapeHtml(plan.rationale || 'Complete a turn to see the current delivery plan.')}</p>
      </div>
    </div>
    <div class="section-title">PLAYBACK STARTUP</div>
    <div class="workspace-grid three">
      <div class="workspace-panel"><h3>Bridge transport</h3><div class="data-row"><span>Text → UI payload</span><strong>${transportMs === null ? '—' : escapeHtml(formatMilliseconds(transportMs))}</strong></div><p>Measures QWebChannel/message transport after text and TTS are ready.</p></div>
      <div class="workspace-panel"><h3>Audio readiness</h3><div class="data-row"><span>Payload → canplay</span><strong>${decodeMs === null ? '—' : escapeHtml(formatMilliseconds(decodeMs))}</strong></div><p>12.12.2 prefers a bounded local file URL instead of moving a large base64 audio blob through the UI bridge.</p></div>
      <div class="workspace-panel"><h3>Browser start</h3><div class="data-row"><span>Canplay → speaking</span><strong>${schedulerMs === null ? '—' : escapeHtml(formatMilliseconds(schedulerMs))}</strong></div><p>Lip-sync graph setup now waits until playback has actually started.</p></div>
    </div>
    <div class="section-title">AVATAR PRESENTATION</div>
    <div class="workspace-panel">
      <div class="presentation-mode-row">
        <button class="action-button ${avatarPresentation === 'live' ? 'active' : ''}" data-avatar-presentation="live"><strong>Live 3D</strong><small>MaryCosma VRM · expressions + lip sync</small></button>
        <button class="action-button ${avatarPresentation === 'art' ? 'active' : ''}" data-avatar-presentation="art"><strong>Portrait Art</strong><small>Local Mary artwork · zero renderer dependency</small></button>
      </div>
      <div class="section-title" style="margin-top:14px">CAMERA</div>
      <div class="action-grid"><button class="action-button" data-avatar-frame="full"><strong>Full</strong><small>Whole-character framing</small></button><button class="action-button" data-avatar-frame="portrait"><strong>Portrait</strong><small>Default companion framing</small></button><button class="action-button" data-avatar-frame="close"><strong>Close</strong><small>Face / upper body</small></button></div>
    </div>
  `;
}

function renderSettings() {
  const providers = dashboardState.providers || {};
  const paths = dashboardState.paths || {};
  const apps = integrationState.creative_apps || [];
  const socket = runtimeStatus.presence_socket || {};
  const yt = youtubeStatus || {};
  return `
    <div class="workspace-grid">
      <div class="workspace-panel accent"><h3>Runtime</h3><div class="data-row"><span>Host</span><strong>${escapeHtml(providers.host || 'unknown')} / ${escapeHtml(providers.platform || 'unknown')}</strong></div><div class="data-row"><span>Conversation</span><strong>${escapeHtml((providers.effective_conversation_route || []).join(' → ') || 'none')}</strong></div><div class="data-row"><span>Fast chat model</span><strong>Groq · llama-3.1-8b-instant</strong></div><div class="data-row"><span>Task/general</span><strong>${escapeHtml((providers.effective_task_route || []).join(' → ') || 'none')}</strong></div><div class="data-row"><span>Paid expert</span><strong>OpenAI · explicit only</strong></div></div>
      <div class="workspace-panel"><h3>Private state</h3><div class="data-row"><span>Data root</span><strong>${escapeHtml(paths.data_root || 'unknown')}</strong></div><div class="data-row"><span>Workspace</span><strong>${escapeHtml(paths.workspace_root || 'unknown')}</strong></div><div class="action-grid"><button class="action-button" id="settings-open-data"><strong>Open Data Folder</strong><small>Mary's persistent private state</small></button><button class="action-button" id="settings-open-workspace"><strong>Open Workspace</strong><small>Project/filesystem root</small></button></div></div>
    </div>
    <div class="section-title">CONNECTED / OPTIONAL</div>
    <div class="workspace-grid three"><div class="workspace-panel"><h3>Local WebSocket</h3><div class="data-row"><span>Status</span><strong>${socket.enabled ? (socket.started ? 'Running' : 'Enabled') : 'Off'}</strong></div><div class="data-row"><span>Endpoint</span><strong>${escapeHtml(`${socket.host || '127.0.0.1'}:${socket.port || 8765}`)}</strong></div><p>Read-only loopback presence transport for future phone/browser clients. Disabled by default.</p></div><div class="workspace-panel"><h3>YouTube</h3><div class="data-row"><span>Search</span><strong>${yt.enabled && yt.configured ? 'Ready' : 'Optional'}</strong></div><p>Explicit public metadata search only. Results do not become memory unless you intentionally save them into Research.</p></div><div class="workspace-panel"><h3>OpenAI Expert</h3><div class="data-row"><span>Policy</span><strong>Per-task authorization</strong></div><p>Your paid API is not in normal conversation routing. Mary can consult it when a hard task actually needs stronger specialist reasoning.</p></div></div>
    <div class="section-title">CREATIVE APP INTEGRATIONS</div>
    <div class="workspace-panel"><div class="integration-grid">${apps.map((item) => `<div class="integration-item ${item.available ? '' : 'unavailable'}"><div class="integration-icon">✦</div><div><strong>${escapeHtml(item.label)}</strong><small>${item.available ? escapeHtml(item.path || 'Ready') : `Set ${escapeHtml(item.environment_variable)}`}</small></div></div>`).join('') || '<div class="workspace-empty">No integration state yet.</div>'}</div></div>
    <div class="section-title">UPDATES</div>
    <div class="workspace-panel"><h3>Mary Launcher</h3><p>The separate game-style launcher owns version checks and verified update staging. Persistent data stays outside replaceable program versions.</p></div>
  `;
}

function renderWorkspace(screen) {
  if (screen === 'chat') return;
  const meta = SCREEN_META[screen] || ['MARY', titleCase(screen), ''];
  $('#workspace-eyebrow').textContent = meta[0];
  $('#workspace-title').textContent = meta[1];
  $('#workspace-description').textContent = meta[2];
  const renderers = {
    home: renderHome,
    memories: renderMemories,
    growth: renderGrowth,
    personality: renderPersonality,
    mind: renderMind,
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
  $('#mind-rebuild')?.addEventListener('click', () => {
    if (!bridge?.rebuildCognitiveReservoir) return;
    bridge.rebuildCognitiveReservoir((raw) => {
      const result = parsePayload(raw);
      if (result.ok) {
        toast(`Reservoir rebuilt · ${result.records || 0} records`);
        bridge.getDashboardState?.((payload) => applyDashboardState(payload));
      } else {
        toast(result.error || 'Reservoir rebuild failed.', 'error');
      }
    });
  });
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
  $('#presence-idle-test')?.addEventListener('click',()=>bridge?.getIdleAction?.((raw)=>applyIdleAction(raw,{preview:true})));
  $$('[data-performance-context]').forEach((button)=>button.addEventListener('click',()=>{
    bridge?.setPerformanceContext?.(button.dataset.performanceContext,(raw)=>{
      const r=parsePayload(raw);
      if(r.error){toast(r.error,'error');return;}
      dashboardState.performance_context=r;
      toast(`Mary stage · ${titleCase(r.mode||button.dataset.performanceContext)}`);
      renderWorkspace('stream');
    });
  }));
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
  $$('#workspace-body [data-screen-jump]').forEach((button) => button.addEventListener('click', () => {
    setScreen(button.dataset.screenJump);
  }));
  $$('#workspace-body [data-avatar-presentation]').forEach((button) => button.addEventListener('click', () => {
    setAvatarPresentation(button.dataset.avatarPresentation);
    toast(button.dataset.avatarPresentation === 'art' ? 'Portrait Art presentation enabled.' : 'Live 3D presentation enabled.');
    if (currentScreen === 'voice') renderWorkspace('voice');
  }));
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
    if (!query) return;
    if (!bridge?.searchYouTube || !youtubeStatus.enabled || !youtubeStatus.configured) {
      bridge?.openExternalUrl?.(`https://www.youtube.com/results?search_query=${encodeURIComponent(query)}`);
      return;
    }
    bridge.searchYouTube(query, (raw) => {
      const result = parsePayload(raw);
      youtubeStatus = result.status || youtubeStatus;
      youtubeResults = result.results || [];
      if (!result.ok) toast(result.error || 'YouTube search failed.', 'error');
      renderWorkspace('media');
    });
  });
  $('#youtube-browser-button')?.addEventListener('click', () => bridge?.openExternalUrl?.('https://www.youtube.com/'));
  $$('#workspace-body [data-youtube-open]').forEach((button) => button.addEventListener('click', () => bridge?.openExternalUrl?.(button.dataset.youtubeOpen)));
  $$('#workspace-body [data-youtube-save]').forEach((button) => button.addEventListener('click', () => {
    const item = youtubeResults.find((entry) => entry.video_id === button.dataset.youtubeSave);
    if (!item || !bridge?.saveYouTubeToResearch) return;
    bridge.saveYouTubeToResearch(item.title, item.url, (raw) => {
      const result = parsePayload(raw);
      if (result.ok) toast('Saved to Research.'); else toast(result.error || 'Could not save result.', 'error');
      refreshEcosystem();
    });
  }));
  $('#ambient-toggle')?.addEventListener('click', () => {
    const enabled = localStorage.getItem('mary.ambientEnabled') !== 'false';
    localStorage.setItem('mary.ambientEnabled', enabled ? 'false' : 'true');
    if (enabled) ambientAudio?.pause(); else ensureAmbientMusic();
    renderWorkspace('media');
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
$('#workspace-close')?.addEventListener('click', () => setScreen('chat'));
$$('#quick-actions [data-prompt]').forEach((button) => button.addEventListener('click', () => submitPrompt(button.dataset.prompt)));

// ---------------------------------------------------------------------------
// Local media mini-player
// ---------------------------------------------------------------------------

function chooseMusic() {
  if (!bridge?.chooseMediaFile) return;
  bridge.chooseMediaFile((raw) => {
    const result = parsePayload(raw);
    if (!result.selected || !result.url) return;
    if (!musicAudio) return;
    musicAudio.src = result.url;
    const trackName = $('#track-name');
    if (trackName) trackName.textContent = String(result.path || '').split(/[\\/]/).pop() || 'Local audio';
    const trackArtist = $('#track-artist');
    if (trackArtist) trackArtist.textContent = 'Local file · playing with Mary';
    musicAudio.play().then(() => { if (musicPlayButton) musicPlayButton.textContent = '❚❚'; }).catch((error) => toast(`Could not play audio: ${error}`, 'error'));
  });
}

$('#choose-music-button')?.addEventListener('click', chooseMusic);
musicPlayButton?.addEventListener('click', () => {
  if (!musicAudio) return;
  if (!musicAudio.src) { chooseMusic(); return; }
  if (musicAudio.paused) musicAudio.play().then(() => { if (musicPlayButton) musicPlayButton.textContent = '❚❚'; }).catch(() => {});
  else { musicAudio.pause(); if (musicPlayButton) musicPlayButton.textContent = '▶'; }
});
musicAudio?.addEventListener('ended', () => { if (musicPlayButton) musicPlayButton.textContent = '▶'; });
$('#music-volume-button')?.addEventListener('click', () => {
  if (!musicAudio) return;
  musicAudio.muted = !musicAudio.muted;
  const volumeButton = $('#music-volume-button');
  if (volumeButton) volumeButton.textContent = musicAudio.muted ? '×' : '♪';
});

// ---------------------------------------------------------------------------
// Command palette
// ---------------------------------------------------------------------------

const commands = [
  { label: 'Mary Home', hint: 'Companion Pulse', action: () => setScreen('home') },
  { label: 'Local Mind', hint: 'Cognitive Reservoir', action: () => setScreen('mind') },
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
  if (!commandPalette || !commandInput || !commandResults) return;
  renderCommands('');
  if (!commandPalette.open) commandPalette.showModal();
  commandInput.value = '';
  window.setTimeout(() => commandInput?.focus(), 20);
}

// 12.11.1: the screen launcher replaced the old titlebar palette button.
// Keep Ctrl+K working without allowing a removed optional DOM control to abort
// the entire frontend module during boot.
$('#command-palette-button')?.addEventListener('click', openCommandPalette);
commandInput?.addEventListener('input', () => renderCommands(commandInput.value));
commandInput?.addEventListener('keydown', (event) => {
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
  if (event.key === 'Escape' && !commandPalette?.open && currentScreen !== 'chat') setScreen('chat');
});

function openScreenLauncher() {
  if (!screenLauncher) return;
  if (!screenLauncher.open) screenLauncher.showModal();
}
$('#screen-launcher-button')?.addEventListener('click', openScreenLauncher);
$('#workspace-menu-button')?.addEventListener('click', openScreenLauncher);
$('#screen-launcher-close')?.addEventListener('click', () => screenLauncher?.close());
$$('[data-launch-screen]').forEach((button) => button.addEventListener('click', () => {
  screenLauncher?.close();
  setScreen(button.dataset.launchScreen);
}));
screenLauncher?.addEventListener('click', (event) => { if (event.target === screenLauncher) screenLauncher.close(); });

// Start the quiet local bed after the first human gesture so this also works in
// browser-preview mode where autoplay policy may be stricter than Qt WebEngine.
window.addEventListener('pointerdown', ensureAmbientMusic, { once: true });
window.addEventListener('keydown', ensureAmbientMusic, { once: true });

// ---------------------------------------------------------------------------
// Window chrome
// ---------------------------------------------------------------------------

$('#window-minimize')?.addEventListener('click', () => bridge?.minimizeWindow?.());
$('#window-maximize')?.addEventListener('click', () => bridge?.maximizeWindow?.());
$('#window-close')?.addEventListener('click', () => bridge?.closeWindow?.());
$('#titlebar')?.addEventListener('pointerdown', (event) => {
  if (event.button !== 0) return;
  if (event.target.closest('button')) return;
  bridge?.startWindowMove?.();
});
$('#titlebar')?.addEventListener('dblclick', (event) => {
  if (event.target.closest('button')) return;
  bridge?.maximizeWindow?.();
});

// ---------------------------------------------------------------------------
// Qt bridge
// ---------------------------------------------------------------------------

function activateBridge(connectedBridge, { surface = 'desktop' } = {}) {
  bridge = connectedBridge;
  document.body.classList.toggle('mary-web-mobile', surface === 'mobile');
  if (surface === 'mobile') installMaryPwa();
  bootStep(58, surface === 'mobile' ? 'Connected to Mary mobile core…' : 'Connected to Mary core…');
  setConnected(true, 'Connection: Strong');

  window.setTimeout(() => {
    const boot = $('#boot-screen');
    if (boot && !boot.classList.contains('hidden')) {
      finishBoot('Mary is ready.');
      ensureAmbientMusic();
    }
  }, 5000);

  bridge.messageReady.connect((raw) => {
    const payload = parsePayload(raw);
    appendMessage('Mary', payload.text || '[No response]', 'mary');
    rememberAmbientAvatarState(payload.avatar || {});
    const packet = payload.runtime?.performance_packet || payload.voice?.performance_packet || {};
    const preReactionMs = applyPerformancePacket(packet);
    if (payload.runtime?.trace) applyTurnTrace(payload.runtime.trace);
    // Desktop voice returns audio. Mobile browser voice is handled by the
    // HTTP bridge so the same transcript never plays twice.  A bounded
    // deterministic pre-reaction lets Mary's face move before speech begins.
    if (!bridge._isHttpBridge) {
      window.setTimeout(() => playVoice(payload.voice || {}), preReactionMs);
    }
  });
  bridge.avatarStateChanged.connect((raw) => rememberAmbientAvatarState(parsePayload(raw)));
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
  bridge.getLastTurnTrace?.((raw) => applyTurnTrace(parsePayload(raw)));
  bridge.getAvatarState((raw) => rememberAmbientAvatarState(parsePayload(raw)));
  bridge.getCharacterState?.((raw) => applyCharacterState(raw));
  bridge.getDashboardState?.((raw) => {
    applyDashboardState(raw);
    bootStep(86, 'Loading memory, state, and ecosystem…');
    window.setTimeout(() => { finishBoot('Mary is ready.'); ensureAmbientMusic(); }, 280);
  });
  bridge.getYouTubeStatus?.((raw) => {
    youtubeStatus = parsePayload(raw);
    if (currentScreen === 'media') renderWorkspace('media');
  });
  bridge.getIntegrationState?.((raw) => {
    integrationState = parsePayload(raw);
    if (currentScreen === 'studio' || currentScreen === 'settings') renderWorkspace(currentScreen);
  });
  bridge.getCreativeWorkspaceState?.((raw) => {
    creativeWorkspaceState = parsePayload(raw);
    if (currentScreen === 'studio') renderWorkspace('studio');
  });
}

async function connectBridge() {
  if (window.qt?.webChannelTransport && typeof QWebChannel !== 'undefined') {
    new QWebChannel(window.qt.webChannelTransport, (channel) => {
      activateBridge(channel.objects.maryBridge, { surface: 'desktop' });
    });
    return;
  }

  try {
    const webBridge = await createHttpBridge();
    activateBridge(webBridge, { surface: 'mobile' });
  } catch (error) {
    setConnected(false, 'Mary mobile server unavailable');
    renderWorkspace(currentScreen);
    finishBoot('Mary mobile server unavailable.');
    console.error('[MaryMobile] bridge connection failed', error);
  }
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
    const homeValue=$('#presence-home-focus-value'); if(homeValue) homeValue.textContent=formatFocusTime(remaining);
    const homeLive=$('#presence-home-live'); if(homeLive) homeLive.innerHTML=`<i></i>FOCUS ${formatFocusTime(remaining)}`;
    if(remaining===0 && !focus._notified){ focus._notified=true; const audio=new Audio('./assets/sounds/focus_complete.wav'); audio.volume=.16; audio.play().catch(()=>{}); toast('Focus block complete.'); }
  }
  if(bridge && !document.hidden && !busy && conversationState==='idle' && performance.now()-lastPresencePulseAt>15000){
    lastPresencePulseAt=performance.now();
    bridge.pulsePresence?.();
  }
  if(bridge && conversationState==='idle' && performance.now()-lastIdleActionAt>90000){
    lastIdleActionAt=performance.now();
    bridge.getIdleAction?.((raw)=>applyIdleAction(raw));
  }
},1000);

window.addEventListener('resize', () => {
  resizeRenderer();
  setAvatarFraming(avatarFraming);
});

bootStep(28, 'Loading character renderer…');
syncAvatarPresentation();
loadMaryVrm();
window.setTimeout(()=>{ if(!bridge) finishBoot('Mary web preview mode.'); }, 4000);
connectBridge();
refreshConversationControls();
animate();
