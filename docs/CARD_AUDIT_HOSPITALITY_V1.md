# Hospitality Card Audit v1

Этот документ фиксирует первый отдельный режим аудита для объектов hospitality:

- hotel
- resort
- apartment stay
- guest house
- villa

Цель: перестать оценивать такие карточки как salon/clinic и приблизить аудит к reasoning-уровню Atlas.

## 1. Почему нужен отдельный режим

Для hospitality карточек типичные проблемы другие:

1. mismatch ожиданий и фактического опыта;
2. booking offers ошибочно попадают в услуги;
3. основной рычаг роста — не только completeness, но и positioning;
4. отзывы важны как источник recurring objections;
5. фото должны продавать experience, а не просто факт наличия объекта.

## 2. Как определяется режим

Режим `hospitality` включается по признакам в:

- `business.business_type`
- `business.name`
- `cards.overview.category`
- `cards.overview.categories`

Сигналы:

- `hotel`
- `resort`
- `apartment`
- `guest house`
- `villa`
- `holiday`
- `lodging`

## 3. Что меняется в аудите

Вместо generic completeness-аудита приоритет получают:

1. `positioning_description_gap`
2. `expectation_mismatch`
3. `services_booking_offers_gap`
4. `photo_story_gap`
5. `reviews_marketing_underused`
6. `activity_signals_gap`

## 4. Новые reasoning-сигналы

Из отзывов извлекаются темы.

### Позитивные

- простор
- тишина
- бассейн
- парковка
- кухня
- чистота
- близость к аэропорту
- family fit

### Негативные / objections

- ожидание близости к пляжу
- зависимость от машины
- шум самолётов

## 5. Смысловая логика summary

Summary в hospitality-режиме должен отвечать:

1. в чём уже сильный social proof;
2. какие сильные стороны подтверждают отзывы;
3. где mismatch ожиданий;
4. почему карточка теряет конверсию;
5. какой следующий правильный слой доработки.

## 6. Что не считать услугами

Нельзя класть в `services_preview`:

- `Booking.com`
- `Agoda`
- `TUI`
- `Bluepillow`
- `Wego`
- `Expedia`
- `официальный сайт`
- `compare prices`
- `варианты от партнёров`

Такие позиции трактуются как `booking offers`, а не как услуги объекта.

## 7. Что хотим получить в v2

Следующий слой для v2:

1. review-theme extraction не по keyword rules, а по structured AI pass;
2. отдельные блоки:
   - `best_fit_guest_profile`
   - `weak_fit_guest_profile`
   - `search_intents_to_target`
   - `photo_shots_missing`
3. multilingual audit generation без ручной правки page payload;
4. отдельный режим для `wellness/spa destination`, когда объект смешанный: stay + treatments.
