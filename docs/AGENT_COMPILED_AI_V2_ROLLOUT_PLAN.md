# Agents: Compiled AI v2 rollout plan

Обновлено: 13 августа 2026

## Цель

Сделать раздел «Агенты» рабочим инструментом для владельца локального бизнеса:
он выбирает проверенную практику или описывает результат своими словами,
проверяет понятный сценарий, подключает данные, запускает безопасный тест и
только затем включает работу. Исполнение использует сохранённый DSL; модель не
выбирает следующий шаг во время запуска.

Целевой результат: технически надёжный runtime, сертифицированный каталог
шаблонов и React Flow как визуальный слой над существующим DSL, без второго
движка исполнения.

## Что изменилось в Compiled AI v2

В первой версии препринта граница описывалась как «модель во время runtime не
нужна». Вторая версия от 31 июля 2026 года формулирует её точнее:

- LLM удалена из control flow и не планирует следующий шаг;
- фиксированный план выполняется детерминированно;
- внутри плана разрешены узкие model calls для смысловых подзадач;
- у каждого такого шага должны быть фиксированные purpose, input schema,
  output schema, лимиты и fallback;
- сильнее формализованы Code Foundry, безопасность, drift и ограничения.

LocalOS хранит это разделение как `runtime_planner_required = false` и
`runtime_model_steps`. Старое поле `runtime_llm_required` остаётся временным
alias для совместимости.

## План внедрения

### Этап 1. Контракт v2

- отделить планировщик runtime от ограниченных model steps;
- сохранить совместимость старых версий blueprint;
- запретить незарегистрированные model calls;
- показать поля контракта в compiled artifact и метриках.

Готово, когда unit-тест доказывает, что модель не управляет графом, а
зарегистрированный смысловой шаг сохраняет фиксированные схемы и fallback.

### Этап 2. Каталог шаблонов

- хранить шаблоны отдельно от `agent_blueprints`;
- манифест: key, semver, бизнес-результат, вертикаль, trigger, inputs, DSL,
  connections, approval policy, limits, output, risk и certification;
- не создавать по десять черновиков в каждом аккаунте;
- старые seeded examples скрыть из обычного списка без удаления данных;
- создавать персональный blueprint только после выбора шаблона пользователем.

Первые шесть beta-кандидатов: ежедневная сводка, ответы на негативные отзывы,
SEO-проверка услуг, новости из сигналов, записи на завтра и результат из Google
Sheets.

### Этап 3. Четыре ворот сертификации

1. Technical gate: DSL, типы, allowlist, approvals и limits валидны.
2. Fixture gate: positive, negative, boundary и regression fixtures совпадают
   с golden results.
3. Security gate: prompt injection, утечки и обход подтверждений не проходят.
4. Production gate: пилотный бизнес подтвердил полезность результата, а
   владелец шаблона принял evidence bundle.

Статус `certified` разрешён только после четырёх зелёных ворот. До реального
пилота первые шесть шаблонов имеют статус `beta`, а не фиктивный `certified`.

### Этап 4. React Flow viewer

- строить граф только из текущего execution contract;
- показывать три пользовательских типа: подготовка, действие, решение человека;
- включить pan, zoom, fit view и read-only инспекцию;
- сохранить линейное представление как доступную текстовую альтернативу;
- загружать React Flow лениво только при открытии сценария.

### Этап 5. Ограниченный editor

- разрешить только зарегистрированные типы узлов;
- валидировать граф на клиенте и сервере тем же DSL validator;
- сохранять изменения новой candidate-версией, не меняя active runtime;
- требовать preview и явное включение перед production run;
- дать rollback на последнюю проверенную версию.

## Проверка внедрения

| Контур | Проверка | Условие приёмки |
| --- | --- | --- |
| Контракт | Unit-тест planner/model-step separation | Нет runtime planning; bounded steps имеют schema и fallback |
| Каталог | Manifest/API contract tests | 10 манифестов, первые 6 beta, semver и четыре gate |
| Данные | List API regression | Seeded examples скрыты; пользовательские агенты не потеряны |
| Безопасность | Negative fixtures | Внешние sends/writes останавливаются на approval |
| Viewer | Frontend build и browser pass | Граф совпадает с линейным сценарием, доступен на desktop/mobile |
| Версии | Candidate/active regression | Редактирование не меняет рабочую версию до подтверждения |
| Пилот | Evidence bundle | Минимум 3 запуска на шаблон, отзыв владельца, дефекты и решение owner |
| Rollout | Метрики | success rate, intervention rate, time-to-first-value и rollback rate видимы |

## Решение о готовности

- `production-capable`: runtime и approval boundary проходят технические проверки;
- `beta-ready`: technical, fixture и security gates зелёные;
- `certified`: дополнительно пройден production gate;
- общий выпуск каталога: не менее шести certified templates и успешный
  browser/rollback smoke test.

До завершения пилотов корректная формулировка состояния: фундамент
production-capable в узком контуре, каталог и visual authoring находятся в beta.

## Проверочные команды

```bash
scripts/test_agent_template_catalog.sh
scripts/test_compiled_validation_fixtures.sh
scripts/test_agent_graph_roundtrip.sh
npm --prefix frontend run build
```
