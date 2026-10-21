import type { TelegramWebApp } from '@/features/telegram/types';

type MaxWebApp = {
  initData?: string;
  initDataUnsafe?: { start_param?: string };
  BackButton?: TelegramWebApp['BackButton'];
  openLink?: (url: string) => void;
  openMaxLink?: (url: string) => void;
  downloadFile?: (url: string, filename: string) => void;
  PermissionsManager?: {
    init: () => Promise<void> | void;
    requestAccess: (permissions: string[], reason: string) => Promise<unknown>;
  };
};

declare global {
  interface Window { WebApp?: MaxWebApp }
}

export const miniAppPlatform = () => window.location.pathname.startsWith('/max/') ? 'max' : 'telegram';
export const miniAppPath = () => `/${miniAppPlatform()}/control`;
export const miniAppChannel = () => miniAppPlatform() === 'max' ? 'max_mini_app' : 'telegram_mini_app';
export const miniAppLabel = () => miniAppPlatform() === 'max' ? 'MAX' : 'Telegram';
export const miniAppSdkUrl = () => miniAppPlatform() === 'max'
  ? 'https://st.max.ru/js/max-web-app.js' : 'https://telegram.org/js/telegram-web-app.js?63';

export const miniAppLaunchParams = () => {
  const params = new URLSearchParams(window.location.search);
  const start = miniWebApp()?.initDataUnsafe?.start_param || params.get(miniAppPlatform() === 'max' ? 'WebAppStartParam' : 'tgWebAppStartParam');
  if (start?.startsWith('nav_') && start.length <= 512) {
    try {
      const encoded = start.slice(4).replace(/-/g, '+').replace(/_/g, '/');
      const navigation: unknown = JSON.parse(new TextDecoder().decode(Uint8Array.from(atob(encoded), character => character.charCodeAt(0))));
      if (navigation && typeof navigation === 'object') {
        for (const [key, value] of Object.entries(navigation)) {
          if (['screen', 'scope_type', 'scope_id', 'item_type', 'item_id'].includes(key) && typeof value === 'string' && !params.has(key)) params.set(key, value);
        }
      }
    } catch { /* Invalid navigation cannot grant access; open the default screen. */ }
  }
  return params;
};

export const miniWebApp = (): TelegramWebApp | undefined => {
  if (miniAppPlatform() === 'telegram') return window.Telegram?.WebApp;
  const max = window.WebApp;
  if (!max) return undefined;
  return { initData: max.initData, initDataUnsafe: max.initDataUnsafe, BackButton: max.BackButton };
};

export const downloadMiniAppFile = (url: string, filename: string): boolean => {
  if (miniAppPlatform() === 'max') {
    if (!window.WebApp?.downloadFile) throw new Error('Обновите MAX для скачивания файлов.');
    window.WebApp.downloadFile(url, filename);
    return true;
  }
  const telegram = window.Telegram?.WebApp;
  if (!telegram?.downloadFile || !telegram.isVersionAtLeast?.('8.0')) return false;
  telegram.downloadFile({ url, file_name: filename });
  return true;
};

const bridgeDeadline = <T,>(operation: Promise<T>) => new Promise<T>((resolve, reject) => {
  const timer = window.setTimeout(() => reject(new Error('MAX не ответил на запрос микрофона. Повторите или загрузите аудиофайл.')), 10000);
  operation.then(resolve, reject).finally(() => window.clearTimeout(timer));
});

export const requestMiniAppMicrophone = async () => {
  if (miniAppPlatform() !== 'max') return;
  const permissions = window.WebApp?.PermissionsManager;
  if (!permissions) throw new Error('Обновите MAX для записи голоса или загрузите аудиофайл.');
  try {
    await bridgeDeadline(Promise.resolve(permissions.init()));
    const info = await bridgeDeadline(permissions.requestAccess(['mic'], 'Для голосового поручения LocalOS'));
    if (info && typeof info === 'object') {
      if ('error' in info) throw new Error('Разрешите микрофон для LocalOS в настройках MAX и устройства, затем повторите.');
      if ('mic' in info && info.mic && typeof info.mic === 'object' &&
        (('appAccessGranted' in info.mic && info.mic.appAccessGranted === false) || ('systemAccessGranted' in info.mic && info.mic.systemAccessGranted === false))) {
        throw new Error('Разрешите микрофон для LocalOS в настройках MAX и устройства, затем повторите.');
      }
    }
  } catch (error) {
    if (error instanceof Error) throw error;
    throw new Error('Разрешите микрофон для LocalOS в настройках MAX и устройства, затем повторите.');
  }
};

export const openMiniAppLink = (url: string) => {
  if (miniAppPlatform() === 'max' && window.WebApp?.openLink) {
    if (url.startsWith('https://max.ru/') && window.WebApp.openMaxLink) window.WebApp.openMaxLink(url);
    else window.WebApp.openLink(url);
    return;
  }
  if (miniAppPlatform() === 'telegram' && url.startsWith('https://t.me/') && window.Telegram?.WebApp?.openTelegramLink) {
    window.Telegram.WebApp.openTelegramLink(url);
    return;
  }
  window.open(url, '_blank', 'noopener,noreferrer');
};

/** Only close after a deliberate, authorized handoff to the bot. */
export const closeMiniAppForBotHandoff = (): boolean => {
  if (miniAppPlatform() !== 'telegram' || !window.Telegram?.WebApp?.close) return false;
  try { window.Telegram.WebApp.close(); return true; } catch { return false; }
};

export const loadMiniAppSdk = () => new Promise<void>((resolve) => {
  if (miniWebApp()) { resolve(); return; }
  const url = miniAppSdkUrl();
  let settled = false;
  const finish = () => {
    if (settled) return;
    settled = true;
    window.clearTimeout(timeout);
    resolve();
  };
  const timeout = window.setTimeout(finish, 5000);
  const existing = document.querySelector<HTMLScriptElement>(`script[src="${url}"]`);
  const script = existing || document.createElement('script');
  script.addEventListener('load', finish, { once: true });
  script.addEventListener('error', finish, { once: true });
  if (!existing) { script.src = url; script.async = true; document.head.appendChild(script); }
});

export const safeCheckoutReturn = (value: string | null): string | null => {
  if (!value || value.length > 500 || !value.startsWith("/") || value.startsWith("//") || /[\\\x00-\x1f]/.test(value)) return null;
  const path = value.split(/[?#]/, 1)[0];
  return path.startsWith("/dashboard/") || path === "/telegram/control" || path === "/max/control" ? value : null;
};
