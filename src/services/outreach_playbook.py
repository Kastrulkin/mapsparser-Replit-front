"""Approved LocalOS outreach methodology and segment language.

The B2B Telegram corpus supplies reusable methods, never recipient facts.
Owner language is kept as a hypothesis vocabulary and may only be attributed
to a particular lead when separate evidence supports it.
"""

from __future__ import annotations

from typing import Any

from services.outreach_template_service import (
    OUTREACH_TEMPLATES,
    TEMPLATE_LIBRARY_VERSION,
)


PLAYBOOK_VERSION = "localos_outreach_playbook_v4"
CORPUS_TAG = "telegram_b2b"
PAIN_SIGNAL_LIBRARY_VERSION = "beauty_pain_signals_v4"

B2B_METHOD_RULES = (
    "Начинать с проверяемого действия или артефакта получателя, а не с общего комплимента.",
    "Разделять наблюдение, гипотезу и мост к предложению.",
    "Строить оффер как результат, короткий механизм, доказательство и один лёгкий следующий шаг.",
    "Каждым следующим касанием добавлять новый аргумент, а не повторять первое письмо.",
    "Не предлагать звонок слишком рано: сначала дать полезный материал, кейс или понятную идею.",
    "Автоматизировать подготовку и очередь, но оставлять человеку approval и остановку по ответу.",
    "Писать кратко: узнаваемая ситуация, что делает LocalOS, один подтверждённый результат и один короткий вопрос.",
    "В касании о контенте начинать с знакомой работы и цены времени, а затем называть конкретный результат.",
    "Не обещать автоматическую связку «выполненная услуга → пост»: черновик допустим только при настроенной передаче обезличенного названия услуги.",
    "Не повторять одну боль во всей цепочке: каждое касание должно показывать новую сторону системы.",
    "Не называть касание последним: получатель мог не видеть предыдущие.",
    "Тема каждого outreach email: «Название клиента | ЛокалОС | Сотрудничество».",
)

BEAUTY_OWNER_PAINS = (
    {
        "key": "marketing_and_clients",
        "phrases": (
            "Клиентов нет от слова совсем",
            "Ведём соцсети, запускаем рекламу, а записи всё равно нет",
            "Не знаю, что публиковать, и времени постоянно снимать контент нет",
        ),
        "localos_bridge": "Карты, автопостинг и системный поиск локального спроса.",
        "support": "supported",
    },
    {
        "key": "staff_and_processes",
        "phrases": (
            "Мастера уходят и клиентов за собой уводят",
            "Мастера саботируют правила и считают, что салон им должен",
        ),
        "localos_bridge": "КПИ, понятные схемы работы и контроль исполнения.",
        "support": "supported",
    },
    {
        "key": "reviews_and_service",
        "phrases": (
            "День забит, а тут прилетает плохой отзыв. Как на него правильно ответить?",
            "Как реагировать на жалобы и не потерять репутацию?",
            "Мастер не понял клиента, а разбираться теперь владельцу",
        ),
        "localos_bridge": "Мониторинг отзывов, очередь ответов и проверяемые сценарии сервиса.",
        "support": "supported",
    },
    {
        "key": "pricing_and_average_ticket",
        "phrases": (
            "Работы много, а средний чек всё равно маленький",
            "Боюсь, что после повышения цены клиенты разбегутся",
        ),
        "localos_bridge": "Аналитика услуг, допродажи, кросс-продажи и партнёрские пакеты.",
        "support": "supported",
    },
    {
        "key": "operations_and_burnout",
        "phrases": (
            "Если не я, то никто",
            "Работаю за администратора, управляющего и бухгалтера",
            "Бизнес есть, команда есть, даже деньги есть - но жить некогда",
        ),
        "localos_bridge": "Автоматизация повторяющихся задач и единый контур контроля.",
        "support": "supported",
    },
    {
        "key": "retention",
        "phrases": (
            "Новых клиентов много, а возвратность низкая",
            "Постоянно привлекать новых клиентов слишком дорого",
        ),
        "localos_bridge": "Сценарии повторных касаний; владение клиентской базой зависит от подключённой CRM.",
        "support": "partial",
    },
    {
        "key": "revenue_without_profit",
        "phrases": (
            "Салон работает, а денег нет",
            "Клиенты есть, мастера заняты, но в конце месяца остаются копейки",
        ),
        "localos_bridge": "Финансовые КПИ, разбор услуг и регулярный контроль показателей.",
        "support": "supported",
    },
)

