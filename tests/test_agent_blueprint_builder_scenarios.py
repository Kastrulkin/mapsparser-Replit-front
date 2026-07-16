import json
from datetime import datetime, timezone
from pathlib import Path

from tests.agent_blueprint_fakes import *  # noqa: F403


def test_openclaw_planner_loop_understands_review_schedule_and_localos_telegram_bot():
    from services.agent_openclaw_planner_loop import build_openclaw_planner_loop

    result = build_openclaw_planner_loop(
        {
            "schema": "localos_openclaw_planner_context_v1",
            "task": (
                "Создай агента, который каждю среду в 9 утра проверяет наличие новых отзывов - "
                "запускает парсер. Если они есть, то генерирует ответ. Оба - отзыв и ответ "
                "присылает мне в телеграм через бота"
            ),
            "allowed_capabilities": ["reviews.fetch", "communications.draft"],
            "required_bindings": [
                {
                    "key": "reviews_source",
                    "provider": "localos_reviews",
                    "capability": "reviews.fetch",
                    "required_config": [],
                },
                {
                    "key": "telegram_delivery",
                    "provider": "telegram",
                    "capability": "communications.draft",
                    "required_config": ["bot_mode"],
                },
            ],
            "connection_state": {},
            "connection_answer_bindings": {},
            "output_contract": {
                "format": "json_only",
                "compiled_workflow_owner": "localos",
            },
        }
    )

    questions = {item["key"]: item for item in result["clarifying_questions"]}

    assert "telegram_target" not in questions
    assert "schedule_frequency" not in questions
    assert "post_format" not in questions


def test_agent_builder_does_not_treat_scheduled_telegram_message_as_outreach():
    from services.agent_builder_session import build_agent_builder_state
    from services.agent_blueprint_draft_builder import compile_agent_blueprint, infer_blueprint_category

    prompt = 'Сощздай агента, который каждое утро в 9 утра шлёт мне сообщение "Привет" в телеграм'

    draft = compile_agent_blueprint(prompt)
    state = build_agent_builder_state([{"role": "user", "content": prompt}])
    questions_text = " ".join(str(item.get("question") or "") for item in state["missing_questions"]).lower()

    assert infer_blueprint_category(prompt) == "custom"
    assert draft["category"] == "custom"
    assert draft["version_payload"]["trigger"] == "schedule.daily"
    assert draft["version_payload"]["schedule"]["time"] == "09:00"
    assert state["category"] == "custom"
    assert "лид" not in questions_text
    assert "prospectingleads" not in questions_text


