import { beforeEach, describe, expect, it, vi } from 'vitest';

import { createBrowserSessionFetch } from './browserSessionFetch';


describe('browser session fetch transport', () => {
  beforeEach(() => {
    document.cookie = 'localos_csrf=; Max-Age=0; path=/';
    vi.stubEnv('VITE_BROWSER_COOKIE_AUTH_ENABLED', 'true');
  });

  it('adds credentials and CSRF only to same-origin mutations', async () => {
    document.cookie = 'localos_csrf=csrf-token; path=/';
    const baseFetch = vi.fn().mockResolvedValue(new Response('{}', { status: 200 }));
    const sessionFetch = createBrowserSessionFetch(baseFetch);

    await sessionFetch('/api/users/profile', { method: 'PUT', body: '{}' });

    expect(baseFetch).toHaveBeenCalledWith(
      '/api/users/profile',
      expect.objectContaining({
        credentials: 'include',
        headers: expect.objectContaining({ 'X-CSRF-Token': 'csrf-token' }),
      }),
    );
  });

  it('does not leak browser credentials or CSRF to external origins', async () => {
    document.cookie = 'localos_csrf=csrf-token; path=/';
    const baseFetch = vi.fn().mockResolvedValue(new Response('{}', { status: 200 }));
    const sessionFetch = createBrowserSessionFetch(baseFetch);

    await sessionFetch('https://provider.example/resource', { method: 'POST', body: '{}' });

    expect(baseFetch).toHaveBeenCalledWith(
      'https://provider.example/resource',
      expect.not.objectContaining({ credentials: 'include' }),
    );
    const requestOptions = baseFetch.mock.calls[0][1];
    expect(new Headers(requestOptions?.headers).has('X-CSRF-Token')).toBe(false);
  });

  it('keeps the original request untouched while the feature is disabled', async () => {
    vi.stubEnv('VITE_BROWSER_COOKIE_AUTH_ENABLED', 'false');
    const baseFetch = vi.fn().mockResolvedValue(new Response('{}', { status: 200 }));
    const sessionFetch = createBrowserSessionFetch(baseFetch);
    const options = { method: 'POST', headers: { Authorization: 'Bearer miniapp-token' } };

    await sessionFetch('/api/operator/mobile/action', options);

    expect(baseFetch).toHaveBeenCalledWith('/api/operator/mobile/action', options);
  });
});