# These mappings are hypotheses to test, never facts about a recipient.  Each
# executable rule requires several public observations so that a single post,
# vacancy or discount cannot be turned into a diagnosis about the owner.
BEAUTY_PAIN_SIGNAL_HYPOTHESES = (
    {
        "key": "active_social_with_map_gap",
        "pain_key": "marketing_and_clients",
        "required_signals": ["active_official_social", "map_visibility_gap"],
        "hypothesis": (
            "Компания уже старается привлекать клиентов через контент, "
            "а карты могут быть недоиспользованным каналом."
        ),
        "safe_formulation": (
            "Вы активно ведёте соцсети. Карты тоже могли бы помогать вам привлекать клиентов."
        ),
        "contraindications": [
            "Соцсеть не подтверждена как официальная.",
            "Нет свежей регулярной активности.",
            "Нет отдельного подтверждения слабой карточки на картах.",
        ],
        "status": "testable",
    },
    {
        "key": "active_external_channels_with_incomplete_map_profile",
        "pain_key": "marketing_and_clients",
        "required_signals": [
            "active_official_social",
            "official_website",
            "map_owner_not_verified",
            "empty_map_service_catalog",
            "no_map_news",
        ],
        "hypothesis": (
            "Компания поддерживает сайт и официальный канал, а карточка на картах "
            "может оставаться недоиспользованным каналом привлечения."
        ),
        "safe_formulation": (
            "Вы ведёте сайт и Telegram, но в карточке на картах пока нет услуг и новостей. "
            "Карты тоже могли бы помогать привлекать новых клиентов."
        ),
        "contraindications": [
            "Соцсеть не подтверждена как официальная или давно не обновлялась.",
            "Официальный сайт не найден.",
            "В карточке есть услуги или новости.",
            "Данные карточки подтверждены владельцем.",
        ],
        "status": "testable",
    },
    {
        "key": "active_social_with_service_price_gap",
        "pain_key": "pricing_and_average_ticket",
        "required_signals": ["active_official_social", "verified_service_price_gap"],
        "hypothesis": (
            "Компания уже привлекает внимание контентом, но неполные цены в карточке "
            "могут усложнять выбор услуги и запись."
        ),
        "safe_formulation": (
            "Вы активно ведёте канал. В карточке у части услуг не указана цена; "
            "можно проверить, насколько легко клиенту выбрать и записаться."
        ),
        "contraindications": [
            "Источник не подтверждён как официальный канал компании.",
            "Каталог услуг неполный или не относится к этой компании.",
            "Цены отсутствуют менее чем у 30% из как минимум пяти услуг.",
        ],
        "status": "testable",
    },
    {
        "key": "active_social_with_unanswered_negative_review",
        "pain_key": "reviews_and_service",
        "required_signals": ["active_official_social", "fresh_negative_review_without_response"],
        "hypothesis": (
            "Компания развивает публичный канал, а работа с отзывами может оставаться "
            "ручной задачей владельца."
        ),
        "safe_formulation": (
            "Вы активно ведёте канал, при этом в карточке есть свежий отзыв с оценкой "
            "до 3 без ответа компании."
        ),
        "contraindications": [
            "У отзыва уже есть ответ компании.",
            "Отзыв старше 180 дней или относится к другой компании.",
            "Нельзя пересказывать обвинения из отзыва или делать вывод о качестве услуг.",
        ],
        "status": "testable",
    },
    {
        "key": "recent_price_update_announcement",
        "pain_key": "pricing_and_average_ticket",
        "required_signals": ["recent_official_price_update_post"],
        "hypothesis": (
            "Если после обновления прайса новые цены приходится отдельно переносить "
            "на сайт, карты и другие площадки, LocalOS может подготовить эти обновления на проверку."
        ),
        "safe_formulation": (
            "Вы обновили цены и прайс-лист. Если новые цены приходится переносить на несколько "
            "площадок, LocalOS может подготовить обновления на проверку."
        ),
        "hypothesis_status": "conditional_operator_approved",
        "localos_action": (
            "LocalOS готовит обновления цен для сайта, карт и других площадок - "
            "вам остаётся проверить и подтвердить."
        ),
        "contraindications": [
            "Публикация не относится к официальному каналу компании.",
            "Обновление старше 30 дней.",
            "Нельзя утверждать, сколько времени получатель тратит на перенос цен.",
        ],
        "status": "testable",
    },
    {
        "key": "recent_new_service_announcement",
        "pain_key": "marketing_and_clients",
        "required_signals": ["recent_official_new_service_post"],
        "hypothesis": (
            "Запуск новой услуги создаёт конкретный момент, когда карты, контент и "
            "повторные касания могут поддержать спрос."
        ),
        "safe_formulation": (
            "Вы недавно анонсировали новую услугу. Можно проверить, как поддержать "
            "запуск в картах и других публичных каналах."
        ),
        "contraindications": [
            "Публикация не относится к официальному каналу компании.",
            "Анонс старше 30 дней.",
            "Нельзя утверждать, что новая услуга продаётся плохо.",
        ],
        "status": "testable",
    },
    {
        "key": "recent_event_announcement",
        "pain_key": "marketing_and_clients",
        "required_signals": ["recent_official_event_post"],
        "hypothesis": (
            "Событие даёт конкретный повод синхронизировать контент, карты и "
            "локальное продвижение."
        ),
        "safe_formulation": (
            "Вы анонсировали событие для клиентов. Можно проверить, как использовать "
            "этот повод в картах и других каналах."
        ),
        "contraindications": [
            "Публикация не относится к официальному каналу компании.",
            "Событие уже прошло и публикация старше 30 дней.",
            "Нельзя обещать посещаемость или продажи без отдельного расчёта.",
        ],
        "status": "testable",
    },
    {
        "key": "repeated_open_slots",
        "pain_key": "marketing_and_clients",
        "required_signals": ["two_recent_official_open_slot_posts"],
        "hypothesis": (
            "Компания регулярно старается заполнить свободные окна; "
            "системное привлечение записей может быть актуальной задачей."
        ),
        "safe_formulation": (
            "Вы несколько раз публиковали свободные окна. Возможно, вам актуальны "
            "дополнительные источники записи."
        ),
        "contraindications": [
            "Найдено только одно объявление.",
            "Публикация старше 30 дней.",
            "Источник не принадлежит компании.",
        ],
        "status": "testable",
    },
    {
        "key": "unanswered_reviews_with_active_presence",
        "pain_key": "reviews_and_service",
        "required_signals": ["two_recent_unanswered_reviews", "active_official_presence"],
        "hypothesis": (
            "Компания развивает публичное присутствие, но регулярная работа с отзывами "
            "может оставаться без внимания."
        ),
        "safe_formulation": (
            "У вас есть свежие отзывы без ответа. Их можно разобрать и подготовить ответы."
        ),
        "contraindications": [
            "Ответ владельца не проверен.",
            "Отзывы не относятся к этой компании.",
            "Отзыв только один или он старше 90 дней.",
        ],
        "status": "testable",
    },
    {
        "key": "repeated_discount_promotions",
        "pain_key": "pricing_and_average_ticket",
        "required_signals": ["three_recent_official_discount_posts"],
        "hypothesis": (
            "Компания регулярно стимулирует спрос скидками; может быть полезно проверить "
            "средний чек и альтернативные механики предложения."
        ),
        "safe_formulation": (
            "Вы регулярно публикуете акции. Можно проверить, какие предложения дают запись "
            "без постоянного снижения цены."
        ),
        "contraindications": [
            "Акция сезонная или единичная.",
            "Нет трёх публикаций за 60 дней.",
            "Нельзя утверждать, что средний чек низкий."
        ],
        "status": "testable",
    },
    {
        "key": "repeated_hiring_signals",
        "pain_key": "staff_and_processes",
        "required_signals": ["two_recent_official_hiring_posts"],
        "hypothesis": (
            "Компания несколько раз искала сотрудников; найм или организация работы команды "
            "могут быть актуальной задачей."
        ),
        "safe_formulation": (
            "Вы несколько раз публиковали вакансии. Возможно, сейчас актуальны найм и "
            "понятные схемы работы команды."
        ),
        "contraindications": [
            "Найдена одна вакансия.",
            "Вакансия размещена агрегатором, а не компанией.",
            "Нельзя делать вывод о текучести сотрудников."
        ],
        "status": "testable",
    },
    {
        "key": "multi_location_profile_inconsistency",
        "pain_key": "operations_and_burnout",
        "required_signals": ["multiple_locations", "verified_profile_inconsistency"],
        "hypothesis": (
            "У сети есть расхождения между карточками; стандартизация регулярных задач "
            "может быть актуальна руководителю."
        ),
        "safe_formulation": (
            "У нескольких точек отличаются данные в карточках. Это можно привести к одному "
            "стандарту и дальше проверять автоматически."
        ),
        "contraindications": [
            "Не подтверждено, что точки относятся к одной сети.",
            "Расхождения не перечислены по каждой карточке.",
            "Нельзя утверждать, что владелец выгорает."
        ],
        "status": "testable",
    },
)