def test_agent_builder_understands_core_user_scenarios_without_cross_domain_questions():
    from services.agent_builder_session import build_agent_builder_state

    scenarios = [
        (
            "reviews_to_telegram",
            "Проверять новые отзывы каждый день, готовить черновик ответа и присылать отзыв + ответ владельцу в Telegram.",
            "custom",
            ["external_reviews", "telegram"],
            ["telegram_destination"],
            ["лид", "prospectingleads", "где искать клиентов"],
        ),
        (
            "daily_reminder",
            "Каждое утро в 9:00 отправлять владельцу короткое сообщение или чеклист дня в Telegram.",
            "custom",
            ["manual_context", "telegram"],
            ["telegram_destination"],
            ["лид", "prospectingleads", "где искать клиентов"],
        ),
        (
            "sheets_to_telegram",
            "Раз в день брать новую строку из Google Sheets и отправлять по ней краткое сообщение в Telegram.",
            "custom",
            ["google_sheets", "telegram"],
            ["google_sheets_target"],
            ["лид", "prospectingleads", "где искать клиентов"],
        ),
        (
            "orders_without_status",
            "Проверять таблицу заказов, находить заказы без статуса или ответственного и присылать список менеджеру.",
            "tables",
            ["uploaded_tables"],
            [],
            ["лид", "prospectingleads"],
        ),
        (
            "negative_reviews",
            "Отслеживать отзывы с оценкой 1-3, срочно уведомлять владельца и готовить аккуратный черновик ответа без обещаний скидок.",
            "reviews",
            ["external_reviews"],
            [],
            ["агент услуг", "prospectingleads", "где искать клиентов"],
        ),
        (
            "map_content_plan",
            "Раз в неделю предлагать 3 темы постов для карточек на картах на основе услуг, сезона и отзывов.",
            "custom",
            ["services", "external_reviews", "business_profile"],
            [],
            ["где искать клиентов", "какие лиды"],
        ),
        (
            "services_check",
            "Раз в неделю смотреть услуги в карточке бизнеса и находить пустые описания, плохие названия или отсутствующие цены.",
            "services",
            ["services"],
            [],
            ["где искать клиентов", "какие лиды"],
        ),
        (
            "finance_import",
            "Читать таблицу расходов, находить новые строки, нормализовать категории и готовить их к добавлению в финансы LocalOS после подтверждения.",
            "custom",
            ["google_sheets", "localos_finance"],
            ["google_sheets_target"],
            ["где искать клиентов", "какие лиды"],
        ),
        (
            "partner_search",
            "Найти потенциальных партнёров в городе, собрать shortlist, подготовить первое сообщение и ждать ручного подтверждения перед отправкой.",
            "partnerships",
            ["prospectingleads", "services"],
            [],
            ["где искать клиентов", "какие лиды"],
        ),
        (
            "booking_control",
            "Каждый день проверять ближайшие записи клиентов и готовить напоминания, но отправлять только после подтверждения человека.",
            "communications",
            ["appointments"],
            [],
            ["где искать клиентов", "prospectingleads"],
        ),
    ]

    for key, prompt, expected_category, expected_sources, expected_question_keys, forbidden_question_terms in scenarios:
        state = build_agent_builder_state([{"role": "user", "content": prompt}])
        preview = state["preview"]
        questions = state["missing_questions"]
        question_keys = {str(item.get("key") or "") for item in questions}
        questions_text = " ".join(str(item.get("question") or "") for item in questions).lower()
        sources = set(preview["data_sources"])

        assert state["category"] == expected_category, key
        for source in expected_sources:
            assert source in sources, key
        for question_key in expected_question_keys:
            assert question_key in question_keys, key
        for term in forbidden_question_terms:
            assert term not in questions_text, key


def test_agent_builder_understands_second_browser_scenario_pack_without_wrong_domains():
    from services.agent_builder_session import build_agent_builder_state

    scenarios = [
        (
            "overdue_invoices",
            "Каждый день проверяй неоплаченные счета, находи просроченные больше чем на 3 дня и присылай владельцу список в Telegram.",
            "custom",
            ["localos_finance", "telegram"],
            ["просроченных", "счет"],
            ["где искать клиентов", "какие лиды", "prospectingleads", "формат поста"],
        ),
        (
            "empty_customer_cards",
            "Раз в неделю находи клиентов без телефона, email или источника прихода и готовь список для менеджера.",
            "custom",
            ["clients"],
            ["пустыми полями", "телефон"],
            ["google", "таблиц", "письм", "лид", "prospectingleads"],
        ),
        (
            "expense_control",
            "Каждый вечер проверяй новые расходы в LocalOS, выделяй подозрительно крупные траты и проси владельца подтвердить категорию.",
            "custom",
            ["localos_finance"],
            ["подозрительных расходов", "категор"],
            ["где искать клиентов", "какие лиды", "prospectingleads"],
        ),
        (
            "bookings_no_prepayment",
            "Каждое утро проверяй записи на завтра, находи клиентов без предоплаты и готовь напоминание администратору.",
            "communications",
            ["appointments"],
            ["Черновики сообщений"],
            ["где искать клиентов", "prospectingleads"],
        ),
        (
            "weak_reviews_locations",
            "Раз в неделю сравнивай отзывы по всем точкам сети, находи филиалы с падением рейтинга и присылай короткий разбор.",
            "reviews",
            ["external_reviews", "locations"],
            ["филиалам", "рейтинг"],
            ["черновики ответов", "где искать клиентов", "prospectingleads"],
        ),
        (
            "content_from_reviews",
            "Каждую неделю бери новые положительные отзывы и предлагай 3 идеи постов на их основе для карточек на картах.",
            "custom",
            ["external_reviews", "services"],
            ["3 идеи", "положительных отзывов"],
            ["черновики ответов", "где искать клиентов", "prospectingleads"],
        ),
        (
            "duplicate_services",
            "Раз в неделю проверяй список услуг и находи дубли, похожие названия и услуги без категории.",
            "services",
            ["services"],
            ["Проверка услуг"],
            ["где искать клиентов", "prospectingleads"],
        ),
        (
            "old_clients_reactivation",
            "Каждый понедельник находи клиентов, которые не записывались больше 60 дней, и готовь мягкое сообщение для возврата. Не отправляй без подтверждения.",
            "communications",
            ["appointments"],
            ["клиентов"],
            ["telegram", "телеграм", "где искать клиентов", "prospectingleads"],
        ),
        (
            "partner_replies",
            "Каждый день проверяй ответы потенциальных партнёров, классифицируй их как интересно / отказ / нужен ручной ответ и показывай следующий шаг.",
            "partnerships",
            ["prospectingleads", "outreach_drafts"],
            ["ответов партнёров", "следующий шаг"],
            ["google", "таблиц", "агент отзывов", "черновики ответов"],
        ),
        (
            "daily_problem_digest",
            "Каждое утро собирай один короткий дайджест: новые негативные отзывы, отменённые записи, просроченные задачи и необычные расходы. Присылай в Telegram.",
            "custom",
            ["localos_digest", "telegram"],
            ["ежедневный дайджест", "проблем"],
            ["где искать клиентов", "prospectingleads", "формат поста"],
        ),
    ]

    for key, prompt, expected_category, expected_sources, output_terms, forbidden_terms in scenarios:
        state = build_agent_builder_state([{"role": "user", "content": prompt}], use_ai=True)
        preview = state["preview"]
        questions_text = " ".join(str(item.get("question") or "") for item in state["missing_questions"]).lower()
        surface_text = " ".join(
            [
                state["category"],
                preview["category_label"],
                ", ".join(preview["data_sources"]),
                preview["extraction_rules"],
                preview["output_format"],
                questions_text,
            ]
        ).lower()
        sources = set(preview["data_sources"])

        assert state["category"] == expected_category, key
        for source in expected_sources:
            assert source in sources, key
        for term in output_terms:
            assert term.lower() in surface_text, key
        for term in forbidden_terms:
            assert term.lower() not in questions_text, key


