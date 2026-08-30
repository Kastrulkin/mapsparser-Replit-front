import { beforeEach, describe, expect, it, vi } from 'vitest';

import { NewAuth } from './auth_new';
import { browserAuthenticationAvailable } from './browserSessionFetch';


const jsonResponse = (payload: object) =>
  new Response(JSON.stringify(payload), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  });


describe('browser cookie authentication', () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.sessionStorage.clear();
    document.cookie = 'localos_csrf=; Max-Age=0; path=/';
    vi.restoreAllMocks();
    vi.stubEnv('VITE_BROWSER_COOKIE_AUTH_ENABLED', 'true');
  });

  it('treats an HttpOnly browser session as available without exposing its token', () => {
    expect(browserAuthenticationAvailable(null)).toBe(true);
    expect(browserAuthenticationAvailable('mini-app-token')).toBe(true);
  });

  it('still requires a bearer token when browser cookie auth is disabled', () => {
    vi.stubEnv('VITE_BROWSER_COOKIE_AUTH_ENABLED', 'false');
    expect(browserAuthenticationAvailable(null)).toBe(false);
    expect(browserAuthenticationAvailable('mini-app-token')).toBe(true);
  });

  it('signs in with credentials without persisting the standard token', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({
        success: true,
        user: { id: 'user-1', email: 'cookie@example.com', name: 'Cookie user' },
        token: 'legacy-visible-token',
      }),
    );
    vi.stubGlobal('fetch', fetchMock);
    const auth = new NewAuth();

    const result = await auth.signIn('cookie@example.com', 'secret-password');

    expect(result.user?.id).toBe('user-1');
    expect(window.localStorage.getItem('auth_token')).toBeNull();
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/api/auth/login'),
      expect.objectContaining({ credentials: 'include' }),
    );
  });

  it('restores a browser session from the cookie without a JavaScript token', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({
        success: true,
        user: { id: 'user-1', email: 'cookie@example.com', session_kind: 'standard' },
        businesses: [{ id: 'business-1' }],
      }),
    );
    vi.stubGlobal('fetch', fetchMock);
    const auth = new NewAuth();

    const user = await auth.getCurrentUser();

    expect(user?.id).toBe('user-1');
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/api/auth/me'),
      expect.objectContaining({ credentials: 'include' }),
    );
  });

  it('adds the double-submit CSRF token to mutating requests', async () => {
    document.cookie = 'localos_csrf=csrf-token; path=/';
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ success: true }));
    vi.stubGlobal('fetch', fetchMock);
    const auth = new NewAuth();

    await auth.makeRequest('/auth/logout', { method: 'POST' });

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/api/auth/logout'),
      expect.objectContaining({
        credentials: 'include',
        headers: expect.objectContaining({ 'X-CSRF-Token': 'csrf-token' }),
      }),
    );
  });
});
