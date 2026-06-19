# Canonical Docker/Postgres Runbook

Каноничная инструкция для LocalOS runtime: Docker Compose + PostgreSQL. Старые systemd/SQLite/debug/fix инструкции лежат в `archive/legacy-runbooks/` только для истории.

На production-сервере все команды выполнять из `/opt/seo-app`:

```bash
cd /opt/seo-app
```

## Порты и сервисы

| Сервис | Порт | Описание |
|--------|------|----------|
| **Фронтенд (Dev)** | `3000` | Vite dev server — запускается **на хосте** (`npm run dev`), не в Docker |
| **Бэкенд API** | `8000` | Flask — в контейнере `app` |
| **Postgres** | `5432` | Внутри сети Docker (не проброшен наружу) |

**Локальная разработка с Docker:** бэкенд в контейнерах, фронтенд — отдельно на хосте:
```bash
docker compose up -d --build   # postgres + app + worker
cd frontend && npm run dev     # фронтенд на http://localhost:3000
```
Фронтенд на 3000 проксирует `/api` на бэкенд (8000).

**Продакшен:** фронтенд собирается в `frontend/dist` и раздаётся Flask/Nginx; backend runtime source of truth находится в `/opt/seo-app/src`.

> 📖 Подробнее: [PORTS_AND_SERVICES.md](../PORTS_AND_SERVICES.md), [ALGORITHM_UPDATE.md](../ALGORITHM_UPDATE.md)

## Что нужно на сервере

- Docker
- Docker Compose (v2: `docker compose`)

Установка (Ubuntu/Debian):

```bash
sudo apt-get update && sudo apt-get install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a644 /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update && sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo usermod -aG docker $USER
# выйти из SSH и зайти снова, чтобы применилась группа docker
```

## Перенос проекта

1. На сервере создайте каталог и склонируйте репозиторий (или загрузите архив):
   ```bash
   git clone <url-репозитория> /opt/seo-app
   cd /opt/seo-app
   ```

2. Опционально создайте `.env` в корне проекта:
   ```bash
   POSTGRES_USER=local
   POSTGRES_PASSWORD=<надёжный_пароль>
   POSTGRES_DB=local
   ```
   Если не создавать — будут использованы значения по умолчанию из `docker-compose.yml`.

3. Сборка и запуск (без BuildKit — стабильно, рекомендуется):
   ```bash
   ./scripts/docker-compose-build.sh up -d --build
   ```
   Или вручную: `DOCKER_BUILDKIT=0 docker compose up -d --build`.  
   При старте контейнеры app и worker ждут готовности Postgres, выполняют `flask db upgrade` (создают таблицы, в т.ч. `parsequeue`), затем запускают приложение/воркер.

4. Проверка:
   ```bash
   curl -s http://localhost:8000/health
   docker compose ps
   ```
   Для UI: запустите фронтенд на хосте (`cd frontend && npm run dev`) и откройте http://localhost:3000

## Важно

- **Postgres и приложение — в разных контейнерах.** Подключение к БД задаётся через `DATABASE_URL` (в compose подставляется автоматически).
- **Данные БД** хранятся в volume `pgdata`. При `docker compose down` volume не удаляется; при `docker compose down -v` — удаляется.
- **Сборка без BuildKit:** по умолчанию проект собирается с `DOCKER_BUILDKIT=0`, чтобы избежать ошибки gRPC на Docker Desktop. Используйте скрипт или переменную окружения при каждой сборке.
- Обновление кода: пересоберите образ и перезапустите:
  ```bash
  cd /opt/seo-app
  git pull   # или загрузите новые файлы
  ./scripts/docker-compose-build.sh up -d --build
  ```

Для production hotfix предпочтительнее partial deploy:

```bash
cd /opt/seo-app
./scripts/deploy_backend_src.sh                 # backend-only: sync src, restart app/worker
./scripts/deploy_frontend_dist.sh --build       # frontend-only: build/sync dist
```

Перед schema migration на production обязательно сделать backup БД. Данные production вручную не менять без отдельного approval.

## Освобождение места на диске

После частых пересборок и обновлений образов Docker копит остановленные контейнеры, висячие образы и кэш сборки (иногда несколько гигабайт). Периодически можно чистить:

