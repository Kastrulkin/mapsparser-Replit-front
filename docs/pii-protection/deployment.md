# Воспроизведение и выключенная интеграция

Текущий VPS-статус: `beta`, включён только текстовый Оператор веба/Telegram.
[Выкладка 13.11.2026](operator-activation-20261113.md) и
[эксплуатация/аварийная блокировка](operations.md) имеют приоритет над историческими
инструкциями выключенного пилота ниже. Тесты — только на синтетике.

Статус: `internal`, выключенная интеграция выложена на VPS 02.11.2026 по разрешению
пользователя. Флаг остаётся `false`; миграции и изменения рабочих записей не выполнялись.
Модели установлены в отдельном синтетическом образе. Результаты и границы рабочего
включения: [VPS deployment](vps-deployment-20261102.md).
Команды ниже воспроизводят отдельное окружение с синтетическими данными.

Общий процесс и выделенный Redis уже развёрнуты отдельно на VPS (03.11.2026).
После явного разрешения пользователя к нему подключены app, три обработчика
и Telegram-бот, выполнены поочерёдные перезапуски и проверки. Флаг выключен;
сервер принимает только синтетические scope.
[Схема, секреты и нагрузка](shared-runtime-20261103.md),
[выкладка клиентов](shared-wiring-20261103.md).
Подключение закреплено в `.env:COMPOSE_FILE` VPS и автоматически сохраняется
при обычном пересоздании через `docker compose`:
[конфигурация и десять синтетических проверок](shared-persistence-20261103.md).

Следующая приёмка текстового Оператора, публичных снимков, правил восстановления
и квот — [04.11.2026](operator-acceptance-20261104.md). Профиль квот хранится
в закрытом `/etc/localos/pii/runtime.json`: `protect_rps=10`, `protect_burst=4`,
`business_protect_rps=4`, `business_protect_burst=4`. Для изменения профиля нужен
перезапуск только PII runtime; ключи шифрования и Redis credentials сохраняются.

## Установка и повторение

Использовать Python 3.11 и именованную tmux-сессию. Корень — текущий checkout
LocalOS. Не загружать `.env` приложения и не передавать production credentials.

```sh
tmux new -s pii-pilot
python3 -m venv /private/tmp/localos-pii-venv
/private/tmp/localos-pii-venv/bin/python -m pip install -r requirements.pii-pilot.txt
/private/tmp/localos-pii-venv/bin/python -m pip check
/private/tmp/localos-pii-venv/bin/python scripts/pii_pilot/run.py --output-dir /private/tmp/pii-results
env -i PATH=/usr/bin:/bin PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
  /private/tmp/localos-pii-venv/bin/python -m pytest -q \
  tests/test_pii_protection.py tests/test_llm_budget_boundary.py tests/test_operator_tool_loop.py
env -i PATH=/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
  /private/tmp/localos-pii-venv/bin/python scripts/pii_pilot/gateway_benchmark.py /private/tmp/pii-results/gateway-performance.json
```

На Apple Silicon запускать Python внутри tmux через `/usr/bin/arch -arm64`, если
tmux запускает дочерние процессы через Rosetta. В проведённом эксперименте для
macOS использован cryptography 46.0.4 (готовый пакет); это измерительная среда,
не изменение базового production requirements/constraints. Полный состав
установленного окружения — `results/environment-freeze.txt`.

`run.py` запускает каждый профиль отдельным subprocess с очищенным окружением.
Внутри benchmark запрещены DNS и socket connect. Ошибка детектора не превращается
в успешный результат. Сеть разрешена только для предварительной установки
общедоступных библиотек и моделей, без клиентских данных.

## Linux с настоящим Redis

02.11.2026 этот путь выполнен на локальном Docker / ARM64. Квоты читаются из cgroup,
а не предполагаются по параметрам запуска. Флаг образа остаётся `false`.
Команды ниже запускать внутри именованной tmux-сессии из локального checkout,
только с локальным Docker daemon; реальные данные или `.env` не копировать.

```sh
python3 scripts/pii_pilot/prepare_linux_context.py /private/tmp/localos-pii-stage
docker --host unix:///var/run/docker.sock build \
  -f scripts/pii_pilot/Dockerfile -t localos-pii-pilot:local /private/tmp/localos-pii-stage
mkdir -p /private/tmp/localos-pii-results
chmod 0777 /private/tmp/localos-pii-results
docker --host unix:///var/run/docker.sock run --rm --name localos-pii-local \
  --network none --cpus=2 --memory=4g --memory-swap=4g --pids-limit=256 \
  --read-only --cap-drop=ALL --security-opt=no-new-privileges \
  --tmpfs /tmp:rw,mode=1777,size=512m \
  --mount type=bind,source=/private/tmp/localos-pii-stage,target=/opt/pilot,readonly \
  --mount type=bind,source=/private/tmp/localos-pii-results,target=/evidence \
  localos-pii-pilot:local python scripts/pii_pilot/linux_entry.py
```

Staging разрешает только перечисленные исходники и синтетические fixtures, без
конфигурации/БД/файлов клиентов. Образ содержит зависимости и redis-server.
В контейнере создаётся отдельный Redis 127.0.0.1:16379/15 без host-порта и RDB/AOF;
он завершается вместе с прогоном. Для проверки Redis используется фиксированный
loopback URL, никакие production URL тестами не принимаются.

В `run.json` сохраняются результаты команд и ограничения; `tests.xml` фиксирует
все тесты, `comparison/` — четыре отдельные оценки, `redis-performance.json` —
200 прогревочных, 600 последовательных и 600 параллельных запросов с фактическими
SET/GET и восстановлением. `--skip-comparison` повторяет tests + Redis benchmark
без повторения неизменного сравнения библиотек. Состав окружения и SHA-манифест
сохраняются отдельно. Результаты текущего запуска — [benchmark.md](benchmark.md).

