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
const micButton = document.querySelector('#mic-button');
const thinking = document.querySelector('#thinking');
const statusDot = document.querySelector('#status-dot');
const statusText = document.querySelector('#status-text');
const modelLabel = document.querySelector('#model-label');
const stateName = document.querySelector('#state-name');
const stateContinuity = document.querySelector('#state-continuity');
const stateRelationship = document.querySelector('#state-relationship');
const stateMemories = document.querySelector('#state-memories');
const stateMood = document.querySelector('#state-mood');
const stateEnergy = document.querySelector('#state-energy');
const stateRuntime = document.querySelector('#state-runtime');
const stateTask = document.querySelector('#state-task');

let bridge = null;
let currentVrm = null;
let modelBaseY = 0;
let busy = false;
let listeningState = 'idle';
let conversationState = 'idle';
let activeSpeechAudio = null;
let speechAudioContext = null;
let speechAudioSource = null;
let speechAnalyser = null;
let speechWaveform = null;
let activeMouthExpression = null;
let lipSyncWeight = 0;

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

function refreshConversationControls() {
  const listening = conversationState === 'listening';
  const transcribing = conversationState === 'transcribing';
  const thinkingNow = conversationState === 'thinking';
  const speaking = conversationState === 'speaking';
  const interrupted = conversationState === 'interrupted';

  listeningState = listening ? 'listening' : (transcribing ? 'transcribing' : 'idle');

  // Typed input can barge in while Mary is speaking. It is disabled only while
  // microphone capture/transcription or Mary's reasoning turn owns the runtime.
  input.disabled = listening || transcribing || thinkingNow || interrupted || busy;
  sendButton.disabled = input.disabled;
  micButton.disabled = transcribing || thinkingNow || interrupted || busy;

  micButton.classList.toggle('listening', listening);
  micButton.classList.toggle('transcribing', transcribing);
  micButton.classList.toggle('speaking', speaking);
  micButton.setAttribute('aria-pressed', listening ? 'true' : 'false');
  micButton.textContent = listening
    ? 'Stop'
    : (transcribing ? '…' : (speaking ? 'Interrupt' : 'Mic'));

  thinking.classList.toggle('hidden', !thinkingNow);

  const labels = {
    idle: 'Mary ready',
    listening: 'Listening…',
    transcribing: 'Transcribing…',
    thinking: 'Thinking…',
    speaking: 'Mary speaking',
    interrupted: 'Interrupted…',
  };
  setConnected(true, labels[conversationState] || 'Mary ready');
}

function setBusy(value) {
  busy = Boolean(value);
  refreshConversationControls();
}

function setListeningState(state) {
  // Backwards-compatible microphone signal. The authoritative lifecycle comes
  // from conversationStateChanged, but this keeps Alpha 1 recorder events sane
  // if they arrive a fraction earlier than the state snapshot.
  const value = String(state || 'idle');
  if (value === 'listening' || value === 'transcribing') {
    conversationState = value;
    refreshConversationControls();
  }
}

function setConversationState(raw) {
  const payload = parsePayload(raw);
  const state = String(payload.state || raw || 'idle').toLowerCase();
  if (!['idle', 'listening', 'transcribing', 'thinking', 'speaking', 'interrupted'].includes(state)) return;
  conversationState = state;
  refreshConversationControls();
}

function applyCharacterState(raw) {
  const payload = parsePayload(raw);
  const character = payload.character || {};
  const memory = payload.memory || {};

  stateName.textContent = character.name || 'Mary';
  stateContinuity.textContent = character.continuity === 'persistent_capable' ? 'Persistent' : (character.continuity || 'Unknown');
  stateRelationship.textContent = character.relationship || 'Beginning';
  stateMemories.textContent = String(character.memory_count ?? ((memory.episodic || 0) + (memory.semantic || 0)));
  stateMood.textContent = String(character.mood || 'neutral').replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
  stateEnergy.textContent = String(character.energy || 'calm').replace(/\b\w/g, (letter) => letter.toUpperCase());
  stateRuntime.textContent = String(character.status || conversationState || 'idle').replace(/\b\w/g, (letter) => letter.toUpperCase());
  stateTask.textContent = character.current_task || 'None';
}

