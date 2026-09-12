import { defineConfig } from 'vite';
import { resolve } from 'node:path';

function marySafeRendererPlugin() {
  const replaceRequired = (code, before, after, label) => {
    if (!code.includes(before)) throw new Error(`Mary safe-renderer marker missing: ${label}`);
    return code.replace(before, after);
  };

  return {
    name: 'mary-safe-renderer',
    enforce: 'pre',
    transform(code, id) {
      if (!/[\\/]desktop[\\/]src[\\/]main\.js$/.test(id)) return null;
      let next = code;
      next = replaceRequired(
        next,
        'installExperienceLayer({ app });',
        `bootStep(10, 'Starting Mary interface…');\ntry {\n  installExperienceLayer({ app });\n} catch (error) {\n  console.warn('[MaryUI] passive experience layer failed; continuing without it', error);\n}`,
        'experience-layer boot'
      );
      next = replaceRequired(
        next,
        `function finishBoot(message = 'Mary is ready.') {\n  const boot = $('#boot-screen');`,
        `function finishBoot(message = 'Mary is ready.') {\n  window.__MARY_UI_BOOTED__ = true;\n  const boot = $('#boot-screen');`,
        'boot completion'
      );
      next = replaceRequired(
        next,
        `const renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true });\nrenderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));\nrenderer.outputColorSpace = THREE.SRGBColorSpace;\nrenderer.shadowMap.enabled = true;`,
        `let renderer = null;\nlet rendererFailure = null;\nconst rendererMode = new URLSearchParams(window.location.search).get('mary_renderer') || 'auto';\n\nfunction initializeRenderer() {\n  if (renderer) return true;\n  if (rendererMode === 'portrait') {\n    console.info('[MaryUI] 3D renderer intentionally disabled for this host; using portrait fallback');\n    return false;\n  }\n  try {\n    renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true });\n    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));\n    renderer.outputColorSpace = THREE.SRGBColorSpace;\n    renderer.shadowMap.enabled = true;\n    return true;\n  } catch (error) {\n    rendererFailure = error;\n    renderer = null;\n    console.warn('[MaryUI] WebGL avatar renderer unavailable; using portrait fallback', error);\n    try { canvas?.classList.add('hidden'); } catch (_) {}\n    return false;\n  }\n}`,
        'renderer construction'
      );
      next = replaceRequired(
        next,
        `function resizeRenderer() {\n  const rect = canvas.getBoundingClientRect();`,
        `function resizeRenderer() {\n  if (!renderer || !canvas) return;\n  const rect = canvas.getBoundingClientRect();`,
        'renderer resize guard'
      );
      next = replaceRequired(
        next,
        `async function loadMaryVrm() {\n  const loader = new GLTFLoader();`,
        `async function loadMaryVrm() {\n  if (!renderer) {\n    currentVrm = null;\n    syncAvatarPresentation();\n    return;\n  }\n  const loader = new GLTFLoader();`,
        'VRM load guard'
      );
      next = replaceRequired(
        next,
        '  renderer.render(scene, camera);',
        '  if (renderer) renderer.render(scene, camera);',
        'render loop guard'
      );
      next = replaceRequired(
        next,
        `bootStep(28, 'Loading character renderer…');\nsyncAvatarPresentation();\nloadMaryVrm();`,
        `bootStep(28, 'Loading character renderer…');\nconst rendererReady = initializeRenderer();\nsyncAvatarPresentation();\nif (rendererReady) {\n  loadMaryVrm();\n} else {\n  bootStep(36, 'Avatar renderer unavailable · using portrait mode…');\n}`,
        'renderer startup'
      );
      return { code: next, map: null };
    },
    transformIndexHtml(html) {
      let next = html;
      // Historical HTML labels should never make a current build look like an
      // unrelated 12.x/13.7 client. Runtime authority still comes from Core.
      next = next
        .replaceAll('12.12', '13.8')
        .replaceAll('13.7', '13.8')
        .replace('PERSONAL COMPANION SYSTEM · 13.8', 'PERSISTENT COMPANION SYSTEM · 13.8')
        .replace('Your AI Companion', 'Your Persistent AI Companion');
      return {
        html: next,
        tags: [
          {
            tag: 'link',
            injectTo: 'head',
            attrs: { rel: 'stylesheet', href: './polish-13-7.css' },
          },
          {
            tag: 'link',
            injectTo: 'head',
            attrs: { rel: 'stylesheet', href: './relational-13-8.css' },
          },
          {
            tag: 'script',
            injectTo: 'body-prepend',
            children: `(() => {\n  const updateBoot = (message) => { const node = document.getElementById('boot-status'); if (node) node.textContent = message; };\n  const report = (kind, detail) => {\n    const message = String(detail || 'unknown frontend failure');\n    console.error(\`[MaryUI][\${kind}] \${message}\`);\n    if (!window.__MARY_UI_BOOTED__) updateBoot(\`Desktop startup error · \${message.slice(0, 110)}\`);\n  };\n  window.addEventListener('error', (event) => {\n    if (event?.target?.tagName === 'SCRIPT') return report('script', \`could not load \${event.target.src || 'frontend script'}\`);\n    if (event?.message) report('error', event.message);\n  }, true);\n  window.addEventListener('unhandledrejection', (event) => report('promise', event?.reason?.message || event?.reason || 'unhandled promise rejection'));\n  window.setTimeout(() => {\n    if (!window.__MARY_UI_BOOTED__) {\n      const node = document.getElementById('boot-status');\n      if (node && node.textContent.trim() === 'Initializing Mary…') updateBoot('Desktop frontend did not start · check the VS Code terminal');\n    }\n  }, 7000);\n})();`,
          },
        ],
      };
    },
  };
}

export default defineConfig({
  base: './',
  plugins: [marySafeRendererPlugin()],
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    sourcemap: true,
    rolldownOptions: {
      input: {
        main: resolve(import.meta.dirname, 'index.html'),
        launcher: resolve(import.meta.dirname, 'launcher.html'),
      },
      output: {
        // Keep the large 3D runtime out of Mary's application chunk. Vite 8
        // uses Rolldown and recommends output.codeSplitting over manualChunks.
        codeSplitting: {
          groups: [
            {
              name: 'vrm-runtime',
              test: /node_modules[\\/]@pixiv[\\/]three-vrm/,
              priority: 30,
            },
            {
              name: 'three-runtime',
              test: /node_modules[\\/]three[\\/]/,
              priority: 20,
            },
            {
              name: 'vendor',
              test: /node_modules/,
              priority: 10,
            },
          ],
        },
      },
    },
  },
});