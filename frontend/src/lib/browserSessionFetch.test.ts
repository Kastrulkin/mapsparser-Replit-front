import { beforeEach, describe, expect, it, vi } from 'vitest';

import { clearLegacyBrowserCredentials, createBrowserSessionFetch } from './browserSessionFetch';


describe('browser session fetch transport', () => {
  beforeEach(() => {
    document.cookie = 'localos_csrf=; Max-Age=0; path=/';
    window.localStorage.clear();
    window.sessionStorage.clear();
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

  it('removes empty and non-empty legacy browser bearer headers from cookie requests', async () => {
    const baseFetch = vi.fn().mockResolvedValue(new Response('{}', { status: 200 }));
    const sessionFetch = createBrowserSessionFetch(baseFetch);

    await sessionFetch('/api/dashboard', { headers: { Authorization: 'Bearer null' } });
    await sessionFetch('/api/dashboard', { headers: { Authorization: 'Bearer legacy-browser-token' } });

    expect(new Headers(baseFetch.mock.calls[0][1]?.headers).has('Authorization')).toBe(false);
    expect(new Headers(baseFetch.mock.calls[1][1]?.headers).has('Authorization')).toBe(false);
  });

  it('preserves only an explicit Mini App session bearer', async () => {
    window.sessionStorage.setItem('localos_mini_session', 'miniapp-token');
    const baseFetch = vi.fn().mockResolvedValue(new Response('{}', { status: 200 }));
    const sessionFetch = createBrowserSessionFetch(baseFetch);
    await sessionFetch('/api/operator/mobile/today', {
      headers: { Authorization: 'Bearer miniapp-token' },
    });
    const miniAppOptions = baseFetch.mock.calls[0][1];
    expect(new Headers(miniAppOptions?.headers).get('Authorization')).toBe('Bearer miniapp-token');
  });

  it('preserves an active demo session bearer without retaining standard browser tokens', async () => {
    window.sessionStorage.setItem('localos_demo_mode', '1');
    window.localStorage.setItem('demo_auth_token', 'demo-token');
    window.localStorage.setItem('auth_token', 'legacy-browser-token');
    window.localStorage.setItem('token', 'legacy-browser-alias');
    const baseFetch = vi.fn().mockResolvedValue(new Response('{}', { status: 200 }));
    const sessionFetch = createBrowserSessionFetch(baseFetch);

    clearLegacyBrowserCredentials();
    await sessionFetch('/api/dashboard', { headers: { Authorization: 'Bearer demo-token' } });

    expect(window.localStorage.getItem('auth_token')).toBeNull();
    expect(window.localStorage.getItem('token')).toBeNull();
    expect(window.localStorage.getItem('demo_auth_token')).toBe('demo-token');
    expect(new Headers(baseFetch.mock.calls[0][1]?.headers).get('Authorization')).toBe('Bearer demo-token');
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
