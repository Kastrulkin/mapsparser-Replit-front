import { EventEmitter } from 'node:events';
import { describe, expect, it } from 'vitest';
import { observeRuntimeErrors } from '../../e2e/staging/runtimeErrors';

const emitConsole = (page: EventEmitter, sourceUrl: string, type = 'error') => {
  page.emit('console', {
    type: () => type,
    location: () => ({ url: sourceUrl }),
    text: () => 'synthetic console failure',
  });
};

describe('staging runtime error observation', () => {
  it.each([
    ['http://127.0.0.1:18000', 'http://127.0.0.1:18000/assets/app.js'],
    ['http://127.0.0.1:38019', 'http://127.0.0.1:38019/assets/app.js'],
    ['http://127.0.0.1:45127', 'http://127.0.0.1:45127/api/finance'],
    ['http://localhost:38019/path/', 'http://localhost:38019/assets/app.js'],
    ['https://staging.example.invalid/dashboard', 'https://staging.example.invalid:443/assets/app.js'],
    ['http://[::1]:38019', 'http://[::1]:38019/assets/app.js'],
    ['http://127.0.0.1:38019', '/assets/app.js'],
    ['http://127.0.0.1:38019', 'blob:http://127.0.0.1:38019/synthetic-id'],
    ['http://127.0.0.1:38019', ''],
    ['http://127.0.0.1:38019', 'http://[malformed'],
    ['http://127.0.0.1:38019', 'data:text/javascript,console.error(1)'],
  ])('records first-party console errors for configured base %s and source %s', (baseURL, sourceUrl) => {
    const page = new EventEmitter();
    const errors = observeRuntimeErrors(page, baseURL);
    emitConsole(page, sourceUrl);
    expect(errors).toEqual(['synthetic console failure']);
  });

  it.each([
    'https://widget.example.invalid/widget.js',
    'http://127.0.0.1:18000/assets/app.js',
    'http://127.0.0.1:38019@foreign.example.invalid/app.js',
  ])('does not count known foreign origins: %s', (sourceUrl) => {
    const page = new EventEmitter();
    const errors = observeRuntimeErrors(page, 'http://127.0.0.1:38019');
    emitConsole(page, sourceUrl);
    expect(errors).toEqual([]);
  });

  it.each(['warn', 'log'])('does not turn %s messages into errors', (type) => {
    const page = new EventEmitter();
    const errors = observeRuntimeErrors(page, 'http://127.0.0.1:38019');
    emitConsole(page, '', type);
    expect(errors).toEqual([]);
  });

  it('always preserves uncaught page errors', () => {
    const page = new EventEmitter();
    const errors = observeRuntimeErrors(page, 'http://127.0.0.1:38019');
    page.emit('pageerror', new Error('uncaught synthetic exception'));
    expect(errors).toEqual(['uncaught synthetic exception']);
  });

  it.each([undefined, '', 'invalid', 'file:///tmp/staging.html'])('rejects invalid baseURL %s before adding listeners', (baseURL) => {
    const page = new EventEmitter();
    expect(() => observeRuntimeErrors(page, baseURL)).toThrow();
    expect(page.eventNames()).toEqual([]);
  });
});
