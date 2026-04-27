#!/bin/bash
# Скрипт для очистки ненужных файлов на сервере
# Безопасно удаляет только временные и кеш-файлы

set -e

echo "🧹 Очистка ненужных файлов на сервере"
echo "========================================"
echo ""

cd /opt/seo-app || {
    echo "❌ Директория проекта не найдена!"
    exit 1
}

# Показываем размер ДО очистки
echo "📊 Размер проекта ДО очистки:"
du -sh . 2>/dev/null
echo ""

# 1. Очистка Python кешей
echo "🗑️  1. Очистка Python кешей (__pycache__, *.pyc)..."
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -type f -name "*.pyc" -delete 2>/dev/null || true
find . -type f -name "*.pyo" -delete 2>/dev/null || true
echo "   ✅ Python кеши удалены"
echo ""

# 2. Очистка старых бэкапов БД (оставляем только последние 5)
echo "🗑️  2. Очистка старых бэкапов БД..."
if [ -d "db_backups" ]; then
    cd db_backups
    BACKUP_COUNT=$(ls -1 *.backup 2>/dev/null | wc -l)
    if [ "$BACKUP_COUNT" -gt 5 ]; then
        # Удаляем все кроме последних 5
        ls -t *.backup 2>/dev/null | tail -n +6 | xargs rm -f 2>/dev/null || true
        echo "   ✅ Удалены старые бэкапы (оставлено последних 5)"
    else
        echo "   ℹ️  Бэкапов меньше 5, ничего не удалено"
    fi
    cd ..
fi
echo ""

# 3. Очистка логов
echo "🗑️  3. Очистка логов..."
# Логи проекта
find . -type f -name "*.log" -not -path "./.git/*" -delete 2>/dev/null || true
# Логи в /tmp
> /tmp/seo_main.out 2>/dev/null || true
> /tmp/seo_worker.out 2>/dev/null || true
echo "   ✅ Логи очищены"
echo ""

# 4. Очистка node_modules/.cache (если есть)
echo "🗑️  4. Очистка кешей npm..."
if [ -d "frontend/node_modules/.cache" ]; then
    rm -rf frontend/node_modules/.cache
    echo "   ✅ Удален node_modules/.cache"
fi
if [ -d "frontend/.vite" ]; then
    rm -rf frontend/.vite
    echo "   ✅ Удален frontend/.vite"
fi
npm cache clean --force 2>/dev/null || true
echo ""

# 5. Очистка временных файлов
echo "🗑️  5. Очистка временных файлов..."
# Временные JSON файлы тестов
find . -type f -name "test_*.json" -not -path "./.git/*" -delete 2>/dev/null || true
# Временные файлы в корне
rm -f tmp 2>/dev/null || true
rm -f *.tmp 2>/dev/null || true
echo "   ✅ Временные файлы удалены"
echo ""

# 6. Проверка дублирующих фронтенд-сборок
echo "🗑️  6. Проверка сборок фронтенда..."
if [ -d "frontend/dist" ]; then
    DIST_SIZE=$(du -sh frontend/dist 2>/dev/null | cut -f1)
    echo "   ℹ️  Канонический dist: frontend/dist ($DIST_SIZE)"
fi
for legacy_dir in dist tmp_frontend_dist tmp_frontend_dist_fix; do
    if [ -d "$legacy_dir" ]; then
        LEGACY_SIZE=$(du -sh "$legacy_dir" 2>/dev/null | cut -f1)
        echo "   ⚠️  Найден legacy-каталог: $legacy_dir ($LEGACY_SIZE)"
    fi
done
echo ""

# 7. Очистка старых uploads (если есть)
echo "🗑️  7. Очистка старых загрузок..."
if [ -d "uploads" ]; then
    # Удаляем файлы старше 30 дней
    find uploads -type f -mtime +30 -delete 2>/dev/null || true
    echo "   ✅ Удалены файлы старше 30 дней"
fi
echo ""

# 8. Показываем что занимает больше всего места
echo "📊 Топ-10 самых больших директорий:"
du -sh */ .* 2>/dev/null | sort -h | tail -10
echo ""

# Показываем размер ПОСЛЕ очистки
echo "📊 Размер проекта ПОСЛЕ очистки:"
du -sh . 2>/dev/null
echo ""

echo "✅ Очистка завершена!"
echo ""
echo "💡 Рекомендации:"
echo "   - Если node_modules очень большой (>500MB), можно переустановить:"
echo "     cd frontend && rm -rf node_modules && npm install"
echo "   - Если .git большой, можно почистить историю (осторожно!)"
echo "   - Проверьте размер БД: ls -lh src/reports.db"