def test_agent_builder_understands_third_browser_scenario_pack_without_generic_outputs():
    from services.agent_builder_session import build_agent_builder_state

    scenarios = [
        (
            "photo_quality",
            "Раз в неделю проверяй фотографии в карточках филиалов, находи устаревшие, тёмные или нерелевантные фото и предлагай, что заменить.",
            "custom",
            ["business_cards", "photos", "locations"],
            ["фото", "замен"],
            ["лид", "prospectingleads", "подозрительных расходов", "черновики ответов"],
        ),
        (
            "competitor_prices",
            "Каждый понедельник сравнивай цены на ключевые услуги с конкурентами поблизости и присылай краткий список, где мы выше или ниже рынка.",
            "custom",
            ["services", "competitors"],
            ["конкурент", "выше или ниже"],
            ["проверка услуг", "черновики ответов", "где искать клиентов"],
        ),
        (
            "cancellation_risk",
            "Каждое утро находи записи клиентов, которые часто отменяют визиты, и готовь администратору список для ручного подтверждения.",
            "communications",
            ["appointments"],
            ["риском отмены", "администратор"],
            ["доставка", "статусы реакции", "prospectingleads"],
        ),
        (
            "new_services_control",
            "Когда в LocalOS появляется новая услуга, проверяй название, описание, цену и готовь улучшенную версию для карточек.",
            "services",
            ["services"],
            ["улучшенная версия", "новой услуги"],
            ["какой результат", "отзывы"],
        ),
        (
            "customer_questions_monitoring",
            "Каждый день собирай новые вопросы клиентов из Telegram/WhatsApp, группируй по темам и предлагай ответы для базы знаний.",
            "custom",
            ["telegram", "whatsapp", "customer_questions"],
            ["вопросов клиентов", "базы знаний"],
            ["какие темы вопросов", "prospectingleads", "финансы"],
        ),
        (
            "team_tasks_check",
            "Каждое утро находи просроченные задачи сотрудников и присылай владельцу короткий список: задача, ответственный, срок, следующий шаг.",
            "custom",
            ["localos_tasks", "team"],
            ["просроченных задач", "ответственный"],
            ["какие данные", "финансы localos", "prospectingleads"],
        ),
        (
            "no_discount_promos",
            "Раз в неделю предлагай 3 идеи продвижения без скидок на основе сезонности, услуг и отзывов клиентов.",
            "custom",
            ["services", "external_reviews", "seasonality"],
            ["без скидок", "3 идеи"],
            ["черновики ответов", "проверка услуг", "prospectingleads"],
        ),
        (
            "repeated_complaints",
            "Если в отзывах или сообщениях повторяется одна и та же проблема, собери примеры и предложи, что изменить в сервисе.",
            "custom",
            ["external_reviews", "customer_messages", "services"],
            ["повторяющиеся жалобы", "изменить в сервисе"],
            ["где человек должен проверить", "черновики ответов", "prospectingleads"],
        ),
        (
            "manager_report",
            "Каждую пятницу собирай отчёт по филиалам: отзывы, записи, выручка, расходы, проблемы и рекомендации на следующую неделю.",
            "custom",
            ["external_reviews", "appointments", "localos_finance", "locations"],
            ["отчёт по филиалам", "рекомендации"],
            ["подозрительных расходов", "проверка услуг", "prospectingleads"],
        ),
        (
            "holiday_readiness",
            "За две недели до праздников проверяй карточки, услуги, посты и расписание, находи пробелы и готовь чеклист подготовки.",
            "custom",
            ["business_cards", "services", "posts", "schedule"],
            ["чеклист подготовки", "праздникам"],
            ["проверка услуг", "черновики ответов", "prospectingleads"],
        ),
    ]

    for key, prompt, expected_category, expected_sources, output_terms, forbidden_terms in scenarios:
        state = build_agent_builder_state([{"role": "user", "content": prompt}], use_ai=True)
        preview = state["preview"]
        questions_text = " ".join(str(item.get("question") or "") for item in state["missing_questions"]).lower()
        surface_text = " ".join(
            [
                state["category"],
                preview["category_label"],
                ", ".join(preview["data_sources"]),
                preview["extraction_rules"],
                preview["output_format"],
                questions_text,
            ]
        ).lower()
        sources = set(preview["data_sources"])

        assert state["category"] == expected_category, key
        for source in expected_sources:
            assert source in sources, key
        for term in output_terms:
            assert term.lower() in surface_text, key
        for term in forbidden_terms:
            assert term.lower() not in surface_text, key