Общий RAM-бюджет всего LocalOS с настоящим количеством app/worker и другими
сервисами этим отдельным контейнером не измерялся. Без Docker обычный Python-
прогон пропускает шесть real-Redis тестов явно; в финальном Linux-прогоне skip нет.

## Runtime-конфигурация

| Переменная | По умолчанию | Значение |
|---|---|---|
| `PII_PROTECTION_ENABLED` | `false` | Подключение слоя ко всем поддержанным LLM-задачам |
| `PII_PROTECTION_MODE` | `enforce` | `diagnostic` распознаёт локально, но никогда не вызывает провайдера; `enforce` защищает настроенную область; на VPS это только текстовый Оператор |
| `PII_PROTECTION_SCOPE` | `all` | При env-only включении область; VPS задаёт `operator_text` |
| `PII_ACTIVATION_CONFIG_FILE` | `/run/secrets/localos-pii-activation.json` | Несекретная настройка enabled/scope/mode, читается при обращении |
| `PII_ACTIVATION_REQUIRED` | `false` | Обязательность файла; на VPS дополнительно сохранён source marker для входа Оператора |
| `PII_PROTECTION_ENGINE` | `piighost_presidio` | Альтернатива: `preserve` с установленным pilot-профилем |
| `PII_RUNTIME_TRANSPORT` | `auto` | При существующем клиентском файле выбирается shared; `shared` требует файл, `local` использует процессный путь |
| `PII_RUNTIME_CONFIG_FILE` | `/run/secrets/localos-pii-client.json` | API-only клиентский файл `0600`, без Fernet-ключа и Redis credentials |
| `PII_MAPPING_KEY` | отсутствует | Отдельный Fernet-ключ; генерировать и хранить вне Git/логов |
| `PII_REDIS_URL` | отсутствует | Общий Redis, приватный маршрут/ACL; не использовать произвольный клиентский URL |
| `PII_MAPPING_TTL_SECONDS` | `900` | Допустимый диапазон 60–86400 секунд |

При shared-транспорте клиент читает только API-конфигурацию из файла; ключ mapping,
Redis URL и TTL находятся в закрытом `runtime.json` общего процесса. Переменные
`PII_MAPPING_KEY`/`PII_REDIS_URL` выше относятся к локальному процессному пути.

Существующие provider/API переменные не переименованы. Поля `pii_session_id` и
`pii_policy`, `pii_public_context` добавлены в Python-контракт как необязательные, внешние HTTP API
не менялись. По умолчанию тяжёлые зависимости не устанавливаются в app image:
они установлены в отдельном общем runtime. При отсутствии
пакетов/моделей/Redis/ключа включённая защита возвращает отказ, а не plaintext.

Для VPS добавлен `requirements.pii-vps.txt`: выбранный piighost/Presidio и зависимости
синтетических проверок, без Preserve. Версии закреплены в `requirements.pii-linux.lock.txt`,
SHA моделей — в `requirements.pii.txt`. `scripts/pii_pilot/Dockerfile.vps` собирает отдельный
образ; зависимости основного приложения не меняются. Проверочный entrypoint принимает
`--expected-cpus 0.5 --expected-memory-mib 768 --skip-comparison` и сверяет эти значения
с cgroup до запуска тестов и измерений. Стандартный CI-профиль остаётся 2 CPU / 4 GiB.

В тестовом стеке PII-переменные передаются явно. Для VPS действует отдельный
Compose-профиль с read-only файлами и областью `operator_text`; его нужно сохранять
во всех процедурах пересоздания. Глобальное включение всех AI-функций не принято: неподдержанные legacy/embedding/image маршруты будут
блокироваться. Для рабочих tool fields потребуется проверенная серверная
`pii_restore_fields` allowlist; пользователю и модели её назначать нельзя.

## Обновление и откат

Обновлять только закреплённые версии после повторения корпуса, scope/TTL,
tool-call, streaming, fail-closed и trace-тестов. Не включать local LLM или большие
словари без отдельного RAM/CPU-теста. Смена ключа требует перезапуска участвующих
процессов; старые mapping могут стать недоступны — восстановление должно отказать.

В синтетическом окружении откат — вернуть предыдущую версию кода и выключенный
флаг. Для будущего рабочего cohort сначала остановить чувствительные AI-задачи:
переключение флага в `false` возвращает прежние маршруты и не сохраняет гарантию
подмены. 02.11.2026 разрешённая выкладка завершена под выключенным флагом. Подключение
к рабочему текстовому Оператору выполнено 13.11.2026, остальной охват остаётся отдельным этапом. На VPS уже подключён общий
runtime с выделенным Redis/ключом, локальные NLP-модели в пяти consumers не загружены.
Для следующего рабочего этапа нужна ограниченная проверенная группа задач;
13.11.2026 включена область `operator_text`; для неё `synthetic_only=false`.
Секреты и TTL сохранены. Безопасный аварийный барьер — `enabled=true, mode=blocked`,
с обновлением host-файла и копий в текущих контейнерах; порядок в [operations.md](operations.md).

CI добавлен отдельным workflow `.github/workflows/pii-pilot.yml`; он собирает
такой же изолированный Linux-контейнер с Redis, без сети и с квотами 2 CPU / 4 GiB,
и сохраняет только результаты синтетического корпуса.
Hosted CI пока не запускался. Локальные результаты и известный посторонний сбой
широкого regression-прогона перечислены в [benchmark.md](benchmark.md).
