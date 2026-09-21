// Offline, value-free classification of frozen provider-debug findings.
// Reads Git objects as data; never executes captured HTML/JavaScript or URLs.
'use strict';
const fs = require('fs');
const cp = require('child_process');
const crypto = require('crypto');
const assert = require('assert/strict');
const evidence = '.agent/tasks/production-readiness-20260917/evidence/';
const privateDir = '/private/tmp/localos-git-history-verified-20260921.qZcoBF';
const metadata = JSON.parse(fs.readFileSync(evidence + 'git-all-refs-history-metadata-20260921.json'));
const reportBytes = fs.readFileSync(privateDir + '/history-redacted.json');
const hash = (bytes) => crypto.createHash('sha256').update(bytes).digest('hex');
assert.equal(hash(reportBytes), metadata.report_sha256, 'Frozen report digest mismatch');
const report = JSON.parse(reportBytes);
assert.equal(report.length, 711);
const selected = metadata.findings.filter((row) => row.file.startsWith('debug_data/'));
assert.equal(selected.length, 572);
const specs = [...new Set(selected.map((row) => row.commit + ':' + row.file))];
assert(specs.every((spec) => /^[a-f0-9]{40}:debug_data\/[A-Za-z0-9_./-]+$/.test(spec)));
const batch = cp.execFileSync('/usr/bin/git', ['cat-file', '--batch'], {
  input: specs.join('\n') + '\n', maxBuffer: 128 * 1024 * 1024,
  stdio: ['pipe', 'pipe', 'pipe'],
  env: {PATH: '/usr/bin:/bin', GIT_NO_REPLACE_OBJECTS: '1', GIT_CONFIG_NOSYSTEM: '1',
    GIT_CONFIG_GLOBAL: '/dev/null', GIT_TERMINAL_PROMPT: '0'},
});
const objects = new Map();
let offset = 0;
let totalBytes = 0;
for (const spec of specs) {
  const end = batch.indexOf(10, offset);
  assert(end >= offset, 'Missing object header');
  const header = batch.subarray(offset, end).toString('ascii').match(/^([a-f0-9]{40}) blob ([0-9]+)$/);
  assert(header, 'Unexpected object type or absent object; content withheld');
  const size = Number(header[2]);
  const bytes = batch.subarray(end + 1, end + 1 + size);
  assert.equal(bytes.length, size);
  const objectId = crypto.createHash('sha1').update(Buffer.from('blob ' + size + '\0')).update(bytes).digest('hex');
  assert.equal(objectId, header[1], 'Raw object digest mismatch');
  assert.equal(batch[end + 1 + size], 10);
  offset = end + size + 2;
  totalBytes += size;
  objects.set(spec, {bytes, blob: objectId, sha256: hash(bytes)});
}
assert.equal(offset, batch.length);
const values = new Map();
const rows = [];
for (const row of selected) {
  const finding = report[row.id - 1];
  assert(finding.Secret === 'REDACTED', 'Nonredacted report field; content withheld');
  assert.equal(finding.File, row.file);
  assert.equal(finding.Commit, row.commit);
  assert.equal(finding.StartLine, row.start_line);
  assert.equal(finding.EndLine, row.end_line);
  assert.equal(finding.RuleID, row.rule);
  const object = objects.get(row.commit + ':' + row.file);
  const text = object.bytes.toString('utf8');
  const line = text.split('\n')[row.start_line - 1];
  assert.equal(typeof line, 'string');
  const matches = [];
  if (finding.StartLine === finding.EndLine && finding.Match.split('REDACTED').length === 2) {
    // Binding uses the whole scanner match, not a guessed substring/column.
    for (const match of line.matchAll(/["']?([A-Za-z_][A-Za-z0-9_-]{0,50})["']?\s*[:=]\s*(["'])((?:\\.|[^"'\\])*)\2/g)) {
      if (match[3] && line.replaceAll(match[3], 'REDACTED').includes(finding.Match)) {
        matches.push({field: match[1], value: match[3]});
      }
    }
  }
  const candidates = [...new Map(matches.map((match) => [JSON.stringify([match.field, match.value]), match])).values()];
  let classification = 'UNKNOWN';
  let field = null;
  let valueLength = null;
  let typedPath = null;
  let equalityGroup = null;
  if (candidates.length === 1) {
    const candidate = candidates[0];
    if (candidate.field === 'hittoken' && row.file.endsWith('.json')) {
      let data = null;
      try { data = JSON.parse(text); } catch { /* Preserve unknown; no raw parse error. */ }
      if (typeof data?.settings?.hittoken === 'string' && data.settings.hittoken === candidate.value) {
        classification = 'HISTORICAL_PROVIDER_HITTOKEN_MATERIAL';
        typedPath = 'settings.hittoken';
      }
    } else if (candidate.field === 'aesKey' && row.file.endsWith('.html')) {
      classification = 'HISTORICAL_PROVIDER_HTML_AESKEY_MATERIAL';
    } else if (candidate.field === 'clientKey' && row.file.endsWith('.html')) {
      classification = 'HISTORICAL_PROVIDER_HTML_CLIENTKEY_MATERIAL';
    } else if (candidate.field === 'ordToken' && row.file.endsWith('.json')) {
      let data = null;
      try { data = JSON.parse(text); } catch { /* Preserve unknown. */ }
      const queue = [data];
      let found = false;
      while (queue.length) {
        const node = queue.pop();
        if (!node || typeof node !== 'object') continue;
        if (!Array.isArray(node) && node.ordToken === candidate.value) found = true;
        for (const child of Object.values(node)) {
          if (child && typeof child === 'object') queue.push(child);
        }
      }
      if (found) {
        classification = 'HISTORICAL_PROVIDER_ORDTOKEN_MATERIAL';
        typedPath = '**.ordToken';
      }
    }
    if (classification !== 'UNKNOWN') {
      field = candidate.field;
      valueLength = candidate.value.length;
      if (!values.has(candidate.value)) values.set(candidate.value, values.size + 1);
      equalityGroup = values.get(candidate.value);
    }
  }
  rows.push({id: row.id, blob: object.blob, source_sha256: object.sha256,
    classification, field, typed_path: typedPath, exact_match_binding: classification !== 'UNKNOWN',
    value_length: valueLength, equality_group: equalityGroup});
}
const counts = {};
for (const row of rows) counts[row.classification] = (counts[row.classification] || 0) + 1;
console.log(JSON.stringify({schema_version: 1, report_sha256: hash(reportBytes),
  git_read_environment: {GIT_NO_REPLACE_OBJECTS: '1', GIT_CONFIG_NOSYSTEM: '1',
    GIT_CONFIG_GLOBAL: '/dev/null', GIT_TERMINAL_PROMPT: '0', inherited_environment: false},
  support_sha256: hash(fs.readFileSync(__filename)),
  selected: selected.length, source_specs: specs.length, source_bytes: totalBytes,
  counts, distinct_classified_values: values.size, rows,
  limits: ['No non-secret clearance', 'No validity, expiry, privilege or provider-purpose proof',
    'No provider request, application execution, DB access, Docker, deletion or history rewrite',
    'Values and value hashes withheld; source hashes describe complete artifacts only'],
}, null, 2));
