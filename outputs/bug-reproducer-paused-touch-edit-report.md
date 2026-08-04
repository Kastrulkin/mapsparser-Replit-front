# Bug Reproducer: paused queued touch edit

## FIX_PROVEN

LocalOS показывал редактор для VK-касания в очереди, но отправлял изменение в endpoint, который разрешал только `draft/draft`. Backend возвращал `409`, и текст не сохранялся.

## Подтверждённая причина

| Слой | До исправления | Контракт |
| --- | --- | --- |
| Frontend | Редактор показывался без проверки статуса | Редактировать можно черновик или приостановленное неотправленное касание |
| API/service | `PATCH` отклонял любой статус кроме `draft` | Paused-редактирование допустимо только при paused queue row |
| Safety | Текст был уже в подтверждённом snapshot | Правка сбрасывает snapshot и блокирует resume до повторной проверки |

## Исправление

- Добавлен явный frontend-guard `draft/draft` и `paused/paused`.
- Paused-правка блокирует запись очереди и отклоняет уже отправленные касания.
- Изменяются touch и связанный `outreachmessagedrafts`, но queue остаётся на паузе.
- Прежнее approval аннулируется; после успешной проверки snapshot пересчитывается.
- Resume невозможен, пока изменённое сообщение не прошло проверку.

## Evidence

| Проверка | Результат |
| --- | --- |
| Исходный регрессионный тест | FAIL по ожидаемому frontend/API mismatch |
| Узкие paused-edit и review тесты | 3 passed |
| Профильные backend/API/UI тесты | 97 passed |
| Vite production build | passed |
| ESLint | 0 errors; 4 pre-existing hook warnings |

## Approvals

- Gate 1: получено разрешение создать и запустить reproducer.
- Gate 2: получено отдельное разрешение на production-fix.

## Limitations

Изменение не выкладывалось на production и не затрагивало production-данные. Browser-проверка живого flow возможна после выкладки.
