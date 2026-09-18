import { execFileSync } from 'node:child_process';
import { resolve } from 'node:path';


export const fixtureCommand = (...args: string[]) => {
  const repositoryRoot = resolve(process.cwd(), '..');
  const socialPublicationFixture = args.some((argument) => (
    argument === 'reset-social-publication-reconciliation'
    || argument === 'inspect-social-publication-reconciliation'
  ));
  const stagingContainer = process.env.JOURNEY_STAGING_CONTAINER;
  if (stagingContainer) {
    const dockerArgs = ['exec'];
    if (socialPublicationFixture) {
      dockerArgs.push('-e', 'LOCALOS_STAGING_FIXTURE_MODE=1');
    }
    dockerArgs.push(stagingContainer, 'python', '/app/scripts/staging_fixture_cli.py', ...args);
    return execFileSync('docker', [
      ...dockerArgs,
    ], { cwd: repositoryRoot, encoding: 'utf8' }).trim();
  }
  const nativeDatabaseUrl = process.env.JOURNEY_STAGING_DATABASE_URL;
  if (nativeDatabaseUrl) {
    let target: URL;
    try {
      target = new URL(nativeDatabaseUrl);
    } catch {
      throw new Error('Only an isolated native staging test database is allowed.');
    }
    if (!['postgresql:', 'postgres:'].includes(target.protocol)
      || !['127.0.0.1', '[::1]'].includes(target.hostname)
      || !/^\/localos_staging_[a-z0-9_]*test[a-z0-9_]*$/.test(target.pathname)
      || target.search || target.hash) {
      throw new Error('Only an isolated native staging test database is allowed.');
    }
    const fixtureEnv = { ...process.env };
    for (const key of ['PGHOSTADDR', 'PGSERVICE', 'PGSERVICEFILE', 'PGOPTIONS']) {
      delete fixtureEnv[key];
    }
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
          ...fixtureEnv,
          APP_ENV: 'staging',
          DATABASE_URL: nativeDatabaseUrl,
          ...(socialPublicationFixture ? { LOCALOS_STAGING_FIXTURE_MODE: '1' } : {}),
          PYTHON_DOTENV_DISABLED: '1',
          // Keep any caller-provided sitecustomize network guard first.
          PYTHONPATH: [process.env.PYTHONPATH, resolve(repositoryRoot, 'src'), repositoryRoot].filter(Boolean).join(':'),
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
      'exec', '-T',
      ...(socialPublicationFixture ? ['-e', 'LOCALOS_STAGING_FIXTURE_MODE=1'] : []),
      'app', 'python', '/app/scripts/staging_fixture_cli.py',
      ...args,
    ],
    { cwd: repositoryRoot, encoding: 'utf8' },
  ).trim();
};
