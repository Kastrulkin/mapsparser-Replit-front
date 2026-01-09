// API Configuration
// Определяет базовый URL для API запросов в зависимости от окружения

const getApiUrl = (): string => {
    // В продакшене используем текущий домен
    if (import.meta.env.PROD) {
        return window.location.origin;
    }

    // В разработке используем переменную окружения или localhost
    return import.meta.env.VITE_API_URL || 'http://localhost:8000';
};

export const API_URL = getApiUrl();

// Вспомогательная функция для создания полного URL эндпоинта
export const getApiEndpoint = (path: string): string => {
    // Убираем начальный слеш если он есть
    const cleanPath = path.startsWith('/') ? path : `/${path}`;
    return `${API_URL}${cleanPath}`;
};
