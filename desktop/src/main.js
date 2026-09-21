import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { VRMLoaderPlugin, VRMUtils } from '@pixiv/three-vrm';
import { createVRMAnimationClip, VRMAnimationLoaderPlugin, VRMLookAtQuaternionProxy } from '@pixiv/three-vrm-animation';
import './style.css';
import './uplift.css';
import './presence.css';
import './neon-street.css';
import './presence-flow.css';
import './companion-window.css';
import { renderPresenceHome } from './ui/presenceHome.js';
import { formatMilliseconds, normalizeTurnTrace, providerAttemptSummary, timingValue } from './runtime/turnTrace.js';
import { createHttpBridge, installMaryPwa } from './runtime/httpBridge.js';
import './mobile.css';
import './experience-v2.css';
import './product-shell-13-66.css';
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
let residentHearingState = { enabled: false, active: false, state: 'off' };
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
let creatorLabState = { previewDataUrl: '', description: '', draft: '', busy: false };
let modelExperimentTrialState = { experimentId: '', prompt: 'Give a concise character-consistent response to this held-out trial prompt.', taskId: '', status: '', result: '', provider: '', model: '', busy: false };
let fabricGovernanceState = { loaded: false, loading: false, world: {}, skills: {} };
let busy = false;
let conversationState = 'idle';
let activeSpeechAudio = null;
let speechAudioContext = null;
let speechAudioSource = null;
let speechAnalyser = null;
let speechWaveform = null;
let activeMouthExpression = null;
let lipSyncWeight = 0;
let activeSpeechAlignment = [];
let currentVrm = null;
let avatarLoadError = '';
const BASE_DELIVERY_PLAN = { profile: 'neutral', energy: .4, gesture_energy: .3, avatar_expression: 'neutral', gesture_style: 'natural', gaze_style: 'engaged', head_style: 'natural', performance_beats: [] };
let currentDeliveryPlan = { ...BASE_DELIVERY_PLAN };
let currentPerformanceBeatIndex = -1;
let currentPerformancePacket = {};
let currentMotionCue = null;
let semanticMotionLastCue = null;
let semanticMotionId = '';
let semanticMotionBlend = 0;
let motionManifest = new Map();
let motionManifestStatus = { loaded: false, count: 0, error: '' };
let vrmaMixer = null;
let vrmaAction = null;
let vrmaActiveMotionId = '';
let vrmaRequestedMotionId = '';
let vrmaRequestGeneration = 0;
const vrmaClipCache = new Map();
const vrmaFailedMotions = new Set();
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
let studioMotionCue = null;
let windowPresentationMode = document.documentElement.dataset.windowMode || 'standard';
let stageScenePreset = localStorage.getItem('mary.stageScenePreset') || 'transparent';
let stageSceneBeforeCompanion = stageScenePreset;
let stageCameraYaw = Number(localStorage.getItem('mary.stageCameraYaw') || 0);
let stageCameraElevation = Number(localStorage.getItem('mary.stageCameraElevation') || 0);
let stageLighting = {
  key: Number(localStorage.getItem('mary.stageLight.key') || 2.35),
  fill: Number(localStorage.getItem('mary.stageLight.fill') || 1.25),
  rim: Number(localStorage.getItem('mary.stageLight.rim') || 1.05),
};

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

function providerDisplayName(value) {
  const name = String(value || '').trim().toLowerCase();
  const labels = {
    local_device: 'Local Model',
    groq: 'Groq',
    gemini: 'Gemini',
    openrouter: 'OpenRouter',
    ollama: 'Ollama',
    llama_cpp: 'llama.cpp',
    openai: 'OpenAI',
  };
  return labels[name] || titleCase(name || 'runtime');
}

function connectedNodeCount(snapshot = {}) {
  const rows = Array.isArray(snapshot?.nodes) ? snapshot.nodes : [];
  return rows.filter((node) => node && node.connected !== false).length;
}

function projectProductShell() {
  const setText = (selector, value) => {
    const node = $(selector);
    if (node) node.textContent = String(value ?? '');
  };

  const fabric = dashboardState?.compute_fabric || {};
  const routing = fabric?.routing || {};
  const routes = routing?.routes || {};
  const configuredConversation = Array.isArray(routes.conversation)
    ? routes.conversation
    : [];
  const dashboardRoute = Array.isArray(dashboardState?.providers?.effective_conversation_route)
    ? dashboardState.providers.effective_conversation_route
    : [];
  const route = configuredConversation.length ? configuredConversation : dashboardRoute;
  const capabilities = fabric?.capability_routes || {};
  const local = capabilities['llm.local'] || {};
  const lastGeneration = routing?.last_generation || {};
  const localReady = Boolean(local?.available);
  const coreConnected = Boolean(statusDot?.classList.contains('connected'));
  const voice = runtimeStatus?.voice || {};
  const nodes = dashboardState?.nodes || runtimeStatus?.nodes || {};
  const nodeCount = connectedNodeCount(nodes);
  const activeProvider = String(
    lastGeneration.selected_provider
    || lastTurnTrace.provider
    || runtimeStatus.provider
    || route[0]
    || ''
  ).trim();
  const activeModel = String(
    lastGeneration.selected_model
    || lastTurnTrace.model
    || runtimeStatus.model
    || ''
  ).trim();

  const coreState = coreConnected ? 'Connected' : 'Connecting';
  const coreDetail = coreConnected ? 'Canonical Mary Core' : 'Reconnecting to Mary';

  let computeState = 'Fallback ready';
  let computeDetail = route.length
    ? route.map(providerDisplayName).join(' → ')
    : 'Local + free-cloud fabric';
  if (localReady) {
    computeState = 'Local model ready';
    const selectedNode = String(local.selected_node_id || '').trim();
    computeDetail = selectedNode ? `Ready on ${selectedNode}` : 'Bounded local compute available';
  } else if (activeProvider) {
    computeState = providerDisplayName(activeProvider);
    computeDetail = activeModel || computeDetail;
  }

  const voiceState = voice.enabled
    ? providerDisplayName(voice.provider || 'voice')
    : 'Text ready';
  const voiceDetail = voice.enabled
    ? (voice.local
      ? 'Local voice'
      : 'Server voice · text remains available if voice degrades')
    : 'Voice optional · chat remains available';

  const presenceState = titleCase(conversationState || 'idle');
  const presenceDetail = ({
    idle: 'Ready to talk',
    listening: 'Listening to you',
    transcribing: 'Turning speech into text',
    responding: 'Building a response',
    thinking: 'Working through the turn',
    speaking: 'Mary is speaking',
    interrupted: 'Switching turns',
  })[conversationState] || 'Ready';

  setText('#shell-core-state', coreState);
  setText('#shell-core-detail', coreDetail);
  setText('#shell-compute-state', computeState);
  setText('#shell-compute-detail', computeDetail);
  setText('#shell-voice-state', voiceState);
  setText('#shell-voice-detail', voiceDetail);
  setText('#shell-presence-state', presenceState);
  setText('#shell-presence-detail', presenceDetail);

  setText('#system-core-value', coreState);
  setText('#system-compute-value', localReady ? 'Local ready' : (activeProvider ? providerDisplayName(activeProvider) : 'Fallback'));
  setText('#system-voice-value', voice.enabled ? providerDisplayName(voice.provider || 'voice') : 'Text');
  setText('#system-nodes-value', nodeCount);

  const overview = localReady
    ? 'Canonical Mary Core is linked to replaceable local compute with cloud fallback.'
    : 'Canonical Mary Core is linked; local compute can join without changing Mary identity.';
  setText('#system-overview-copy', overview);

  app.dataset.coreLink = coreConnected ? 'connected' : 'connecting';
  app.dataset.localCompute = localReady ? 'ready' : 'fallback';
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
    : (currentVrm
      ? 'Live VRM active'
      : avatarLoadError
        ? 'Portrait mode · 3D avatar unavailable'
        : 'VRM unavailable · local reference art');
  $$('[data-avatar-presentation]').forEach((button) => {
    button.classList.toggle('active', button.dataset.avatarPresentation === avatarPresentation);
  });
}

function setAvatarPresentation(mode = 'live') {
  avatarPresentation = mode === 'art' ? 'art' : 'live';
  localStorage.setItem('mary.avatarPresentation', avatarPresentation);
  syncAvatarPresentation();
}

function setWindowPresentationMode(mode = 'standard') {
  const next = mode === 'companion' ? 'companion' : 'standard';
  const previous = windowPresentationMode;
  windowPresentationMode = next;
  document.documentElement.dataset.windowMode = next;
  if (next === 'companion') {
    stageSceneBeforeCompanion = stageScenePreset;
    applyStageScenePreset('transparent');
  } else if (previous === 'companion') {
    applyStageScenePreset(stageSceneBeforeCompanion || 'transparent');
  }
  if (bridge?.setWindowPresentationMode) {
    bridge.setWindowPresentationMode(next);
  } else if (next === 'companion') {
    toast('Companion window mode requires the native Desktop host.', 'error');
    windowPresentationMode = 'standard';
    document.documentElement.dataset.windowMode = 'standard';
  }
  resizeRenderer();
  window.setTimeout(() => setAvatarFraming(avatarFraming), 30);
}

window.addEventListener('mary-window-mode', (event) => {
  const mode = String(event?.detail?.mode || 'standard').toLowerCase();
  const previous = windowPresentationMode;
  windowPresentationMode = mode === 'companion' ? 'companion' : 'standard';
  document.documentElement.dataset.windowMode = windowPresentationMode;
  if (windowPresentationMode === 'companion') {
    stageSceneBeforeCompanion = stageScenePreset;
    applyStageScenePreset('transparent');
  } else if (previous === 'companion') {
    applyStageScenePreset(stageSceneBeforeCompanion || 'transparent');
  }
  resizeRenderer();
  window.setTimeout(() => setAvatarFraming(avatarFraming), 30);
});

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

const renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true, preserveDrawingBuffer: true });
renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.shadowMap.enabled = true;

const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(28, 1, 0.1, 100);
camera.position.set(0, 1.35, 2.6);

const lookAtTarget = new THREE.Object3D();
lookAtTarget.name = 'maryPerformanceLookAtTarget';
scene.add(lookAtTarget);
const gazeTargetPosition = new THREE.Vector3();

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

const stageGroundMaterial = new THREE.MeshStandardMaterial({
  color: 0x101522,
  roughness: .72,
  metalness: .08,
  transparent: true,
  opacity: .72,
});
const stageGround = new THREE.Mesh(new THREE.CircleGeometry(1.35, 64), stageGroundMaterial);
stageGround.rotation.x = -Math.PI / 2;
stageGround.visible = false;
stageGround.receiveShadow = true;
scene.add(stageGround);

const stageRoom = new THREE.Group();
const stageRoomWallMaterial = new THREE.MeshStandardMaterial({ color: 0x111521, roughness: .9, metalness: 0 });
const stageRoomWall = new THREE.Mesh(new THREE.PlaneGeometry(4.2, 2.8), stageRoomWallMaterial);
stageRoomWall.position.set(0, 1.4, -1.15);
stageRoomWall.receiveShadow = true;
stageRoom.add(stageRoomWall);
const stageRoomBarMaterialA = new THREE.MeshBasicMaterial({ color: 0x7aa5ff, transparent: true, opacity: .78 });
const stageRoomBarMaterialB = new THREE.MeshBasicMaterial({ color: 0xff4fa6, transparent: true, opacity: .72 });
const stageRoomBarA = new THREE.Mesh(new THREE.BoxGeometry(.035, 1.8, .025), stageRoomBarMaterialA);
const stageRoomBarB = new THREE.Mesh(new THREE.BoxGeometry(.035, 1.5, .025), stageRoomBarMaterialB);
stageRoomBarA.position.set(-1.3, 1.42, -1.08);
stageRoomBarA.rotation.z = -.14;
stageRoomBarB.position.set(1.28, 1.15, -1.08);
stageRoomBarB.rotation.z = .16;
stageRoom.add(stageRoomBarA, stageRoomBarB);
const stageRoomAccentA = new THREE.PointLight(0x7aa5ff, .8, 4.5, 2);
const stageRoomAccentB = new THREE.PointLight(0xff4fa6, .7, 4.5, 2);
stageRoomAccentA.position.set(-1.1, 1.7, .1);
stageRoomAccentB.position.set(1.1, 1.25, .1);
stageRoom.add(stageRoomAccentA, stageRoomAccentB);
stageRoom.visible = false;
scene.add(stageRoom);

function applyStageScenePreset(name = stageScenePreset) {
  const normalized = ['transparent', 'void', 'studio', 'neon'].includes(name) ? name : 'transparent';
  stageScenePreset = normalized;
  localStorage.setItem('mary.stageScenePreset', normalized);
  stageGroundMaterial.emissiveIntensity = 0;
  if (normalized === 'transparent') {
    renderer.setClearColor(0x000000, 0);
    stageGround.visible = false;
    stageRoom.visible = false;
  } else if (normalized === 'void') {
    renderer.setClearColor(0x050611, 1);
    stageRoom.visible = false;
    stageGroundMaterial.color.setHex(0x101522);
    stageGroundMaterial.emissive.setHex(0x000000);
    stageGroundMaterial.opacity = .66;
    stageGround.visible = true;
  } else if (normalized === 'studio') {
    renderer.setClearColor(0x111521, 1);
    stageRoom.visible = true;
    stageRoomWallMaterial.color.setHex(0x28303c);
    stageRoomWallMaterial.emissive.setHex(0x000000);
    stageRoomWallMaterial.emissiveIntensity = 0;
    stageRoomBarA.visible = false;
    stageRoomBarB.visible = false;
    stageRoomAccentA.visible = false;
    stageRoomAccentB.visible = false;
    stageGroundMaterial.color.setHex(0x252b38);
    stageGroundMaterial.emissive.setHex(0x000000);
    stageGroundMaterial.opacity = .82;
    stageGround.visible = true;
  } else {
    renderer.setClearColor(0x03050e, 1);
    stageRoom.visible = true;
    stageRoomWallMaterial.color.setHex(0x0d0a18);
    stageRoomWallMaterial.emissive.setHex(0x090316);
    stageRoomWallMaterial.emissiveIntensity = .18;
    stageRoomBarA.visible = true;
    stageRoomBarB.visible = true;
    stageRoomAccentA.visible = true;
    stageRoomAccentB.visible = true;
    stageGroundMaterial.color.setHex(0x130d22);
    stageGroundMaterial.emissive.setHex(0x24082a);
    stageGroundMaterial.emissiveIntensity = .34;
    stageGroundMaterial.opacity = .74;
    stageGround.visible = true;
  }
  stageGroundMaterial.needsUpdate = true;
}

function applyStageLighting(values = stageLighting) {
  stageLighting = {
    key: Math.max(0, Math.min(5, Number(values.key ?? stageLighting.key) || 0)),
    fill: Math.max(0, Math.min(5, Number(values.fill ?? stageLighting.fill) || 0)),
    rim: Math.max(0, Math.min(5, Number(values.rim ?? stageLighting.rim) || 0)),
  };
  keyLight.intensity = stageLighting.key;
  fillLight.intensity = stageLighting.fill;
  rimLight.intensity = stageLighting.rim;
  localStorage.setItem('mary.stageLight.key', String(stageLighting.key));
  localStorage.setItem('mary.stageLight.fill', String(stageLighting.fill));
  localStorage.setItem('mary.stageLight.rim', String(stageLighting.rim));
}

function applyStageLightingPreset(name = 'balanced') {
  const presets = {
    balanced: { key: 2.35, fill: 1.25, rim: 1.05 },
    soft: { key: 1.65, fill: 1.45, rim: .65 },
    neon: { key: 2.0, fill: 1.8, rim: 1.65 },
    dramatic: { key: 2.9, fill: .48, rim: 1.9 },
  };
  applyStageLighting(presets[name] || presets.balanced);
}

