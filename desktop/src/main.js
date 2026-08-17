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

const clock = new THREE.Clock();
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
  const box = new THREE.Box3().setFromObject(vrm.scene);
  const size = box.getSize(new THREE.Vector3());
  const center = box.getCenter(new THREE.Vector3());
  const height = Math.max(size.y, 1.0);
  const targetY = center.y + height * 0.06;
  const distance = height * 1.05;

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
    currentVrm.scene.rotation.y = Math.PI;
    scene.add(currentVrm.scene);
    fitCamera(currentVrm);
    fallback.classList.add('hidden');
    applyAvatarState({ expression: 'neutral', emotion_intensity: 0 });
  } catch (error) {
    console.warn('MaryCosma.vrm was not loaded:', error);
    fallback.classList.remove('hidden');
  }
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

  const delta = clock.getDelta();
  const elapsed = clock.elapsedTime;

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
    });

    bridge.avatarStateChanged.connect((raw) => applyAvatarState(parsePayload(raw)));
    bridge.busyChanged.connect((value) => setBusy(value));
    bridge.errorOccurred.connect((message) => {
      setBusy(false);
      appendMessage('System', message, 'system');
    });

    bridge.getStatus((raw) => {
      const status = parsePayload(raw);
      modelLabel.textContent = `${status.provider || 'unknown'} · ${status.model || 'unknown'}`;
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
