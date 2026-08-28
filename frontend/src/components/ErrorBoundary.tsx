import React, { Component, ErrorInfo, ReactNode } from 'react';
import { Button } from './ui/button';

const CHUNK_RELOAD_STORAGE_KEY = 'localos_chunk_reload_attempted';
const LANGUAGE_PROVIDER_VERSION_MISMATCH = 'useLanguage must be used within a LanguageProvider';

interface Props {
    children?: ReactNode;
    fallback?: ReactNode;
}

interface State {
    hasError: boolean;
    error: Error | null;
    errorInfo: ErrorInfo | null;
}

export class ErrorBoundary extends Component<Props, State> {
    public state: State = {
        hasError: false,
        error: null,
        errorInfo: null
    };

    public static getDerivedStateFromError(error: Error): State {
        return { hasError: true, error, errorInfo: null };
    }

    public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
        console.error('Uncaught error:', error, errorInfo);

        if (
            error.message === LANGUAGE_PROVIDER_VERSION_MISMATCH &&
            window.sessionStorage.getItem(CHUNK_RELOAD_STORAGE_KEY) !== '1'
        ) {
            window.sessionStorage.setItem(CHUNK_RELOAD_STORAGE_KEY, '1');
            const nextUrl = new URL(window.location.href);
            nextUrl.searchParams.set('__localos_reload', String(Date.now()));
            window.setTimeout(() => window.location.replace(nextUrl.toString()), 0);
            return;
        }

        this.setState({ error, errorInfo });
    }

    private handleReload = () => {
        window.location.reload();
    };

    public render() {
        if (this.state.hasError) {
            if (this.props.fallback) {
                return this.props.fallback;
            }

            return (
                <div className="min-h-screen flex items-center justify-center bg-gray-50 flex-col p-4">
                    <div className="bg-white p-8 rounded-lg shadow-md max-w-md w-full text-center">
                        <div className="text-4xl mb-4">😵</div>
                        <h1 className="text-2xl font-bold text-gray-900 mb-2">Что-то пошло не так</h1>
                        <p className="text-gray-600 mb-6">
                            Произошла ошибка при отрисовке интерфейса. Мы уже знаем о ней и работаем над исправлением.
                        </p>
                        {this.state.error && (
                            <div className="bg-red-50 text-red-700 p-3 rounded text-left text-xs font-mono mb-6 overflow-auto max-h-32">
                                {this.state.error.toString()}
                            </div>
                        )}
                        <div className="flex gap-4 justify-center">
                            <Button onClick={this.handleReload}>
                                Обновить страницу
                            </Button>
                            <Button variant="outline" onClick={() => window.location.href = '/'}>
                                На главную
                            </Button>
                        </div>
                    </div>
                </div>
            );
        }

        return this.props.children;
    }
}