APPROVED_LOCALOS_CASES = (
    {
        "key": "salon_price_300plus_clicks_v1",
        "pain_keys": ("pricing_and_average_ticket", "operations_and_burnout"),
        "signal_keys": ("recent_price_update_announcement",),
        "recipient_segments": ("private_beauty_specialist", "beauty_team", "beauty_network"),
        "safe_formulation": (
            "Салон красоты в пару кликов обновляет прайс-лист на 300+ позиций через LocalOS. "
            "Вам может быть интересно также сэкономить время?"
        ),
        "result": "beauty_pricelist_300_positions_update",
        "status": "approved",
        "source": "founder_confirmed_case",
    },
    {
        "key": "beauty_maps_zero_to_ten",
        "pain_keys": ("marketing_and_clients",),
        "signal_keys": ("active_social_with_map_gap", "map_gap"),
        "recipient_segments": ("private_beauty_specialist", "beauty_team", "beauty_network"),
        "safe_formulation": (
            "Для салона красоты мы настроили работу с картами и подняли запись "
            "с 0 до 10 клиентов в день только за счёт этого канала."
        ),
        "result": "0_to_10_clients_per_day_from_maps",
        "status": "approved",
        "source": "founder_confirmed_case",
    },
    {
        "key": "beauty_service_catalog_orders_plus_ten",
        "pain_keys": ("pricing_and_average_ticket", "marketing_and_clients"),
        "signal_keys": ("service_catalog_gap",),
        "recipient_segments": ("private_beauty_specialist", "beauty_team", "beauty_network"),
        "safe_formulation": (
            "Для салона мы сократили список услуг и сделали названия понятнее. "
            "Заказы выросли на 10%."
        ),
        "result": "orders_plus_10_percent",
        "status": "approved",
        "source": "founder_confirmed_case",
    },
    {
        "key": "beauty_service_catalog_revenue_plus_twenty",
        "pain_keys": ("pricing_and_average_ticket", "revenue_without_profit"),
        "signal_keys": ("service_catalog_gap",),
        "recipient_segments": ("private_beauty_specialist", "beauty_team", "beauty_network"),
        "safe_formulation": (
            "Для салона мы сократили список услуг и сделали названия понятнее. "
            "Выручка выросла на 20%."
        ),
        "result": "revenue_plus_20_percent",
        "status": "approved",
        "source": "founder_confirmed_case",
    },
    {
        "key": "reviews_save_seven_hours",
        "pain_keys": ("reviews_and_service", "operations_and_burnout"),
        "signal_keys": ("unanswered_reviews",),
        "recipient_segments": (),
        "safe_formulation": (
            "Для сети кафе мы настроили подготовку ответов на отзывы с проверкой человеком. "
            "Это освободило 7 часов в неделю."
        ),
        "result": "seven_hours_saved_per_week",
        "status": "approved",
        "source": "founder_confirmed_case",
    },
    {
        "key": "beauty_social_autopublishing",
        "pain_keys": ("operations_and_burnout", "marketing_and_clients"),
        "signal_keys": ("regular_manual_content",),
        "recipient_segments": ("private_beauty_specialist", "beauty_team", "beauty_network"),
        "safe_formulation": (
            "Для салона красоты мы автоматизировали публикации в VK и Telegram, "
            "а публикации на картах оставили под ручным контролем."
        ),
        "result": "vk_telegram_autopublishing_maps_manual",
        "status": "approved",
        "source": "founder_confirmed_case",
    },
    {
        "key": "culture_map_visits_plus_seven_hundred",
        "pain_keys": ("marketing_and_clients",),
        "signal_keys": ("active_social_with_map_gap", "map_gap"),
        "recipient_segments": (),
        "safe_formulation": (
            "Для культурного пространства работа с картами увеличила посещаемость "
            "карточки на 700%."
        ),
        "result": "map_card_visits_plus_700_percent",
        "status": "approved",
        "source": "founder_confirmed_case",
    },
)

