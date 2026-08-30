import { execFileSync } from 'node:child_process';
import { resolve } from 'node:path';

import { expect, test } from '@playwright/test';


const OWNER_EMAIL = 'owner@localos-e2e.invalid';
const OWNER_PASSWORD = 'LocalOS-E2E-2026!';

const fixtureCommand = (...args: string[]) => {
  const repositoryRoot = resolve(process.cwd(), '..');
  const nativeDatabaseUrl = process.env.JOURNEY_STAGING_DATABASE_URL;
  if (nativeDatabaseUrl) {
    return execFileSync(
      '/usr/bin/arch',
      [
        '-arm64',
        resolve(repositoryRoot, 'venv/bin/python'),
        resolve(repositoryRoot, 'scripts/staging_fixture_cli.py'),
        ...args,
      ],
      {
        cwd: repositoryRoot,
        encoding: 'utf8',
        env: {
          ...process.env,
          APP_ENV: 'staging',
          DATABASE_URL: nativeDatabaseUrl,
          PYTHONPATH: `${resolve(repositoryRoot, 'src')}:${repositoryRoot}`,
        },
      },
    ).trim();
  }
  return execFileSync(
    'docker',
    [
      'compose', '-p', 'localos-staging',
      '-f', 'docker-compose.yml',
      '-f', 'docker-compose.staging.yml',
      'exec', '-T', 'app', 'python', '/app/scripts/staging_fixture_cli.py',
      ...args,
    ],
    { cwd: repositoryRoot, encoding: 'utf8' },
  ).trim();
};

const loginOwner = async (page: import('@playwright/test').Page) => {
  const response = await page.request.post('/api/auth/login', {
    data: { email: OWNER_EMAIL, password: OWNER_PASSWORD },
  });
  expect(response.status(), await response.text()).toBe(200);
};

test('partnership workspace summaries execute against PostgreSQL without type errors', async ({ page }) => {
  const businessId = fixtureCommand('owner-business-id');
  await loginOwner(page);

  const paths = [
    `/api/partnership/leads?business_id=${encodeURIComponent(businessId)}`,
    `/api/partnership/blockers-summary?business_id=${encodeURIComponent(businessId)}&window_days=30`,
    `/api/partnership/ralph-loop-summary?business_id=${encodeURIComponent(businessId)}&window_days=30`,
  ];

  for (const path of paths) {
    const response = await page.request.get(path);
    const body = await response.text();
    expect(response.status(), `${path}: ${body}`).toBe(200);
    expect(body).not.toMatch(/operator does not exist|text\s*=\s*uuid|LINE\s+\d+:/i);
  }
});