def test_agent_builder_understands_fourth_browser_scenario_pack_without_generic_outputs():
    from services.agent_builder_session import build_agent_builder_state

    scenarios = [
        (
            "inventory_control",
            "Каждый вечер проверяй остатки расходников и товаров, находи позиции ниже минимума и готовь список, что заказать.",
            "custom",
            ["inventory", "products", "supplies"],
            ["список для закупки", "сколько заказать"],
            ["подозрительных расходов", "финансы localos", "prospectingleads", "какой результат"],
        ),
        (
            "staff_schedule_check",
            "Раз в неделю проверяй расписание смен, находи пересечения, пустые окна и перегрузки по сотрудникам.",
            "custom",
            ["staff_schedule", "team"],
            ["расписании смен", "перегруз"],
            ["готовый результат по задаче", "prospectingleads", "какой результат"],
        ),
        (
            "cancellation_reasons",
            "Каждую неделю собирай отменённые записи, группируй причины и предлагай, что изменить в процессе записи.",
            "custom",
            ["appointments", "clients"],
            ["причин отмен", "процессе записи"],
            ["риск отмены", "черновики сообщений", "статусы реакции"],
        ),
        (
            "admin_response_control",
            "Каждый день проверяй чаты с клиентами и находи диалоги, где администратор долго не ответил или ответил неполно.",
            "custom",
            ["customer_chats", "team"],
            ["администратор", "долго не ответил"],
            ["готовый результат по задаче", "prospectingleads"],
        ),
        (
            "faq_from_chats",
            "Раз в неделю бери повторяющиеся вопросы из клиентских переписок и предлагай новые пункты для FAQ на сайте или в карточке.",
            "custom",
            ["customer_chats", "customer_questions", "business_cards"],
            ["пункты faq", "клиентских переписок"],
            ["какой результат", "telegram", "whatsapp", "prospectingleads"],
        ),
        (
            "new_employee_check",
            "Когда добавляется новый сотрудник, проверяй, заполнены ли фото, описание, услуги, график и привязка к филиалу.",
            "custom",
            ["team", "staff_profiles", "services", "schedule", "locations"],
            ["нового сотрудника", "график"],
            ["проблемных фото", "какой результат", "prospectingleads"],
        ),
        (
            "seasonal_services",
            "Раз в месяц проверяй, какие сезонные услуги пора добавить, скрыть или обновить в карточках и прайсе.",
            "services",
            ["services", "seasonality", "business_cards", "price_list"],
            ["сезонных услуг", "добавить, скрыть или обновить"],
            ["что агент должен понять", "проверка услуг", "prospectingleads"],
        ),
        (
            "revenue_anomalies",
            "Каждое утро сравнивай вчерашнюю выручку с обычным уровнем по дню недели и присылай владельцу резкие отклонения.",
            "custom",
            ["localos_finance", "revenue"],
            ["отклонений выручки", "обычный уровень"],
            ["готовый результат по задаче", "подозрительных расходов", "какой результат", "prospectingleads"],
        ),
        (
            "map_questions_answers",
            "Каждый день проверяй новые вопросы пользователей в Яндекс/Google-карточках и готовь ответы для ручного подтверждения.",
            "custom",
            ["business_cards", "map_questions"],
            ["ответов на вопросы", "яндекс/google-карточках"],
            ["готовый результат по задаче", "черновики ответов и причины ручной проверки", "prospectingleads"],
        ),
        (
            "location_description_quality",
            "Раз в неделю проверяй описания всех филиалов, находи устаревшую информацию, одинаковые тексты и слабые формулировки.",
            "custom",
            ["locations", "business_cards", "location_descriptions"],
            ["описаниях филиалов", "слабые формулировки"],
            ["готовый результат по задаче", "prospectingleads", "какой результат"],
        ),
    ]

    for key, prompt, expected_category, expected_sources, output_terms, forbidden_terms in scenarios:
        state = build_agent_builder_state([{"role": "user", "content": prompt}], use_ai=True)
        preview = state["preview"]
        questions_text = " ".join(str(item.get("question") or "") for item in state["missing_questions"]).lower()
        surface_text = " ".join(
            [
                state["category"],
                preview["category_label"],
                ", ".join(preview["data_sources"]),
                preview["extraction_rules"],
                preview["output_format"],
                questions_text,
            ]
        ).lower()
        sources = set(preview["data_sources"])

        assert state["category"] == expected_category, key
        for source in expected_sources:
            assert source in sources, key
        for term in output_terms:
            assert term.lower() in surface_text, key
        for term in forbidden_terms:
            assert term.lower() not in surface_text, key


