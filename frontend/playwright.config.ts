import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  timeout: 30_000,
  expect: { timeout: 5_000 },
  use: {
    baseURL: 'http://127.0.0.1:4173',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [
    { name: 'android-360', use: { ...devices['Galaxy S9+'], viewport: { width: 360, height: 800 } } },
    { name: 'telegram-393', use: { ...devices['Pixel 7'], viewport: { width: 393, height: 852 } } },
  ],
  webServer: {
    command: 'npm run dev -- --host 127.0.0.1 --port 4173',
    url: 'http://127.0.0.1:4173/telegram/control?preview=1',
    reuseExistingServer: true,
  },
});
