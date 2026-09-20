import { fileURLToPath } from 'node:url';
import react from '../../../../frontend/node_modules/@vitejs/plugin-react-swc/index.js';

const frontend = fileURLToPath(new URL('../../../../frontend/', import.meta.url));
export default {
  root: frontend,
  envDir: false,
  plugins: [react()],
  resolve: { alias: { '@': `${frontend}src` } },
  test: {
    include: ['src/**/*.test.{ts,tsx}'],
    environment: 'jsdom',
    setupFiles: [`${frontend}src/test/setup.ts`],
    css: true,
    maxWorkers: 1,
  },
};
