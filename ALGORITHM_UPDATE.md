# 🔄 Алгоритм обновления проекта

## 📋 Четкий порядок действий для применения изменений

> 📖 **Связанная документация:**
> - [PORTS_AND_SERVICES.md](./PORTS_AND_SERVICES.md) — порты и сервисы проекта
> - [README.md](./README.md) — основное описание проекта
> - [docs/DOCKER_DEPLOY.md](./docs/DOCKER_DEPLOY.md) — запуск в Docker
> - [SERVER_UPDATE_SAFETY.md](./SERVER_UPDATE_SAFETY.md) — безопасность обновления на сервере

---

## 🐳 Запуск и обновление с Docker (локально и на VPS)

Если проект запускается через **Docker Compose** (контейнеры `postgres`, `app`, `worker`), порядок действий другой: не используются legacy systemd/venv-сценарии и внешний web-root. Ниже — единый сценарий для локального запуска и обновления на сервере.

### Каноническая раздача фронтенда

- Production source of truth для фронтенда: `/opt/seo-app/frontend/dist`
- Runtime path в `app` container: `/app/frontend/dist`
- `localos.pro` должен получать SPA только через Flask на `127.0.0.1:8000`
- Для hotfix фронтенда используйте:

```bash
cd /opt/seo-app
bash scripts/deploy_frontend_dist.sh
```

Старые пути вроде legacy web-root, `/opt/seo-app/dist` и `tmp_frontend_dist*` не должны участвовать в production deploy.

### Требования

- Установленные Docker и Docker Compose (v2: `docker compose`).
- В корне проекта опционально файл `.env` с переменными для Postgres (если не заданы — подставляются значения по умолчанию из `docker-compose.yml`).

### Первый запуск (локально или на сервере)

```bash
# Из корня проекта
cd "/path/to/project"   # замените на свой путь

# Сборка образов (включая фронтенд) и запуск в фоне
./scripts/docker-compose-build.sh up -d --build

# Дождаться готовности Postgres и приложения (миграции выполняются в entrypoint)
./scripts/docker-compose-build.sh ps
# postgres, app, worker — состояние "running"
```

**Проверка бэкенда:**

```bash
curl -s http://localhost:8000/health
# Ожидается ответ с состоянием сервиса
```

**Фронтенд при локальной разработке:** Docker Compose не поднимает фронтенд. Запускайте его на хосте:

```bash
cd frontend
npm install
npm run dev
# Открыть http://localhost:3000 — запросы к API проксируются на backend (порт 8000)
```

На продакшене фронтенд обычно собирают и раздают через Nginx (отдельная настройка на сервере; см. разделы ниже про обновление без Docker).

### Обновление кода (Docker)

После изменений в репозитории (например, `git pull`):

```bash
# Пересобрать образы (включая фронтенд — multi-stage build) и запустить контейнеры
./scripts/docker-compose-build.sh up -d --build

# При необходимости принудительно пересоздать контейнеры
./scripts/docker-compose-build.sh up -d --build --force-recreate
```

Фронтенд собирается внутри Docker (этап `frontend-builder` в Dockerfile) и копируется в образ `app`. Миграции БД (Flask-Migrate) применяются автоматически при старте контейнеров `app` и `worker`. Отдельно запускать `flask db upgrade` не нужно, если только не требуется выполнить миграции вручную (например, в отладочных целях):

```bash
./scripts/docker-compose-build.sh exec app flask db upgrade
```

**Пользователи, блокировка и верификация:** в таблице `users` используются флаги `is_active` (блокировка, по умолчанию TRUE), `is_verified` (верификация, по умолчанию TRUE) и `is_superadmin` (доступ ко всем бизнесам, по умолчанию FALSE). При `is_active = FALSE` логин возвращает **403** (account_blocked), `/api/auth/me` с валидным токеном тоже возвращает **403**. Код **401** — только для неверных кредов или отсутствующего/битого токена.

### Остановка (Docker)

```bash
./scripts/docker-compose-build.sh down
# Данные Postgres остаются в volume pgdata.
# Полное удаление с данными: ./scripts/docker-compose-build.sh down -v
```

### Когда какой способ использовать