```bash
# Посмотреть, что занимает место
docker system df -v

# Безопасная очистка (оставляет текущие образы app/worker/postgres):
docker container prune -f    # остановленные контейнеры
docker image prune -f        # образы без тега (dangling)
docker builder prune -f      # часть кэша сборки

# Более жёсткая: весь кэш сборки (следующая сборка будет дольше)
docker builder prune -a -f

# Радикально: всё неиспользуемое, в т.ч. образы без запущенных контейнеров
docker system prune -a -f
```

После первой тройки команд обычно освобождается 1–2 ГБ.

**Не используйте** `docker system prune -a -f` без необходимости: он удаляет все образы, у которых нет запущенного контейнера (в т.ч. `seo-worker`, если воркер остановлен, и базовый образ `python:3.11-slim`). После этого потребуется заново делать `./scripts/docker-compose-build.sh up -d --build`.

**Один лишний buildx-builder:** если в `docker buildx ls` видно два контейнерных билдера (например `cleanbuilder` и `gifted_wozniak`), достаточно одного. Удалить лишний: `docker buildx rm gifted_wozniak` (имя подставьте из списка).

## Остановка

```bash
docker compose down
```

Только остановка контейнеров; volume с данными Postgres остаётся.

---

## Опционально: сборка с BuildKit

По умолчанию проект собирается **без BuildKit** (`DOCKER_BUILDKIT=0`), чтобы стабильно работать на Docker Desktop (на многих машинах BuildKit даёт ошибку gRPC с непечатаемыми символами в заголовках).

Если хотите попробовать сборку с BuildKit (быстрее, кэш слоёв):

```bash
docker compose up -d --build
```

При ошибке `failed to dial gRPC ... x-docker-expose-session-sharedkey contains value with non-printable ASCII` — это окружение Docker/buildx, не код. Решение: снова использовать сборку без BuildKit (`./scripts/docker-compose-build.sh up -d --build`) или один раз сбросить buildx: `docker buildx rm --all-inactive`, `docker buildx create --use`, `docker buildx inspect --bootstrap`.

<details>
<summary>Подробнее про buildx (если пробуете BuildKit)</summary>

### Что такое buildx builder

**buildx** — это клиент Docker для сборки образов. Он использует отдельный *builder* (процесс/контейнер), с которым общается по gRPC. Если сессия builder’а повредилась (например, после обновления Docker Desktop или смены context), в заголовках gRPC могут оказаться непечатаемые символы, и сборка падает. Сброс builder’а обычно восстанавливает работу за 2–3 минуты.

### Recovery: пошаговый алгоритм

Выполните по порядку из корня проекта:

```bash
# Сбросить buildx builder
docker buildx rm --all-inactive
docker buildx create --use
docker buildx inspect --bootstrap

# Пересобрать проект
docker compose build --no-cache
docker compose up -d
```

После этого сборка должна проходить. Если ошибка повторится — см. «Частые причины» ниже.

### Диагностика: сборка без BuildKit

Чтобы убедиться, что причина именно в BuildKit/buildx, можно временно отключить его:

```bash
DOCKER_BUILDKIT=0 docker compose build
```

Это **диагностический режим**: сборка идёт по старой схеме (без BuildKit). Использовать его постоянно не рекомендуется (медленнее, меньше возможностей). После проверки лучше выполнить recovery выше и собирать с BuildKit.

### Частые причины проблемы

- **Обновление Docker Desktop** — после апдейта старый buildx builder может остаться в неконсистентном состоянии.
- **Сломанный или «залипший» buildx builder** — решается сбросом (`docker buildx rm ...` и `create --use`).
- **Прокси / VPN / грязные env-переменные** — могут подмешиваться в gRPC-заголовки; попробуйте отключить VPN/прокси или запустить сборку в чистом терминале без лишних `export`.
- **Смена Docker context** (например, переключение на удалённый daemon) — текущий builder мог быть привязан к старому context; после смены context создайте новый builder (см. recovery).

### Best practice

- **После обновления Docker Desktop** — один раз выполнить сброс buildx builder (блок команд из раздела «Recovery» выше).
- **Если при сборке видите ошибку gRPC** — не чинить код и не менять Dockerfile; сначала восстановить окружение по recovery-алгоритму.

</details>
