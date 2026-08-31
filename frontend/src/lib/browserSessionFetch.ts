import { API_URL } from '../config/api';


const UNSAFE_METHODS = new Set(['POST', 'PUT', 'PATCH', 'DELETE']);
const LEGACY_BROWSER_TOKEN_KEYS = ['auth_token', 'token'];
let installed = false;


export const browserCookieAuthEnabled = () =>
  import.meta.env.VITE_BROWSER_COOKIE_AUTH_ENABLED === 'true';


export const browserAuthenticationAvailable = (bearerToken?: string | null): boolean =>
  Boolean(bearerToken) || browserCookieAuthEnabled();


export const browserCookieValue = (name: string): string => {
  if (typeof document === 'undefined') return '';
  const prefix = `${encodeURIComponent(name)}=`;
  const item = document.cookie.split('; ').find((value) => value.startsWith(prefix));
  return item ? decodeURIComponent(item.slice(prefix.length)) : '';
};


const storageValue = (kind: 'localStorage' | 'sessionStorage', key: string): string => {
  if (typeof window === 'undefined') return '';
  try {
    return window[kind].getItem(key) || '';
  } catch {
    return '';
  }
};


export const browserBearerToken = (): string => {
  if (typeof window === 'undefined') return '';
  if (storageValue('sessionStorage', 'localos_demo_mode') === '1') {
    return storageValue('localStorage', 'demo_auth_token');
  }
  if (browserCookieAuthEnabled()) return '';
  return storageValue('localStorage', 'auth_token') || storageValue('localStorage', 'token');
};


export const clearLegacyBrowserCredentials = (): void => {
  if (typeof window === 'undefined' || !browserCookieAuthEnabled()) return;
  for (const key of LEGACY_BROWSER_TOKEN_KEYS) {
    try {
      window.localStorage.removeItem(key);
    } catch {
      // Storage may be unavailable in a restricted browser context.
    }
  }
};


const explicitScopedBearer = (): string[] => {
  if (typeof window === 'undefined') return [];
  const miniSession = storageValue('sessionStorage', 'localos_mini_session');
  const demoSession = storageValue('sessionStorage', 'localos_demo_mode') === '1'
    ? storageValue('localStorage', 'demo_auth_token')
    : '';
  return [miniSession, demoSession].filter(Boolean);
};


const bearerToken = (value: string): string => {
  const match = value.match(/^Bearer\s+(.+)$/i);
  return match?.[1]?.trim() || '';
};


const requestUrl = (input: RequestInfo | URL): string => {
  if (typeof input === 'string') return input;
  if (input instanceof URL) return input.toString();
  return input.url;
};


const isLocalOsOrigin = (input: RequestInfo | URL): boolean => {
  if (typeof window === 'undefined') return false;
  try {
    const target = new URL(requestUrl(input), window.location.origin);
    const apiOrigin = new URL(API_URL || window.location.origin, window.location.origin).origin;
    return target.origin === window.location.origin || target.origin === apiOrigin;
  } catch {
    return false;
  }
};


const requestMethod = (input: RequestInfo | URL, init?: RequestInit): string => {
  if (init?.method) return init.method.toUpperCase();
  if (input instanceof Request) return input.method.toUpperCase();
  return 'GET';
};


const mergedHeaders = (input: RequestInfo | URL, init?: RequestInit): Record<string, string> => {
  const headers: Record<string, string> = {};
  if (input instanceof Request) {
    input.headers.forEach((value, key) => {
      headers[key] = value;
    });
  }
  new Headers(init?.headers).forEach((value, key) => {
    headers[key] = value;
  });
  return headers;
};


export const createBrowserSessionFetch = (baseFetch: typeof fetch): typeof fetch =>
  (input, init) => {
    if (!browserCookieAuthEnabled() || !isLocalOsOrigin(input)) {
      return baseFetch(input, init);
    }

    const headers = mergedHeaders(input, init);
    for (const key of Object.keys(headers)) {
      if (key.toLowerCase() !== 'authorization') continue;
      const token = bearerToken(headers[key] || '');
      if (!token || !explicitScopedBearer().includes(token)) delete headers[key];
    }
    if (UNSAFE_METHODS.has(requestMethod(input, init))) {
      const csrfToken = browserCookieValue('localos_csrf');
      if (csrfToken && !new Headers(headers).has('X-CSRF-Token')) {
        headers['X-CSRF-Token'] = csrfToken;
      }
    }

    return baseFetch(input, {
      ...init,
      credentials: 'include',
      headers,
    });
  };


export const installBrowserSessionFetch = (): void => {
  if (installed || !browserCookieAuthEnabled() || typeof window === 'undefined') return;
  clearLegacyBrowserCredentials();
  window.fetch = createBrowserSessionFetch(window.fetch.bind(window));
  installed = true;
};