| Сценарий | Способ |
|----------|--------|
| Локальная разработка с единым окружением (Postgres + app + worker) | **Docker**: `./scripts/docker-compose-build.sh up -d --build` + фронт `npm run dev` |
| Деплой на VPS с контейнерами | **Docker**: на сервере `git pull` и `./scripts/docker-compose-build.sh up -d --build` |
| Сервер без Docker (systemd, venv, Nginx) | **Legacy-only**: не использовать для текущего `localos.pro`; см. разделы ниже только как исторический контекст |

### Если Docker build падает (BuildKit / buildx)

Ошибки вида `failed to dial gRPC` и `header key "x-docker-expose-session-sharedkey" contains value with non-printable ASCII characters` связаны с **окружением Docker** (buildx builder), а не с кодом проекта. Подробно: [docs/DOCKER_DEPLOY.md](./docs/DOCKER_DEPLOY.md#если-docker-build-падает-buildkit--buildx).

**Recovery за 2–3 минуты** (из корня проекта):

```bash
# Сбросить buildx builder
docker buildx rm --all-inactive
docker buildx create --use
docker buildx inspect --bootstrap

# Пересобрать проект (скрипт использует DOCKER_BUILDKIT=0)
./scripts/docker-compose-build.sh up -d --build
```

**Диагностика** (чтобы убедиться, что причина в BuildKit): `DOCKER_BUILDKIT=0 docker compose build` — только для проверки, не для постоянного использования.

**Best practice:** после обновления Docker Desktop один раз сбросить buildx builder; при gRPC-ошибке на этапе build не менять код и Dockerfile — восстанавливать окружение по командам выше.

---

## 🔒 Безопасность обновления: Telegram-боты

### ⚠️ **ВАЖНО: Влияние обновления на ботов**

**Боты НЕ пострадают при обновлении, если:**
- Они работают через systemd сервисы (рекомендуется)
- Мы НЕ изменяли файлы ботов (`telegram_bot.py`, `telegram_reviews_bot.py`)
- Мы перезапускаем только Flask сервер (`main.py`), а не боты

**Боты нужно перезапустить, если:**
- Мы изменяли `telegram_bot.py` или `telegram_reviews_bot.py`
- Мы изменяли зависимости, которые используют боты
- Мы изменяли структуру БД, к которой обращаются боты

### ✅ **Проверка статуса ботов перед обновлением:**

```bash
# Проверить статус ботов
systemctl status telegram-bot telegram-reviews-bot

# Проверить логи ботов (последние 10 строк)
journalctl -u telegram-bot -n 10 --no-pager
journalctl -u telegram-reviews-bot -n 10 --no-pager

# Проверить процессы ботов
ps aux | grep "telegram_bot.py\|telegram_reviews_bot.py" | grep -v grep
```

### 1️⃣ Изменения в **Frontend** (React/TypeScript)

*При запуске через Docker фронтенд для разработки запускают на хосте (`npm run dev`); production deploy выполняется только через канонический Docker-путь из раздела выше. Старый non-Docker сценарий больше не является актуальным runbook и не должен использоваться.*

**⚠️ КРИТИЧЕСКИ ВАЖНО:** После **ЛЮБЫХ** изменений в `frontend/src/*` **ОБЯЗАТЕЛЬНО** пересобрать фронтенд и обновить канонический `frontend/dist`, иначе изменения не появятся в браузере!

#### Шаг 1: Пересобрать фронтенд
```bash
cd frontend
rm -rf dist  # ОБЯЗАТЕЛЬНО удалить старую сборку!
npm run build
```

#### Шаг 2: Проверить сборку
```bash
ls -lh dist/assets/index-*.js
# Должен быть свежий файл с текущей датой и временем
# Если дата старая - сборка не прошла или используется старый файл
```

#### Шаг 3: Автоматическое обновление (РЕКОМЕНДУЕТСЯ)
Вместо legacy server-update wrapper используйте канонический deploy-скрипт. Он собирает фронтенд, синхронизирует `/opt/seo-app/frontend/dist` и проверяет live runtime path `/app/frontend/dist`.

```bash
cd /opt/seo-app
bash scripts/deploy_frontend_dist.sh --build
```

**Почему именно так?**
- `npm run build` обновляет локальный `frontend/dist`, но прод использует bind mount `/opt/seo-app/frontend/dist -> /app/frontend/dist`.
- Скрипт синхронизирует именно канонический dist и проверяет live HTML внутри контейнера.
- Старые пути legacy web-root, `/opt/seo-app/dist` и `tmp_frontend_dist*` не участвуют в production deploy.

#### Шаг 4 (опционально): Если скрипт недоступен — ручное обновление
Если нужно обновить вручную, не пропускайте синхронизацию в канонический dist:
```bash
cd /opt/seo-app/frontend
npm run build
cd /opt/seo-app
bash scripts/verify_frontend_dist_integrity.sh frontend/dist
docker cp frontend/dist/. seo-app-app-1:/app/frontend/dist/
docker compose exec -T app sh -lc 'grep -n "/assets/index-" /app/frontend/dist/index.html'
```

#### Шаг 5: Очистить кеш браузера

#### Шаг 4: Проверить сервер
```bash
lsof -iTCP:8000 -sTCP:LISTEN
# Должен показать процесс на порту 8000

# Или использовать команду из PORTS_AND_SERVICES.md
lsof -i :8000  # Бэкенд API
```

#### Шаг 5: Очистить кеш браузера
- **Жесткая перезагрузка:** **Cmd+Shift+R** (Mac) или **Ctrl+Shift+R** (Windows/Linux)
- **Или режим инкогнито:** **Cmd+Shift+N**
- **Или очистить кеш вручную:** DevTools → Network → Disable cache

---

### 2️⃣ Изменения в **Backend** (Python/Flask)

*При запуске через Docker перезапуск — через `./scripts/docker-compose-build.sh up -d --build` или `./scripts/docker-compose-build.sh restart app worker` (см. раздел «Запуск и обновление с Docker»). Ниже — порядок для деплоя без Docker (systemd, venv).*

**⚠️ КРИТИЧЕСКИ ВАЖНО:** После **ЛЮБЫХ** изменений в файлах `src/*.py` (включая `main.py`, `database_manager.py`, `auth_system.py`, `worker.py` и т.д.) **ОБЯЗАТЕЛЬНО** перезапустить процессы, иначе изменения не применятся!

**🔒 БЕЗОПАСНОСТЬ:** При перезапуске Flask сервера **НЕ трогаем Telegram-ботов**! Они работают как отдельные systemd сервисы и должны продолжать работать.

**⚠️ КРИТИЧЕСКИ ВАЖНО:** Перед обновлением на сервере **ОБЯЗАТЕЛЬНО** убедиться, что изменения запушены на GitHub и обновлены на сервере через `git pull`!

#### Шаг 1: Проверить, что изменения запушены на GitHub (локально)
```bash
# Проверить статус git
git status
# Должно быть "Your branch is up to date with 'origin/main'"

# Если есть незапушенные коммиты - запушить:
git push origin main
```

#### Шаг 2: Обновить код на сервере (если на сервере)
```bash
# На сервере: получить последние изменения
cd /opt/seo-app
git pull origin main

# ⚠️ КРИТИЧЕСКИ ВАЖНО: Проверить, что код действительно обновился!
# Проверить последний коммит:
git log --oneline -1
# Должен быть последний коммит с исправлениями

# Или проверить конкретный файл (если знаешь, что изменилось):
grep -A 5 "def get_business_by_id" src/database_manager.py
# Должен быть актуальный код
```

#### Шаг 3: Проверить статус ботов (если на сервере)
```bash
# На сервере: проверить, что боты работают
systemctl status telegram-bot telegram-reviews-bot
# Должны быть "active (running)"
```

#### Шаг 4: Перезапуск контейнеров

На текущем production runtime используйте Docker Compose:

```bash
cd /opt/seo-app
docker compose restart app
docker compose restart worker
```

Если задача связана только с frontend deploy, используйте канонический:

```bash
cd /opt/seo-app
bash scripts/deploy_frontend_dist.sh --build
```

**⚠️ ВАЖНО:** Сервиса с именем `mapsparser` не существует! Используйте `seo-api`.

#### Шаг 5: Запустить новый процесс Flask
```bash
cd "/path/to/project"  # Замени на свой путь
source venv/bin/activate
python src/main.py >/tmp/seo_main.out 2>&1 &
sleep 3
```

#### Шаг 6: Проверить запуск Flask
```bash
# Проверка порта
lsof -iTCP:8000 -sTCP:LISTEN
# Должен показать новый процесс с новым PID

# Проверка логов на ошибки
tail -20 /tmp/seo_main.out | grep -E "ERROR|Traceback|AssertionError" || tail -10 /tmp/seo_main.out
# Должно быть "SEO анализатор запущен на порту 8000" без ошибок
```

#### Шаг 7: Если есть worker - запустить его тоже
```bash
python src/worker.py >/tmp/seo_worker.out 2>&1 &
sleep 2
ps aux | grep "python.*worker" | grep -v grep
```

#### Шаг 8: Проверить, что боты всё ещё работают (если на сервере)
```bash
# На сервере: проверить статус ботов после перезапуска Flask
systemctl status telegram-bot telegram-reviews-bot
# Должны быть "active (running)" - боты не должны были остановиться!

# Если боты остановились (не должно быть), перезапустить их:
# systemctl restart telegram-bot telegram-reviews-bot
```

#### Шаг 9: Если изменялась БД - очистить старые сессии
```bash
sqlite3 src/reports.db "DELETE FROM UserSessions WHERE user_id = (SELECT id FROM Users WHERE email='ВАШ_EMAIL');"
```

#### Шаг 10: Выйти и войти заново в браузере
- Старые сессии могут содержать устаревшие данные

---

### 3️⃣ Изменения в **Базу данных**

**🔒 БЕЗОПАСНОСТЬ:** Миграции БД **НЕ влияют** на работу Telegram-ботов, если мы не изменяли таблицы, к которым они обращаются. Боты продолжат работать во время миграции.

#### Шаг 1: Проверить статус ботов (если на сервере)
```bash
# На сервере: убедиться, что боты работают
systemctl status telegram-bot telegram-reviews-bot
```

#### Шаг 2: Создать бэкап
```bash
python src/safe_db_utils.py
# Или вручную:
cp src/reports.db db_backups/reports_$(date +%Y%m%d_%H%M%S).db.backup
```

#### Шаг 3: Применить миграцию
```bash
python src/migrate_wizard_data_safe.py
# Или другую миграцию (например, migrate_workflow_agents.py)
```

#### Шаг 4: Проверить данные
```bash
sqlite3 src/reports.db "SELECT COUNT(*) FROM Businesses;"
```

#### Шаг 5: Проверить, что боты всё ещё работают (если на сервере)
```bash
# На сервере: проверить статус ботов после миграции
systemctl status telegram-bot telegram-reviews-bot
# Должны быть "active (running)"
```

#### Шаг 6: Если изменялась структура - перезапустить сервер
```bash
# См. раздел "Изменения в Backend"
# ⚠️ Перезапускаем только Flask сервер, боты не трогаем!
```

---

### 4️⃣ Комбинированные изменения (Frontend + Backend)

**🔒 БЕЗОПАСНОСТЬ:** При комбинированном обновлении **НЕ трогаем Telegram-ботов**! Они работают независимо и должны продолжать работать.

#### Полная последовательность (с учётом жёсткой остановки процессов Flask):
```bash
# 0. Проверить статус ботов (если на сервере)
systemctl status telegram-bot telegram-reviews-bot

# 1. Остановить только Flask процессы
# ⚠️ НЕ трогаем telegram_bot.py и telegram_reviews_bot.py!
pkill -9 -f "python.*main.py" || true
pkill -9 -f "python.*user_api.py" || true
pkill -9 -f "python.*worker.py" || true
sleep 2

# Дополнительная защита: если порт 8000 занят — убить PID вручную
PID=$(lsof -tiTCP:8000 -sTCP:LISTEN || true)
if [ ! -z "$PID" ]; then
    echo "⚠️ Порт 8000 всё ещё занят, убиваю PID $PID"
    kill -9 "$PID"
    sleep 2
fi

# Убедиться, что порт свободен
lsof -iTCP:8000 -sTCP:LISTEN || echo "✅ Порт 8000 свободен"

# 2. Пересобрать фронтенд
cd frontend
rm -rf dist
npm run build
cd ..

# 3. Проверить сборку
ls -lh frontend/dist/assets/index-*.js

# 4. Запустить Flask сервер
source venv/bin/activate
python src/main.py >/tmp/seo_main.out 2>&1 &
sleep 3

# 5. Проверить запуск Flask
lsof -iTCP:8000 -sTCP:LISTEN

# 6. Проверить, что боты всё ещё работают (если на сервере)
systemctl status telegram-bot telegram-reviews-bot
# Должны быть "active (running)"

# 7. Очистить старые сессии (если изменялась логика авторизации)
sqlite3 src/reports.db "DELETE FROM UserSessions;"

# 8. Проверить логи Flask
tail -20 /tmp/seo_main.out

# 9. Проверить логи ботов (если на сервере)
journalctl -u telegram-bot -n 10 --no-pager
journalctl -u telegram-reviews-bot -n 10 --no-pager
```

---

## 🎯 Для текущей проблемы с is_superadmin

### Что сделано:
1. ✅ Исправлен `auth_system.py` - добавлено `bool()` для `is_superadmin`
2. ✅ Удалены старые сессии из БД
3. ✅ Перезапущен сервер

### Что нужно сделать СЕЙЧАС:

1. **Убедиться, что сервер перезапущен:**
```bash
ps aux | grep "python.*main.py" | grep -v grep
# Если процесс старый (по времени), убить и запустить заново
```

2. **Выйти из системы в браузере** (кнопка "Выйти")

3. **Очистить localStorage в браузере:**
   - Открой консоль (F12)
   - Выполни: `localStorage.clear()`

4. **Войти заново** - создастся новая сессия

5. **Проверить консоль** - должно быть `is_superadmin: true`

---

## 🚨 Обновление Telegram-ботов (если нужно)

**⚠️ Перезапускать ботов нужно ТОЛЬКО если:**
- Мы изменяли `telegram_bot.py` или `telegram_reviews_bot.py`
- Мы изменяли зависимости, которые используют боты
- Мы изменяли структуру БД, к которой обращаются боты

### Процедура перезапуска ботов:

```bash
# Перезапустить бота управления
systemctl restart telegram-bot

# Перезапустить бота обмена отзывами
systemctl restart telegram-reviews-bot

# Проверить статус
systemctl status telegram-bot telegram-reviews-bot

# Проверить логи на ошибки
journalctl -u telegram-bot -n 20
journalctl -u telegram-reviews-bot -n 20
```

---

## ⚠️ Частые проблемы и решения

### Проблема: Изменения не видны

**Причина 1: Кеш браузера**
- Решение: Жесткая перезагрузка (Cmd+Shift+R) или режим инкогнито
- Проверка: Открой DevTools → Network → Disable cache → перезагрузи страницу

**Причина 2: Старый код на сервере (САМАЯ ЧАСТАЯ ПРОБЛЕМА!)**
- Симптомы: Ошибки в консоли браузера, старые данные, 500 ошибки, изменения не применяются
- Причина: Изменения не запушены на GitHub или не обновлены на сервере через `git pull`
- Решение: 
  ```bash
  # 1. Локально: убедиться, что изменения запушены
  git status
  # Если есть незапушенные коммиты:
  git push origin main
  
  # 2. На сервере: обновить код
  cd /opt/seo-app
  git pull origin main
  
  # 3. Проверить, что код обновился
  git log --oneline -1
  # Должен быть последний коммит
  
  # 4. Перезапустить app container
  docker compose restart app
  python src/main.py >/tmp/seo_main.out 2>&1 &
  sleep 3
  ```
- Проверка: 
  - `git log --oneline -1` - должен быть последний коммит
  - `tail -20 /tmp/seo_main.out` - должны быть свежие логи без старых ошибок
  - Проверить конкретный файл: `grep -A 5 "def get_business_by_id" src/database_manager.py`

**Причина 2a: Старый процесс Flask в памяти**
- Симптомы: Ошибки в консоли браузера, старые данные, 500 ошибки
- Решение: 
  ```bash
  # Найти PID процесса
  lsof -iTCP:8000 -sTCP:LISTEN
  # Убить процесс
  kill -9 <PID>
  # Или убить все процессы main.py
  pkill -9 -f "python.*main.py"
  # Запустить заново (ПОСЛЕ обновления кода через git pull!)
  source venv/bin/activate
  python src/main.py >/tmp/seo_main.out 2>&1 &
  ```
- Проверка: `tail -20 /tmp/seo_main.out` - должны быть свежие логи без старых ошибок

**Причина 3: Фронтенд не пересобран**
- Симптомы: Изменения в React компонентах не видны
- Решение: 
  ```bash
  cd frontend
  rm -rf dist  # ОБЯЗАТЕЛЬНО!
  npm run build
  ls -lh dist/assets/index-*.js  # Проверить дату файла
  ```
- Проверка: Файл должен иметь текущую дату/время

**Причина 4: Старая сессия в БД**
- Симптомы: Проблемы с авторизацией, старые данные пользователя
- Решение: Удалить старые сессии и войти заново
  ```bash
  sqlite3 src/reports.db "DELETE FROM UserSessions WHERE user_id = (SELECT id FROM Users WHERE email='ВАШ_EMAIL');"
  ```

**Причина 5: Используется старая версия кода из памяти Python**
- Симптомы: Изменения в Python файлах не работают, но код в файле правильный
- Решение: Перезапустить процесс (см. Причина 2)
- Проверка: `ps aux | grep "python.*main"` - проверить время запуска процесса

**Причина 6: Боты перестали работать после обновления**
- Симптомы: Боты не отвечают на сообщения после обновления
- Решение: 
  ```bash
  # Проверить статус
  systemctl status telegram-bot telegram-reviews-bot
  
  # Если остановлены - перезапустить
  systemctl restart telegram-bot telegram-reviews-bot
  
  # Проверить логи на ошибки
  journalctl -u telegram-bot -n 50
  journalctl -u telegram-reviews-bot -n 50
  ```
- Профилактика: Всегда проверять статус ботов ДО и ПОСЛЕ обновления

---

## 📝 Чеклист перед деплоем

### Общий чеклист:
- [ ] Фронтенд пересобран (`npm run build`)
- [ ] Проверен новый JS файл в `dist/assets/`
- [ ] Старый процесс Flask остановлен
- [ ] Новый процесс Flask запущен
- [ ] Проверен порт 8000 (процесс слушает)
- [ ] Проверены логи сервера (нет ошибок)
- [ ] Очищены старые сессии (если нужно)
- [ ] Протестирован вход заново
- [ ] Проверена консоль браузера (нет ошибок)

### Чеклист для сервера (с ботами):
- [ ] **Проверен статус ботов ДО обновления** (`systemctl status telegram-bot telegram-reviews-bot`)
- [ ] **Сохранены логи ботов** (на всякий случай)
- [ ] **Обновлен код** через `git pull`
- [ ] **Применены миграции БД** (если есть)
- [ ] **Пересобран фронтенд**
- [ ] **Перезапущен только Flask сервер** (`main.py`), боты не трогались
- [ ] **Проверен статус ботов ПОСЛЕ обновления** (должны быть "active (running)")
- [ ] **Проверены логи ботов на ошибки** (`journalctl -u telegram-bot -n 20`)
- [ ] **Протестирована работа ботов** (отправлено тестовое сообщение)

---

## 🚀 Автоматизация (рекомендуется)

### ✅ Используй канонический deploy-скрипт `scripts/deploy_frontend_dist.sh`

**Скрипт уже включает:**
- ✅ локальную пересборку фронтенда (`npm run build`) при запуске с `--build`
- ✅ синхронизацию канонического `frontend/dist` на сервер
- ✅ обновление runtime path `/app/frontend/dist`
- ✅ быструю проверку live `index.html`
- ✅ защиту от рассинхрона между host dist и container dist

### Команда для запуска:

```bash
cd /opt/seo-app
bash scripts/deploy_frontend_dist.sh --build
```

### Что делать, если есть локальные изменения на сервере:

```bash
# Если git pull не работает из-за локальных изменений:
git reset --hard origin/main

# Затем запустить скрипт:
bash scripts/deploy_frontend_dist.sh --build
```

### После выполнения скрипта:

1. **Очистить кэш браузера:** Ctrl+Shift+R (Windows/Linux) или Cmd+Shift+R (Mac)
2. **Или открыть в режиме инкогнито**
3. **Проверить изменения в интерфейсе**

---

**Скрипт находится в:** `scripts/deploy_frontend_dist.sh`