APPROVED_LOCALOS_PROOFS = tuple(
    item["safe_formulation"] for item in APPROVED_LOCALOS_CASES
) + ("LocalOS применяется более чем в 240 точках малого бизнеса.",)

APPROVED_FOUNDER_ORIGIN = (
    "Сначала я создавал LocalOS для себя - чтобы меньше тонуть в операционке. "
    "Теперь с его помощью мы освобождаем от повторяющихся задач других предпринимателей."
)

APPROVED_LOCALOS_MESSAGE_EXAMPLES = (
    {
        "key": "estem_yclients_content_time_v1",
        "pain_key": "operations_and_burnout",
        "status": "approved",
        "source": "founder_editorial_correction",
        "rules": (
            "Начинать с знакомой работы и потери времени.",
            "Называть результат: отдельные черновики для площадок.",
            "Связь с YCLIENTS описывать условно: только если настроена передача названия услуги без данных пациента.",
            "Черновики проверяет команда; публикация в Картах остаётся ручной.",
        ),
        "text": (
            "Здравствуйте!\n\n"
            "Я Александр Демьянов, основатель LocalOS.\n\n"
            "Вы ведёте соцсети: 2 августа в канале Эстем вышел разбор ботулинотерапии с тремя преимуществами и указанием врача Дарьи Резник.\n\n"
            "Посты для нескольких площадок приходится писать и редактировать несколько раз, а это отнимает время.\n\n"
            "LocalOS помогает управлять контентом сразу для Telegram, VK и Яндекс Карт. "
            "Если из YCLIENTS можно передавать название выполненной услуги без данных пациента, LocalOS подготовит по ней отдельные черновики. "
            "Команда проверит тексты, а публикация в Картах останется ручной.\n\n"
            "Вы бы хотели сэкономить время на постах в соцсетях?"
        ),
    },
    {
        "key": "reviews_owner_day_interruption",
        "pain_key": "reviews_and_service",
        "case_key": "reviews_save_seven_hours",
        "status": "approved",
        "source": "founder_editorial_correction",
        "text": (
            "День забит, а тут прилетает плохой отзыв. Как на него правильно ответить? "
            "Мастер не понял клиента, а разбираться теперь владельцу.\n\n"
            "LocalOS отслеживает новые отзывы и готовит ответы - вам остаётся только подтвердить. "
            "Для сети кафе это освободило 7 часов в неделю.\n\n"
            "Вам может быть это интересно?"
        ),
    },
    {
        "key": "fgf_partnership_acquisition_owner_v1",
        "pain_key": "marketing_and_clients",
        "status": "approved",
        "source": "founder_editorial_correction",
        "text": (
            "Здравствуйте! Я Александр Демьянов, основатель LocalOS.\n\n"
            "Вижу, что FGF уже использует платное продвижение в Яндексе. "
            "Но не стоит зависеть от одного канала привлечения.\n\n"
            "LocalOS подберёт местные бизнесы со смежной аудиторией и подготовит "
            "предложение о партнёрстве. Вы сами решите, кому отправить.\n\n"
            "Вам было бы интересно найти новые источники клиентов через партнёрства?"
        ),
    },
)

