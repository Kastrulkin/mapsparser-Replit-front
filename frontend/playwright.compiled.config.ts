import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  timeout: 20_000,
  expect: { timeout: 5_000 },
  workers: 1,
  use: {
    baseURL: 'http://127.0.0.1:4186',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [
    { name: 'desktop-chromium', use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 960 } } },
    { name: 'telegram-393', use: { ...devices['Pixel 7'], viewport: { width: 393, height: 852 } } },
  ],
  webServer: {
    command: 'npm run dev -- --host 127.0.0.1 --port 4186',
    env: { VITE_COMPILED_SCRIPT_PREVIEW_ENABLED: 'true' },
    url: 'http://127.0.0.1:4186/telegram/control?preview=1',
    reuseExistingServer: false,
  },
});
