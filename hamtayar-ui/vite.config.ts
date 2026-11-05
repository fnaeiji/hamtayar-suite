import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import { fileURLToPath } from 'node:url';
import { resolve } from 'node:path';
const root = fileURLToPath(new URL('.', import.meta.url));
export function codeApiTarget(value: string | undefined) {
  const url = new URL(value || 'http://127.0.0.1:8000');
  if (
    !['http:', 'https:'].includes(url.protocol) ||
    !['127.0.0.1', 'localhost', '[::1]'].includes(url.hostname) ||
    url.username ||
    url.password ||
    url.pathname !== '/' ||
    url.search ||
    url.hash
  )
    throw new Error('CGC_API_TARGET must be an explicit loopback HTTP(S) origin.');
  return url.origin;
}
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, root, '');
  const proxy = {
    '/code-api': {
      target: codeApiTarget(env.CGC_API_TARGET),
      changeOrigin: true,
      timeout: 30 * 60 * 1000,
      proxyTimeout: 30 * 60 * 1000,
      rewrite: (path: string) => path.replace(/^\/code-api/, '/api'),
    },
  };
  return {
    plugins: [react()],
    resolve: {
      alias: {
        react: resolve(root, 'node_modules/react'),
        'react-dom': resolve(root, 'node_modules/react-dom'),
        'lucide-react': resolve(root, 'node_modules/lucide-react'),
        cytoscape: resolve(root, 'node_modules/cytoscape'),
      },
    },
    server: {
      host: '127.0.0.1',
      port: 5174,
      strictPort: true,
      fs: { allow: [root, resolve(root, '../CGC/HamtayarDemo/frontend')] },
      proxy,
    },
    preview: { host: '127.0.0.1', port: 4173, strictPort: true, proxy },
    build: {
      rollupOptions: {
        input: {
          main: resolve(root, 'index.html'),
          code: resolve(root, 'code/index.html'),
        },
      },
    },
  };
});
