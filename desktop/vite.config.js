import { defineConfig } from 'vite';
import { resolve } from 'node:path';

export default defineConfig({
  base: './',
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
