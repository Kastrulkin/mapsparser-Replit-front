# Card Audit Ideal Policy (LocalOS)

Этот документ фиксирует, что мы считаем «идеальной карточкой» и как считаем gap-анализ.
Канонический источник порогов и весов: `src/core/card_audit_policy.py`.

## 1) Цель

Аудит должен детерминированно отвечать на два вопроса:

1. Что в карточке уже в хорошем состоянии.
2. Чего не хватает до «сильной зоны» и какие шаги дадут наибольший эффект.

## 2) Модель идеальной карточки

Идеальная карточка в v1:

1. `Профиль`: заполнены сайт и базовые контакты, есть адрес, карточка синхронизируется.
2. `Репутация`: рейтинг в целевой зоне, достаточный объём отзывов, нет backlog отзывов без ответа.
3. `Услуги`: есть структурированный список услуг и цены.
4. `Активность`: есть свежие обновления и карточка выглядит живой.
5. `Контент`: есть фото (минимум базового порога).

## 3) Канонические пороги (v1)

Параметры вынесены в `src/core/card_audit_policy.py`:

1. `rating.risk_max = 4.4`
2. `rating.target_min = 4.7`
3. `reviews.target_min = 20`
4. `services.minimum_visible = 5`
5. `photos.good_min = 5`
6. `activity.recent_days = 45`
7. `unanswered_reviews.high_severity_min = 3`
8. Регулярность ведения карточки:
   1. `cadence.news_posts_per_month_min = 4`
   2. `cadence.photos_per_month_min = 8`
   3. `cadence.reviews_response_hours_max = 48`
9. Health-зоны:
   1. `strong_min = 80`
   2. `growth_min = 55`

## 4) Веса итогового score

Итоговый `summary_score` считается как взвешенная сумма:

1. `profile = 0.20`
2. `reputation = 0.35`
3. `services = 0.30`
4. `activity = 0.15`

Сами веса также хранятся в `src/core/card_audit_policy.py`.

## 5) Что выдаёт аудит

Оба пайплайна (аудит лида и аудит активного бизнеса) выдают согласованные поля:

1. `summary_score`, `health_level`, `health_label`
2. `subscores`
3. `findings` (факты разрывов)
4. `recommended_actions` (приоритетные шаги)
5. `current_state` (текущие метрики карточки)
6. `revenue_potential` (оценка диапазона потерь/резерва)
7. `issue_blocks` (канонический формат для UI):
   1. `title`
   2. `problem`
   3. `evidence`
   4. `impact`
   5. `fix`
   6. `priority`
   7. `section`
8. `top_3_issues` (герой-блок с тремя главными проблемами)
9. `action_plan`:
   1. `next_24h`
   2. `next_7d`
   3. `ongoing`
10. `cadence` (норматив регулярной работы с карточкой)

## 6) Как менять политику

1. Меняем только `src/core/card_audit_policy.py`.
2. Не правим пороги точечно в `card_audit.py`.
3. После изменения:
   1. запускаем `python3 -m py_compile src/core/card_audit.py src/core/card_audit_policy.py`
   2. для фронта при необходимости `npm --prefix frontend run build`
   3. перегенерируем audit snapshot/page_json для нужных карточек.

## 7) Принцип интерпретации

Аудит должен быть «фактоцентричным», а не шаблонным:

1. В summary и рекомендациях обязательно отражаем фактические значения карточки.
2. Формулировки «что улучшить» должны опираться на `current_state` и пороги policy.
3. Если метрика уже в норме, показываем режим «поддерживать», а не «чинить».
