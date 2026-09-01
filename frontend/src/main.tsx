import { createRoot } from 'react-dom/client'
import App from './App.tsx'
import './index.css'

import { ErrorBoundary } from './components/ErrorBoundary';
import { installDomOwnershipGuard } from './lib/domOwnershipGuard';
import { installBrowserSessionFetch } from './lib/browserSessionFetch';

const CHUNK_RELOAD_STORAGE_KEY = 'localos_chunk_reload_attempted';
const TELEGRAM_CONTROL_PATH = '/telegram/control';
const TELEGRAM_SDK_URL = 'https://telegram.org/js/telegram-web-app.js?63';
const TELEGRAM_SDK_TIMEOUT_MS = 5_000;

installBrowserSessionFetch();

const isDynamicImportError = (message: string) =>
    /failed to fetch dynamically imported module|importing a module script failed|chunkloaderror|loading chunk/i.test(message);

const messageFromUnknown = (value: unknown) => {
    if (value instanceof Error) return value.message;
    if (typeof value === 'string') return value;
    return '';
};

const reloadAfterDynamicImportError = () => {
    if (sessionStorage.getItem(CHUNK_RELOAD_STORAGE_KEY) === '1') return;
    sessionStorage.setItem(CHUNK_RELOAD_STORAGE_KEY, '1');

    const nextUrl = new URL(window.location.href);
    nextUrl.searchParams.set('__localos_reload', String(Date.now()));
    window.location.replace(nextUrl.toString());
};

window.addEventListener('error', (event) => {
    const message = event.message || messageFromUnknown(event.error);
    if (isDynamicImportError(message)) {
        reloadAfterDynamicImportError();
    }
});

window.addEventListener('unhandledrejection', (event) => {
    const message = messageFromUnknown(event.reason);
    if (isDynamicImportError(message)) {
        reloadAfterDynamicImportError();
    }
});

if (new URL(window.location.href).searchParams.has('__localos_reload')) {
    window.setTimeout(() => {
        sessionStorage.removeItem(CHUNK_RELOAD_STORAGE_KEY);

        const cleanUrl = new URL(window.location.href);
        cleanUrl.searchParams.delete('__localos_reload');
        window.history.replaceState(window.history.state, '', cleanUrl.toString());
    }, 5000);
}


const rootElement = document.getElementById("root");
if (!rootElement) {
    throw new Error('LocalOS root element was not found.');
}

installDomOwnershipGuard(rootElement);

const renderApplication = () => {
    createRoot(rootElement).render(
        <ErrorBoundary>
            <App />
        </ErrorBoundary>
    );
};

const isTelegramControlRoute = () => window.location.pathname === TELEGRAM_CONTROL_PATH;

const loadTelegramSdk = () => new Promise<void>((resolve) => {
    if (window.Telegram?.WebApp) {
        resolve();
        return;
    }

    let settled = false;
    const finish = () => {
        if (settled) return;
        settled = true;
        window.clearTimeout(timeoutId);
        resolve();
    };
    const timeoutId = window.setTimeout(finish, TELEGRAM_SDK_TIMEOUT_MS);
    const existing = document.querySelector<HTMLScriptElement>(`script[src="${TELEGRAM_SDK_URL}"]`);
    const script = existing || document.createElement('script');
    script.addEventListener('load', finish, { once: true });
    script.addEventListener('error', finish, { once: true });
    if (!existing) {
        script.src = TELEGRAM_SDK_URL;
        script.async = true;
        script.dataset.localosTelegramSdk = 'true';
        document.head.appendChild(script);
    }
});

const startApplication = async () => {
    if (isTelegramControlRoute()) await loadTelegramSdk();
    renderApplication();
};

void startApplication();