function captureAvatarPng() {
  if (!currentVrm) {
    toast('Live VRM is not loaded, so there is no 3D frame to capture.', 'error');
    return;
  }
  try {
    renderer.render(scene, camera);
    const dataUrl = renderer.domElement.toDataURL('image/png');
    const anchor = document.createElement('a');
    anchor.href = dataUrl;
    anchor.download = `Mary-${new Date().toISOString().replaceAll(':', '-').replaceAll('.', '-')}.png`;
    document.body.append(anchor);
    anchor.click();
    anchor.remove();
    toast('Mary stage PNG captured.');
  } catch (error) {
    toast(`Could not capture the Mary stage: ${error?.message || error}`, 'error');
  }
}

function copyStageSetup() {
  const payload = {
    version: 1,
    body: 'MaryCosma.vrm',
    framing: avatarFraming,
    lighting: { ...stageLighting },
    scene: stageScenePreset,
    camera_yaw: stageCameraYaw,
    camera_elevation: stageCameraElevation,
    vrma_assets: motionManifestStatus.count,
    vrma_active_motion: vrmaActiveMotionId,
    expression: String(ambientAvatarState.expression || 'neutral'),
    motion_preview: studioMotionCue?.motion_id || '',
    authority: 'presentation_only',
  };
  const text = JSON.stringify(payload, null, 2);
  if (navigator.clipboard?.writeText) {
    navigator.clipboard.writeText(text)
      .then(() => toast('Stage setup copied.'))
      .catch(() => window.prompt('Copy Mary stage setup:', text));
  } else {
    window.prompt('Copy Mary stage setup:', text);
  }
}

applyStageLighting();
applyStageScenePreset(stageScenePreset);

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

  const yaw = THREE.MathUtils.degToRad(Math.max(-45, Math.min(45, stageCameraYaw)));
  const elevation = Math.max(-.3, Math.min(.3, stageCameraElevation));
  camera.position.set(
    center.x + Math.sin(yaw) * distance,
    targetY + elevation,
    center.z + Math.cos(yaw) * distance,
  );
  camera.lookAt(center.x, targetY + elevation * .28, center.z);
}

