import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { VRMLoaderPlugin, VRMUtils } from '@pixiv/three-vrm';
import './style.css';

const canvas = document.querySelector('#avatar-canvas');
const fallback = document.querySelector('#avatar-fallback');
const messages = document.querySelector('#messages');
const composer = document.querySelector('#composer');
const input = document.querySelector('#message-input');
const sendButton = document.querySelector('#send-button');
const thinking = document.querySelector('#thinking');
const statusDot = document.querySelector('#status-dot');
const statusText = document.querySelector('#status-text');
const modelLabel = document.querySelector('#model-label');

let bridge = null;
let currentVrm = null;
let modelBaseY = 0;
let busy = false;
let activeSpeechAudio = null;

// ---------------------------------------------------------------------------
// Three.js / VRM presentation
// ---------------------------------------------------------------------------

const renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true });
renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.shadowMap.enabled = true;

const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(30, 1, 0.1, 100);
camera.position.set(0, 1.35, 2.6);

const key = new THREE.DirectionalLight(0xffffff, 2.2);
key.position.set(1.5, 2.5, 2.5);
scene.add(key);

const fill = new THREE.DirectionalLight(0x8aa8ff, 1.2);
fill.position.set(-2, 1.2, 1.0);
scene.add(fill);
scene.add(new THREE.HemisphereLight(0xffffff, 0x202030, 1.8));

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

function fitCamera(vrm) {
  // Make sure camera.aspect reflects the actual avatar viewport before
  // calculating a framing distance.
  resizeRenderer();

  const box = new THREE.Box3().setFromObject(vrm.scene);
  const size = box.getSize(new THREE.Vector3());
  const center = box.getCenter(new THREE.Vector3());

  const height = Math.max(size.y, 1.0);
  const width = Math.max(size.x, 0.5);

  const verticalFov = THREE.MathUtils.degToRad(camera.fov);
  const horizontalFov = 2 * Math.atan(
    Math.tan(verticalFov / 2) * Math.max(camera.aspect, 0.1),
  );

  // Fit both the avatar height and width, then add breathing room.
  // The previous prototype used height * 1.05, which is much too close
  // for a 30-degree camera and crops Mary around the torso.
  const verticalDistance = (height / 2) / Math.tan(verticalFov / 2);
  const horizontalDistance = (width / 2) / Math.tan(horizontalFov / 2);
  const distance = Math.max(verticalDistance, horizontalDistance) * 1.18;

  // Center the complete character rather than biasing the camera toward
  // the face. This gives a comfortable full-body framing by default.
  const targetY = center.y;

  camera.position.set(center.x, targetY, center.z + distance);
  camera.lookAt(center.x, targetY, center.z);
  modelBaseY = vrm.scene.position.y;
}

async function loadMaryVrm() {
  const loader = new GLTFLoader();
  loader.register((parser) => new VRMLoaderPlugin(parser));

  try {
    const gltf = await loader.loadAsync('./models/MaryCosma.vrm');
    const vrm = gltf.userData.vrm;
    if (!vrm) throw new Error('No VRM object was found in the model.');

    if (currentVrm) scene.remove(currentVrm.scene);

    VRMUtils.removeUnnecessaryVertices(vrm.scene);
    VRMUtils.combineSkeletons(vrm.scene);

    currentVrm = vrm;

    // VRM 1.0 already uses +Z as the standardized forward direction.
    // Only legacy VRM 0.x models require the 180-degree compatibility turn.
    VRMUtils.rotateVRM0(currentVrm);
    applyRelaxedStandingPose(currentVrm);

    scene.add(currentVrm.scene);
    fitCamera(currentVrm);
    fallback.classList.add('hidden');
    applyAvatarState({ expression: 'neutral', emotion_intensity: 0 });
  } catch (error) {
    console.warn('MaryCosma.vrm was not loaded:', error);
    fallback.classList.remove('hidden');
  }
}


function quaternionArrayFromEuler(x = 0, y = 0, z = 0) {
  const quaternion = new THREE.Quaternion().setFromEuler(
    new THREE.Euler(x, y, z, 'XYZ'),
  );
  return [quaternion.x, quaternion.y, quaternion.z, quaternion.w];
}

// VRM humanoids use T-pose as their reference pose. This small normalized
// offset gives Mary a relaxed standing presentation until we add real VRMA
// animation clips/state-machine playback.
const RELAXED_STANDING_POSE = {
  // VRM normalized humanoid rest pose is a T-pose. Rotating the upper arms
  // toward the torso gives Mary a natural A/standing pose. These signs are
  // intentionally opposite the earlier prototype, which raised the arms.
  leftUpperArm: { rotation: quaternionArrayFromEuler(0, 0, -1.28) },
  rightUpperArm: { rotation: quaternionArrayFromEuler(0, 0, 1.28) },
  // Add a small forward elbow bend so the arms do not look rigidly pinned.
  leftLowerArm: { rotation: quaternionArrayFromEuler(0, -0.10, -0.10) },
  rightLowerArm: { rotation: quaternionArrayFromEuler(0, 0.10, 0.10) },
};

function applyRelaxedStandingPose(vrm) {
  const humanoid = vrm?.humanoid;
  if (!humanoid?.setNormalizedPose) return;
  humanoid.setNormalizedPose(RELAXED_STANDING_POSE);
  vrm.update(0);
}

