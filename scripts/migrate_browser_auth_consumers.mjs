#!/usr/bin/env node

import { execFileSync } from 'node:child_process';
import { readFileSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';


const root = new URL('../', import.meta.url);
const frontendRoot = new URL('frontend/src/', root);
const matches = execFileSync(
  'rg',
  [
    '-l',
    String.raw`(?:window\.)?localStorage\.getItem\(['"](?:auth_token|token)['"]\)`,
    fileURLToPath(frontendRoot),
    '--glob',
    '!**/*.test.*',
  ],
  { encoding: 'utf8' },
).trim().split('\n').filter(Boolean);

const centralFiles = new Set([
  fileURLToPath(new URL('frontend/src/lib/auth_new.ts', root)),
  fileURLToPath(new URL('frontend/src/lib/browserSessionFetch.ts', root)),
]);

const importPattern = /import\s*\{([^}]*)\}\s*from\s*(['"])([^'"]*browserSessionFetch)\2;/m;
const tokenReadPattern = /(?:window\.)?localStorage\.getItem\((['"])(?:auth_token|token)\1\)/g;

for (const file of matches) {
  if (centralFiles.has(file)) continue;
  const original = readFileSync(file, 'utf8');
  let updated = original.replace(tokenReadPattern, 'browserBearerToken()');
  updated = updated.replace(/browserBearerToken\(\)\s*\|\|\s*browserBearerToken\(\)/g, 'browserBearerToken()');
  if (updated === original) continue;

  const existingImport = updated.match(importPattern);
  if (existingImport) {
    const names = existingImport[1].split(',').map((name) => name.trim()).filter(Boolean);
    if (!names.includes('browserBearerToken')) names.push('browserBearerToken');
    updated = updated.replace(importPattern, `import { ${names.join(', ')} } from ${existingImport[2]}${existingImport[3]}${existingImport[2]};`);
  } else {
    updated = `import { browserBearerToken } from '@/lib/browserSessionFetch';\n${updated}`;
  }
  writeFileSync(file, updated);
}

process.stdout.write(`Migrated ${matches.filter((file) => !centralFiles.has(file)).length} browser auth consumer files.\n`);
