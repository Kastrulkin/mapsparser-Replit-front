// API Configuration
// Определяет базовый URL для API запросов в зависимости от окружения

const getApiUrl = (): string => {
    // В разработке можно переопределить через .env
    if (import.meta.env.VITE_API_URL) {
        return import.meta.env.VITE_API_URL;
    }

    // В продакшене используем текущий домен (относительный путь для корректной работы через Nginx)
    if (import.meta.env.PROD) {
        return window.location.origin;
    }

    // В локальной разработке - localhost
    return 'http://localhost:8000';
};

export const API_URL = getApiUrl();

// Вспомогательная функция для создания полного URL эндпоинта
export const getApiEndpoint = (path: string): string => {
    // Убираем начальный слеш если он есть
    const cleanPath = path.startsWith('/') ? path : `/${path}`;

    // Если API_URL это origin (например https://site.com), то просто соединяем
    if (API_URL.startsWith('http')) {
        // Убираем слеш в конце API_URL если он есть
        const cleanApiUrl = API_URL.endsWith('/') ? API_URL.slice(0, -1) : API_URL;
        return `${cleanApiUrl}${cleanPath}`;
    }

    // Если API_URL относительный (пустой или /api), то...
    // В данном случае мы всегда возвращаем полный URL из getApiUrl
    return `${API_URL}${cleanPath}`;
};
