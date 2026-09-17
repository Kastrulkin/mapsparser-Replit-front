import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { execFileSync } from 'node:child_process';
import { fixtureCommand } from '../../e2e/staging/fixtureCommand';

vi.mock('node:child_process', () => {
  const run = vi.fn(() => 'fixture-ok\n');
  return { execFileSync: run, default: { execFileSync: run } };
});

describe('native staging fixture safety', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.stubEnv('JOURNEY_STAGING_CONTAINER', '');
    vi.stubEnv('JOURNEY_STAGING_DATABASE_URL', 'postgresql://tester@127.0.0.1:35417/localos_staging_test');
    vi.stubEnv('PYTHONPATH', '/tmp/test-no-egress-guard');
    vi.stubEnv('PGHOSTADDR', '192.0.2.8');
    vi.stubEnv('PGSERVICE', 'unrelated');
  });
  afterEach(() => vi.unstubAllEnvs());

  it('preserves the caller network guard and disables implicit dotenv loading', () => {
    expect(fixtureCommand('owner-business-id')).toBe('fixture-ok');
    expect(execFileSync).toHaveBeenCalledWith('/usr/bin/arch', expect.any(Array), expect.objectContaining({
      env: expect.objectContaining({
        PYTHONPATH: expect.stringMatching(/^\/tmp\/test-no-egress-guard:/),
        PYTHON_DOTENV_DISABLED: '1',
      }),
    }));
    const options = vi.mocked(execFileSync).mock.calls[0][2];
    expect(options?.env).not.toHaveProperty('PGHOSTADDR');
    expect(options?.env).not.toHaveProperty('PGSERVICE');
    expect(options?.env).not.toHaveProperty('PGSERVICEFILE');
    expect(options?.env).not.toHaveProperty('PGOPTIONS');
  });

  it.each([
    'postgresql://tester@production.example/localos_staging_test',
    'postgresql://tester@127.0.0.1/production',
    'postgresql://tester@127.0.0.1/localos_staging',
    'postgresql://tester@127.0.0.1/localos_staging_test?hostaddr=192.0.2.8',
    'postgresql://tester@127.0.0.1/localos_staging_test#ignored',
    'not-a-url',
  ])('rejects a non-isolated native target before starting Python: %s', (databaseUrl) => {
    vi.stubEnv('JOURNEY_STAGING_DATABASE_URL', databaseUrl);
    expect(() => fixtureCommand('reset-finance')).toThrow(/isolated native staging/i);
    expect(execFileSync).not.toHaveBeenCalled();
  });
});
