# SEO-анализатор страницы локального бизнеса на Яндекс.Картах

## Описание

Этот сервис позволяет автоматически проанализировать SEO-оптимизацию публичной карточки компании на Яндекс.Картах и получить рекомендации по улучшению. Вводится ссылка на карточку, на выходе — подробный HTML-отчёт.

## Возможности
- Парсинг публичных данных карточки (название, адрес, рейтинг, отзывы и др.)
- Оценка SEO-параметров
- Генерация красивого HTML-отчёта с рекомендациями
- Антибан: рандомизация User-Agent, поддержка прокси
- Веб-интерфейс для создания и просмотра отчётов
- Автоматическая обработка очереди запросов

## Установка

### Локальная разработка
1. Клонируйте репозиторий
2. Установите зависимости:
   ```bash
   pip install -r requirements.txt
   ```
3. Создайте файл `.env` в корне проекта:
   ```env
   SUPABASE_URL=https://your-project.supabase.co
   SUPABASE_KEY=your-supabase-anon-key
   ```
4. Создайте файл `frontend/.env`:
   ```env
   VITE_SUPABASE_URL=https://your-project.supabase.co
   VITE_SUPABASE_KEY=your-supabase-anon-key
   ```

### Установка Playwright
После установки зависимостей обязательно выполните:
```bash
python3 -m playwright install
```
Это скачает браузеры для Playwright.

## Запуск

### Бэкенд (воркер)
```bash
python src/worker.py
```

### Веб-интерфейс
```bash
cd frontend
npm install
npm run dev
```

## Деплой на сервер

### 1. Настройка systemd сервисов
Создайте файл `/etc/systemd/system/seo-worker.service`:
```ini
[Unit]
Description=SEO Worker Service
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/path/to/project
Environment=PATH=/path/to/project/venv/bin
LoadCredential=SUPABASE_URL:/etc/systemd/system/seo-worker.supabase_url
LoadCredential=SUPABASE_KEY:/etc/systemd/system/seo-worker.supabase_key
Environment="SUPABASE_URL=${CREDENTIALS_DIRECTORY}/SUPABASE_URL"
Environment="SUPABASE_KEY=${CREDENTIALS_DIRECTORY}/SUPABASE_KEY"
ExecStart=/path/to/project/venv/bin/python /path/to/project/src/worker.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### 2. Создание секретов
```bash
echo "https://your-project.supabase.co" > /etc/systemd/system/seo-worker.supabase_url
echo "your-supabase-anon-key" > /etc/systemd/system/seo-worker.supabase_key
chmod 600 /etc/systemd/system/seo-worker.supabase_*
```

### 3. Запуск сервиса
```bash
systemctl daemon-reload
systemctl enable seo-worker
systemctl start seo-worker
```

## Структура проекта
- `src/` — исходный код бэкенда
- `frontend/` — веб-интерфейс (React + Vite)
- `src/templates/` — шаблоны для HTML-отчёта
- `data/` — сохранённые отчёты

## Примечания
- Для работы требуется установленный Google Chrome.
- Если Яндекс.Карты требуют капчу — попробуйте сменить прокси или User-Agent.
- Воркер автоматически обрабатывает запросы из таблицы ParseQueue каждые 5 минут.

## TODO
- Улучшить алгоритм анализа и рекомендации
- Добавить массовую обработку ссылок
- Реализовать сравнение с конкурентами 