function setConnected(value, label = '') {
  statusDot.classList.toggle('connected', value);
  statusText.textContent = label || (value ? 'Mary ready' : 'Disconnected');
}

function parsePayload(value) {
  if (typeof value === 'object' && value !== null) return value;
  try { return JSON.parse(value); } catch (_) { return {}; }
}


const MOUTH_PRESET_CANDIDATES = ['aa', 'oh', 'ou', 'ih', 'ee'];

function resolveMouthExpression() {
  const manager = currentVrm?.expressionManager;
  if (!manager) return null;

  for (const preset of MOUTH_PRESET_CANDIDATES) {
    try {
      if (manager.getExpression?.(preset)) return preset;
    } catch (_) { /* optional expression */ }
  }

  return null;
}

function resetLipSyncMouth() {
  const manager = currentVrm?.expressionManager;
  if (manager) {
    for (const preset of MOUTH_PRESET_CANDIDATES) {
      try { manager.setValue(preset, 0); } catch (_) { /* optional preset */ }
    }
  }

  activeMouthExpression = null;
  lipSyncWeight = 0;
}

function disconnectLipSyncGraph() {
  resetLipSyncMouth();

  try { speechAudioSource?.disconnect(); } catch (_) { /* best-effort */ }
  try { speechAnalyser?.disconnect(); } catch (_) { /* best-effort */ }

  speechAudioSource = null;
  speechAnalyser = null;
  speechWaveform = null;
}

function ensureSpeechAudioContext() {
  const AudioContextClass = window.AudioContext || window.webkitAudioContext;
  if (!AudioContextClass) return null;

  if (!speechAudioContext) {
    speechAudioContext = new AudioContextClass();
  }

  return speechAudioContext;
}

function attachLipSyncToAudio(audio) {
  disconnectLipSyncGraph();

  const context = ensureSpeechAudioContext();
  if (!context) return;

  try {
    const source = context.createMediaElementSource(audio);
    const analyser = context.createAnalyser();

    // A short time-domain window is responsive enough for speech while the
    // attack/release smoothing below prevents Mary's mouth from chattering.
    analyser.fftSize = 256;
    analyser.smoothingTimeConstant = 0.45;

    source.connect(analyser);
    analyser.connect(context.destination);

    speechAudioSource = source;
    speechAnalyser = analyser;
    speechWaveform = new Uint8Array(analyser.fftSize);
    activeMouthExpression = resolveMouthExpression();

    if (context.state === 'suspended') {
      context.resume().catch(() => {});
    }
  } catch (error) {
    console.warn('Lip sync audio analyser could not be attached:', error);
    disconnectLipSyncGraph();
  }
}

function updateLipSync() {
  const manager = currentVrm?.expressionManager;
  if (!manager || !speechAnalyser || !speechWaveform || !activeMouthExpression) {
    return;
  }

  let target = 0;

  if (activeSpeechAudio && !activeSpeechAudio.paused && !activeSpeechAudio.ended) {
    speechAnalyser.getByteTimeDomainData(speechWaveform);

    let sumSquares = 0;
    for (let index = 0; index < speechWaveform.length; index += 1) {
      const sample = (speechWaveform[index] - 128) / 128;
      sumSquares += sample * sample;
    }

    const rms = Math.sqrt(sumSquares / speechWaveform.length);

    // Remove the quiet noise floor, then expand normal speech amplitudes into
    // the full VRM expression range. The square root makes quieter syllables
    // visible without forcing loud speech permanently wide-open.
    const gated = Math.max(0, (rms - 0.018) * 7.5);
    target = Math.min(1, Math.sqrt(gated));
  }

  const response = target > lipSyncWeight ? 0.48 : 0.24;
  lipSyncWeight += (target - lipSyncWeight) * response;

  if (lipSyncWeight < 0.015 && target === 0) lipSyncWeight = 0;

  try {
    manager.setValue(activeMouthExpression, lipSyncWeight);
  } catch (_) { /* optional mouth preset */ }
}

