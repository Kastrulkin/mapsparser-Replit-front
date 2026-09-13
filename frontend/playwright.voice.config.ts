import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './e2e', testMatch: ['operator-request-history.spec.ts', 'work-journal.spec.ts'],
  timeout: 30_000, workers: 1, expect: { timeout: 8_000 },
  use: { baseURL: 'http://127.0.0.1:4189', trace: 'retain-on-failure', screenshot: 'only-on-failure' },
  projects: [
    { name: 'desktop', use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 960 } } },
    { name: 'mobile-360', use: { ...devices['Galaxy S9+'], viewport: { width: 360, height: 800 } } },
    { name: 'mobile-393', use: { ...devices['Pixel 7'], viewport: { width: 393, height: 852 } } },
  ],
  webServer: { command: 'npm run dev -- --host 127.0.0.1 --port 4189', url: 'http://127.0.0.1:4189', reuseExistingServer: false },
});
