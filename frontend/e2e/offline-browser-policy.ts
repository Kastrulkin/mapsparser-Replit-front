const allowedFrontendPorts = new Set(['4173', '4186', '4189', '4197']);

export const telegramSdkUrl = 'https://telegram.org/js/telegram-web-app.js?63';

export type OfflineRequestAction = 'allow' | 'stub-telegram-sdk' | 'block-api' | 'block-external';

export type OfflineRequestDecision = {
  action: OfflineRequestAction;
  safeUrl: string;
};

const safeUrl = (url: URL) => `${url.protocol}//${url.host}${url.pathname}`;

const decodedPathname = (url: URL) => {
  try {
    return decodeURIComponent(url.pathname);
  } catch {
    return url.pathname;
  }
};

const isApiPath = (url: URL) => {
  return url.pathname.startsWith('/api') || decodedPathname(url).startsWith('/api');
};

const parseBaseUrl = (baseURL: string) => {
  const url = new URL(baseURL);
  const isAllowedHost = url.hostname === '127.0.0.1' || url.hostname === 'localhost';
  if (url.protocol !== 'http:' || !isAllowedHost || !allowedFrontendPorts.has(url.port)) {
    throw new Error(`Offline browser guard requires a loopback frontend baseURL on an approved port, received ${safeUrl(url)}`);
  }
  return url;
};

export const createOfflineBrowserPolicy = (baseURL: string) => {
  const base = parseBaseUrl(baseURL);

  const isAllowedFrontendUrl = (url: URL) => {
    if (url.hostname !== base.hostname || url.port !== base.port) return false;
    return url.protocol === 'http:' || url.protocol === 'ws:';
  };

  return {
    decide(requestUrl: string): OfflineRequestDecision {
      const url = new URL(requestUrl);
      if (url.href === telegramSdkUrl) {
        return { action: 'stub-telegram-sdk', safeUrl: safeUrl(url) };
      }
      if (isApiPath(url)) {
        return { action: 'block-api', safeUrl: safeUrl(url) };
      }
      if (isAllowedFrontendUrl(url)) {
        return { action: 'allow', safeUrl: safeUrl(url) };
      }
      return { action: 'block-external', safeUrl: safeUrl(url) };
    },
  };
};
