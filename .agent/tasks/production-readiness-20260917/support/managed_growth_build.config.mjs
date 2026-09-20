import { fileURLToPath } from 'node:url';
import appConfig from '../../../../frontend/vite.config.ts';

export default {
  ...appConfig,
  root: fileURLToPath(new URL('../../../../frontend/', import.meta.url)),
  envDir: false,
};
