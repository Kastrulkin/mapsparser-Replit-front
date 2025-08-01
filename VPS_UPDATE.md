# 🔄 Инструкция по обновлению на VPS

## На VPS выполните следующие команды:

### 1. Перейдите в директорию проекта
```bash
cd /path/to/your/project  # замените на реальный путь к проекту
```

### 2. Проверьте статус git
```bash
git status
```

### 3. Обновите код с GitHub
```bash
git pull origin main
```

### 4. Перезапустите воркер
```bash
systemctl restart seo-worker
```

### 5. Проверьте статус воркера
```bash
systemctl status seo-worker
```

### 6. Проверьте логи воркера
```bash
journalctl -u seo-worker -f
```

## 🔍 Если возникают проблемы:

### Проверьте, что воркер запущен:
```bash
ps aux | grep worker.py
```

### Проверьте переменные окружения:
```bash
cat .env
```

### Проверьте права доступа:
```bash
ls -la
```

## ✅ После обновления система должна:

- Исправить ошибку "no tools or prompts"
- Работать с Hugging Face API
- Корректно выполнять AI-анализ
- Генерировать отчёты

## 📝 Что изменилось в этом обновлении:

1. **Исправлен model_config.py** - убрана ссылка на несуществующую модель
2. **Добавлена MCP конфигурация** для Hugging Face
3. **Улучшен AI-анализ** с использованием facebook/bart-base
4. **Добавлены тестовые файлы** для проверки системы

---

**Команда для быстрого обновления:**
```bash
cd /path/to/project && git pull origin main && systemctl restart seo-worker
``` 