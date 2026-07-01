import { createRoot } from 'react-dom/client'
import App from './App.tsx'
import './index.css'

import { ErrorBoundary } from './components/ErrorBoundary';

const CHUNK_RELOAD_STORAGE_KEY = 'localos_chunk_reload_attempted';

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


createRoot(document.getElementById("root")!).render(
    <ErrorBoundary>
        <App />
    </ErrorBoundary>
);
