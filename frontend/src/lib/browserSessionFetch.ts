import { API_URL } from '../config/api';


const UNSAFE_METHODS = new Set(['POST', 'PUT', 'PATCH', 'DELETE']);
let installed = false;


export const browserCookieAuthEnabled = () =>
  import.meta.env.VITE_BROWSER_COOKIE_AUTH_ENABLED === 'true';


export const browserCookieValue = (name: string): string => {
  if (typeof document === 'undefined') return '';
  const prefix = `${encodeURIComponent(name)}=`;
  const item = document.cookie.split('; ').find((value) => value.startsWith(prefix));
  return item ? decodeURIComponent(item.slice(prefix.length)) : '';
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
      if (
        key.toLowerCase() === 'authorization'
        && /^Bearer(?:\s+(?:null|undefined))?\s*$/i.test(headers[key] || '')
      ) {
        delete headers[key];
      }
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
  window.fetch = createBrowserSessionFetch(window.fetch.bind(window));
  installed = true;
};
