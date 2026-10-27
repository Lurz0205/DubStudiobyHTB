import { defineConfig, type Plugin } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
import fs from 'node:fs';
import path from 'node:path';

function inlineCssPlugin(): Plugin {
  return {
    name: 'inline-css-plugin',
    closeBundle() {
      const distDir = path.resolve(__dirname, 'dist');
      const htmlPath = path.join(distDir, 'index.html');
      const assetsDir = path.join(distDir, 'assets');

      if (!fs.existsSync(htmlPath)) return;

      let cssContent = '';
      if (fs.existsSync(assetsDir)) {
        const files = fs.readdirSync(assetsDir);
        for (const file of files) {
          if (file.endsWith('.css')) {
            const cssFile = path.join(assetsDir, file);
            cssContent += fs.readFileSync(cssFile, 'utf-8') + '\n';
          }
        }
      }

      if (cssContent) {
        let html = fs.readFileSync(htmlPath, 'utf-8');
        const styleTag = `<style id="dubstudio-core-css">\n${cssContent}\n</style>`;
        if (html.includes('id="dubstudio-core-css"')) {
          html = html.replace(/<style id="dubstudio-core-css">[\s\S]*?<\/style>/, styleTag);
        } else if (html.includes('</head>')) {
          html = html.replace('</head>', `  ${styleTag}\n</head>`);
        } else {
          html = styleTag + html;
        }
        fs.writeFileSync(htmlPath, html, 'utf-8');
        console.log(`[inline-css-plugin] Successfully inlined ${cssContent.length} chars of CSS into dist/index.html`);
      }
    },
  };
}

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    inlineCssPlugin(),
  ],
  base: '/',
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8765',
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://127.0.0.1:8765',
        ws: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: false,
    rollupOptions: {
      output: {
        entryFileNames: 'assets/[name].js',
        chunkFileNames: 'assets/[name].js',
        assetFileNames: 'assets/[name].[ext]',
      },
    },
  },
});