def test_agent_builder_new_50_plus_legacy_40_scenario_corpus_is_complete():
    from tests.agent_builder_scenario_corpus import (
        AGENT_BUILDER_REGRESSION_PLAN,
        LEGACY_AGENT_BUILDER_COMBINATION_PACKS,
        LEGACY_BROWSER_SCENARIO_COUNT,
        MIXED_AGENT_BUILDER_COMBINATIONS,
        NEW_AGENT_BUILDER_SCENARIOS,
    )

    keys = [str(item["key"]) for item in NEW_AGENT_BUILDER_SCENARIOS]
    combination_keys = {key for _, items in MIXED_AGENT_BUILDER_COMBINATIONS for key in items}
    legacy_combination_count = sum(int(pack["scenario_count"]) for pack in LEGACY_AGENT_BUILDER_COMBINATION_PACKS)
    legacy_combination_names = {
        name
        for pack in LEGACY_AGENT_BUILDER_COMBINATION_PACKS
        for name in pack["combinations"]
    }

    assert LEGACY_BROWSER_SCENARIO_COUNT == 40
    assert len(NEW_AGENT_BUILDER_SCENARIOS) == 50
    assert len(set(keys)) == 50
    assert LEGACY_BROWSER_SCENARIO_COUNT + len(NEW_AGENT_BUILDER_SCENARIOS) == 90
    assert len(MIXED_AGENT_BUILDER_COMBINATIONS) >= 10
    assert combination_keys.issubset(set(keys))
    assert len(LEGACY_AGENT_BUILDER_COMBINATION_PACKS) == 4
    assert legacy_combination_count == 40
    assert len(legacy_combination_names) == 40
    assert AGENT_BUILDER_REGRESSION_PLAN["new_scenario_count"] == 50
    assert AGENT_BUILDER_REGRESSION_PLAN["legacy_scenario_count"] == 40
    assert AGENT_BUILDER_REGRESSION_PLAN["total_scenario_count"] == 90
    assert AGENT_BUILDER_REGRESSION_PLAN["new_combinations"] == MIXED_AGENT_BUILDER_COMBINATIONS
    assert AGENT_BUILDER_REGRESSION_PLAN["legacy_combinations"] == LEGACY_AGENT_BUILDER_COMBINATION_PACKS

    all_sources = {source for item in NEW_AGENT_BUILDER_SCENARIOS for source in item["expected_sources"]}
    for source in ["browser_use", "google_sheets", "telegram", "whatsapp", "external_reviews", "localos_finance"]:
        assert source in all_sources


