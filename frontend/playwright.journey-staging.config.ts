import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './e2e/staging',
  timeout: 30_000,
  expect: { timeout: 7_000 },
  workers: 1,
  reporter: [['list']],
  use: {
    baseURL: process.env.JOURNEY_STAGING_BASE_URL || 'http://127.0.0.1:18000',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [
    { name: 'desktop', use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 1000 } } },
    { name: 'laptop', use: { ...devices['Desktop Chrome'], viewport: { width: 1024, height: 768 } } },
    { name: 'mobile', use: { ...devices['Pixel 7'], viewport: { width: 393, height: 852 } } },
  ],
});

