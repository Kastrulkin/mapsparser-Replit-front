# Эксплуатация защиты текстового Оператора

Статус: `beta`. Текущий результат включения, проверенные границы и доказательства:
[выкладка 13.11.2026](operator-activation-20261113.md).

## Что сохранять при выкладке

На VPS все команды выполнять из `/opt/seo-app`, долгие операции — внутри tmux.
Канонический `COMPOSE_FILE` в серверном `.env` включает:

```text
docker-compose.yml:docker/compiled-script-runner/compose.fragment.yml:docker/pii-runtime/compose.client.fragment.yml
```

Не исключать PII-профиль при собственном `docker compose -f ...`. Он добавляет
приложению, worker, operator-worker, outreach-worker и telegram-bot два read-only
файла в `/run/secrets` и частную сеть. Отсутствующие файлы не создаются автоматически.
Серверный `.activation-required` в `src/services/pii_protection` сохранять при
синхронизации исходников. Его отсутствие в локальном checkout намеренно; удалять
серверный marker во время обычной выкладки нельзя.

Текущие контейнеры могут иметь копии настроек вместо bind mounts. Они сохраняются
при restart. При правильном пересоздании Compose подключает защищённые host-файлы.
При ошибочном пропуске профиля серверный marker заставляет запрос отказать до LLM.

Обычные backend-перезапуски выполняются с `LOCALOS_MIGRATION_MODE=schema-check-only`.
Не уменьшать настроенный период завершения outreach-worker: он может дожидаться
текущей операции. При таймауте клиента сначала проверить состояние контейнера;
не запускать параллельный повтор и не завершать процесс принудительно.

## Сохранённые Compose JSON

Исправление 16.11.2026: файл, из которого фактически пересоздавали обработчик,
содержал старые PII-параметры. Теперь защищённые сервисы в этом файле наследуют
актуальный `docker/pii-runtime/compose.client.fragment.yml` через `extends`.
Собственные копии шести policy-переменных и двух privacy mounts удалены из child-
описаний, чтобы они не перекрывали родительский профиль. Остальные параметры
сохранены. Изолированные проверки подтвердили два пересоздания и наследование
последующего изменения профиля; рабочий outreach-worker пересоздан один раз.

Перед использованием другого сохранённого JSON прогнать проверку:

```sh
cd /opt/seo-app
python3 scripts/ensure_pii_compose_inheritance.py \
  --compose-file /opt/seo-app/backups/vr-yougile-marker-20261115/compose.release.private.json
```

Для применения добавить `--apply`. Команда сохраняет точную исходную копию
`*.before-pii-<timestamp>.json`, проверяет отсутствие изменений вне PII и не
перезапускает сервисы. Файлы с реальными environment остаются на VPS с правами
`0600`; их содержимое не печатать, не коммитить и не переносить в отчёты.

Затем пересоздать только нужный сервис в tmux, сохраняя его период завершения:

```sh
cd /opt/seo-app
docker compose \
  --project-directory /opt/seo-app/backups/vr-yougile-marker-20261115 \
  --project-name seo-app \
  -f /opt/seo-app/backups/vr-yougile-marker-20261115/compose.release.private.json \
  up -d --no-deps --no-build --pull never --force-recreate outreach-worker
```

Проверить новую container ID, оба read-only файла, эффективные `operator_text` /
`enforce`, общий runtime и синтетический canary. Только наличие копии файла в
старом контейнере не доказывает сохранение настройки при пересоздании.
Канонический backend hot-sync также сохраняет серверный `.activation-required`
при `rsync --delete`.

[Причина, исправление и доказательства](persistence-20261116.md).

## Остановка LLM при инциденте

Безопасный барьер — `enabled=true`, `scope=operator_text`, `mode=blocked`.
Выключенный флаг возвращает прежние маршруты и не заменяет этот барьер.
Файл `/etc/localos/pii/activation.json` должен оставаться `root:root`, `0600`.
Сохранять inode host-файла, поскольку к нему привязаны single-file bind mounts.

Следующая административная команда меняет только несекретную настройку активации
и её копии, не затрагивает ключи, Redis или бизнес-записи. Выполнять на VPS от root
в tmux. При частичном отказе повторить после восстановления доступа; не переключать
на `enabled=false`.

```sh
cd /opt/seo-app
python3 - <<'PY'
import json
import os
import subprocess
from pathlib import Path

root = Path('/opt/seo-app')
path = Path('/etc/localos/pii/activation.json')
target = '/run/secrets/localos-pii-activation.json'
services = ['operator-worker', 'outreach-worker', 'worker', 'telegram-bot', 'app']
value = {'version': 1, 'enabled': True, 'scope': 'operator_text', 'mode': 'blocked'}

def run(args):
    return subprocess.check_output(args, cwd=root, text=True, timeout=30)

fd = os.open(path, os.O_WRONLY | os.O_NOFOLLOW)
with os.fdopen(fd, 'r+b') as file:
    file.write((json.dumps(value) + '\n').encode())
    file.truncate()
    file.flush()
    os.fsync(file.fileno())
os.chown(path, 0, 0)
os.chmod(path, 0o600)
for service in services:
    cid = run(['docker', 'compose', 'ps', '-q', service]).strip()
    container = json.loads(run(['docker', 'inspect', cid]))[0]
    mounts = [m for m in container['Mounts'] if m['Destination'] == target]
    if mounts:
        assert len(mounts) == 1 and mounts[0]['Source'] == str(path) and not mounts[0]['RW']
    else:
        run(['docker', 'cp', str(path), cid + ':' + target + '.new'])
        run(['docker', 'exec', cid, 'sh', '-c',
             'chown 0:0 ' + target + '.new && chmod 600 ' + target +
             '.new && mv ' + target + '.new ' + target])
print('Operator LLM blocked')
PY
```

Для возврата после восстановления runtime/Redis/конфигурации сначала выполнить
синтетический canary, затем применить тот же порядок с `mode=enforce`. Перезапуск
для изменения mode не требуется: настройка читается при обращении. Публикации,
отправки, платежи и прочие внешние действия сохраняют ручное подтверждение.

## Проверка после изменений

Порядок: `docker compose ps`, журналы приложения с ограничением времени (не
публиковать их содержимое), HTTP `/`, `/health`, `/ready`, затем целевые проверки.
Проверять эффективную `activation.configuration()` и `gateway.enabled()` внутри
доверенного запроса; старое environment текущих контейнеров может оставаться
выключенным. Вне запроса Оператора `enabled()` штатно false.

Синтетический canary должен подтвердить подмену перед транспортом, точное
восстановление, один общий PID модели и отсутствие вызовов провайдера при сбое.
Не использовать рабочие сообщения, клиентские записи и настоящие отправки как
тестовые данные. Redis хранит шифрованные соответствия 900 секунд; ключи не
печатать и не копировать в документацию. Квоты: 10 protect/с общая и 4/с на бизнес,
burst 4; отказ по квоте не должен приводить к передаче открытого текста.