def test_agent_builder_understands_new_50_mixed_scenarios_without_wrong_domains():
    from services.agent_builder_session import build_agent_builder_state
    from tests.agent_builder_scenario_corpus import NEW_AGENT_BUILDER_SCENARIOS

    for item in NEW_AGENT_BUILDER_SCENARIOS:
        key = str(item["key"])
        state = build_agent_builder_state([{"role": "user", "content": item["prompt"]}], use_ai=True)
        preview = state["preview"]
        questions_text = " ".join(str(question.get("question") or "") for question in state["missing_questions"]).lower()
        surface_text = " ".join(
            [
                state["category"],
                preview["category_label"],
                ", ".join(preview["data_sources"]),
                preview["extraction_rules"],
                preview["output_format"],
                questions_text,
            ]
        ).lower()
        sources = set(preview["data_sources"])

        assert state["category"] == item["expected_category"], key
        for source in item["expected_sources"]:
            assert source in sources, key
        for term in item["expected_terms"]:
            assert str(term).lower() in surface_text, key
        for term in item["forbidden_terms"]:
            assert str(term).lower() not in surface_text, key


def test_agent_builder_keeps_real_user_scenarios_on_the_obvious_next_step():
    from services.agent_builder_session import build_agent_builder_state

    scenarios = [
        (
            "sales_to_finance",
            "Каждый вечер проверяй Google-таблицу с продажами, находи новые строки и готовь их к добавлению во вкладку Финансы. Перед внесением показывай мне список на подтверждение.",
            ["что агент должен понять", "что нужно извлечь"],
            ["google_sheets_target"],
        ),
        (
            "telegram_content_reactions",
            "После публикации поста в Telegram проверяй реакции и комментарии через API, собирай выводы и предлагай, что изменить в следующем контент-плане.",
            ["кто будет принимать решение", "где человек должен проверить"],
            [],
        ),
        (
            "negative_review_event",
            "Если появляется отзыв с оценкой 1-3, сразу присылай мне уведомление в Telegram, кратко объясняй проблему клиента и предлагай аккуратный ответ без обещаний скидок.",
            ["когда запускать агента"],
            [],
        ),
        (
            "weekly_owner_report",
            "Каждую пятницу собирай краткий отчёт: новые отзывы, продажи, расходы, записи, проблемы в карточке и что нужно сделать на следующей неделе. Присылай в Telegram.",
            ["в какой telegram", "когда запускать агента", "какой формат поста"],
            [],
        ),
        (
            "answered_review_drafts",
            "Агент должен парсить отзывы каждую среду в 9 утра. Все отображать в аккаунте ЛокалОС. Если появляются новые, то генерировать ответ и оповещать меня в телеграмме + присылать отзыв и ответ\nОтдельные черновики человек проверяет в телегираме - по оповещению",
            ["нужны отдельные черновики ответов или общий план реакции"],
            [],
        ),
    ]

    for key, prompt, forbidden_fragments, expected_question_keys in scenarios:
        state = build_agent_builder_state([{"role": "user", "content": prompt}])
        questions = state["missing_questions"]
        question_keys = {str(item.get("key") or "") for item in questions}
        questions_text = " ".join(str(item.get("question") or "") for item in questions).lower()

        for fragment in forbidden_fragments:
            assert fragment not in questions_text, key
        for question_key in expected_question_keys:
            assert question_key in question_keys, key

    ai_state = build_agent_builder_state(
        [
            {
                "role": "user",
                "content": "После публикации поста в Telegram проверяй реакции и комментарии через API, собирай выводы и предлагай, что изменить в следующем контент-плане.",
            }
        ],
        use_ai=True,
    )
    ai_questions_text = " ".join(str(item.get("question") or "") for item in ai_state["missing_questions"]).lower()

    assert ai_state["category"] == "custom"
    assert "telegram" in set(ai_state["preview"]["data_sources"])
    assert ai_state["preview"]["feasibility"]["status"] != "forbidden"
    assert "какие данные агент должен использовать" not in ai_questions_text
    assert "в какой telegram" not in ai_questions_text


