import { defineConfig } from '@playwright/test';
export default defineConfig({
  testDir: './e2e', testMatch: 'promotion-review.spec.ts',
  outputDir: '/tmp/localos-site-review-20261119/playwright-results',
  reporter: [['list'], ['json', { outputFile: '/tmp/localos-site-review-20261119/browser-tests.json' }]],
  timeout: 30000, expect: { timeout: 7000 }, workers: 2,
  use: { baseURL: 'http://127.0.0.1:4178', screenshot: 'only-on-failure', trace: 'retain-on-failure' },
  projects: [
    { name: 'desktop', use: { viewport: { width: 1440, height: 1000 } } },
    { name: 'mobile', use: { viewport: { width: 360, height: 800 }, isMobile: true, hasTouch: true } },
  ],
});
