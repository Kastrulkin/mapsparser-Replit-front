# Используем Node.js для сборки фронтенда
FROM node:18-alpine AS frontend-builder

WORKDIR /app/frontend

# Копируем package.json и package-lock.json
COPY frontend/package*.json ./

# Устанавливаем зависимости
RUN npm ci --legacy-peer-deps

# Копируем исходный код фронтенда
COPY frontend/ ./

# Собираем фронтенд
RUN npm run build

# Используем Python для бэкенда
FROM python:3.11-slim

WORKDIR /app

# Устанавливаем системные зависимости
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Копируем requirements.txt и устанавливаем Python зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем исходный код бэкенда
COPY src/ ./src/

# Копируем собранный фронтенд
COPY --from=frontend-builder /app/frontend/dist ./static

# Копируем конфигурационные файлы
COPY nginx-config.conf ./
COPY update_server.sh ./

# Создаём пользователя для безопасности
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Открываем порт
EXPOSE 8000

# Запускаем приложение
CMD ["python", "src/main.py"]