function stopVoicePlayback({ notifyBridge = true } = {}) {
  if (activeSpeechAudio) {
    try {
      activeSpeechAudio.pause();
      activeSpeechAudio.currentTime = 0;
    } catch (_) { /* best-effort */ }
  }

  activeSpeechAudio = null;
  disconnectLipSyncGraph();

  if (notifyBridge && bridge?.voicePlaybackFinished) {
    bridge.voicePlaybackFinished();
  }
}

function playVoice(voice = {}) {
  if (!voice?.enabled || voice.status !== 'success' || !voice.audio_base64) return;

  stopVoicePlayback({ notifyBridge: false });

  const mimeType = voice.mime_type || 'audio/mpeg';
  const audio = new Audio(`data:${mimeType};base64,${voice.audio_base64}`);
  activeSpeechAudio = audio;
  attachLipSyncToAudio(audio);

  audio.addEventListener('play', () => {
    if (activeSpeechAudio === audio) {
      bridge?.voicePlaybackStarted?.();
    }
  });

  audio.addEventListener('ended', () => {
    if (activeSpeechAudio === audio) {
      activeSpeechAudio = null;
      disconnectLipSyncGraph();
      bridge?.voicePlaybackFinished?.();
    }
  });

  audio.addEventListener('error', () => {
    if (activeSpeechAudio === audio) {
      activeSpeechAudio = null;
      disconnectLipSyncGraph();
      bridge?.voicePlaybackFinished?.();
    }
    appendMessage('System', 'Mary generated voice audio, but playback failed.', 'system');
  });

  audio.play().catch((error) => {
    if (activeSpeechAudio === audio) activeSpeechAudio = null;
    disconnectLipSyncGraph();
    bridge?.voicePlaybackFinished?.();
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
    bridge.conversationStateChanged.connect((raw) => setConversationState(raw));
    if (bridge.characterStateChanged) {
      bridge.characterStateChanged.connect((raw) => applyCharacterState(raw));
    }
    bridge.voicePlaybackStopRequested.connect(() => {
      stopVoicePlayback({ notifyBridge: false });
    });
    bridge.errorOccurred.connect((message) => {
      setBusy(false);
      appendMessage('System', message, 'system');
    });

    bridge.listeningStateChanged.connect((state) => setListeningState(state));
    bridge.transcriptionReady.connect((text) => {
      const transcript = String(text || '').trim();
      if (!transcript || busy) return;
      appendMessage('Unbe', transcript, 'user');
      bridge.sendMessage(transcript);
    });

    bridge.getStatus((raw) => {
      const status = parsePayload(raw);
      const voiceLabel = status.voice?.enabled ? ` · voice:${status.voice.provider}` : '';
      const sttLabel = status.speech_to_text?.enabled ? ` · mic:${status.speech_to_text.provider}` : '';
      modelLabel.textContent = `${status.provider || 'unknown'} · ${status.model || 'unknown'}${voiceLabel}${sttLabel}`;
      if (status.conversation) setConversationState(status.conversation);
    });

    bridge.getAvatarState((raw) => applyAvatarState(parsePayload(raw)));
    if (bridge.getCharacterState) {
      bridge.getCharacterState((raw) => applyCharacterState(raw));
    }
  });
}

micButton.addEventListener('click', () => {
  if (!bridge || conversationState === 'transcribing' || conversationState === 'thinking') return;

  if (conversationState === 'listening') {
    bridge.stopListening();
    return;
  }

  // Barge-in is immediate on the presentation side: silence Mary before Qt
  // starts recording, while the Python runtime records the interrupted state.
  if (conversationState === 'speaking' || activeSpeechAudio) {
    stopVoicePlayback({ notifyBridge: false });
  }
  bridge.startListening();
});

composer.addEventListener('submit', (event) => {
  event.preventDefault();
  const text = input.value.trim();
  if (!text || busy || !bridge) return;
  if (['listening', 'transcribing', 'thinking', 'interrupted'].includes(conversationState)) return;

  if (conversationState === 'speaking' || activeSpeechAudio) {
    stopVoicePlayback({ notifyBridge: false });
  }

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