# These are versioned product corrections, not model inspiration.  A draft may
# use one only when its candidate explicitly selects the contract key.
APPROVED_OUTREACH_COPY_CONTRACTS = (
    {
        "key": "fgf_average_ticket_owner_v1",
        "status": "approved",
        "source": "founder_editorial_correction",
        "angle": "average_ticket",
        "required_exact_phrases": (
            "Подскажите, прорабатывали ли другие способы увеличения среднего чека?",
            "Вам было бы интересно увеличить средний чек?",
        ),
        "rules": (
            "Первый вопрос — диагностический; финальный вопрос — единственный CTA.",
            "Матрица строится из подтверждённого прайса, а медицинскую совместимость подтверждает врач.",
            "Не подменять трудозатраты ручной адаптации темой повторной проверки фактов.",
            "Писать кратко и без дополнительного CTA.",
        ),
    },
    {
        "key": "fgf_partnership_acquisition_owner_v1",
        "status": "approved",
        "source": "founder_editorial_correction",
        "angle": "integrated_system",
        "required_exact_phrases": (
            "Но не стоит зависеть от одного канала привлечения.",
            "Вам было бы интересно найти новые источники клиентов через партнёрства?",
        ),
        "rules": (
            "Говорить о партнёрствах как о дополнительном источнике клиентов, без обещания результата.",
            "Подбор и предложение — черновики; получателей утверждает пользователь.",
            "Не добавлять второй CTA.",
        ),
    },
)


