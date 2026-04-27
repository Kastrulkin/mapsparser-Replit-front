# Card Audit Profile System v1

Этот документ фиксирует общий подход к `audit_profile` в LocalOS.

Цель: чтобы сильный аудит был не только у hospitality-кейсов, а у всех ключевых вертикалей:

- `hospitality`
- `wellness`
- `medical`
- `beauty`
- `food`
- `fitness`
- `default_local_business`

## 1. Зачем нужен profile-based audit

Один и тот же deterministic checklist плохо работает на разных бизнесах:

1. для `medical` важны специализация, маршрут пациента и trust layer;
2. для `beauty` важны услуги как точки входа в запись, фото результата и prices;
3. для `hospitality` важны positioning, expectation mismatch и review objections;
4. для `wellness` важны процедуры как SEO-единицы, equipment trust и activity signals;
5. для `food` важны меню, визуальные триггеры и occasion-based intent;
6. для `fitness` важны format clarity, equipment, расписание и абонементы.

То есть единый score остаётся, но reasoning должен быть профильным.

## 2. Канонический pipeline

Путь аудита в v1:

1. определить `audit_profile`;
2. собрать factual layer:
   - рейтинг
   - число отзывов
   - услуги
   - цены
   - фото
   - свежесть активности
   - ответы на отзывы
3. собрать reasoning layer:
   - кому подходит
   - кому не подходит
   - какие intents нужно закрывать
   - каких фото не хватает
   - в чём positioning gap
4. собрать профильные `issue_blocks`;
5. собрать профильный `action_plan`;
6. собрать `summary_text`, который звучит как аудит, а не как dry metrics dump.

## 3. Поля reasoning layer

Независимо от профиля система должна уметь отдавать:

1. `audit_profile`
2. `audit_profile_label`
3. `best_fit_customer_profile`
4. `weak_fit_customer_profile`
5. `best_fit_guest_profile`
6. `weak_fit_guest_profile`
7. `search_intents_to_target`
8. `photo_shots_missing`
9. `positioning_focus`
10. `strength_themes`
11. `objection_themes`
12. `description_gap`
13. `services_gap`
14. `photos_gap`
15. `review_signal_strength`
16. `review_response_gap`

Эти поля должны быть доступны:

- в каноническом business audit
- в lead preview audit
- на публичной audit-странице

## 4. Профили v1

### 4.1 Hospitality

Фокус:

1. positioning
2. expectation mismatch
3. booking offers не считать услугами
4. recurring objections из отзывов
5. photo story как часть conversion

Ключевые issue types:

1. `positioning_description_gap`
2. `expectation_mismatch`
3. `services_booking_offers_gap`
4. `photo_story_gap`
5. `reviews_marketing_underused`
6. `activity_signals_gap`

### 4.2 Wellness

Фокус:

1. процедуры как SEO-единицы
2. equipment trust
3. distinction между spa / massage / recovery / detox
4. reviews как marketing layer
5. active profile signals

Ключевые issue types:

1. `positioning_description_gap`
2. `services_seo_gap`
3. `photo_story_gap`
4. `reviews_marketing_underused`
5. `category_positioning_gap`
6. `activity_signals_gap`

### 4.3 Medical

Фокус:

1. специализация и направления
2. путь пациента: consultation -> diagnostics -> treatment
3. снижение тревожности через понятное описание визита
4. trust visuals: doctors, equipment, reception
5. отзывы как trust layer, а не просто social proof

Ключевые issue types:

1. `positioning_description_gap`
2. `services_medical_gap`
3. `services_no_price`
4. `photo_story_gap`
5. `reviews_trust_underused`
6. `category_positioning_gap`
7. `activity_signals_gap`

### 4.4 Beauty

Фокус:

1. услуги как точки входа в запись
2. prices on high-intent services
3. before/after и proof of result
4. reviews as retention + repeat-booking layer
5. freshness через кейсы, новинки, сезонные офферы

Ключевые issue types:

1. `positioning_description_gap`
2. `services_beauty_gap`
3. `services_no_price`
4. `photo_story_gap`
5. `reviews_marketing_underused`
6. `category_positioning_gap`
7. `activity_signals_gap`

### 4.5 Food

Пока профиль определяется, но reasoning остаётся базовым+intent layer.

Следующий шаг для food:

1. menu hits
2. occasion-based positioning
3. atmosphere visuals
4. dishes as SEO entities

### 4.6 Fitness

Пока профиль определяется, но reasoning остаётся базовым+intent layer.

Следующий шаг для fitness:

1. class format clarity
2. trainer differentiation
3. equipment visibility
4. schedule / membership clarity

### 4.7 Default Local Business

Fallback для сервисов без ярко выраженной вертикали.

Цель:

1. не ломать аудит
2. дать базовый quality layer
3. не использовать generic summary там, где уже есть специализированный профиль

## 5. Правила summary

Summary в сильном аудите не должен быть просто “оценка и потери выручки”.

Для профильных вертикалей summary должен отвечать:

1. на чём уже строится доверие;
2. что именно не дожато;
3. какой сейчас главный рычаг роста;
4. почему карточка недобирает поиск/конверсию;
5. что делать первым.

## 6. Правила issue blocks

Каждый `issue_block` должен содержать:

1. `title`
2. `problem`
3. `evidence`
4. `impact`
5. `fix`
6. `priority`
7. `section`

Правило качества:

- `problem` должен быть понятен владельцу бизнеса;
- `evidence` должен ссылаться на реальные сигналы карточки;
- `impact` должен объяснять, что это ломает: trust / search / conversion;
- `fix` должен быть выполнимым.

## 7. Что считать “сильным аудитом”

Внутренний критерий качества аудита:

1. он не путает тип бизнеса;
2. он не анализирует noise как service;
3. он объясняет реальную проблему, а не только числовой gap;
4. он помогает отправить аудит клиенту без ручного переписывания;
5. он даёт next steps, которые можно реально выполнить за 24h / 7d / ongoing.

## 8. Текущий статус v1

В коде уже усилены:

1. `hospitality`
2. `wellness`
3. `medical`
4. `beauty`

Следующие шаги:

1. усилить `food`
2. усилить `fitness`
3. привести `default_local_business` к тому же уровню ясности
4. добавить multilingual rendering для dynamic audit text
5. уменьшить долю ручной правки публичных audit pages до нуля
