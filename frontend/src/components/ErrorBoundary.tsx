import React, { Component, ErrorInfo, ReactNode } from 'react';
import { Button } from './ui/button';

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
        this.setState({ error, errorInfo });
    }

    private handleReload = () => {
        window.location.reload();
    };

    public render() {
        <p className="text-gray-600 mb-6">
            Произошла ошибка при отрисовке интерфейса. Мы уже знаем о ней и работаем над исправлением.
        </p>
        {
            this.state.error && (
                <div className="bg-red-50 text-red-700 p-3 rounded text-left text-xs font-mono mb-6 overflow-auto max-h-32">
                    {this.state.error.toString()}
                </div>
            )
        }
        <div className="flex gap-4 justify-center">
            <Button onClick={this.handleReload}>
                Обновить страницу
            </Button>
            <Button variant="outline" onClick={() => window.location.href = '/'}>
                На главную
            </Button>
        </div>
                    </div >
                </div >
            );
    }

        return this.props.children;
    }
}
