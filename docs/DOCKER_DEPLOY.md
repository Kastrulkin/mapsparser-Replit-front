# Запуск проекта в Docker на сервере

Краткая инструкция: как перенести и запустить один и тот же docker-compose локально и на VPS.

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
   git clone <url-репозитория> /opt/beautybot
   cd /opt/beautybot
   ```

2. Опционально создайте `.env` в корне проекта:
   ```bash
   POSTGRES_USER=beautybot
   POSTGRES_PASSWORD=<надёжный_пароль>
   POSTGRES_DB=beautybot
   ```
   Если не создавать — будут использованы значения по умолчанию из `docker-compose.yml`.

3. Сборка и запуск:
   ```bash
   docker compose up -d --build
   ```
   При старте контейнеры app и worker ждут готовности Postgres, выполняют `flask db upgrade` (создают таблицы, в т.ч. `parsequeue`), затем запускают приложение/воркер.

4. Проверка:
   ```bash
   curl -s http://localhost:8000/health
   docker compose ps
   ```

## Важно

- **Postgres и приложение — в разных контейнерах.** Подключение к БД задаётся через `DATABASE_URL` (в compose подставляется автоматически).
- **Данные БД** хранятся в volume `pgdata`. При `docker compose down` volume не удаляется; при `docker compose down -v` — удаляется.
- Обновление кода: пересоберите образ и перезапустите:
  ```bash
  git pull   # или загрузите новые файлы
  docker compose up -d --build
  ```

## Остановка

```bash
docker compose down
```

Только остановка контейнеров; volume с данными Postgres остаётся.

---

## Если Docker build падает (BuildKit / buildx)

Проект использует Docker Compose v2 и сборку через **BuildKit** (buildx). На части машин сборка может падать с ошибкой вида:

```
failed to dial gRPC
header key "x-docker-expose-session-sharedkey" contains value with non-printable ASCII characters
```

**Это проблема окружения Docker (buildx / BuildKit), а не кода проекта.** Менять Dockerfile или код приложения не нужно.

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
