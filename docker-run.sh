#!/bin/bash

# Скрипт для управления Docker контейнерами

case "$1" in
    "build")
        echo "🔨 Сборка Docker образа..."
        docker compose build
        ;;
    "up")
        echo "🚀 Запуск приложения..."
        docker compose up -d
        ;;
    "dev")
        echo "🛠️ Запуск в режиме разработки..."
        docker compose --profile dev up -d
        ;;
    "down")
        echo "🛑 Остановка контейнеров..."
        docker compose down
        ;;
    "logs")
        echo "📋 Просмотр логов..."
        docker compose logs -f
        ;;
    "restart")
        echo "🔄 Перезапуск приложения..."
        docker compose restart
        ;;
    "clean")
        echo "🧹 Очистка Docker ресурсов..."
        docker compose down -v
        docker system prune -f
        ;;
    "status")
        echo "📊 Статус контейнеров:"
        docker compose ps
        ;;
    *)
        echo "Использование: $0 {build|up|dev|down|logs|restart|clean|status}"
        echo ""
        echo "Команды:"
        echo "  build   - Собрать Docker образ"
        echo "  up      - Запустить приложение"
        echo "  dev     - Запустить в режиме разработки"
        echo "  down    - Остановить контейнеры"
        echo "  logs    - Просмотр логов"
        echo "  restart - Перезапустить приложение"
        echo "  clean   - Очистить Docker ресурсы"
        echo "  status  - Показать статус контейнеров"
        exit 1
        ;;
esac
