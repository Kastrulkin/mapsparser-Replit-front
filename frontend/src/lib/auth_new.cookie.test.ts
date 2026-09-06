import { beforeEach, describe, expect, it, vi } from 'vitest';

import { HttpError, NewAuth } from './auth_new';
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

  it('clears both legacy standard browser token keys in cookie mode', () => {
    window.localStorage.setItem('auth_token', 'legacy-token');
    window.localStorage.setItem('token', 'legacy-alias');

    new NewAuth();

    expect(window.localStorage.getItem('auth_token')).toBeNull();
    expect(window.localStorage.getItem('token')).toBeNull();
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

  it('keeps the bearer session after a transient profile request failure', async () => {
    vi.stubEnv('VITE_BROWSER_COOKIE_AUTH_ENABLED', 'false');
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')));
    const auth = new NewAuth();
    window.localStorage.setItem('auth_token', 'existing-session-token');

    const user = await auth.getCurrentUser();

    expect(user).toBeNull();
    expect(window.localStorage.getItem('auth_token')).toBe('existing-session-token');
  });

  it('clears the bearer session after an authenticated request returns 401', async () => {
    vi.stubEnv('VITE_BROWSER_COOKIE_AUTH_ENABLED', 'false');
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(
      JSON.stringify({ error: 'Недействительный токен' }),
      { status: 401, headers: { 'Content-Type': 'application/json' } },
    )));
    const auth = new NewAuth();
    window.localStorage.setItem('auth_token', 'expired-session-token');

    const user = await auth.getCurrentUser();

    expect(user).toBeNull();
    expect(window.localStorage.getItem('auth_token')).toBeNull();
  });

  it('preserves the HTTP status, server code, and message for a JSON API failure', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(
      JSON.stringify({ error: 'Конфликт версии', code: 'REVISION_CONFLICT' }),
      { status: 409, headers: { 'Content-Type': 'application/json' } },
    )));
    const auth = new NewAuth();

    await expect(auth.makeRequest('/operator/today/preference', { method: 'POST' })).rejects.toMatchObject({
      name: 'HttpError', status: 409, code: 'REVISION_CONFLICT', message: 'Конфликт версии',
    });
  });

  it('keeps the expired-session message and clears the bearer token on a typed 401 error', async () => {
    vi.stubEnv('VITE_BROWSER_COOKIE_AUTH_ENABLED', 'false');
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve(new Response(
      JSON.stringify({ error: 'Недействительный токен', code: 'TOKEN_EXPIRED' }),
      { status: 401, headers: { 'Content-Type': 'application/json' } },
    ))));
    const auth = new NewAuth();
    window.localStorage.setItem('auth_token', 'expired-session-token');

    await expect(auth.makeRequest('/operator/today')).rejects.toBeInstanceOf(HttpError);
    await expect(auth.makeRequest('/operator/today')).rejects.toMatchObject({ status: 401, code: 'TOKEN_EXPIRED', message: 'Сессия истекла. Войдите снова.' });
    expect(window.localStorage.getItem('auth_token')).toBeNull();
  });

  it('returns typed errors for non-JSON responses and network failures', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(new Response('upstream unavailable', {
      status: 502,
      headers: { 'Content-Type': 'text/plain' },
    })).mockRejectedValueOnce(new TypeError('Failed to fetch')));
    const auth = new NewAuth();

    await expect(auth.makeRequest('/operator/today')).rejects.toMatchObject({ name: 'HttpError', status: 502, code: 'INVALID_RESPONSE' });
    await expect(auth.makeRequest('/operator/today')).rejects.toMatchObject({ name: 'HttpError', status: null, code: 'NETWORK_ERROR', message: 'Ошибка соединения с сервером: Failed to fetch' });
  });

  it.each([403, 502])('retains status %s when a JSON response is malformed', async (status) => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve(new Response('{broken', {
      status, headers: { 'Content-Type': 'application/json' },
    }))));
    await expect(new NewAuth().makeRequest('/operator/today')).rejects.toMatchObject({
      name: 'HttpError', status, code: 'INVALID_RESPONSE',
    });
  });

  it('expires the session even when 401 has a malformed body', async () => {
    vi.stubEnv('VITE_BROWSER_COOKIE_AUTH_ENABLED', 'false');
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve(new Response('{broken', {
      status: 401, headers: { 'Content-Type': 'application/json' },
    }))));
    const auth = new NewAuth();
    window.localStorage.setItem('auth_token', 'expired-token');
    await expect(auth.makeRequest('/operator/today')).rejects.toMatchObject({ status: 401, message: 'Сессия истекла. Войдите снова.' });
    expect(window.localStorage.getItem('auth_token')).toBeNull();
  });
});