def beauty_outreach_guidance() -> dict[str, Any]:
    """Return prompt-safe guidance without asserting pains about a recipient."""

    return {
        "version": PLAYBOOK_VERSION,
        "method_source": CORPUS_TAG,
        "method_rules": list(B2B_METHOD_RULES),
        "pain_language_status": "segment_hypothesis_only",
        "pain_library": [
            {
                "key": item["key"],
                "phrases": list(item["phrases"]),
                "localos_bridge": item["localos_bridge"],
                "support": item["support"],
            }
            for item in BEAUTY_OWNER_PAINS
        ],
        "pain_signal_library_version": PAIN_SIGNAL_LIBRARY_VERSION,
        "pain_signal_hypotheses": [
            {
                "key": item["key"],
                "pain_key": item["pain_key"],
                "required_signals": list(item["required_signals"]),
                "hypothesis": item["hypothesis"],
                "hypothesis_status": item.get("hypothesis_status", "segment_hypothesis_only"),
                "safe_formulation": item["safe_formulation"],
                "localos_action": item.get("localos_action"),
                "contraindications": list(item["contraindications"]),
                "status": item["status"],
            }
            for item in BEAUTY_PAIN_SIGNAL_HYPOTHESES
        ],
        "approved_founder_origin": APPROVED_FOUNDER_ORIGIN,
        "approved_cases": [
            {
                **item,
                "pain_keys": list(item["pain_keys"]),
                "signal_keys": list(item["signal_keys"]),
                "recipient_segments": list(item["recipient_segments"]),
            }
            for item in APPROVED_LOCALOS_CASES
        ],
        "approved_message_examples": [dict(item) for item in APPROVED_LOCALOS_MESSAGE_EXAMPLES],
        "approved_copy_contracts": [
            {
                **item,
                "required_exact_phrases": list(item["required_exact_phrases"]),
                "rules": list(item["rules"]),
            }
            for item in APPROVED_OUTREACH_COPY_CONTRACTS
        ],
        "template_library_version": TEMPLATE_LIBRARY_VERSION,
        "outreach_templates": [
            {
                **item,
                "angles": list(item["angles"]),
                "required_evidence": list(item["required_evidence"]),
            }
            for item in OUTREACH_TEMPLATES
        ],
        "approved_proofs": list(APPROVED_LOCALOS_PROOFS),
        "constraints": [
            "Не приписывать боль получателю без отдельного evidence.",
            "В одном касании использовать одну боль и один CTA.",
            "Цитировать язык владельцев только как узнаваемую ситуацию сегмента.",
            "Не повторять карточку на картах в каждом follow-up.",
        ],
    }


def beauty_touch_learning_dimensions(
    angle: str,
    *,
    case_key: str | None = None,
) -> dict[str, Any]:
    """Return explicit dimensions used to compare outcomes of playbook touches."""

    pain_by_angle = {
        "signal": "marketing_and_clients",
        "founder_story": "operations_and_burnout",
        "proof": "marketing_and_clients",
        "audit_step": "integrated_operating_system",
        "phone_handoff": "diagnostic_open_question",
        "respectful_close": "operations_and_burnout",
        "content_operations": "operations_and_burnout",
        "average_ticket": "pricing_and_average_ticket",
        "reviews_service": "reviews_and_service",
        "integrated_system": "integrated_operating_system",
        "founder_origin": "operations_and_burnout",
    }
    return {
        "playbook_version": PLAYBOOK_VERSION,
        "pain_key": pain_by_angle.get(str(angle or "").strip()),
        "case_key": case_key,
    }
