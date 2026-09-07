import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

// 子路径部署支持：构建时传 VITE_BASE_PATH（如 /yhj/checkin/），默认根路径。
function resolveBase(): string {
  const raw = process.env.VITE_BASE_PATH || '/';
  if (raw === '/') return '/';
  const base = raw.startsWith('/') ? raw : `/${raw}`;
  return base.endsWith('/') ? base : `${base}/`;
}

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');

  return {
    base: resolveBase(),
    plugins: [react()],
    server: {
      host: '127.0.0.1',
      proxy: {
        '/api': env.VITE_API_PROXY_TARGET || 'http://127.0.0.1:8000',
      },
    },
    test: {
      environment: 'jsdom',
      globals: true,
      setupFiles: ['./src/test/setup.ts'],
      css: true,
      restoreMocks: true,
    },
  };
});