def test_agent_feasibility_resolver_reports_ready_missing_choice_and_forbidden():
    from services.agent_feasibility_resolver import resolve_agent_feasibility

    required_bindings = [
        {
            "key": "google_sheets_read",
            "provider": "google_sheets",
            "capability": "google_sheets.read_rows",
            "required_config": ["spreadsheet_id", "sheet_name"],
        },
        {
            "key": "telegram_delivery",
            "provider": "telegram",
            "capability": "communications.draft",
            "required_config": ["bot_mode"],
        },
    ]
    missing = resolve_agent_feasibility(
        description="Возьми заказ из Google Sheets и подготовь пост в Telegram",
        required_capabilities=["google_sheets.read_rows", "communications.draft"],
        required_bindings=required_bindings,
        connected_integrations=[
            {
                "id": "telegram-1",
                "provider": "telegram",
                "status": "active",
                "display_name": "Business bot",
                "config": {"bot_mode": "business_bot"},
            }
        ],
    )
    assert missing["status"] == "needs_connection"
    assert missing["ready"] is False
    assert [item["provider"] for item in missing["missing_connections"]] == ["google_sheets"]
    assert missing["missing_connections"][0]["route_state"] == "available"
    assert any(item["provider"] == "native_localos" for item in missing["missing_connections"][0]["provider_routes"])
    assert missing["ready_bindings"][0]["provider"] == "telegram"
    assert missing["ready_bindings"][0]["route_state"] == "connected"
    assert missing["capabilities"][0]["route_state"] == "available"
    assert any(item["provider"] == "openclaw" for item in missing["capabilities"][1]["provider_routes"])

    choice = resolve_agent_feasibility(
        required_capabilities=["google_sheets.read_rows"],
        required_bindings=[required_bindings[0]],
        connected_integrations=[
            {
                "id": "sheet-1",
                "provider": "google_sheets",
                "status": "active",
                "display_name": "Orders A",
                "config": {"spreadsheet_id": "a", "sheet_name": "Orders"},
            },
            {
                "id": "sheet-2",
                "provider": "google_sheets",
                "status": "active",
                "display_name": "Orders B",
                "config": {"spreadsheet_id": "b", "sheet_name": "Orders"},
            },
        ],
    )
    assert choice["status"] == "needs_choice"
    assert choice["connection_choices"][0]["connection_count"] == 2

    forbidden = resolve_agent_feasibility(
        description="Подключись к компьютерам Роскосмоса и забери данные",
        required_capabilities=["unknown.external_access"],
    )
    assert forbidden["status"] == "forbidden"
    assert forbidden["forbidden"][0]["term"] == "роскосмос"


def test_agent_feasibility_resolver_blocks_maton_until_api_key_connection_exists():
    from services.agent_feasibility_resolver import resolve_agent_feasibility

    result = resolve_agent_feasibility(
        description="Отправляй сообщения через Maton",
        required_capabilities=["communications.send_offer"],
        required_bindings=[
            {
                "key": "maton_delivery",
                "provider": "maton",
                "capability": "communications.send_offer",
                "required_config": ["channel"],
            }
        ],
        connected_integrations=[],
    )

    assert result["status"] == "needs_connection"
    assert result["missing_connections"][0]["provider"] == "maton"
    assert result["capabilities"][0]["status"] == "supported"
    assert any(action["service"] == "maton" for action in result["capabilities"][0]["openclaw_actions"])