async function loadMaryVrm() {
  const loader = new GLTFLoader();
  loader.register((parser) => new VRMLoaderPlugin(parser));

  try {
    const gltf = await loader.loadAsync('./models/MaryCosma.vrm');
    const vrm = gltf.userData.vrm;
    if (!vrm) throw new Error('No VRM object was found in MaryCosma.vrm.');

    resetVrmaRuntime();
    if (currentVrm) scene.remove(currentVrm.scene);
    VRMUtils.removeUnnecessaryVertices(vrm.scene);
    VRMUtils.combineSkeletons(vrm.scene);
    currentVrm = vrm;
    VRMUtils.rotateVRM0(currentVrm);
    ensureVrmLookAtAnimationProxy(currentVrm);
    if (currentVrm.lookAt) {
      currentVrm.lookAt.target = lookAtTarget;
      currentVrm.lookAt.autoUpdate = true;
    }
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
    stageGround.position.set(center.x, box.min.y + .006, center.z);
    stageGround.scale.setScalar(Math.max(.75, Math.min(1.65, size.x * 1.4)));
    const roomScale = Math.max(.78, Math.min(1.55, size.y / 1.68));
    stageRoom.scale.setScalar(roomScale);
    stageRoom.position.set(center.x, box.min.y, center.z - size.z * .18);
    avatarLoadError = '';
    setAvatarFraming(avatarFraming);
    // Qt may settle the stage geometry one frame after the model finishes loading.
    window.requestAnimationFrame(() => setAvatarFraming(avatarFraming));
    syncAvatarPresentation();
    applyAvatarState({ expression: 'neutral', emotion_intensity: 0 });
    reportPresentationCapabilities();
  } catch (error) {
    console.warn('MaryCosma.vrm was not loaded:', error);
    avatarLoadError = String(error?.message || error || 'VRM load failed');
    currentVrm = null;
    syncAvatarPresentation();
    reportPresentationCapabilities();
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

function faceExpressionNames(manager) {
  const names = Object.keys(manager?.expressionMap || {});
  const reserved = new Set([
    ...(manager?.blinkExpressionNames || []),
    ...(manager?.mouthExpressionNames || []),
    ...(manager?.lookAtExpressionNames || []),
  ].map((item) => String(item).toLowerCase()));
  return names.filter((name) => !reserved.has(String(name).toLowerCase()));
}

function resolveFaceExpression(manager, requested = 'neutral') {
  const raw = String(requested || 'neutral').trim();
  const key = raw.toLowerCase().replaceAll('-', '_').replaceAll(' ', '_');
  const exactNames = Object.keys(manager?.expressionMap || {});
  const exact = exactNames.find((name) => String(name).toLowerCase() === key);
  if (exact) return exact;

  const aliases = {
    loving: ['happy', 'smile', 'joy'],
    affectionate: ['happy', 'smile', 'joy'],
    warmth: ['happy', 'relaxed', 'smile'],
    grateful: ['happy', 'relaxed', 'smile'],
    gratitude: ['happy', 'relaxed', 'smile'],
    proud: ['happy', 'relaxed'],
    excited: ['happy', 'surprised'],
    amused: ['happy', 'relaxed', 'smile'],
    playful: ['happy', 'relaxed', 'smile'],
    curious: ['relaxed', 'neutral', 'surprised'],
    calm: ['relaxed', 'neutral'],
    hopeful: ['relaxed', 'happy'],
    concerned: ['sad', 'relaxed'],
    lonely: ['sad', 'relaxed'],
    disappointed: ['sad', 'relaxed'],
    frustrated: ['angry', 'sad'],
    firm: ['angry', 'neutral'],
    confused: ['surprised', 'relaxed'],
    afraid: ['surprised', 'sad'],
    neutral: ['neutral', 'relaxed'],
  };
  const candidates = [key, ...(aliases[key] || []), PRESET_MAP[key]].filter(Boolean);
  for (const candidate of candidates) {
    const found = exactNames.find((name) => String(name).toLowerCase() === String(candidate).toLowerCase());
    if (found) return found;
  }

  const custom = manager?.customExpressionMap || {};
  const customNames = Object.keys(custom);
  const fuzzyTokens = new Set(candidates.flatMap((item) => String(item).split(/[_\s-]+/)).filter(Boolean));
  for (const name of customNames) {
    const lower = String(name).toLowerCase();
    if ([...fuzzyTokens].some((token) => token.length > 2 && lower.includes(token))) return name;
  }
  return exactNames.find((name) => String(name).toLowerCase() === 'neutral')
    || exactNames.find((name) => String(name).toLowerCase() === 'relaxed')
    || null;
}

function resetKnownExpressions(manager) {
  for (const name of faceExpressionNames(manager)) {
    try { manager.setValue(name, 0); } catch (_) { /* optional/custom expression */ }
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
  const preset = resolveFaceExpression(manager, expression);
  const beatEnergy = clamp(beat.energy ?? currentDeliveryPlan.energy ?? .4);
  const intensity = Math.max(.08, Math.min(.82, .18 + beatEnergy * .62));
  if (preset) {
    try { manager.setValue(preset, intensity); } catch (_) { /* optional/custom expression */ }
  }
}

function desktopPresentationCapabilities() {
  const liveBody = Boolean(currentVrm);
  return {
    expression_cues: liveBody,
    gaze_cues: liveBody,
    head_motion: liveBody,
    semantic_motion: liveBody,
    motion_assets: liveBody && motionManifestStatus.count > 0,
    lip_sync: liveBody,
    voice_direction: true,
    scene_context: true,
    lighting_control: true,
    transparent_overlay: true,
    capture: liveBody,
    locomotion: false,
    vr: false,
  };
}

function reportPresentationCapabilities() {
  if (!bridge?.setPresentationCapabilities || bridge?._isHttpBridge) return;
  const payload = JSON.stringify(desktopPresentationCapabilities());
  try {
    bridge.setPresentationCapabilities(payload, () => {});
  } catch (_) {
    // Capability reporting is presentation telemetry only; a failed renewal
    // must never fail the Desktop or a Mary turn.
  }
}

async function loadMotionManifest() {
  try {
    const response = await fetch('./motions/manifest.json', { cache: 'no-store' });
    if (!response.ok) throw new Error(`motion manifest HTTP ${response.status}`);
    const payload = await response.json();
    const next = new Map();
    for (const raw of Array.isArray(payload?.motions) ? payload.motions.slice(0, 128) : []) {
      const motionId = String(raw?.motion_id || '').trim();
      const uri = String(raw?.uri || '').trim();
      if (!motionId || !uri.toLowerCase().endsWith('.vrma')) continue;
      let parsed;
      try { parsed = new URL(uri, window.location.href); } catch (_) { continue; }
      if (parsed.origin !== window.location.origin || !parsed.pathname.includes('/motions/')) continue;
      next.set(motionId, {
        motion_id: motionId,
        uri: parsed.href,
        loop: Boolean(raw?.loop),
        fade_in_ms: Math.max(60, Math.min(1500, Number(raw?.fade_in_ms) || 180)),
        fade_out_ms: Math.max(60, Math.min(1500, Number(raw?.fade_out_ms) || 240)),
        source: String(raw?.source || 'local').slice(0, 120),
        license: String(raw?.license || 'unknown').slice(0, 120),
      });
    }
    motionManifest = next;
    motionManifestStatus = { loaded: true, count: next.size, error: '' };
  } catch (error) {
    motionManifest = new Map();
    motionManifestStatus = {
      loaded: false,
      count: 0,
      error: String(error?.message || error || 'motion manifest unavailable').slice(0, 220),
    };
  }
  reportPresentationCapabilities();
  if (currentScreen === 'voice') renderWorkspace('voice');
  return motionManifestStatus;
}

function resetVrmaRuntime() {
  vrmaRequestGeneration += 1;
  vrmaRequestedMotionId = '';
  vrmaActiveMotionId = '';
  if (vrmaAction) {
    try { vrmaAction.stop(); } catch (_) { /* best effort */ }
  }
  vrmaAction = null;
  if (vrmaMixer) {
    try { vrmaMixer.stopAllAction(); } catch (_) { /* best effort */ }
  }
  vrmaMixer = null;
  vrmaClipCache.clear();
  vrmaFailedMotions.clear();
}

function ensureVrmLookAtAnimationProxy(vrm) {
  if (!vrm?.lookAt || vrm.scene.getObjectByName?.('lookAtQuaternionProxy')) return;
  try {
    const proxy = new VRMLookAtQuaternionProxy(vrm.lookAt);
    proxy.name = 'lookAtQuaternionProxy';
    vrm.scene.add(proxy);
  } catch (error) {
    console.warn('VRMA look-at proxy unavailable:', error);
  }
}

async function ensureVrmaClip(motionId) {
  if (!currentVrm || !motionManifest.has(motionId) || vrmaFailedMotions.has(motionId)) return null;
  if (vrmaClipCache.has(motionId)) return vrmaClipCache.get(motionId);

  const asset = motionManifest.get(motionId);
  try {
    const loader = new GLTFLoader();
    loader.register((parser) => new VRMAnimationLoaderPlugin(parser));
    const gltf = await loader.loadAsync(asset.uri);
    const vrmAnimation = Array.isArray(gltf.userData?.vrmAnimations)
      ? gltf.userData.vrmAnimations[0]
      : null;
    if (!vrmAnimation) throw new Error('VRMA file contained no VRM animation.');
    const clip = createVRMAnimationClip(vrmAnimation, currentVrm);
    const resolved = { clip, asset };
    vrmaClipCache.set(motionId, resolved);
    return resolved;
  } catch (error) {
    vrmaFailedMotions.add(motionId);
    console.warn(`VRMA motion ${motionId} could not load; procedural fallback remains active:`, error);
    if (currentScreen === 'voice') renderWorkspace('voice');
    return null;
  }
}

function ensureVrmaMixer() {
  if (!currentVrm) return null;
  if (vrmaMixer) return vrmaMixer;
  vrmaMixer = new THREE.AnimationMixer(currentVrm.scene);
  vrmaMixer.addEventListener('finished', (event) => {
    if (event.action !== vrmaAction) return;
    vrmaAction = null;
    vrmaActiveMotionId = '';
  });
  return vrmaMixer;
}

async function requestVrmaMotion(cue) {
  const motionId = String(cue?.motion_id || '');
  if (!motionId || !motionManifest.has(motionId) || vrmaFailedMotions.has(motionId)) return false;
  if (vrmaActiveMotionId === motionId && vrmaAction) return true;
  if (vrmaRequestedMotionId === motionId) return Boolean(vrmaAction);

  const generation = ++vrmaRequestGeneration;
  vrmaRequestedMotionId = motionId;
  const resolved = await ensureVrmaClip(motionId);
  if (generation !== vrmaRequestGeneration || vrmaRequestedMotionId !== motionId || !resolved || !currentVrm) {
    return false;
  }

  const mixer = ensureVrmaMixer();
  if (!mixer) return false;
  const previous = vrmaAction;
  const next = mixer.clipAction(resolved.clip);
  const fadeSeconds = Math.max(.06, resolved.asset.fade_in_ms / 1000);
  next.reset();
  next.enabled = true;
  next.clampWhenFinished = !resolved.asset.loop;
  next.setLoop(resolved.asset.loop ? THREE.LoopRepeat : THREE.LoopOnce, resolved.asset.loop ? Infinity : 1);
  next.setEffectiveWeight(1);
  next.play();

  if (previous && previous !== next) {
    try { previous.crossFadeTo(next, fadeSeconds, false); } catch (_) { next.fadeIn(fadeSeconds); }
  } else {
    next.fadeIn(fadeSeconds);
  }

  vrmaAction = next;
  vrmaActiveMotionId = motionId;
  vrmaRequestedMotionId = '';
  semanticMotionBlend = 0;
  return true;
}

function releaseVrmaMotion() {
  vrmaRequestGeneration += 1;
  vrmaRequestedMotionId = '';
  vrmaActiveMotionId = '';
  if (!vrmaAction) return;
  const action = vrmaAction;
  vrmaAction = null;
  try { action.fadeOut(.24); } catch (_) { try { action.stop(); } catch (_) {} }
}

function syncVrmaMotion(cue) {
  const motionId = String(cue?.motion_id || '');
  const hasAsset = Boolean(motionId && motionManifest.has(motionId) && !vrmaFailedMotions.has(motionId));
  if (!hasAsset) {
    if (vrmaAction || vrmaRequestedMotionId) releaseVrmaMotion();
    return false;
  }
  void requestVrmaMotion(cue);
  return Boolean(vrmaAction || vrmaRequestedMotionId);
}

function motionCueForSegment(index) {
  const cues = Array.isArray(currentPerformancePacket?.motion_cues) ? currentPerformancePacket.motion_cues : [];
  if (!cues.length || index < 0) return null;
  return cues.find((cue) => Number(cue?.segment_index) === Number(index)) || null;
}

function motionPoseForCue(cue, elapsed, energy = .35) {
  const id = String(cue?.motion_id || '').toLowerCase();
  const sway = Math.sin(elapsed * 1.75) * Math.min(.08, .02 + energy * .045);
  const pulse = Math.sin(elapsed * 2.1) * Math.min(.10, .02 + energy * .055);
  let leftUpper = [0, 0, -1.28];
  let rightUpper = [0, 0, 1.28];
  let leftLower = [0, -0.10, -0.10];
  let rightLower = [0, 0.10, 0.10];

  if (id === 'explain_small') {
    rightUpper = [-.14, -.06, 1.08 + sway]; rightLower = [-.18, .22, .38 + pulse];
  } else if (id === 'explain_animated') {
    leftUpper = [-.12, .08, -1.00 - sway]; rightUpper = [-.12, -.08, 1.00 + sway];
    leftLower = [-.18, -.20, -.34 - pulse]; rightLower = [-.18, .20, .34 + pulse];
  } else if (id === 'shrug_dry') {
    leftUpper = [-.05, .05, -1.02]; rightUpper = [-.05, -.05, 1.02];
    leftLower = [-.25, -.15, -.48]; rightLower = [-.25, .15, .48];
  } else if (id === 'teasing_point') {
    rightUpper = [-.28, -.10, .86 + sway * .4]; rightLower = [-.08, .12, .18];
    leftUpper = [0, 0, -1.22];
  } else if (id === 'warm_acknowledge') {
    rightUpper = [-.08, -.03, 1.16]; rightLower = [-.12, .10, .20 + sway * .25];
  } else if (id === 'serious_hold' || id === 'boundary_small') {
    leftUpper = [0, 0, -1.20]; rightUpper = [0, 0, 1.20];
    leftLower = [-.06, -.06, -.14]; rightLower = [-.06, .06, .14];
  } else if (id === 'thinking_pause') {
    rightUpper = [-.12, -.03, .98]; rightLower = [-.36, .10, .42];
  } else if (id === 'surprised_react') {
    leftUpper = [-.10, .04, -.94]; rightUpper = [-.10, -.04, .94];
    leftLower = [-.10, -.16, -.24]; rightLower = [-.10, .16, .24];
  } else if (id === 'laugh_small') {
    leftUpper = [-.06, .04, -1.10 - sway]; rightUpper = [-.06, -.04, 1.10 + sway];
    leftLower = [-.16, -.10, -.22]; rightLower = [-.16, .10, .22];
  } else if (id === 'listen_attentive') {
    rightUpper = [0, 0, 1.25]; leftUpper = [0, 0, -1.25];
  } else if (id === 'talk_neutral') {
    rightUpper = [-.03, 0, 1.22 + sway * .25]; leftUpper = [-.03, 0, -1.22 - sway * .25];
    rightLower = [-.08, .10, .12 + pulse * .2]; leftLower = [-.08, -.10, -.12 - pulse * .2];
  }

  return {
    leftUpperArm: { rotation: quaternionArrayFromEuler(...leftUpper) },
    rightUpperArm: { rotation: quaternionArrayFromEuler(...rightUpper) },
    leftLowerArm: { rotation: quaternionArrayFromEuler(...leftLower) },
    rightLowerArm: { rotation: quaternionArrayFromEuler(...rightLower) },
  };
}

function blendPoseRotation(baseRotation, targetRotation, weight) {
  const base = new THREE.Quaternion(...baseRotation);
  const target = new THREE.Quaternion(...targetRotation);
  base.slerp(target, clamp(weight));
  return [base.x, base.y, base.z, base.w];
}

function applySemanticMotionLayer(cue, elapsed, energy, delta) {
  const humanoid = currentVrm?.humanoid;
  if (!humanoid?.setNormalizedPose) return;

  const nextId = String(cue?.motion_id || '');
  if (cue) {
    if (nextId && nextId !== semanticMotionId) {
      // Pull toward the base pose briefly on clip/semantic changes so a new
      // gesture reads as a transition instead of a skeleton snap.
      semanticMotionBlend = Math.min(semanticMotionBlend, .24);
      semanticMotionId = nextId;
    }
    semanticMotionLastCue = cue;
  }

  const targetWeight = cue ? clamp(.34 + energy * .58, .24, .92) : 0;
  const seconds = cue ? .16 : .30;
  const response = Math.min(1, Math.max(.02, delta / seconds));
  semanticMotionBlend += (targetWeight - semanticMotionBlend) * response;

  if (!semanticMotionLastCue) return;
  if (!cue && semanticMotionBlend < .008) {
    semanticMotionBlend = 0;
    semanticMotionId = '';
    semanticMotionLastCue = null;
    humanoid.setNormalizedPose(RELAXED_STANDING_POSE);
    return;
  }

  const targetPose = motionPoseForCue(
    semanticMotionLastCue,
    elapsed,
    energy,
  );
  const layeredPose = {};
  for (const [bone, base] of Object.entries(RELAXED_STANDING_POSE)) {
    const target = targetPose[bone] || base;
    layeredPose[bone] = {
      rotation: blendPoseRotation(
        base.rotation,
        target.rotation || base.rotation,
        semanticMotionBlend,
      ),
    };
  }
  humanoid.setNormalizedPose(layeredPose);
}

function applySemanticMotionPose(cue, elapsed, energy, delta = .016) {
  applySemanticMotionLayer(cue, elapsed, energy, delta);
}

function updatePerformanceBeat() {
  const { index, beat } = performanceBeatState();
  if (index === currentPerformanceBeatIndex) return beat;
  currentPerformanceBeatIndex = index;
  currentMotionCue = motionCueForSegment(index);
  if (beat) applyPerformanceExpression(beat);
  return beat;
}

function applyPerformancePacket(packet = {}) {
  if (performanceSettleTimer) {
    window.clearTimeout(performanceSettleTimer);
    performanceSettleTimer = null;
  }
  currentPerformancePacket = packet && typeof packet === 'object' ? packet : {};
  syncPresenceFlow();
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
    syncPresenceFlow();
    currentDeliveryPlan = { ...BASE_DELIVERY_PLAN };
    currentPerformanceBeatIndex = -1;
    currentMotionCue = null;
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
  const preset = resolveFaceExpression(manager, emotionName);
  const deliveryEnergy = clamp(currentDeliveryPlan.energy ?? 0.4);
  const intensity = Math.max(0.08, clamp(Math.max(state.emotion_intensity ?? state.intensity ?? 0.3, deliveryEnergy * .58)));
  if (preset) {
    try { manager.setValue(preset, intensity); } catch (_) { /* optional/custom expression */ }
  }
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

function updatePerformanceGaze(gazeStyle = 'engaged', delta = .016) {
  if (!currentVrm?.lookAt || !modelBounds) return;
  const { size } = modelBounds;
  const scale = Math.max(.45, Math.min(1.4, size.y || 1));
  const style = String(gazeStyle || 'engaged').toLowerCase();
  let x = 0;
  let y = 0;
  if (style === 'glance_away') x = -.26 * scale;
  else if (style === 'left') x = -.34 * scale;
  else if (style === 'right') x = .34 * scale;
  else if (style === 'up') y = .18 * scale;
  else if (style === 'down') y = -.18 * scale;
  else if (style === 'soft') y = -.035 * scale;

  gazeTargetPosition.copy(camera.position);
  gazeTargetPosition.x += x;
  gazeTargetPosition.y += y;
  const response = Math.min(1, Math.max(.04, delta / (style === 'direct' ? .10 : .20)));
  lookAtTarget.position.lerp(gazeTargetPosition, response);
  lookAtTarget.updateMatrixWorld(true);
  currentVrm.lookAt.target = lookAtTarget;
  currentVrm.lookAt.autoUpdate = true;
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
    if (vrmaMixer) vrmaMixer.update(delta);
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

    // Semantic motion is a presentation projection from Mary's established
    // PerformancePacket. These procedural poses are placeholders for future
    // licensed/local VRMA/FBX clips resolved by the same motion IDs.
    const semanticCue = currentMotionCue
      || ((!activeSpeechAudio && currentScreen === 'voice' && studioMotionCue) ? studioMotionCue : null)
      || (conversationState === 'listening' ? { motion_id: 'listen_attentive' } : null);
    const vrmaOwnsBody = syncVrmaMotion(semanticCue);
    if (!vrmaOwnsBody) {
      applySemanticMotionLayer(semanticCue, elapsed, gestureEnergy, delta);
    }

    updatePerformanceGaze(gazeStyle, delta);

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

const ALIGNMENT_VOWEL_MAP = {
  a: 'aa', e: 'ee', i: 'ih', o: 'oh', u: 'ou',
  y: 'ee',
};

function alignmentMouthExpressionAt(seconds) {
  if (!Array.isArray(activeSpeechAlignment) || !activeSpeechAlignment.length) return null;
  const t = Number(seconds || 0);
  // Alignment marks are ordered. Binary search keeps this cheap even for long speech.
  let low = 0;
  let high = activeSpeechAlignment.length - 1;
  let found = null;
  while (low <= high) {
    const mid = (low + high) >> 1;
    const mark = activeSpeechAlignment[mid] || {};
    const start = Number(mark.start_seconds || 0);
    const end = Number(mark.end_seconds || start);
    if (t < start) high = mid - 1;
    else if (t > end) low = mid + 1;
    else { found = mark; break; }
  }
  if (!found) return null;
  const ch = String(found.text || '').toLowerCase();
  if (/\s|[.,!?;:]/.test(ch)) return '__closed__';
  return ALIGNMENT_VOWEL_MAP[ch] || null;
}


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
  const alignedExpression = activeSpeechAudio ? alignmentMouthExpressionAt(activeSpeechAudio.currentTime) : null;
  if (alignedExpression === '__closed__') target = 0;
  const desiredExpression = alignedExpression && alignedExpression !== '__closed__' ? alignedExpression : activeMouthExpression;
  if (desiredExpression !== activeMouthExpression && MOUTH_PRESET_CANDIDATES.includes(desiredExpression)) {
    for (const preset of MOUTH_PRESET_CANDIDATES) {
      try { manager.setValue(preset, 0); } catch (_) { /* optional */ }
    }
    activeMouthExpression = desiredExpression;
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
  activeSpeechAlignment = [];
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
  activeSpeechAlignment = Array.isArray(voice?.alignment?.characters) ? voice.alignment.characters.slice(0, 12000) : [];
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
      activeSpeechAlignment = [];
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
    activeSpeechAlignment = [];
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
    activeSpeechAlignment = [];
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
  projectProductShell();
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
  syncPresenceFlow();
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
    ? `Conversation: ${route.map(providerDisplayName).join(' → ')}`
    : 'Conversation automatically uses the best ready route.';
  const badges = $('#provider-badges');
  badges.innerHTML = (state.providers || []).map((provider) => `
    <span class="provider-badge ${provider.available ? 'ready' : ''}">${escapeHtml(providerDisplayName(provider.name))} · ${provider.available ? 'READY' : 'OFF'}</span>
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
  projectProductShell();
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

function applyLiveSceneSummary(ecosystem = ecosystemState) {
  const scene = ecosystem?.character_runtime?.live_scene || ecosystem?.presence?.scene || {};
  const realtime = ecosystem?.character_runtime?.realtime || dashboardState.realtime || runtimeStatus.realtime || {};
  const arbiter = realtime.speech_arbiter || {};
  const environment = scene.environment || {};
  const setText = (selector, value) => { const node = $(selector); if (node) node.textContent = value; };
  setText('#scene-mode', titleCase(scene.mode || 'conversation'));
  setText('#scene-floor', titleCase(scene.floor_owner || 'none'));
  setText('#scene-phase', titleCase(scene.realtime_phase || realtime.phase || 'idle'));
  const context = scene.project || scene.activity || scene.workspace || scene.selected_asset || 'No focused scene';
  setText('#scene-context', context);
  const env = environment.foreground_app || environment.obs_scene || Object.values(environment)[0] || 'No live environment signal';
  setText('#scene-environment', env);
  setText('#scene-speech-queue', arbiter.queue_depth ?? 0);
}

function applyDashboardState(raw) {
  const payload = parsePayload(raw);
  dashboardState = payload;
  ecosystemState = payload.ecosystem || ecosystemState || {};
  if (ecosystemState.last_turn) applyTurnTrace(ecosystemState.last_turn);
  applyCompanionPulse(ecosystemState);
  applyLiveSceneSummary(ecosystemState);
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

  projectProductShell();
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
  fabric: ['SYSTEM FABRIC', 'System Fabric', 'Knowledge, temporal world state, procedural learning, model experiments, and compute evidence from the same Core.'],
  diagnostics: ['SYSTEM', 'Runtime & Compute', 'A clear view of Mary Core, local/cloud model routes, capability nodes, realtime state, and measured turn performance.'],
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
  const adapterLab = ecosystemState.adapter_lab || {};
  const candidateCatalog = ecosystemState.model_candidates || {};
  const candidates = candidateCatalog.candidates || [];
  const leaderboard = adapterLab.leaderboard || [];
  const sizeMb = Number(reservoir.size_bytes || 0) / (1024 * 1024);
  const modelRows = models.map((item) => `
    <div class="command-row">
      <span class="kind">${item.role === 'embeddings' ? '◇' : item.role.includes('dialogue') || item.role.includes('character') ? '◉' : '⌁'}</span>
      <div><strong>${escapeHtml(item.model)}</strong><small>${escapeHtml(titleCase(item.role))} · ~${escapeHtml(item.approx_size_gb)} GB · ${escapeHtml(item.notes)}</small></div>
      <span class="status-chip">P${escapeHtml(item.priority)}</span>
    </div>`).join('');
  const candidateRows = candidates.map((item) => {
    const roles = item.roles || [];
    return `<div class="command-row model-candidate-row">
      <span class="kind">${item.kind === 'lora_adapter' ? '↯' : item.kind === 'stt_model' ? '◉' : item.kind === 'vad_model' ? '⌁' : '◇'}</span>
      <div><strong>${escapeHtml(item.id || item.filename || 'candidate')}</strong><small>${escapeHtml(item.runtime || 'runtime')} · ${escapeHtml(item.metadata?.approx_size || item.metadata?.approx_size_gb || item.metadata?.asset_group || '')}${roles.length ? ` · ${escapeHtml(roles.join(' / '))}` : ''}</small></div>
      <span class="status-chip">${escapeHtml(item.license || 'review')}</span>
    </div>`;
  }).join('');
  const leaderboardRows = leaderboard.map((item, index) => `<div class="data-row"><span>#${index + 1} ${escapeHtml(item.config_id || 'config')}</span><strong>${Math.round(Number(item.mary_fit || 0) * 100)}%</strong></div>`).join('');
  const modelRoot = ecosystemState.paths?.model_root || 'platform-local Mary model directory';
  const nodeIntelligence = compute.node_intelligence || {};
  const intelligenceNodes = Array.isArray(nodeIntelligence.nodes) ? nodeIntelligence.nodes : [];
  const demonstratedCaps = intelligenceNodes.reduce((total, item) => total + Number(item?.counts?.demonstrated || 0), 0);
  const authorizedCaps = intelligenceNodes.reduce((total, item) => total + Number(item?.counts?.authorized || 0), 0);
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
        <div class="trace-row"><span>Fast language cortex</span><i style="width:42%"></i><strong>cloud / small local</strong></div>
        <div class="trace-row"><span>Thinking / expert</span><i style="width:100%"></i><strong>only when warranted</strong></div>
      </div></div>
      <div class="workspace-panel"><h3>Escalation rule</h3><p>Known represented state can be answered locally. Novel open-ended language escalates to a fast language model. Hard reasoning can visibly enter Thinking. The provider remains replaceable; Mary remains Core-owned.</p><div class="chip-row"><span class="chip">LOCAL STATE</span><span class="chip">RESERVOIR</span><span class="chip">FAST BRAIN</span><span class="chip">MAIN BRAIN</span><span class="chip">EXPERT</span></div></div>
    </div>
    <div class="section-title">ADAPTER LAB · REVIEWED OPTIONAL ASSETS</div>
    <div class="workspace-grid">
      <div class="workspace-panel hero-panel"><h3>Model candidates</h3><p>Weights stay outside Git. This catalog records exact artifacts, compatibility, licenses and hashes so Mac and Windows can pull local muscle without changing Mary.</p><div class="command-list compact-scroll">${candidateRows || '<div class="workspace-empty">No reviewed candidates yet.</div>'}</div></div>
      <div class="workspace-panel"><h3>Mary-fit leaderboard</h3>${leaderboardRows || '<div class="workspace-empty">No adapter evaluations yet. Baselines stay neutral until measured.</div>'}<div class="data-row"><span>Configurations</span><strong>${(adapterLab.configurations || []).length}</strong></div><small>Policy: ${escapeHtml(adapterLab.policy || 'generation influence only')}</small></div>
    </div>
    <div class="workspace-panel model-root-panel"><span>LOCAL MODEL ROOT</span><code>${escapeHtml(modelRoot)}</code><small>Per-machine runtime assets. Never canonical identity or repository state.</small></div>
    <div class="section-title">LEGACY LOCAL MODEL CATALOG</div>
    <div class="workspace-panel"><div class="command-list">${modelRows || '<div class="workspace-empty">No legacy model catalog.</div>'}</div></div>`;
}

function renderMemories() {
  const highlights = dashboardState.memory_highlights || [];
  const archive = dashboardState.memory_archive || {};
  const episodes = archive.episodic || [];
  const facts = archive.semantic || [];
  const shared = archive.shared_history || [];
  const milestones = archive.milestones || [];
  const activities = dashboardState.recent_activities || [];
  const memory = dashboardState.live?.memory || {};
  const counts = archive.counts || {};
  const episodicTotal = Number(counts.episodic_total ?? memory.episodic ?? episodes.length ?? 0);
  const semanticTotal = Number(counts.semantic_total ?? memory.semantic ?? facts.length ?? 0);
  const sharedHistoryTotal = Number(counts.shared_history_total ?? shared.length ?? 0);
  const milestoneTotal = Number(counts.milestones_total ?? milestones.length ?? 0);
  const profileTotal = Number(counts.creator_profile_total ?? dashboardState.relationship?.profile_records ?? 0);
  const observationTotal = Number(counts.relationship_observation_total ?? 0);
  const durableCount = episodicTotal + semanticTotal;
  const continuityCount = sharedHistoryTotal + milestoneTotal + profileTotal + observationTotal;
  const archiveStatus = durableCount || continuityCount
    ? `${durableCount} memory record${durableCount === 1 ? '' : 's'} · ${sharedHistoryTotal} shared-history event${sharedHistoryTotal === 1 ? '' : 's'} · ${profileTotal} creator-profile record${profileTotal === 1 ? '' : 's'}.`
    : 'The current Core has no visible durable memory or shared-history records yet.';

  const episodicRows = listOrEmpty(episodes, (item) => `
    <div class="memory-record">
      <div class="memory-record-head"><span class="memory-source episodic">EPISODIC</span><small>${escapeHtml(item.when || 'recently')}</small></div>
      <strong>${escapeHtml(item.content || 'Memory')}</strong>
      <small>${escapeHtml(titleCase(item.event_type || item.source || 'interaction'))}</small>
    </div>
  `, 'No episodic memories are stored in the current canonical Core memory file.');

  const semanticRows = listOrEmpty(facts, (item) => `
    <div class="memory-record">
      <div class="memory-record-head"><span class="memory-source semantic">KNOWLEDGE</span><small>${escapeHtml(item.when || 'recently')}</small></div>
      <strong>${escapeHtml(item.value || 'Knowledge')}</strong>
      <small>${escapeHtml([item.subject, item.predicate].filter(Boolean).map(titleCase).join(' · ') || 'Semantic memory')}</small>
    </div>
  `, 'No semantic memories have been promoted in the current canonical Core.');

  const sharedRows = listOrEmpty(shared, (item) => `
    <div class="memory-record shared-history">
      <div class="memory-record-head"><span class="memory-source shared">SHARED HISTORY</span><small>${escapeHtml(item.when || 'recently')}</small></div>
      <strong>${escapeHtml(item.description || 'Shared event')}</strong>
      <small>${escapeHtml(titleCase(item.kind || item.type || 'relationship'))}</small>
    </div>
  `, 'No bounded relationship-history entries are available.');

  const milestoneRows = listOrEmpty(milestones, (item) => `
    <div class="memory-record milestone">
      <div class="memory-record-head"><span class="memory-source milestone">MILESTONE</span><small>${escapeHtml(item.when || 'recently')}</small></div>
      <strong>${escapeHtml(item.title || 'Milestone')}</strong>
      ${item.description && item.description !== item.title ? `<small>${escapeHtml(item.description)}</small>` : ''}
    </div>
  `, 'No relationship milestones are available.');

  return `
    <div class="memory-status-banner ${durableCount ? 'has-memory' : continuityCount ? 'has-continuity' : 'empty'}">
      <div><span>CONTINUITY ARCHIVE</span><strong>${escapeHtml(archiveStatus)}</strong></div>
      <small>Memory and relationship history stay separate canonical owners; this screen is a read-only creator view across both.</small>
    </div>

    <div class="workspace-grid three memory-count-grid">
      <div class="workspace-panel memory-count-card"><span>EPISODIC</span><strong>${episodicTotal}</strong><small>Stored experiences</small></div>
      <div class="workspace-panel memory-count-card"><span>SEMANTIC</span><strong>${semanticTotal}</strong><small>Established knowledge</small></div>
      <div class="workspace-panel memory-count-card"><span>CREATOR PROFILE</span><strong>${profileTotal}</strong><small>Source-aware facts, preferences, goals & interests</small></div>
      <div class="workspace-panel memory-count-card"><span>SHARED HISTORY</span><strong>${sharedHistoryTotal}</strong><small>Relationship-owned continuity</small></div>
      <div class="workspace-panel memory-count-card"><span>RELATIONSHIP OBSERVATIONS</span><strong>${observationTotal}</strong><small>Grounded source-aware observations</small></div>
      <div class="workspace-panel memory-count-card"><span>MILESTONES</span><strong>${milestoneTotal}</strong><small>High-significance continuity</small></div>
    </div>

    <div class="section-title">MEMORY HIGHLIGHTS</div>
    <div class="workspace-panel memory-highlight-panel">
      ${listOrEmpty(highlights, (item) => `
        <div class="data-row"><span>${escapeHtml(item.label || 'Memory')}</span><strong>${escapeHtml(item.title || '—')}</strong></div>
      `, 'No structured highlights yet. The archive below still shows any canonical records that exist.')}
    </div>

    <div class="memory-archive-grid">
      <section class="workspace-panel memory-column"><div class="memory-column-title"><h3>Experiences</h3><span>${episodes.length} / ${episodicTotal}</span></div>${episodicRows}</section>
      <section class="workspace-panel memory-column"><div class="memory-column-title"><h3>Knowledge</h3><span>${facts.length} / ${semanticTotal}</span></div>${semanticRows}</section>
    </div>

    <div class="section-title">SHARED CONTINUITY</div>
    <div class="memory-archive-grid">
      <section class="workspace-panel memory-column"><div class="memory-column-title"><h3>Shared history</h3><span>${shared.length} / ${sharedHistoryTotal}</span></div>${sharedRows}</section>
      <section class="workspace-panel memory-column"><div class="memory-column-title"><h3>Milestones</h3><span>${milestones.length} / ${milestoneTotal}</span></div>${milestoneRows}</section>
    </div>

    <div class="workspace-panel memory-policy-panel">
      <h3>What this means</h3>
      <p>${escapeHtml(archive.policy || 'This is a bounded private projection over canonical memory and relationship continuity.')}</p>
      <div class="data-row"><span>Working context</span><strong>${memory.working ?? 0}</strong></div>
      <div class="data-row"><span>Backup recovered</span><strong>${memory.recovered_from_backup ? 'Yes' : 'No'}</strong></div>
      <div class="data-row"><span>Recent activity</span><strong>${activities.length}</strong></div>
      <small>Archive lists are intentionally bounded for readability; the totals above are the canonical Core counts.</small>
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
  const presence = ecosystemState.presence || {};
  const skills = ecosystemState.skills || [];
  const byKey = Object.fromEntries(skills.map((x) => [x.key, x]));
  const stage = dashboardState.performance_context || runtimeStatus.performance_context || {};
  const mode = stage.mode || 'private';
  const modes = ['private','casual','focus','stream','performance'];
  const modeLabels = { private: 'Private', casual: 'Casual', focus: 'Focus', stream: 'Streamer', performance: 'Performance' };
  const runtime = ecosystemState.character_runtime?.realtime || dashboardState.realtime || runtimeStatus.realtime || {};
  const scene = ecosystemState.character_runtime?.live_scene || presence.scene || {};
  const streaming = ecosystemState.streaming || {};
  const streamStats = streaming.stats || {};
  const chat = streaming.chat || {};
  const chatRecent = chat.recent || [];
  const repeated = chat.repeated_phrases || [];
  const fastBrain = streaming.fast_brain || {};
  const speech = runtime.speech_arbiter || {};
  const decisionTrace = runtime.decision_trace || {};
  const decisionRows = (decisionTrace.recent || []).slice(-8).reverse().map((item) => `<div class="scene-event"><span>${escapeHtml(titleCase(item.kind || 'decision'))} · ${escapeHtml(titleCase(item.outcome || 'unknown'))}</span><strong>${escapeHtml(item.reason || '')}</strong></div>`).join('');
  const world = ecosystemState.world_context || {};
  const pulse = ecosystemState.world_pulse || {};
  const dueWorld = pulse.due || [];
  const recentWorld = world.recent || [];
  const sceneEvents = scene.recent_events || [];
  const environment = scene.environment || {};
  const chatRows = chatRecent.slice(-8).reverse().map((item) => `<div class="stream-chat-line ${item.direct_to_mary ? 'direct' : ''}"><strong>${escapeHtml(item.display_name || 'viewer')}</strong><span>${escapeHtml(item.text || '')}</span><small>${escapeHtml(item.platform || 'stream')}</small></div>`).join('');
  const eventRows = sceneEvents.slice(-6).reverse().map((item) => `<div class="scene-event"><span>${escapeHtml(titleCase(item.kind || 'event'))}</span><strong>${escapeHtml(item.summary || '')}</strong></div>`).join('');
  const worldRows = recentWorld.slice(-6).reverse().map((item) => `<div class="world-pulse-row"><span>${escapeHtml(titleCase(item.lane || 'world'))}</span><strong>${escapeHtml(item.topic || '')}</strong><small>${escapeHtml(item.source || '')}</small></div>`).join('');
  const environmentText = Object.entries(environment).slice(0, 6).map(([key, value]) => `${titleCase(key)}: ${value}`).join(' · ');
  return `<div class="presence-status">
    <div class="presence-node ready"><strong>Presence Core</strong><span>${escapeHtml(titleCase(presence.mode || 'companion'))} · initiative + silence</span></div>
    <div class="presence-node ready"><strong>Live Scene</strong><span>${escapeHtml(titleCase(scene.floor_owner || 'none'))} floor · ${escapeHtml(titleCase(scene.realtime_phase || runtime.phase || 'idle'))}</span></div>
    <div class="presence-node ${streamStats.received ? 'ready' : ''}"><strong>Stream Input</strong><span>${streamStats.received ?? 0} seen · ${streamStats.respond_candidates ?? 0} response candidates</span></div>
    <div class="presence-node"><strong>Speech Floor</strong><span>${speech.active ? 'Mary speaking' : 'Open'} · queue ${speech.queue_depth ?? 0}</span></div>
  </div>
  <div class="workspace-grid three" style="margin-top:12px">
    <div class="workspace-panel hero-panel live-scene-panel"><h3>Live Scene</h3><p>This is Mary's short-lived awareness of now—not memory and not identity.</p><div class="data-row"><span>Mode</span><strong>${escapeHtml(titleCase(scene.mode || 'conversation'))}</strong></div><div class="data-row"><span>Activity</span><strong>${escapeHtml(scene.activity || '—')}</strong></div><div class="data-row"><span>Project</span><strong>${escapeHtml(scene.project || '—')}</strong></div><div class="data-row"><span>Target</span><strong>${escapeHtml(scene.mary_target || 'creator')}</strong></div><small>${escapeHtml(environmentText || 'No live environment observation yet.')}</small></div>
    <div class="workspace-panel accent"><h3>Social Stage</h3><p>Choose how the same Mary is presented on this device. Public/streamer modes strengthen privacy boundaries; they do not create another personality.</p><div class="chip-row">${modes.map((x)=>`<button class="chip ${x===mode?'active':''}" data-performance-context="${x}" aria-pressed="${x===mode?'true':'false'}">${escapeHtml(modeLabels[x] || titleCase(x))}</button>`).join('')}</div><div class="data-row"><span>Current mode</span><strong>${escapeHtml(modeLabels[mode] || titleCase(mode))}</strong></div><div class="data-row"><span>Audience</span><strong>${escapeHtml(titleCase(stage.audience||'creator'))}</strong></div><div class="data-row"><span>Privacy</span><strong>${stage.public?'PUBLIC GUARD':'PRIVATE'}</strong></div></div>
    <div class="workspace-panel"><h3>Speech Arbiter</h3><div class="data-row"><span>Active</span><strong>${escapeHtml(speech.active?.target || 'OPEN')}</strong></div><div class="data-row"><span>Queued</span><strong>${speech.queue_depth ?? 0}</strong></div><div class="data-row"><span>Played / dropped</span><strong>${speech.stats?.played ?? 0} / ${speech.stats?.dropped ?? 0}</strong></div><div class="data-row"><span>Interrupts</span><strong>${speech.stats?.interrupts ?? 0}</strong></div><p>One Mary voice owns the floor. Realtime output decides play, queue, drop or interrupt before TTS.</p></div>
  </div>
  <div class="workspace-grid" style="margin-top:12px">
    <div class="workspace-panel"><h3>Stream Attention</h3><div class="data-row"><span>Received</span><strong>${streamStats.received ?? 0}</strong></div><div class="data-row"><span>Ignored</span><strong>${streamStats.ignored ?? 0}</strong></div><div class="data-row"><span>Noticed</span><strong>${streamStats.noticed ?? 0}</strong></div><div class="data-row"><span>Response candidates</span><strong>${streamStats.respond_candidates ?? 0}</strong></div><div class="data-row"><span>Fast brain</span><strong>${escapeHtml(fastBrain.type || 'deterministic')}</strong></div><p>The fast brain can rank interest; deterministic Presence still owns conversational floor and authority.</p></div>
    <div class="workspace-panel stream-chat-panel"><h3>Recent Chat</h3><div class="stream-chat-list">${chatRows || '<div class="workspace-empty">No stream chat ingested yet.</div>'}</div>${repeated.length ? `<small>Repeated: ${escapeHtml(repeated.slice(0,3).map((x)=>Array.isArray(x)?`${x[0]} ×${x[1]}`:String(x)).join(' · '))}</small>` : ''}</div>
  </div>
  <div class="workspace-grid" style="margin-top:12px">
    <div class="workspace-panel"><h3>Scene Event Trail</h3>${eventRows || '<div class="workspace-empty">No current scene events.</div>'}</div>
    <div class="workspace-panel"><h3>Why Mary Did That</h3>${decisionRows || '<div class="workspace-empty">No realtime decisions recorded yet.</div>'}<small>Bounded causal labels only — no raw dialogue, prompts, audio, identity or memory state.</small></div>
  </div>
  <div class="workspace-grid" style="margin-top:12px">
    <div class="workspace-panel"><h3>World Pulse</h3><div class="data-row"><span>Current items</span><strong>${world.count ?? 0}</strong></div><div class="data-row"><span>Refresh lanes due</span><strong>${dueWorld.length}</strong></div>${worldRows || '<div class="workspace-empty compact">No ephemeral world context loaded yet.</div>'}<small>Current culture expires. It never silently becomes Mary canon.</small></div>
  </div>
  <div class="workspace-panel" style="margin-top:12px"><h3>External performer adapters</h3><p>Twitch, OBS and perception are capability inputs around Core. None of them owns Mary, memory or tool authority.</p><div class="chip-row">${['twitch','obs','vision'].map((k)=>`<span class="chip">${byKey[k]?.enabled?'●':'○'} ${escapeHtml(titleCase(k))}</span>`).join('')}</div><div class="data-row"><span>Twitch</span><strong>EventSub → Core chat</strong></div><div class="data-row"><span>OBS</span><strong>WebSocket events → perception</strong></div><button class="primary-small" id="presence-idle-test" style="height:34px;margin-top:8px">Preview an idle behavior</button></div>`;
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

function renderFabric() {
  const f = dashboardState.system_fabric || {};
  const k = f.knowledge || {};
  const w = f.world || {};
  const worldContext = ecosystemState.world_context || {};
  const worldPulse = ecosystemState.world_pulse || {};
  const dueWorld = Array.isArray(worldPulse.due) ? worldPulse.due : [];
  const c = f.continuity || {};
  const skills = c.skills || {};
  const plans = c.plans || {};
  const competence = c.competence || {};
  const models = f.models || {};
  const lab = models.adapter_lab || {};
  const candidates = models.candidates || {};
  const experiments = models.experiments || {};
  const experimentRows = Array.isArray(experiments.records) ? experiments.records : [];
  const readyExperiments = experimentRows.filter((item) => item?.trial_ready);
  if (!modelExperimentTrialState.experimentId && readyExperiments.length) {
    modelExperimentTrialState.experimentId = String(readyExperiments[0].id || '');
  }
  const compute = f.compute || {};
  const nodes = compute.nodes || {};
  const nodeIntelligence = compute.node_intelligence || {};
  const intelligenceNodes = Array.isArray(nodeIntelligence.nodes) ? nodeIntelligence.nodes : [];
  const authorizedCaps = intelligenceNodes.reduce((total, item) => total + Number(item?.counts?.authorized || 0), 0);
  const demonstratedCaps = intelligenceNodes.reduce((total, item) => total + Number(item?.counts?.demonstrated || 0), 0);
  const capabilityContract = compute.capability_contract || {};
  const improvementAgenda = f.improvement_agenda || {};
  const improvementItems = Array.isArray(improvementAgenda.items) ? improvementAgenda.items : [];
  const embodiment = f.embodiment || {};
  const liveScene = embodiment.live_scene || {};
  const knowledgeEvaluation = k.evaluation_readiness || {};
  const integration = f.integration || {};
  const selectedExperiment = experimentRows.find((item) => String(item?.id || '') === modelExperimentTrialState.experimentId) || {};
  const experimentOptions = readyExperiments.map((item) => `<option value="${escapeHtml(item.id || '')}" ${String(item.id || '') === modelExperimentTrialState.experimentId ? 'selected' : ''}>${escapeHtml(item.candidate_id || item.id || 'experiment')} · ${Math.round(Number(item.mary_fit || 0) * 100)}%</option>`).join('');
  const trialResult = modelExperimentTrialState.result
    ? `<div class="workspace-panel" style="margin-top:10px"><div class="data-row"><span>Provider</span><strong>${escapeHtml(modelExperimentTrialState.provider || 'local')}</strong></div><div class="data-row"><span>Model</span><strong>${escapeHtml(modelExperimentTrialState.model || selectedExperiment.model || 'reviewed experiment')}</strong></div><p>${escapeHtml(modelExperimentTrialState.result)}</p><small>Experimental output only · never injected into Mary's production response or memory.</small></div>`
    : '';
  const worldReview = fabricGovernanceState.world || {};
  const contradictions = Array.isArray(worldReview.contradictions) ? worldReview.contradictions : [];
  const reconciliationGroups = Array.isArray(worldReview.reconciliation_queue) ? worldReview.reconciliation_queue : [];
  const skillReview = fabricGovernanceState.skills || {};
  const skillCandidates = Array.isArray(skillReview.candidates) ? skillReview.candidates : [];
  const approvedSkills = Array.isArray(skillReview.approved) ? skillReview.approved : [];
  const revisionQueue = Array.isArray(skillReview.revision_queue) ? skillReview.revision_queue : [];
  const contradictionCards = reconciliationGroups.length
    ? reconciliationGroups.slice(0, 12).map((group) => {
        const candidates = Array.isArray(group.candidates) ? group.candidates : [];
        const options = candidates.map((item) => {
          const value = typeof item.value === 'string' ? item.value : JSON.stringify(item.value);
          return `<div class="workspace-panel" style="margin-top:8px"><p>${escapeHtml(value || '—')}</p><small>${escapeHtml(item.source || 'unknown source')} · ${Math.round(Number(item.confidence || 0) * 100)}% confidence · ${escapeHtml(item.verification || 'unverified')}</small><button class="action-button" data-world-reconcile="${escapeHtml(item.belief_id || '')}" style="margin-top:8px"><strong>Keep this as current</strong><small>Retire competing claims as history</small></button></div>`;
        }).join('');
        return `<div class="workspace-panel" style="margin-top:8px"><div class="data-row"><span>${escapeHtml(group.subject || 'Unknown')}</span><strong>${escapeHtml(group.predicate || 'claim')}</strong></div><small>${Number(group.candidate_count || candidates.length)} competing current claim(s)</small>${options}</div>`;
      }).join('')
    : contradictions.length
      ? contradictions.slice(0, 12).map((item) => {
          const value = typeof item.value === 'string' ? item.value : JSON.stringify(item.value);
          return `<div class="workspace-panel" style="margin-top:8px"><div class="data-row"><span>${escapeHtml(item.subject || 'Unknown')}</span><strong>${escapeHtml(item.predicate || 'claim')}</strong></div><p>${escapeHtml(value || '—')}</p><small>${escapeHtml(item.source || 'unknown source')} · ${Math.round(Number(item.confidence || 0) * 100)}% confidence · ${escapeHtml(item.verification || 'unverified')}</small><button class="action-button" data-world-reconcile="${escapeHtml(item.id || '')}" style="margin-top:8px"><strong>Keep this as current</strong><small>Retire competing claims as history</small></button></div>`;
        }).join('')
      : '<div class="workspace-empty">No contested current beliefs require review.</div>';
  const skillCandidateCards = skillCandidates.length
    ? skillCandidates.slice(0, 12).map((item) => `<div class="workspace-panel" style="margin-top:8px"><div class="data-row"><span>${escapeHtml(item.name || 'Procedure')}</span><strong>v${escapeHtml(item.version || 0)}</strong></div><p>${escapeHtml(item.description || '')}</p><small>${escapeHtml((item.steps || []).join(' → ') || 'No steps supplied')} · ${Math.round(Number(item.confidence || 0) * 100)}% confidence</small><div class="button-row" style="margin-top:8px"><button class="action-button primary" data-skill-approve="${escapeHtml(item.id || '')}"><strong>Approve</strong><small>Guidance only</small></button><button class="action-button" data-skill-reject="${escapeHtml(item.id || '')}"><strong>Reject</strong><small>Keep current procedure unchanged</small></button></div></div>`).join('')
    : '<div class="workspace-empty">No procedure candidates are waiting for review.</div>';
  const revisionPressure = revisionQueue.length
    ? `<div class="workspace-panel" style="margin-top:10px"><h4>Revision pressure</h4>${revisionQueue.slice(0, 8).map((item) => `<div class="data-row"><span>${escapeHtml(item.name || 'Procedure')} · v${escapeHtml(item.version || 0)}</span><strong>${Math.round(Number(item.failure_rate || 0) * 100)}% failure</strong></div>`).join('')}<small>Evidence only · no approved procedure was changed automatically.</small></div>`
    : '';
  const approvedSkillCards = approvedSkills.length
    ? approvedSkills.slice(0, 8).map((item) => `<div class="data-row"><span>${escapeHtml(item.name || 'Procedure')} · v${escapeHtml(item.version || 0)}</span><button class="action-button" data-skill-revise="${escapeHtml(item.id || '')}"><strong>Propose revision</strong></button></div>`).join('')
    : '<div class="workspace-empty">No approved reusable procedures yet.</div>';
  const improvementCards = improvementItems.length
    ? improvementItems.slice(0, 10).map((item) => `<div class="workspace-panel" style="margin-top:8px"><div class="data-row"><span>${escapeHtml(titleCase(item.kind || 'evidence'))} · ${escapeHtml(item.subject || 'unknown')}</span><strong>${escapeHtml(titleCase(item.attention || item.state || 'review'))}</strong></div><small>${escapeHtml((item.evidence_needed || []).join(' · ') || 'No additional evidence described')}</small></div>`).join('')
    : '<div class="workspace-empty">No current evidence gaps require attention.</div>';
  return `
    <div class="workspace-grid three">
      <div class="workspace-panel accent"><h3>One Mary Core</h3><div class="data-row"><span>Architecture</span><strong>${integration.healthy ? 'Connected' : 'Degraded'}</strong></div><div class="data-row"><span>Operational</span><strong>${integration.operational ? 'Yes' : 'No'}</strong></div><div class="data-row"><span>Connected nodes</span><strong>${nodes.connected ?? nodes.connected_nodes ?? 0}</strong></div><div class="data-row"><span>Authorized node capabilities</span><strong>${authorizedCaps}</strong></div><div class="data-row"><span>Demonstrated capabilities</span><strong>${demonstratedCaps}</strong></div><p>Nodes are replaceable workers. Advertisement, readiness, permission, and demonstrated competence are separate evidence states.</p></div>
      <div class="workspace-panel"><h3>Knowledge + World</h3><div class="data-row"><span>Enabled packs</span><strong>${k.enabled ?? 0}/${k.packs ?? 0}</strong></div><div class="data-row"><span>Indexed chunks</span><strong>${k.indexed_documents ?? 0}</strong></div><div class="data-row"><span>Knowledge tiers</span><strong>${k.substrate?.counts?.active_local ?? 0}/${k.substrate?.counts?.offline_reference ?? 0}/${k.substrate?.counts?.semantic_derivative ?? 0}</strong></div><div class="data-row"><span>Knowledge attention</span><strong>${k.substrate?.attention_required ? "Review" : "Clear"}</strong></div><div class="data-row"><span>Stale local indexes</span><strong>${(k.substrate?.stale_local_indexes || []).length}</strong></div><div class="data-row"><span>Stale semantic derivatives</span><strong>${(k.substrate?.stale_derivatives || []).length}</strong></div><div class="data-row"><span>External context</span><strong>${worldContext.count ?? 0}</strong></div><div class="data-row"><span>Refresh lanes due</span><strong>${dueWorld.length}</strong></div><div class="data-row"><span>Current beliefs</span><strong>${w.beliefs?.current_beliefs ?? 0}</strong></div><div class="data-row"><span>Reconciliation groups</span><strong>${w.review?.reconciliation_groups ?? w.beliefs?.reconciliation_groups ?? 0}</strong></div><div class="data-row"><span>Temporal relations</span><strong>${w.temporal?.relations ?? 0}</strong></div><p>World Pulse plans refreshes only. Retrieved material stays evidence, and superseded history never becomes current truth.</p></div>
      <div class="workspace-panel"><h3>Procedures + Models</h3><div class="data-row"><span>Approved skills</span><strong>${skills.approved ?? 0}</strong></div><div class="data-row"><span>Procedure review pressure</span><strong>${c.procedure_review?.revision_attention ?? skills.revision_attention ?? 0}</strong></div><div class="data-row"><span>Active plans</span><strong>${plans.active_plans ?? 0}</strong></div><div class="data-row"><span>Competence evidence</span><strong>${competence.records ?? 0}</strong></div><div class="data-row"><span>Model candidates</span><strong>${candidates.count ?? 0}</strong></div><div class="data-row"><span>Trial-ready experiments</span><strong>${experiments.trial_ready ?? 0}</strong></div><div class="data-row"><span>Recorded trial outcomes</span><strong>${experiments.trial_outcomes ?? 0}</strong></div><div class="data-row"><span>Completed bounded trials</span><strong>${experiments.completed_trials ?? 0}</strong></div><div class="data-row"><span>Experiment lineage events</span><strong>${experiments.event_count ?? 0}</strong></div><div class="data-row"><span>Adapter configs</span><strong>${(lab.configurations || []).length}</strong></div><p>Skills require creator approval. Benchmarks and competence cannot grant permission or auto-promote a model.</p></div>
    </div>
    <div class="workspace-grid two" style="margin-top:12px">
      <div class="workspace-panel"><h3>Evidence Improvement Agenda</h3><div class="data-row"><span>Open evidence items</span><strong>${improvementAgenda.open_items ?? 0}</strong></div><div class="data-row"><span>Recovery items</span><strong>${improvementAgenda.recovery_items ?? 0}</strong></div><div class="data-row"><span>Evidence gaps</span><strong>${capabilityContract.evidence_gaps ?? 0}</strong></div><div class="data-row"><span>Knowledge regression</span><strong>${knowledgeEvaluation.ready_for_regression ? 'Ready' : 'Needs evidence'}</strong></div><p>Mary can see what evidence would improve a capability or procedure, but this agenda cannot grant permission, run work, or promote a model.</p>${improvementCards}</div>
      <div class="workspace-panel"><h3>Embodiment + Live Presence</h3><div class="data-row"><span>Acting score</span><strong>${escapeHtml(embodiment.canonical_score || 'PerformancePacket')}</strong></div><div class="data-row"><span>Scene mode</span><strong>${escapeHtml(titleCase(liveScene.mode || 'companion'))}</strong></div><div class="data-row"><span>Realtime phase</span><strong>${escapeHtml(titleCase(liveScene.realtime_phase || 'idle'))}</strong></div><div class="data-row"><span>Floor owner</span><strong>${escapeHtml(titleCase(liveScene.floor_owner || 'none'))}</strong></div><div class="data-row"><span>Scene participants</span><strong>${liveScene.participant_count ?? 0}</strong></div><div class="data-row"><span>Desktop body</span><strong>${embodiment.surfaces?.desktop?.semantic_motion ? 'Performance-linked' : 'Degraded-safe'}</strong></div><div class="data-row"><span>iPhone body</span><strong>${embodiment.surfaces?.ios_native?.head_motion ? 'Performance-linked' : 'Degraded-safe'}</strong></div><p>LiveScene is ephemeral. Bodies render the same Mary Core performance and never become identity, memory, emotion, or world-state owners.</p></div>
    </div>
    <div class="workspace-panel" style="margin-top:12px">
      <h3>Explicit Model Trial</h3>
      <p>Run one already-reviewed, benchmarked experiment on the exact authorized local experiment node. The output stays in the lab and cannot replace Mary's production route.</p>
      <label class="field-label"><span>TRIAL-READY EXPERIMENT</span><select id="model-exp-select" ${readyExperiments.length ? '' : 'disabled'}>${experimentOptions || '<option>No trial-ready experiment</option>'}</select></label>
      <label class="field-label"><span>HELD-OUT PROMPT</span><textarea id="model-exp-prompt" rows="3" ${readyExperiments.length ? '' : 'disabled'}>${escapeHtml(modelExperimentTrialState.prompt)}</textarea></label>
      <button class="action-button primary" id="model-exp-run" ${readyExperiments.length && !modelExperimentTrialState.busy ? '' : 'disabled'}><strong>${modelExperimentTrialState.busy ? 'Experiment running…' : 'Run bounded trial'}</strong><small>Exact lineage + benchmark + node permission required</small></button>
      <p id="model-exp-status"><small>${escapeHtml(modelExperimentTrialState.status || (readyExperiments.length ? 'Ready for an explicit trial.' : 'No reviewed experiment currently satisfies the trial gate.'))}</small></p>
      ${trialResult}
    </div>
    <div class="workspace-grid two" style="margin-top:12px">
      <div class="workspace-panel"><h3>World Reconciliation</h3><p>Choose only when competing current evidence should be resolved. The other claims are retired as history, not erased.</p>${fabricGovernanceState.loading ? '<div class="workspace-empty">Loading bounded world evidence…</div>' : contradictionCards}</div>
      <div class="workspace-panel"><h3>Procedure Review</h3><p>Approve or reject learned procedure candidates. Approval never grants tool or node permission.</p>${fabricGovernanceState.loading ? '<div class="workspace-empty">Loading governed skills…</div>' : skillCandidateCards}${revisionPressure}<h4 style="margin-top:14px">Approved procedures</h4>${approvedSkillCards}</div>
    </div>`;
}

function presenceFlowMarkup() {
  return `
    <div class="section-title">LIVE PRESENCE FLOW</div>
    <div class="workspace-panel presence-flow-panel">
      <div class="presence-flow-head">
        <div><h3>Mary nervous system</h3><p>White is available structure. Yellow is the active presentation path for the current turn. This view is ephemeral telemetry only.</p></div>
        <div class="presence-flow-legend"><span><i></i> structure</span><span><i class="live"></i> active flow</span></div>
      </div>
      <svg id="presence-flow" viewBox="0 0 920 430" role="img" aria-label="Live Mary identity, agency, embodiment and presence flow">
        <path class="pf-wire" data-flow="core-identity" d="M460 63 C360 75 260 86 205 118"/>
        <path class="pf-wire" data-flow="core-agency" d="M460 63 L460 118"/>
        <path class="pf-wire" data-flow="core-embodiment" d="M460 63 C560 75 660 86 715 118"/>
        <path class="pf-wire" data-flow="identity-agency" d="M325 164 L375 164"/>
        <path class="pf-wire" data-flow="agency-embodiment" d="M545 164 L595 164"/>
        <path class="pf-wire" data-flow="identity-presence" d="M205 205 C250 270 340 278 460 300"/>
        <path class="pf-wire" data-flow="agency-presence" d="M460 205 L460 300"/>
        <path class="pf-wire" data-flow="embodiment-presence" d="M715 205 C670 270 580 278 460 300"/>
        <path class="pf-wire" data-flow="presence-desktop" d="M460 350 L460 386"/>

        <g class="pf-node pf-core active" data-node="core">
          <circle cx="460" cy="42" r="34"/>
          <text class="pf-title" x="460" y="48" text-anchor="middle">MARY</text>
        </g>
        <g class="pf-node" data-node="identity">
          <rect x="85" y="118" width="240" height="87" rx="16"/>
          <text class="pf-title" x="205" y="147" text-anchor="middle">Identity</text>
          <text class="pf-sub" x="205" y="171" text-anchor="middle">memory · self-model · world · relationship</text>
          <text class="pf-sub" x="205" y="188" text-anchor="middle">knowledge</text>
        </g>
        <g class="pf-node" data-node="agency">
          <rect x="340" y="118" width="240" height="87" rx="16"/>
          <text class="pf-title" x="460" y="147" text-anchor="middle">Agency</text>
          <text class="pf-sub" x="460" y="171" text-anchor="middle">planning · tools · procedures</text>
          <text class="pf-sub" x="460" y="188" text-anchor="middle">autonomy · streaming</text>
        </g>
        <g class="pf-node" data-node="embodiment">
          <rect x="595" y="118" width="240" height="87" rx="16"/>
          <text class="pf-title" x="715" y="147" text-anchor="middle">Embodiment</text>
          <text class="pf-sub" x="715" y="171" text-anchor="middle">avatar · expression · animation</text>
          <text class="pf-sub" x="715" y="188" text-anchor="middle">gaze · voice</text>
        </g>
        <g class="pf-node" data-node="presence">
          <rect x="350" y="300" width="220" height="52" rx="16"/>
          <text class="pf-title" x="460" y="332" text-anchor="middle">Presence</text>
        </g>
        <g class="pf-node" data-node="desktop">
          <rect x="365" y="386" width="190" height="38" rx="14"/>
          <text class="pf-title" x="460" y="411" text-anchor="middle">Desktop</text>
        </g>
      </svg>
    </div>`;
}

function syncPresenceFlow() {
  const root = $('#presence-flow');
  if (!root) return;
  const thinking = ['transcribing', 'thinking', 'responding'].includes(conversationState);
  const listening = conversationState === 'listening';
  const speaking = conversationState === 'speaking' || Boolean(activeSpeechAudio);
  const directed = Boolean(currentPerformancePacket && Object.keys(currentPerformancePacket).length);
  const agencyActive = thinking || directed;
  const embodimentActive = listening || speaking || directed;
  const presenceActive = conversationState !== 'idle' || directed;

  const setNode = (name, active) => root.querySelector(`[data-node="${name}"]`)?.classList.toggle('active', Boolean(active));
  const setWire = (name, active) => root.querySelector(`[data-flow="${name}"]`)?.classList.toggle('active', Boolean(active));

  setNode('identity', true);
  setNode('agency', agencyActive);
  setNode('embodiment', embodimentActive);
  setNode('presence', presenceActive);
  setNode('desktop', true);

  setWire('core-identity', true);
  setWire('core-agency', agencyActive);
  setWire('core-embodiment', embodimentActive);
  setWire('identity-agency', agencyActive);
  setWire('agency-embodiment', directed || speaking);
  setWire('identity-presence', presenceActive);
  setWire('agency-presence', agencyActive);
  setWire('embodiment-presence', embodimentActive);
  setWire('presence-desktop', presenceActive || conversationState === 'idle');
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
  const fabric = dashboardState.compute_fabric || {};
  const routing = fabric.routing || {};
  const routeTable = routing.routes || {};
  const conversationRoute = Array.isArray(routeTable.conversation) ? routeTable.conversation : [];
  const generalRoute = Array.isArray(routeTable.general) ? routeTable.general : [];
  const capabilityRoutes = fabric.capability_routes || {};
  const localRoute = capabilityRoutes['llm.local'] || {};
  const modelExecution = fabric.model_execution || {};
  const activeCandidates = modelExecution.active_candidates || [];
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
  return `${presenceFlowMarkup()}<div class="trace-hero">
    <div class="workspace-panel hero-panel"><h3>Last Turn Trace</h3><p>Measured from the real runtime: provider, cognition, reflection, speech, and perceived response timing. This telemetry is ephemeral and never becomes Mary memory.</p>
      <div class="trace-stack">${timeline.length ? timeline.map(([label,value]) => `<div class="trace-row"><span>${escapeHtml(label)}</span><i style="width:${Math.max(2,(value/max)*100)}%"></i><strong>${escapeHtml(formatMilliseconds(value))}</strong></div>`).join('') : '<div class="workspace-empty">Complete one desktop turn to populate the trace.</div>'}</div>
    </div>
    <div class="workspace-panel accent"><h3>Route</h3><div class="data-row"><span>Provider</span><strong>${escapeHtml(trace.provider || '—')}</strong></div><div class="data-row"><span>Model</span><strong>${escapeHtml(trace.model || '—')}</strong></div><div class="data-row"><span>Purpose</span><strong>${escapeHtml(trace.generation_purpose || '—')}</strong></div><div class="data-row"><span>Routing role</span><strong>${escapeHtml(trace.routing_purpose || trace.generation_purpose || '—')}</strong></div><div class="data-row"><span>Lane</span><strong>${escapeHtml(titleCase(trace.conversation_lane || '—'))}</strong></div><div class="data-row"><span>Response class</span><strong>${escapeHtml(titleCase(trace.response_class || trace.local_mind?.response_class || '—'))}</strong></div><div class="data-row"><span>Engine</span><strong>${escapeHtml(trace.response_engine || trace.local_mind?.response_engine || '—')}</strong></div><div class="data-row"><span>Escalation</span><strong>${escapeHtml(trace.escalation_reason || trace.local_mind?.escalation_reason || '—')}</strong></div><div class="data-row"><span>Shadow</span><strong>${trace.local_mind?.shadow_enabled ? 'ON' : 'OFF'}</strong></div><div class="data-row"><span>Shadow latency</span><strong>${escapeHtml(formatMilliseconds(timings.shadow_ms))}</strong></div><div class="data-row"><span>Classification</span><strong>${escapeHtml(formatMilliseconds(timings.classification_ms))}</strong></div><div class="data-row"><span>Local composer</span><strong>${escapeHtml(formatMilliseconds(timings.local_composer_ms))}</strong></div><div class="data-row"><span>Local audit</span><strong>${escapeHtml(formatMilliseconds(timings.local_audit_ms))}</strong></div><div class="data-row"><span>Reflection</span><strong>${escapeHtml(trace.reflection_mode || '—')}</strong></div><div class="data-row"><span>Voice delivery</span><strong>${escapeHtml(titleCase(trace.delivery_plan?.profile || '—'))}</strong></div><div class="data-row"><span>Local act</span><strong>${escapeHtml(titleCase(trace.local_mind?.plan?.act || '—'))}</strong></div><p>${escapeHtml(providerAttemptSummary(trace))}</p></div>
  </div>
  <div class="section-title">MODEL & COMPUTE FABRIC</div>
  <div class="workspace-grid three">
    <div class="workspace-panel accent"><h3>Conversation Route</h3>
      <div class="data-row"><span>Preferred</span><strong>${escapeHtml(providerDisplayName(conversationRoute[0] || routing.last_generation?.selected_provider || 'automatic'))}</strong></div>
      <div class="data-row"><span>Route</span><strong>${escapeHtml(conversationRoute.map(providerDisplayName).join(' → ') || 'automatic')}</strong></div>
      <div class="data-row"><span>Last provider</span><strong>${escapeHtml(providerDisplayName(trace.provider || routing.last_generation?.selected_provider || '—'))}</strong></div>
      <p>Ordinary conversation can prefer local compute without moving identity, memory, or relationship state out of Mary Core.</p>
    </div>
    <div class="workspace-panel"><h3>Local Compute</h3>
      <div class="data-row"><span>Ready</span><strong>${localRoute.available ? 'YES' : 'FALLBACK'}</strong></div>
      <div class="data-row"><span>Selected node</span><strong>${escapeHtml(localRoute.selected_node_id || '—')}</strong></div>
      <div class="data-row"><span>Engine</span><strong>${escapeHtml(titleCase(localRoute.selected_runtime || '—'))}</strong></div>
      <div class="data-row"><span>Model</span><strong>${escapeHtml(localRoute.selected_model || '—')}</strong></div>
      <div class="data-row"><span>Execution</span><strong class="compute-state ${localRoute.execution === 'authorized' ? 'authorized' : localRoute.available ? 'permission-required' : 'offline'}">${escapeHtml(titleCase(localRoute.execution || 'permission required'))}</strong></div>
      <div class="compute-permission">
        <button id="local-compute-toggle" data-enable-local-compute="${localRoute.execution === 'authorized' ? 'false' : 'true'}" ${localRoute.available ? '' : 'disabled'}>${localRoute.execution === 'authorized' ? 'Disable local compute on this PC' : 'Enable local compute on this PC'}</button>
        <small>${localRoute.available
          ? (localRoute.execution === 'authorized'
            ? 'This device may execute bounded llm.local tasks. Core still owns Mary and cloud remains fallback.'
            : 'The runtime is ready, but device execution is intentionally permission-gated until you enable it.')
          : 'Start or install an approved local runtime first. Mary will keep using cloud fallback meanwhile.'}</small>
        <small>Supported local runtime families: LM Studio, Ollama, llama.cpp. They are optional; cloud conversation remains available.</small>
      </div>
    </div>
    <div class="workspace-panel"><h3>Execution Portfolio</h3>
      <div class="data-row"><span>Candidates</span><strong>${activeCandidates.length}</strong></div>
      <div class="data-row"><span>Task route</span><strong>${escapeHtml(generalRoute.map(providerDisplayName).join(' → ') || 'automatic')}</strong></div>
      <div class="data-row"><span>Fabric revision</span><strong>${escapeHtml(modelExecution.integration_revision || modelExecution.version || '—')}</strong></div>
      <p>Suitability, provider health, quota and resource evidence guide execution without becoming Mary state.</p>
    </div>
  </div>
  <div class="section-title">REALTIME COGNITIVE INFRASTRUCTURE</div>
  <div class="workspace-grid three">
    <div class="workspace-panel accent"><h3>Interaction</h3><div class="data-row"><span>Phase</span><strong>${escapeHtml(titleCase(realtime.phase || 'idle'))}</strong></div><div class="data-row"><span>Anti-echo</span><strong>${realtime.anti_echo === false ? 'OFF' : 'ON'}</strong></div><div class="data-row"><span>Interruptions</span><strong>${realtimeStats.interruptions ?? 0}</strong></div><div class="data-row"><span>Echo suppressions</span><strong>${realtimeStats.suppressed_echo_inputs ?? 0}</strong></div><p>One shared lifecycle coordinates text, speech, interruption and future streaming clients without owning character state.</p></div>
    <div class="workspace-panel"><h3>Attention Bus</h3><div class="data-row"><span>Pending</span><strong>${attention.pending ?? 0}</strong></div><div class="data-row"><span>Published / claimed</span><strong>${attention.published ?? 0} / ${attention.claimed ?? 0}</strong></div><div class="data-row"><span>Dropped</span><strong>${attention.dropped ?? 0}</strong></div><div class="data-row"><span>Next</span><strong>${escapeHtml(titleCase(nextAttention.source || 'none'))}</strong></div><p>Urgency controls what Mary should consider first; provenance and truth remain separate.</p></div>
    <div class="workspace-panel"><h3>Perception Boundary</h3><div class="data-row"><span>Recent observations</span><strong>${(perception.recent || []).length}</strong></div><p>Perception providers describe objective observations. Mary interprets them through her own represented state; raw media is not stored here.</p></div>
  </div>
  <div class="workspace-grid">
    <div class="workspace-panel"><h3>Hybrid Memory Retrieval</h3><div class="data-row"><span>Mode</span><strong>${escapeHtml(retrieval.mode || 'auto')}</strong></div><div class="data-row"><span>Embedding model</span><strong>${escapeHtml(retrieval.embedding_model || '—')}</strong></div><div class="data-row"><span>Vector index</span><strong>${Number(vectorIndex.records ?? vectorIndex.count ?? vectorIndex.vectors ?? 0) > 0 ? `${Number(vectorIndex.records ?? vectorIndex.count ?? vectorIndex.vectors ?? 0)} ready` : 'Not built'}</strong></div><div class="data-row"><span>Last query used vectors</span><strong>${retrieval.last_query_used_vectors ? 'YES' : 'NO'}</strong></div><p>${Number(vectorIndex.records ?? vectorIndex.count ?? vectorIndex.vectors ?? 0) > 0 ? 'Semantic vectors are available as a candidate-retrieval layer.' : 'Structured and lexical recall remain active; vectors are an optional derived index.'} Canonical memory/provenance still decides what is true.</p></div>
    <div class="workspace-panel"><h3>Compute Nodes</h3>${nodeItems.length ? nodeItems.map((node) => `<div class="data-row"><span>${escapeHtml(node.node_id || 'node')}</span><strong>${node.connected ? 'ONLINE' : 'OFFLINE'}</strong></div><small>${escapeHtml(Object.entries(node.capabilities || {}).filter(([,info]) => info?.available).map(([name]) => name).slice(0,8).join(' · ') || 'No active capabilities')}</small>`).join('') : '<div class="workspace-empty">No external compute connected. Mary continues on the Core provider route.</div>'}<p>Capability nodes are replaceable workers only; identity, memory, relationship state and permissions remain Core-owned.</p></div>
  </div>
  <div class="workspace-panel"><h3>Mary Evaluation Set</h3><div class="data-row"><span>Explicit ratings</span><strong>${feedback.records ?? 0}</strong></div><div class="data-row"><span>Positive / negative</span><strong>${feedback.ratings?.positive ?? 0} / ${feedback.ratings?.negative ?? 0}</strong></div><p>Only explicit creator feedback belongs here. It is private future evaluation/training data and never character-state authority.</p></div>
  <div class="section-title">ROLLING METRICS</div>
  <div class="workspace-panel"><div class="metric-grid">${rows.length ? rows.map(([k,v])=>`<div class="metric-card"><span>${escapeHtml(titleCase(k))}</span><strong>${escapeHtml(v.last_ms)} ms</strong><small>avg ${escapeHtml(v.avg_ms)} · max ${escapeHtml(v.max_ms)}</small></div>`).join('') : '<div class="workspace-empty">Metrics appear after live turns.</div>'}</div></div>`;
}

function renderGallery() {
  const lab = creatorLabState;
  return `
    <div class="workspace-grid two">
      <div class="workspace-panel accent">
        <h3>Creator Lab</h3>
        <p>Pick an image explicitly, let an authorized vision node ground what Mary sees, then have canonical Mary author a reviewable draft in her own voice.</p>
        <div class="action-grid">
          <button class="action-button" id="creator-lab-choose"><strong>${lab.previewDataUrl ? 'Change image' : 'Choose image'}</strong><small>Local selection · normalized before vision dispatch</small></button>
          <button class="action-button" id="creator-lab-look" ${lab.previewDataUrl && !lab.busy ? '' : 'disabled'}><strong>Let Mary look</strong><small>Ephemeral pixels → typed vision capability → grounded evidence</small></button>
        </div>
        ${lab.previewDataUrl ? `<img src="${escapeHtml(lab.previewDataUrl)}" alt="Selected Creator Lab image" style="width:100%;max-height:340px;object-fit:contain;border-radius:12px;margin-top:12px;background:rgba(255,255,255,.03)">` : ''}
        <label class="field-label"><span>WHAT MARY SEES · EDITABLE</span><textarea id="creator-lab-description" rows="5" placeholder="Grounded visual evidence appears here…">${escapeHtml(lab.description)}</textarea></label>
        <label class="field-label"><span>WHAT SHOULD MARY DO WITH IT?</span><textarea id="creator-lab-intent" rows="3">Tell me what you'd say about this in your own voice.</textarea></label>
        <label class="field-label"><span>TONE</span><input id="creator-lab-tone" value="natural"></label>
        <button class="action-button primary" id="creator-lab-create" ${lab.busy ? 'disabled' : ''}><strong>${lab.busy ? 'Mary is creating…' : 'Create with Mary'}</strong><small>Draft only · nothing publishes automatically</small></button>
      </div>
      <div class="workspace-panel">
        <h3>Mary's Draft</h3>
        <p id="creator-lab-draft">${escapeHtml(lab.draft || 'Mary’s draft will appear here after grounded creation.')}</p>
        <button class="action-button" id="creator-lab-speak" ${lab.draft && !lab.busy ? '' : 'disabled'}><strong>Hear Mary say it</strong><small>Uses the configured Mary voice route</small></button>
        <div class="data-row"><span>Core media retention</span><strong>Metadata + description only</strong></div>
        <small>Raw pixels are ephemeral task input. Vision evidence does not become memory or canon automatically.</small>
      </div>
      <div class="workspace-panel"><h3>Reference Sheet</h3><img src="./assets/gallery/mary-neon-reference-sheet.png" style="width:100%;height:240px;object-fit:cover;object-position:center;border-radius:10px;opacity:.92" alt="Mary neon reference sheet" /><small>Bundled visual reference for Mary's current design language.</small></div>
      <div class="workspace-panel"><h3>Neon Night Study</h3><img src="./assets/gallery/mary-neon-night-manga.png" style="width:100%;height:240px;object-fit:cover;object-position:center;border-radius:10px;opacity:.92" alt="Mary neon night manga study" /><small>Library visual study preserving Mary's beanie/jacket/skirt palette.</small></div>
      <div class="workspace-panel"><h3>Stream Room Study</h3><img src="./assets/gallery/mary-stream-room-reference.png" style="width:100%;height:240px;object-fit:cover;object-position:center;border-radius:10px;opacity:.92" alt="Mary stream room visual study" /><small>Library visual study for the streamer/companion environment.</small></div>
      <div class="workspace-panel"><h3>VRM</h3><p>MaryCosma.vrm is connected to the live stage and remains the preferred interactive avatar.</p><div class="data-row"><span>Model</span><strong>MaryCosma.vrm</strong></div><div class="data-row"><span>Renderer</span><strong>Three.js + three-vrm</strong></div></div>
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
  const resident = runtimeStatus.resident_hearing || residentHearingState || {};
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
        <div class="data-row"><span>Resident Hearing</span><strong>${resident.enabled ? `ON · ${escapeHtml(titleCase(resident.state || 'listening'))}` : 'OFF · default'}</strong></div>
        <div class="data-row"><span>Input device</span><strong>${escapeHtml(resident.input_device || 'OS default microphone')}</strong></div>
        <button class="action-button" id="resident-hearing-toggle"><strong>${resident.enabled ? 'Turn Resident Hearing Off' : 'Turn Resident Hearing On'}</strong><small>${resident.enabled ? 'Continuous local VAD is armed; raw audio stays on this Mac.' : 'Opt-in for streaming or hands-free use. Push-to-talk remains available separately.'}</small></button>
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
      <div class="workspace-panel"><h3>Audio readiness</h3><div class="data-row"><span>Payload → canplay</span><strong>${decodeMs === null ? '—' : escapeHtml(formatMilliseconds(decodeMs))}</strong></div><p>Desktop playback prefers a bounded local file URL instead of moving a large base64 audio blob through the UI bridge.</p></div>
      <div class="workspace-panel"><h3>Browser start</h3><div class="data-row"><span>Canplay → speaking</span><strong>${schedulerMs === null ? '—' : escapeHtml(formatMilliseconds(schedulerMs))}</strong></div><p>Lip-sync graph setup now waits until playback has actually started.</p></div>
    </div>
    <div class="section-title">AVATAR PRESENTATION</div>
    <div class="workspace-panel">
      <div class="presentation-mode-row">
        <button class="action-button ${avatarPresentation === 'live' ? 'active' : ''}" data-avatar-presentation="live"><strong>Live 3D</strong><small>MaryCosma VRM · expressions + lip sync</small></button>
        <button class="action-button ${avatarPresentation === 'art' ? 'active' : ''}" data-avatar-presentation="art"><strong>Portrait Art</strong><small>Local Mary artwork · zero renderer dependency</small></button>
      </div>
      <div class="avatar-runtime-note">
        <strong>${currentVrm ? 'Live VRM ready' : 'Live VRM is in fallback mode'}</strong><br/>
        ${escapeHtml(currentVrm ? 'Three.js + VRM renderer is active.' : (avatarLoadError || 'The renderer or model is not ready yet. Mary remains fully usable with portrait art.'))}
        <br/><span>${motionManifestStatus.loaded ? `VRMA runtime · ${motionManifestStatus.count} local motion asset${motionManifestStatus.count === 1 ? '' : 's'}` : `VRMA manifest unavailable${motionManifestStatus.error ? ` · ${escapeHtml(motionManifestStatus.error)}` : ''}`}</span>
        ${vrmaFailedMotions.size ? `<br/><span>${vrmaFailedMotions.size} VRMA asset${vrmaFailedMotions.size === 1 ? '' : 's'} failed this session · procedural fallback active</span>` : ''}
        ${currentVrm ? '' : '<br/><button class="ghost-button" id="avatar-retry" style="margin-top:8px">Retry live VRM</button>'}
      </div>
      <div class="section-title" style="margin-top:14px">CAMERA</div>
      <div class="action-grid"><button class="action-button" data-avatar-frame="full"><strong>Full</strong><small>Whole-character framing</small></button><button class="action-button" data-avatar-frame="portrait"><strong>Portrait</strong><small>Default companion framing</small></button><button class="action-button" data-avatar-frame="close"><strong>Close</strong><small>Face / upper body</small></button></div>
      <label class="form-field" style="margin-top:10px"><span>Orbit · <b id="stage-yaw-value">${Math.round(stageCameraYaw)}°</b></span><input id="stage-camera-yaw" type="range" min="-45" max="45" step="1" value="${stageCameraYaw}"></label>
      <label class="form-field"><span>Elevation · <b id="stage-elevation-value">${stageCameraElevation.toFixed(2)}</b></span><input id="stage-camera-elevation" type="range" min="-0.3" max="0.3" step="0.01" value="${stageCameraElevation}"></label>
    </div>
    <div class="section-title">CHARACTER STUDIO</div>
    <div class="workspace-grid">
      <div class="workspace-panel">
        <h3>Performance preview</h3>
        <p>Preview presentation locally without changing Mary's canonical emotion, memory, identity, or relationship state.</p>
        <div class="action-grid">
          <button class="action-button" data-stage-expression="neutral"><strong>Neutral</strong><small>Relaxed face</small></button>
          <button class="action-button" data-stage-expression="happy"><strong>Happy</strong><small>Warm expression</small></button>
          <button class="action-button" data-stage-expression="surprised"><strong>Surprised</strong><small>Reactive expression</small></button>
          <button class="action-button" data-stage-expression="angry"><strong>Firm</strong><small>Stronger expression</small></button>
        </div>
        <div class="section-title" style="margin-top:12px">POSE / MOTION SLOT</div>
        <div class="action-grid">
          <button class="action-button" data-stage-motion="talk_neutral"><strong>Talk</strong><small>Neutral semantic pose</small></button>
          <button class="action-button" data-stage-motion="warm_acknowledge"><strong>Warm</strong><small>Acknowledgement pose</small></button>
          <button class="action-button" data-stage-motion="teasing_point"><strong>Tease</strong><small>Playful point pose</small></button>
          <button class="action-button" data-stage-motion="thinking_pause"><strong>Think</strong><small>Thinking pose</small></button>
          <button class="action-button" data-stage-motion=""><strong>Reset pose</strong><small>Return to ambient body state</small></button>
        </div>
      </div>
      <div class="workspace-panel">
        <h3>Lighting sandbox</h3>
        <p>Renderer-only lighting. Values are local presentation settings and never become Mary state.</p>
        <label class="form-field"><span>Key · <b id="stage-key-value">${stageLighting.key.toFixed(2)}</b></span><input id="stage-key-light" type="range" min="0" max="5" step="0.05" value="${stageLighting.key}"></label>
        <label class="form-field"><span>Fill · <b id="stage-fill-value">${stageLighting.fill.toFixed(2)}</b></span><input id="stage-fill-light" type="range" min="0" max="5" step="0.05" value="${stageLighting.fill}"></label>
        <label class="form-field"><span>Rim · <b id="stage-rim-value">${stageLighting.rim.toFixed(2)}</b></span><input id="stage-rim-light" type="range" min="0" max="5" step="0.05" value="${stageLighting.rim}"></label>
        <div class="action-grid" style="margin-top:10px">
          <button class="action-button" data-stage-lighting="balanced"><strong>Balanced</strong><small>Default companion light</small></button>
          <button class="action-button" data-stage-lighting="soft"><strong>Soft</strong><small>Gentle portrait light</small></button>
          <button class="action-button" data-stage-lighting="neon"><strong>Neon</strong><small>More fill and rim</small></button>
          <button class="action-button" data-stage-lighting="dramatic"><strong>Dramatic</strong><small>High contrast stage light</small></button>
        </div>
        <div class="section-title" style="margin-top:12px">SCENE</div>
        <div class="action-grid">
          <button class="action-button" data-stage-scene="transparent"><strong>Transparent</strong><small>Body-only / overlay-ready</small></button>
          <button class="action-button" data-stage-scene="void"><strong>Void</strong><small>Dark minimal stage</small></button>
          <button class="action-button" data-stage-scene="studio"><strong>Studio</strong><small>Neutral capture stage</small></button>
          <button class="action-button" data-stage-scene="neon"><strong>Neon</strong><small>Mary night-stage floor</small></button>
        </div>
      </div>
    </div>
    <div class="workspace-panel">
      <h3>Capture / handoff</h3>
      <p>Use the same body, pose, framing and lighting as the live presentation. Captures remain creator-directed artifacts.</p>
      <div class="action-grid">
        <button class="action-button" id="stage-capture" ${currentVrm ? '' : 'disabled'}><strong>Capture transparent PNG</strong><small>Current WebGL avatar frame</small></button>
        <button class="action-button" id="stage-copy-setup"><strong>Copy stage setup</strong><small>Portable presentation-only JSON</small></button>
        <button class="action-button" id="desktop-companion-toggle"><strong>${windowPresentationMode === 'companion' ? 'Return to full Desktop' : 'Companion window'}</strong><small>${windowPresentationMode === 'companion' ? 'Restore the normal Mary product shell' : 'Compact transparent always-on-top body · Ctrl+Shift+P'}</small></button>
      </div>
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
    fabric: renderFabric,
    diagnostics: renderDiagnostics,
    gallery: renderGallery,
    media: renderMedia,
    voice: renderVoice,
    settings: renderSettings,
  };
  workspaceBody.innerHTML = (renderers[screen] || (() => '<div class="workspace-empty">Coming soon.</div>'))();
  bindWorkspaceActions();
  if (screen === 'diagnostics') syncPresenceFlow();
}

function bindCreatorLabActions() {
  $('#creator-lab-choose')?.addEventListener('click', () => {
    if (!bridge?.chooseCreatorImage) {
      toast('Creator Lab image picking is unavailable on this surface.', 'error');
      return;
    }
    bridge.chooseCreatorImage((raw) => {
      const result = parsePayload(raw);
      if (!result.ok) {
        if (!result.cancelled) toast(result.error || 'Could not prepare that image.', 'error');
        return;
      }
      creatorLabState = { previewDataUrl: result.preview_data_url || '', description: '', draft: '', busy: false };
      renderWorkspace('gallery');
      toast('Image ready for Mary.');
    });
  });
  $('#creator-lab-look')?.addEventListener('click', () => {
    if (!bridge?.describeCreatorImage) {
      toast('Creator Lab vision is unavailable.', 'error');
      return;
    }
    creatorLabState.description = $('#creator-lab-description')?.value?.trim() || creatorLabState.description;
    creatorLabState.busy = true;
    renderWorkspace('gallery');
    bridge.describeCreatorImage();
  });
  $('#creator-lab-create')?.addEventListener('click', () => {
    const description = $('#creator-lab-description')?.value?.trim() || creatorLabState.description;
    const brief = $('#creator-lab-intent')?.value?.trim() || "Tell me what you'd say about this in your own voice.";
    const tone = $('#creator-lab-tone')?.value?.trim() || 'natural';
    if (!description) {
      toast('Let Mary look at the image or enter visual grounding first.', 'error');
      return;
    }
    if (!bridge?.proposeCreatorSocial) {
      toast('Canonical Creator Lab authoring is unavailable.', 'error');
      return;
    }
    creatorLabState.busy = true;
    creatorLabState.description = description;
    renderWorkspace('gallery');
    bridge.proposeCreatorSocial(brief, description, tone);
  });
  $('#creator-lab-speak')?.addEventListener('click', () => {
    const text = String(creatorLabState.draft || '').trim();
    if (text) bridge?.speakCreatorDraft?.(text);
  });
}

function refreshFabricGovernance({ force = false } = {}) {
  if (fabricGovernanceState.loading || (fabricGovernanceState.loaded && !force)) return;
  if (!bridge?.getWorldReviewState || !bridge?.getSkillReviewState) return;
  fabricGovernanceState.loading = true;
  let pending = 2;
  const done = () => {
    pending -= 1;
    if (pending > 0) return;
    fabricGovernanceState.loading = false;
    fabricGovernanceState.loaded = true;
    if (currentScreen === 'fabric') renderWorkspace('fabric');
  };
  bridge.getWorldReviewState((raw) => {
    fabricGovernanceState.world = parsePayload(raw);
    done();
  });
  bridge.getSkillReviewState((raw) => {
    fabricGovernanceState.skills = parsePayload(raw);
    done();
  });
}

function pollModelExperimentTask(taskId, attempt = 0) {
  if (!taskId || !bridge?.getCapabilityTaskStatus) return;
  if (attempt >= 120) {
    modelExperimentTrialState.busy = false;
    modelExperimentTrialState.status = 'Trial is still running on the selected node. Reopen System Fabric to inspect updated state.';
    if (currentScreen === 'fabric') renderWorkspace('fabric');
    return;
  }
  bridge.getCapabilityTaskStatus(taskId, (raw) => {
    const payload = parsePayload(raw);
    const task = payload.task || {};
    const status = String(task.status || '').toLowerCase();
    if (status === 'completed') {
      const result = task.result || {};
      modelExperimentTrialState.busy = false;
      modelExperimentTrialState.status = 'Trial completed · experimental output only.';
      modelExperimentTrialState.result = String(result.content || '').trim();
      modelExperimentTrialState.provider = String(result.provider || '');
      modelExperimentTrialState.model = String(result.model || '');
      if (currentScreen === 'fabric') renderWorkspace('fabric');
      return;
    }
    if (['failed', 'rejected', 'expired'].includes(status)) {
      modelExperimentTrialState.busy = false;
      modelExperimentTrialState.status = String(task.error || `Trial ended as ${status}.`);
      if (currentScreen === 'fabric') renderWorkspace('fabric');
      return;
    }
    modelExperimentTrialState.status = status ? `Trial ${status} on the selected node…` : 'Waiting for the selected node…';
    if (currentScreen === 'fabric') {
      const statusNode = $('#model-exp-status');
      if (statusNode) statusNode.innerHTML = `<small>${escapeHtml(modelExperimentTrialState.status)}</small>`;
    }
    setTimeout(() => pollModelExperimentTask(taskId, attempt + 1), 500);
  });
}

function bindWorkspaceActions() {
  if (currentScreen === 'gallery') bindCreatorLabActions();
  if (currentScreen === 'fabric') {
    refreshFabricGovernance();
    document.querySelectorAll('[data-world-reconcile]').forEach((button) => button.addEventListener('click', () => {
      if (!bridge?.reconcileWorldBelief) return;
      button.disabled = true;
      bridge.reconcileWorldBelief(button.dataset.worldReconcile, (raw) => {
        const result = parsePayload(raw);
        if (result.ok === false) {
          toast(result.error || 'World reconciliation failed.', 'error');
          button.disabled = false;
          return;
        }
        toast('Current world belief reconciled; competing evidence remains historical.');
        fabricGovernanceState.loaded = false;
        refreshFabricGovernance({ force: true });
      });
    }));
    document.querySelectorAll('[data-skill-approve]').forEach((button) => button.addEventListener('click', () => {
      if (!bridge?.approveSkillCandidate) return;
      button.disabled = true;
      bridge.approveSkillCandidate(button.dataset.skillApprove, (raw) => {
        const result = parsePayload(raw);
        if (result.ok === false) {
          toast(result.error || 'Skill approval failed.', 'error');
          button.disabled = false;
          return;
        }
        toast('Procedure approved. Execution permission is unchanged.');
        fabricGovernanceState.loaded = false;
        refreshFabricGovernance({ force: true });
      });
    }));
    document.querySelectorAll('[data-skill-reject]').forEach((button) => button.addEventListener('click', () => {
      if (!bridge?.rejectSkillCandidate) return;
      button.disabled = true;
      bridge.rejectSkillCandidate(button.dataset.skillReject, (raw) => {
        const result = parsePayload(raw);
        if (result.ok === false) {
          toast(result.error || 'Skill rejection failed.', 'error');
          button.disabled = false;
          return;
        }
        toast('Procedure candidate rejected.');
        fabricGovernanceState.loaded = false;
        refreshFabricGovernance({ force: true });
      });
    }));
    document.querySelectorAll('[data-skill-revise]').forEach((button) => button.addEventListener('click', () => {
      if (!bridge?.reviseApprovedSkill) return;
      const skillId = button.dataset.skillRevise;
      const current = (fabricGovernanceState.skills?.approved || []).find((item) => String(item.id || '') === String(skillId || '')) || {};
      const reason = window.prompt('Why should this approved procedure change?', current.revision_reason || '');
      if (!reason?.trim()) return;
      const existingSteps = Array.isArray(current.steps) ? current.steps : [];
      const edited = window.prompt('Procedure steps — one per line:', existingSteps.join('\n'));
      if (edited === null) return;
      const steps = edited.split(/\r?\n/).map((item) => item.trim()).filter(Boolean).slice(0, 32);
      button.disabled = true;
      bridge.reviseApprovedSkill(skillId, reason.trim(), JSON.stringify(steps), (raw) => {
        const result = parsePayload(raw);
        if (result.ok === false) {
          toast(result.error || 'Could not create the revision candidate.', 'error');
          button.disabled = false;
          return;
        }
        toast('Revision candidate created. The approved predecessor remains active until review.');
        fabricGovernanceState.loaded = false;
        refreshFabricGovernance({ force: true });
      });
    }));
    $('#model-exp-select')?.addEventListener('change', (event) => {
      modelExperimentTrialState.experimentId = String(event.target.value || '');
    });
    $('#model-exp-prompt')?.addEventListener('input', (event) => {
      modelExperimentTrialState.prompt = String(event.target.value || '').slice(0, 12000);
    });
    $('#model-exp-run')?.addEventListener('click', () => {
      const experimentId = String($('#model-exp-select')?.value || modelExperimentTrialState.experimentId || '').trim();
      const prompt = String($('#model-exp-prompt')?.value || modelExperimentTrialState.prompt || '').trim();
      if (!experimentId || !prompt || !bridge?.runModelExperiment) {
        toast('A trial-ready experiment, prompt, and remote Mary Core are required.', 'error');
        return;
      }
      modelExperimentTrialState.experimentId = experimentId;
      modelExperimentTrialState.prompt = prompt;
      modelExperimentTrialState.busy = true;
      modelExperimentTrialState.result = '';
      modelExperimentTrialState.status = 'Core is verifying exact experiment and node readiness…';
      renderWorkspace('fabric');
      bridge.runModelExperiment(experimentId, prompt, (raw) => {
        const result = parsePayload(raw);
        if (result.ok === false) {
          modelExperimentTrialState.busy = false;
          modelExperimentTrialState.status = result.error || 'Experiment dispatch was rejected.';
          renderWorkspace('fabric');
          return;
        }
        const task = result.task || {};
        const taskId = String(task.task_id || '').trim();
        if (!taskId) {
          modelExperimentTrialState.busy = false;
          modelExperimentTrialState.status = 'Core returned no experiment task ID.';
          renderWorkspace('fabric');
          return;
        }
        modelExperimentTrialState.taskId = taskId;
        modelExperimentTrialState.status = `Queued on ${result.node?.node_id || task.selected_node_id || 'authorized node'}…`;
        renderWorkspace('fabric');
        pollModelExperimentTask(taskId);
      });
    });
  }
  $('#resident-hearing-toggle')?.addEventListener('click', () => {
    if (!bridge?.setResidentHearing) return;
    const current = runtimeStatus.resident_hearing || residentHearingState || {};
    bridge.setResidentHearing(!Boolean(current.enabled), (raw) => {
      const result = parsePayload(raw);
      if (result.ok === false) {
        toast(result.error || 'Could not change Resident Hearing.', 'error');
        return;
      }
      residentHearingState = result;
      runtimeStatus.resident_hearing = result;
      toast(result.enabled ? 'Resident Hearing on.' : 'Resident Hearing off.');
      if (currentScreen === 'voice') renderWorkspace('voice');
    });
  });
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
  document.querySelectorAll('[data-performance-context]').forEach((button)=>button.addEventListener('click',()=>{
    bridge?.setPerformanceContext?.(button.dataset.performanceContext,(raw)=>{
      const r=parsePayload(raw);
      if(r.error){toast(r.error,'error');return;}
      dashboardState.performance_context=r;
      toast(`Mary stage · ${titleCase(r.mode||button.dataset.performanceContext)}`);
      renderWorkspace('stream');
    });
  }));
  $('#local-compute-toggle')?.addEventListener('click',()=>{
    const button=$('#local-compute-toggle');
    const enable=button?.dataset.enableLocalCompute === 'true';
    if(!bridge?.setLocalComputePermission){toast('Local compute permission control is unavailable on this surface.','error');return;}
    button.disabled=true;
    bridge.setLocalComputePermission(enable,(raw)=>{
      const r=parsePayload(raw);
      if(!r.ok){toast(r.error||'Could not change local compute permission.','error');button.disabled=false;return;}
      toast(enable ? 'Local compute enabled on this PC.' : 'Local compute disabled on this PC.');
      bridge.getDashboardState?.((stateRaw)=>{
        applyDashboardState(stateRaw);
        if(currentScreen === 'diagnostics') renderWorkspace('diagnostics');
      });
    });
  });
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
  $('#avatar-retry')?.addEventListener('click', async () => {
    avatarLoadError = '';
    try {
      const rendererReady = typeof initializeRenderer === 'function' ? initializeRenderer() : true;
      if (!rendererReady) {
        avatarLoadError = String(
          typeof rendererFailure !== 'undefined' && rendererFailure
            ? rendererFailure.message || rendererFailure
            : 'WebGL renderer is unavailable on this host.'
        );
        syncAvatarPresentation();
      } else {
        await loadMaryVrm();
      }
    } catch (error) {
      avatarLoadError = String(error?.message || error || 'Avatar retry failed');
      syncAvatarPresentation();
    }
    if (currentScreen === 'voice') renderWorkspace('voice');
  });
  $$('#workspace-body [data-prompt]').forEach((button) => button.addEventListener('click', () => {
    setScreen('chat');
    submitPrompt(button.dataset.prompt);
  }));
  $$('#workspace-body [data-avatar-frame]').forEach((button) => button.addEventListener('click', () => {
    setAvatarFraming(button.dataset.avatarFrame);
    toast(`Avatar framing: ${titleCase(button.dataset.avatarFrame)}`);
  }));
  $('#stage-camera-yaw')?.addEventListener('input', (event) => {
    stageCameraYaw = Math.max(-45, Math.min(45, Number(event.target.value) || 0));
    localStorage.setItem('mary.stageCameraYaw', String(stageCameraYaw));
    const label = $('#stage-yaw-value');
    if (label) label.textContent = `${Math.round(stageCameraYaw)}°`;
    setAvatarFraming(avatarFraming);
  });
  $('#stage-camera-elevation')?.addEventListener('input', (event) => {
    stageCameraElevation = Math.max(-.3, Math.min(.3, Number(event.target.value) || 0));
    localStorage.setItem('mary.stageCameraElevation', String(stageCameraElevation));
    const label = $('#stage-elevation-value');
    if (label) label.textContent = stageCameraElevation.toFixed(2);
    setAvatarFraming(avatarFraming);
  });
  $$('#workspace-body [data-stage-expression]').forEach((button) => button.addEventListener('click', () => {
    const expression = String(button.dataset.stageExpression || 'neutral');
    applyAvatarState({ expression, emotion_intensity: expression === 'neutral' ? .08 : .56 });
    toast(`Stage preview: ${titleCase(expression)}`);
  }));
  $$('#workspace-body [data-stage-motion]').forEach((button) => button.addEventListener('click', () => {
    const motionId = String(button.dataset.stageMotion || '');
    studioMotionCue = motionId ? { motion_id: motionId } : null;
    if (!motionId && currentVrm) applyRelaxedStandingPose(currentVrm);
    toast(motionId ? `Motion preview: ${titleCase(motionId)}` : 'Motion preview reset.');
  }));
  $$('#workspace-body [data-stage-lighting]').forEach((button) => button.addEventListener('click', () => {
    applyStageLightingPreset(button.dataset.stageLighting);
    renderWorkspace('voice');
    toast(`Lighting: ${titleCase(button.dataset.stageLighting)}`);
  }));
  $$('#workspace-body [data-stage-scene]').forEach((button) => button.addEventListener('click', () => {
    applyStageScenePreset(button.dataset.stageScene);
    renderWorkspace('voice');
    toast(`Scene: ${titleCase(button.dataset.stageScene)}`);
  }));
  const bindLightSlider = (selector, key, valueSelector) => {
    $(selector)?.addEventListener('input', (event) => {
      applyStageLighting({ ...stageLighting, [key]: Number(event.target.value) });
      const valueNode = $(valueSelector);
      if (valueNode) valueNode.textContent = stageLighting[key].toFixed(2);
    });
  };
  bindLightSlider('#stage-key-light', 'key', '#stage-key-value');
  bindLightSlider('#stage-fill-light', 'fill', '#stage-fill-value');
  bindLightSlider('#stage-rim-light', 'rim', '#stage-rim-value');
  $('#stage-capture')?.addEventListener('click', captureAvatarPng);
  $('#stage-copy-setup')?.addEventListener('click', copyStageSetup);
  $('#desktop-companion-toggle')?.addEventListener('click', () => {
    setWindowPresentationMode(windowPresentationMode === 'companion' ? 'standard' : 'companion');
  });
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
$('#companion-exit')?.addEventListener('click', () => setWindowPresentationMode('standard'));
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
  if (surface === 'desktop') reportPresentationCapabilities();
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
  bridge.creatorImageReady?.connect((raw) => {
    const result = parsePayload(raw);
    creatorLabState.busy = false;
    if (result.ok && result.description) {
      creatorLabState.description = String(result.description);
      if (currentScreen === 'gallery') renderWorkspace('gallery');
      toast(`Mary grounded the image · ${providerDisplayName(result.provider || 'vision')}`);
    } else {
      if (currentScreen === 'gallery') renderWorkspace('gallery');
      toast(result.error || 'Mary could not ground that image.', 'error');
    }
  });
  bridge.creatorSocialReady?.connect((raw) => {
    const result = parsePayload(raw);
    const proposal = result.proposal || result;
    creatorLabState.busy = false;
    creatorLabState.draft = String(proposal.content || '').trim();
    if (currentScreen === 'gallery') renderWorkspace('gallery');
    if (!creatorLabState.draft) toast(result.error || 'Mary returned no Creator Lab draft.', 'error');
  });
  bridge.creatorDraftVoiceReady?.connect((raw) => {
    const payload = parsePayload(raw);
    if (payload.status === 'success') playVoice(payload);
    else toast(payload.error || 'Mary voice preview is unavailable.', 'error');
  });
  bridge.voicePlaybackStopRequested.connect(() => stopVoicePlayback({ notifyBridge: false }));
  bridge.errorOccurred.connect((message) => {
    setBusy(false);
    toast(message, 'error');
    appendMessage('System', message, 'system');
  });
  bridge.residentHearingStateChanged?.connect((raw) => {
    residentHearingState = parsePayload(raw);
    runtimeStatus.resident_hearing = residentHearingState;
    if (currentScreen === 'voice') renderWorkspace('voice');
  });
  bridge.listeningStateChanged.connect((state) => {
    const value = String(state || '').toLowerCase();
    if (['listening', 'transcribing'].includes(value)) setConversationState(value);
  });
  bridge.transcriptionReady.connect((text) => {
    const transcript = String(text || '').trim();
    if (!transcript || busy) return;
    appendMessage('Unbe', transcript, 'user');
    if (typeof bridge.sendVoiceMessage === 'function') {
      bridge.sendVoiceMessage(transcript);
    } else {
      bridge.sendMessage(transcript);
    }
  });

  bridge.getStatus((raw) => {
    runtimeStatus = parsePayload(raw);
    residentHearingState = runtimeStatus.resident_hearing || residentHearingState;
    const voiceLabel = runtimeStatus.voice?.enabled ? ` · voice:${runtimeStatus.voice.provider}` : '';
    const sttLabel = runtimeStatus.speech_to_text?.enabled ? ` · mic:${runtimeStatus.speech_to_text.provider}` : '';
    modelLabel.textContent = `${providerDisplayName(runtimeStatus.provider || 'runtime')} · ${runtimeStatus.model || 'MaryV2'}${voiceLabel}${sttLabel}`;
    if (runtimeStatus.conversation) setConversationState(runtimeStatus.conversation);
    projectProductShell();
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
loadMotionManifest();
loadMaryVrm();
window.setTimeout(()=>{ if(!bridge) finishBoot('Mary web preview mode.'); }, 4000);
connectBridge();
refreshConversationControls();
animate();
