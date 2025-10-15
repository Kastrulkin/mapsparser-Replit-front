# 🐳 Docker Setup для SEO Bot

Этот проект теперь поддерживает Docker для упрощённого развёртывания и переноса.

## 🚀 Быстрый старт

### 1. Сборка и запуск
```bash
# Собрать образ
./docker-run.sh build

# Запустить приложение
./docker-run.sh up
```

### 2. Режим разработки
```bash
# Запустить с hot-reload для фронтенда
./docker-run.sh dev
```

## 📋 Доступные команды

| Команда | Описание |
|---------|----------|
| `./docker-run.sh build` | Собрать Docker образ |
| `./docker-run.sh up` | Запустить приложение |
| `./docker-run.sh dev` | Запустить в режиме разработки |
| `./docker-run.sh down` | Остановить контейнеры |
| `./docker-run.sh logs` | Просмотр логов |
| `./docker-run.sh restart` | Перезапустить приложение |
| `./docker-run.sh clean` | Очистить Docker ресурсы |
| `./docker-run.sh status` | Показать статус контейнеров |

## 🌐 Доступ к приложению

- **Основное приложение**: http://localhost:8000
- **Фронтенд в режиме разработки**: http://localhost:3000

## 📁 Структура Docker

```
├── Dockerfile              # Основной образ (Python + собранный фронтенд)
├── Dockerfile.frontend     # Образ для разработки фронтенда
├── docker-compose.yml      # Конфигурация сервисов
├── docker-run.sh          # Скрипт управления
└── .dockerignore          # Исключения для сборки
```

## 🔧 Конфигурация

### Переменные окружения
Создайте файл `.env` в корне проекта:
```env
# API настройки
API_BASE_URL=https://beautybot.pro/api
GIGACHAT_API_KEY=your_gigachat_key

# База данных
DATABASE_URL=your_database_url
```

### Порты
- **8000**: Основное приложение (Python + статический фронтенд)
- **3000**: Фронтенд в режиме разработки (только при `./docker-run.sh dev`)

## 🚀 Развёртывание на сервере

### 1. Копирование на сервер
```bash
# Скопировать проект на сервер
scp -r . user@server:/path/to/project/

# Или использовать git
git clone <repository>
```

### 2. Запуск на сервере
```bash
# На сервере
cd /path/to/project
./docker-run.sh build
./docker-run.sh up
```

### 3. Настройка Nginx (опционально)
```nginx
server {
    listen 80;
    server_name your-domain.com;
    
    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## 🛠️ Разработка

### Локальная разработка
```bash
# Запустить только фронтенд в режиме разработки
./docker-run.sh dev
```

### Изменения в коде
- **Фронтенд**: Изменения автоматически перезагружаются
- **Бэкенд**: Требуется пересборка образа

### Пересборка после изменений
```bash
./docker-run.sh down
./docker-run.sh build
./docker-run.sh up
```

## 🐛 Отладка

### Просмотр логов
```bash
./docker-run.sh logs
```

### Вход в контейнер
```bash
docker-compose exec seo-app bash
```

### Проверка статуса
```bash
./docker-run.sh status
```

## 🧹 Очистка

### Остановка и удаление контейнеров
```bash
./docker-run.sh down
```

### Полная очистка (включая образы)
```bash
./docker-run.sh clean
```

## ⚡ Преимущества Docker

1. **Портативность**: Работает одинаково на любой системе
2. **Изоляция**: Не влияет на системные зависимости
3. **Версионирование**: Легко откатиться к предыдущей версии
4. **Масштабируемость**: Простое горизонтальное масштабирование
5. **CI/CD**: Интеграция с системами автоматического развёртывания

## 🔄 Миграция с локальной разработки

Если у вас уже есть локальная версия:

1. **Остановите локальные сервисы**:
   ```bash
   pkill -f "python3 -m http.server"
   ```

2. **Соберите Docker образ**:
   ```bash
   ./docker-run.sh build
   ```

3. **Запустите в Docker**:
   ```bash
   ./docker-run.sh up
   ```

4. **Проверьте работу**: http://localhost:8000
