import { execFileSync } from 'node:child_process';
import { resolve } from 'node:path';


export const fixtureCommand = (...args: string[]) => {
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