const PRESET_MAP = {
  happy: 'happy',
  excited: 'happy',
  loving: 'happy',
  affectionate: 'happy',
  grateful: 'happy',
  proud: 'happy',
  sad: 'sad',
  lonely: 'sad',
  disappointed: 'sad',
  angry: 'angry',
  frustrated: 'angry',
  surprised: 'surprised',
  afraid: 'surprised',
  calm: 'relaxed',
  hopeful: 'relaxed',
  curious: 'relaxed',
  concerned: 'sad',
  confused: 'surprised',
};

function resetKnownExpressions(manager) {
  for (const preset of ['happy', 'sad', 'angry', 'surprised', 'relaxed']) {
    try { manager.setValue(preset, 0); } catch (_) { /* model may omit preset */ }
  }
}

function applyAvatarState(state = {}) {
  if (!currentVrm?.expressionManager) return;
  const manager = currentVrm.expressionManager;
  resetKnownExpressions(manager);

  const preset = PRESET_MAP[state.expression];
  if (preset) {
    const intensity = Math.max(0.15, Math.min(1, Number(state.emotion_intensity ?? 0.4)));
    try { manager.setValue(preset, intensity); } catch (_) { /* optional preset */ }
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

function animate(now = performance.now()) {
  requestAnimationFrame(animate);
  resizeRenderer();

  const delta = Math.min(Math.max((now - previousFrameMs) / 1000, 0), 0.1);
  previousFrameMs = now;
  const elapsed = now / 1000;

  if (currentVrm) {
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
// Chat UI / Python bridge
// ---------------------------------------------------------------------------

function appendMessage(speaker, text, kind) {
  const article = document.createElement('article');
  article.className = `message ${kind}`;

  const label = document.createElement('div');
  label.className = 'speaker';
  label.textContent = speaker;

  const bubble = document.createElement('div');
  bubble.className = 'bubble';
  bubble.textContent = text;

  article.append(label, bubble);
  messages.append(article);
  messages.scrollTop = messages.scrollHeight;
}

function setBusy(value) {
  busy = Boolean(value);
  sendButton.disabled = busy;
  input.disabled = busy;
  thinking.classList.toggle('hidden', !busy);
}

function setConnected(value, label = '') {
  statusDot.classList.toggle('connected', value);
  statusText.textContent = label || (value ? 'Mary ready' : 'Disconnected');
}

function parsePayload(value) {
  if (typeof value === 'object' && value !== null) return value;
  try { return JSON.parse(value); } catch (_) { return {}; }
}


function stopVoicePlayback() {
  if (!activeSpeechAudio) return;
  try {
    activeSpeechAudio.pause();
    activeSpeechAudio.currentTime = 0;
  } catch (_) { /* best-effort */ }
  activeSpeechAudio = null;
}

function playVoice(voice = {}) {
  if (!voice?.enabled || voice.status !== 'success' || !voice.audio_base64) return;

  stopVoicePlayback();

  const mimeType = voice.mime_type || 'audio/mpeg';
  const audio = new Audio(`data:${mimeType};base64,${voice.audio_base64}`);
  activeSpeechAudio = audio;

  audio.addEventListener('play', () => {
    if (activeSpeechAudio === audio) setConnected(true, 'Mary speaking');
  });

  audio.addEventListener('ended', () => {
    if (activeSpeechAudio === audio) {
      activeSpeechAudio = null;
      setConnected(true, 'Mary ready');
    }
  });

  audio.addEventListener('error', () => {
    if (activeSpeechAudio === audio) {
      activeSpeechAudio = null;
      setConnected(true, 'Mary ready');
    }
    appendMessage('System', 'Mary generated voice audio, but playback failed.', 'system');
  });

  audio.play().catch((error) => {
    if (activeSpeechAudio === audio) activeSpeechAudio = null;
    setConnected(true, 'Mary ready');
    appendMessage('System', `Voice playback failed: ${error}`, 'system');
  });
}

function connectBridge() {
  if (!window.qt?.webChannelTransport || typeof QWebChannel === 'undefined') {
    setConnected(false, 'Open this UI through MaryV2 Desktop');
    return;
  }

  new QWebChannel(window.qt.webChannelTransport, (channel) => {
    bridge = channel.objects.maryBridge;
    setConnected(true, 'Mary ready');

    bridge.messageReady.connect((raw) => {
      const payload = parsePayload(raw);
      appendMessage('Mary', payload.text || '[No response]', 'mary');
      applyAvatarState(payload.avatar || {});
      playVoice(payload.voice || {});
    });

    bridge.avatarStateChanged.connect((raw) => applyAvatarState(parsePayload(raw)));
    bridge.busyChanged.connect((value) => setBusy(value));
    bridge.errorOccurred.connect((message) => {
      setBusy(false);
      appendMessage('System', message, 'system');
    });

    bridge.getStatus((raw) => {
      const status = parsePayload(raw);
      const voiceLabel = status.voice?.enabled ? ` · voice:${status.voice.provider}` : '';
      modelLabel.textContent = `${status.provider || 'unknown'} · ${status.model || 'unknown'}${voiceLabel}`;
    });

    bridge.getAvatarState((raw) => applyAvatarState(parsePayload(raw)));
  });
}

composer.addEventListener('submit', (event) => {
  event.preventDefault();
  const text = input.value.trim();
  if (!text || busy || !bridge) return;

  appendMessage('Unbe', text, 'user');
  input.value = '';
  bridge.sendMessage(text);
});

input.addEventListener('keydown', (event) => {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault();
    composer.requestSubmit();
  }
});

window.addEventListener('resize', resizeRenderer);

loadMaryVrm();
connectBridge();
animate();