def test_communication_agent_showcase_has_five_safe_mvp_blueprints():
    from services.agent_blueprint_draft_builder import build_communication_agent_showcase_blueprints

    drafts = build_communication_agent_showcase_blueprints()
    expected = {
        "appointment_reminder": ("appointment.reminder.before", "communications.send_reminder", "approved_batch_only"),
        "post_visit_followup": ("visit.completed.after", "communications.send_reminder", "approved_batch_only"),
        "inactive_client_winback": ("client.inactive.since", "communications.send_offer", "approved_batch_only"),
        "package_offer_after_service": ("service.completed.relevant", "communications.send_offer", "approved_batch_only"),
        "inbound_request_reply_draft": ("inbound.message.received", "communications.draft", "draft_only"),
    }

    assert len(drafts) == 5
    by_key = {draft["metadata"]["communication_template_key"]: draft for draft in drafts}
    assert set(by_key) == set(expected)

    for key, values in expected.items():
        trigger, capability, mode = values
        draft = by_key[key]
        payload = draft["version_payload"]
        steps = payload["steps"]

        assert draft["category"] == "communications"
        assert payload["trigger"] == trigger
        assert payload["send_capability"] == capability
        assert payload["mode"] == mode
        assert payload["audience_rules"]
        assert payload["consent_rules"]
        assert payload["message_template"]
        assert payload["persona"]
        assert payload["delivery_outcome_journal"]["external_dispatch_performed"] is False
        assert payload["limits"]["external_send_requires_approval"] is True
        assert payload["limits"]["autonomous_send_allowed"] is False
        assert payload["external_dispatch_performed"] is False
        assert draft["metadata"]["compiled_artifact_candidate"]["schema"] == "localos_compiled_artifact_candidate_v1"
        assert draft["metadata"]["compiled_artifact_candidate"]["status"] == "validation_passed"
        assert draft["metadata"]["compiled_validation"]["valid"] is True
        assert draft["metadata"]["compiled_process"]["schema"] == "compiled_communications_workflow_v1"
        assert "communications.draft" in payload["capability_allowlist"]
        if capability != "communications.draft":
            assert capability in payload["capability_allowlist"]
            send_step = [step for step in steps if step["key"] == "send_message"][0]
            assert send_step["type"] == "capability"
            assert send_step["requires_approval"] is True
            assert send_step["payload"]["external_dispatch_performed"] is False
        else:
            assert payload["capability_allowlist"] == ["appointments.read", "communications.draft"]
            send_step = [step for step in steps if step["key"] == "send_message"][0]
            assert send_step["type"] == "artifact"
            assert send_step["payload"]["delivery_state"] == "not_dispatched"


def test_communication_agent_compiler_selects_mvp_templates_from_text():
    from services.agent_blueprint_draft_builder import compile_agent_blueprint

    examples = [
        ("Сделай сообщение после визита", "post_visit_followup"),
        ("Вернуть клиента, который давно не был", "inactive_client_winback"),
        ("Пакетное предложение после релевантной услуги", "package_offer_after_service"),
        ("Черновик ответа на входящий запрос", "inbound_request_reply_draft"),
    ]

    for prompt, expected_key in examples:
        draft = compile_agent_blueprint(prompt)
        assert draft["category"] == "communications"
        assert draft["metadata"]["communication_template_key"] == expected_key


def test_agent_product_view_uses_aiagent_as_voice_persona():
    from services.agent_product_layer import (
        attach_persona_to_version,
        attach_product_agent_to_blueprint,
        parse_persona_row,
    )

    persona = parse_persona_row(
        {
            "id": "voice-1",
            "name": "Администратор Анна",
            "type": "communication",
            "description": "Голос администратора",
            "personality": "спокойная и внимательная",
            "identity": "администратор салона",
            "speech_style": "коротко и дружелюбно",
            "restrictions_json": "{\"no_promises\": true}",
            "variables_json": "{\"signature\": \"Анна\"}",
            "is_active": 1,
        }
    )
    personas = {"voice-1": persona}
    version = attach_persona_to_version(
        {
            "id": "version-1",
            "version_number": 2,
            "persona_agent_id": "voice-1",
        },
        personas,
    )
    blueprint = attach_product_agent_to_blueprint(
        {
            "id": "blueprint-1",
            "name": "Напоминания о записи",
            "category": "communications",
            "status": "draft",
            "metadata_json": "{\"compiler\": \"agent_compiler_v1\"}",
        },
        version,
        personas,
    )

    assert version["persona"]["source"] == "AIAgents"
    assert version["persona"]["role"] == "agent_voice"
    assert blueprint["product_agent"]["kind"] == "agent"
    assert blueprint["product_agent"]["source"] == "agent_blueprints"
    assert blueprint["product_agent"]["persona_agent_id"] == "voice-1"
    assert blueprint["product_agent"]["voice"]["name"] == "Администратор Анна"
    assert blueprint["product_agent"]["components"]["persona"]["role"] == "agent_voice"
    assert blueprint["product_agent"]["legacy"]["communication_agent_is_blueprint_category"] is True
