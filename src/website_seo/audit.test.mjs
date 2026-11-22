import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { test } from 'node:test';
import { fileURLToPath } from 'node:url';

test('checks the supplied pages with the network disabled', () => {
  const blockNetwork = `
    import net from 'node:net';
    import http from 'node:http';
    import https from 'node:https';
    const deny = () => { throw new Error('Unexpected request from website audit'); };
    globalThis.fetch = net.Socket.prototype.connect = http.request = https.request = deny;
  `;
  const preload = 'data:text/javascript,' + encodeURIComponent(blockNetwork);
  const runner = fileURLToPath(new URL('./audit.mjs', import.meta.url));
  const pages = [
    {
      url: 'https://example.com/',
      html: '<meta name="robots" content="noindex"><h1>Пример</h1>',
    },
    {
      url: 'https://example.com/vanilla',
      html: `<html><head><title>Веганское ванильное мороженое в Бангкоке</title>
        <meta name="description" content="Попробуйте ванильное мороженое на растительной основе в Бангкоке. Узнайте, какие вкусы есть в меню и как сделать заказ с доставкой.">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <link rel="canonical" href="https://example.com/vanilla"></head>
        <body><h1>Ванильное мороженое</h1></body></html>`,
    },
  ];
  const result = spawnSync(process.execPath, ['--import', preload, runner], {
    input: JSON.stringify(pages),
    encoding: 'utf8',
    timeout: 12000,
  });
  assert.equal(result.status, 0, result.error?.message || result.stderr);
  const audited = JSON.parse(result.stdout);
  assert.deepEqual(audited.map(page => page.url), pages.map(page => page.url));
  const firstPageRules = audited[0].findings.map(finding => finding.rule);
  assert(firstPageRules.includes('core-robots-meta'));
  assert(firstPageRules.includes('core-title-present'));
  assert(!firstPageRules.includes('core-title-length'));
  assert.deepEqual(audited[1].findings, []);
});
