'use strict';

// Offline evidence preparation only. No checkout, refs, config, or source edits.
const fs = require('fs');
const path = require('path');
const cp = require('child_process');
const crypto = require('crypto');
const assert = require('assert');

process.env.GIT_NO_REPLACE_OBJECTS = '1';
process.env.GIT_CONFIG_NOSYSTEM = '1';
process.env.GIT_CONFIG_GLOBAL = '/dev/null';
process.env.GIT_TERMINAL_PROMPT = '0';

const root = process.cwd();
const privateDir = process.argv[2];
const output = process.argv[3];
assert(privateDir && output, 'Expected private directory and manifest path');
const stat = fs.lstatSync(privateDir);
assert(stat.isDirectory() && !stat.isSymbolicLink());
assert.strictEqual(stat.mode & 0o077, 0, 'Private directory must exclude group/other');
const git = args => cp.execFileSync('/usr/bin/git', args, {
  cwd: root, maxBuffer: 64 * 1024 * 1024,
});
const string = args => git(args).toString('utf8').trim();
const sha256 = value => crypto.createHash('sha256').update(value).digest('hex');
const refText = string(['for-each-ref', '--format=%(objectname) %(objecttype) %(refname)']);
const refs = refText.split('\n').filter(Boolean).map(line => {
  const [oid, type, name] = line.split(' ');
  assert(/^[0-9a-f]{40}$/.test(oid));
  return { name, oid, type };
});
const head = string(['rev-parse', 'HEAD']);
const commits = new Set([head]);
const trees = new Set();
const unsupported = [];
for (const ref of refs) {
  if (ref.type === 'commit') commits.add(ref.oid);
  else if (ref.type === 'tree') trees.add(ref.oid);
  else if (ref.type === 'tag') {
    const peeled = string(['rev-parse', ref.oid + '^{}']);
    const type = string(['cat-file', '-t', peeled]);
    if (type === 'commit') commits.add(peeled);
    else if (type === 'tree') trees.add(peeled);
    else unsupported.push({ ...ref, peeled, peeledType: type });
  } else unsupported.push(ref);
}
assert.strictEqual(unsupported.length, 0, 'Uncovered ref object type');
const commitTips = [...commits].sort();
const reachableText = string(['rev-list', ...commitTips]);
const reachableCommits = reachableText.split('\n').filter(Boolean).sort();
const commitObjects = new Set(string([
  'rev-list', '--objects', '--no-object-names', ...commitTips,
]).split('\n').filter(Boolean));
const treeBlobs = new Map();
for (const tree of [...trees].sort()) {
  const entries = git(['ls-tree', '-r', '-z', tree]).toString('utf8').split('\0').filter(Boolean);
  for (const entry of entries) {
    const tab = entry.indexOf('\t');
    const [mode, type, oid] = entry.slice(0, tab).split(' ');
    const file = entry.slice(tab + 1);
    if (type !== 'blob') continue;
    const locations = treeBlobs.get(oid) || [];
    locations.push({ tree, mode, file });
    treeBlobs.set(oid, locations);
  }
}
// Materialize only tree-ref blobs not reachable from any scanned commit.
// Blob IDs are filenames; no historical path/symlink is followed or executed.
const snapshotDir = path.join(privateDir, 'tree-only-blobs');
fs.mkdirSync(snapshotDir, { mode: 0o700 });
const additionalBlobs = [];
for (const [oid, locations] of [...treeBlobs].sort()) {
  if (commitObjects.has(oid)) continue;
  assert(/^[0-9a-f]{40}$/.test(oid));
  const bytes = git(['cat-file', 'blob', oid]);
  const file = path.join(snapshotDir, oid);
  fs.writeFileSync(file, bytes, { mode: 0o600, flag: 'wx' });
  // Compute the raw Git object ID in-process: no hash-object filters can run.
  const blobId = crypto.createHash('sha1')
    .update(Buffer.from('blob ' + bytes.length + '\0')).update(bytes).digest('hex');
  assert.strictEqual(blobId, oid);
  additionalBlobs.push({ oid, bytes: bytes.length, sha256: sha256(bytes), locations });
}
const configPath = path.join(privateDir, 'scanner-defaults.toml');
const config = '[extend]\nuseDefault = true\n';
fs.writeFileSync(configPath, config, { mode: 0o600, flag: 'wx' });
const scannerPath = '/usr/local/bin/gitleaks';
const manifest = {
  schema_version: 1,
  captured_at: new Date().toISOString(),
  root, head, refs, commitTips,
  refInventorySha256: sha256(refText),
  shallow: string(['rev-parse', '--is-shallow-repository']),
  reachableCommitCount: reachableCommits.length,
  reachableCommitsSha256: sha256(reachableCommits.join('\n')),
  reachableCommitObjectCount: commitObjects.size,
  treeRefCount: refs.filter(ref => ref.type === 'tree').length,
  uniqueTreeRoots: [...trees].sort(),
  uniqueTreeBlobs: treeBlobs.size,
  additionalBlobs,
  snapshotDir, configPath, configSha256: sha256(config),
  scanner: {
    path: scannerPath,
    version: cp.execFileSync(scannerPath, ['version'], { encoding: 'utf8' }).trim(),
    sha256: sha256(fs.readFileSync(scannerPath)),
  },
  limits: [
    'Local refs frozen at capture time, including locally cached remote refs; no fetch.',
    'No reflog-only/unreachable objects or non-Git uncommitted/ignored files.',
    'Default scanner rules/allowlists retained; explicit ignore files/comments bypassed.',
    'No credential validation/revocation or production/image/log evidence.',
  ],
};
fs.writeFileSync(output, JSON.stringify(manifest, null, 2) + '\n', { mode: 0o600, flag: 'wx' });
console.log(JSON.stringify({
  manifest: output, head, refs: refs.length, commitTips: commitTips.length,
  reachableCommits: reachableCommits.length, treeRefs: manifest.treeRefCount,
  uniqueTreeRoots: trees.size, additionalBlobs: additionalBlobs.length,
  additionalBytes: additionalBlobs.reduce((sum, item) => sum + item.bytes, 0),
  scanner: manifest.scanner.version, shallow: manifest.shallow,
}, null, 2));
