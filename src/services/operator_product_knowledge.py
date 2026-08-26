from __future__ import annotations

import json
import re
from typing import Any


PRODUCT_SOURCES = ("PRODUCT.md", "README.md")


FEATURES: tuple[dict[str, Any], ...] = (
    {
        "key": "today",
        "title": "Сегодня и рабочая сводка",
        "aliases": ("сегодня", "сводка", "внимание", "дела на сегодня", "что важно"),
        "summary": "Собирает сохранённые сигналы бизнеса и показывает, что требует внимания первым.",
        "can_do": ("показать отзывы без ответа", "показать предупреждения, approvals и несвежие данные", "дать переход к следующему действию"),
        "boundaries": ("сводка не обновляет внешние источники сама",),
        "route": "/dashboard/today",
        "status": "available",
    },
    {
        "key": "profile",
        "title": "Профиль и данные бизнеса",
        "aliases": ("профиль", "бизнес", "компания", "адрес", "реквизиты", "данные бизнеса"),
        "summary": "Хранит основные сведения, контекст, сайт, точки и настройки выбранного бизнеса.",
        "can_do": ("показать выбранный бизнес", "открыть редактирование профиля", "использовать контекст бизнеса в рекомендациях и черновиках"),
        "boundaries": ("изменение доступа и критичных настроек выполняется в профильном интерфейсе",),
        "route": "/dashboard/profile",
        "status": "available",
    },
    {
        "key": "maps",
        "title": "Карты и аудит карточки",
        "aliases": ("карты", "карточка", "яндекс карты", "яндекс бизнес", "2гис", "google business", "аудит карточки", "парсинг"),
        "summary": "Показывает сохранённые данные карточек, рейтинг, отзывы, услуги, свежесть, ошибки и рекомендации.",
        "can_do": ("прочитать последний снимок и статус парсинга", "показать аудит и слабые места", "подготовить или запустить поддерживаемое обновление с учётом кредитов"),
        "boundaries": ("свежая внешняя проверка может быть платной", "изменения во внешних кабинетах не выполняются без отдельного поддерживаемого provider flow и подтверждения"),
        "route": "/dashboard/card",
        "status": "available",
    },
    {
        "key": "competitors",
        "title": "Конкуренты и соседи",
        "aliases": ("конкурент", "конкуренты", "сосед", "соседи", "рядом", "наблюдение за конкурентами", "цены конкурента"),
        "summary": "Сравнивает бизнес с сохранёнными ближайшими конкурентами и позволяет открыть их последний снимок.",
        "can_do": ("показать сохранённых конкурентов", "сопоставить рейтинг, отзывы и доступные данные", "открыть раздел для целевой проверки конкурента"),
        "boundaries": ("слово «сосед» требует выбора, если конкурентов несколько", "новый внешний парсинг нельзя выдавать за уже выполненный и он требует отдельного поддерживаемого запуска"),
        "route": "/dashboard/card?tab=competitors",
        "status": "beta",
    },
    {
        "key": "services",
        "title": "Услуги и меню",
        "aliases": ("услуга", "услуги", "прайс", "цена", "меню услуг", "категория услуг", "seo услуг"),
        "summary": "Управляет услугами, категориями, ценами, описаниями и предложениями по улучшению меню.",
        "can_do": ("показать услуги", "подготовить SEO-улучшения и группировку", "изменить одну однозначно указанную цену", "применить подтверждённый пакет внутренних изменений"),
        "boundaries": ("массовое применение требует preview и подтверждения", "внешние карты автоматически не меняются"),
        "route": "/dashboard/card?tab=services",
        "status": "available",
    },
    {
        "key": "seo_visibility",
        "title": "SEO и поисковая видимость",
        "aliases": ("seo", "сео", "wordstat", "поисковые запросы", "ключевые слова", "видимость в поиске", "минус слова"),
        "summary": "Показывает поисковые запросы и SEO-сигналы карточки и помогает улучшать названия и описания услуг.",
        "can_do": ("открыть сохранённые запросы и Wordstat-инструменты", "показать SEO-проблемы услуг", "подготовить безопасные предложения по текстам"),
        "boundaries": ("частотность и позиция зависят от источника и даты проверки", "предложение по тексту не изменяет внешнюю карточку автоматически"),
        "route": "/dashboard/card?tab=keywords",
        "status": "available",
    },
    {
        "key": "reviews",
        "title": "Отзывы и репутация",
        "aliases": ("отзыв", "отзывы", "репутация", "ответ на отзыв", "ответов на отзывы", "публикация ответов на отзывы", "неотвеченные отзывы", "рейтинг"),
        "summary": "Хранит отзывы, показывает отзывы без ответа и готовит черновики ответов.",
        "can_do": ("показать сохранённые отзывы без ответа", "проверить новые отзывы через обновление карт", "подготовить один или несколько черновиков ответов"),
        "boundaries": ("публикация ответа на карту остаётся ручной, пока точный provider write не поддержан и не подтверждён",),
        "route": "/dashboard/card?tab=reviews&review_filter=all",
        "status": "available",
    },
    {
        "key": "content",
        "title": "Контент, новости и публикации",
        "aliases": ("контент", "контент-план", "пост", "публикация", "новость", "соцсети", "календарь контента"),
        "summary": "Готовит новости, посты, контент-планы и хранит историю черновиков и результатов.",
        "can_do": ("показать контент за дату или период", "подготовить новость, social draft или контент-план", "открыть календарь и историю"),
        "boundaries": ("генерация может расходовать кредиты", "подготовка ничего не публикует", "внешняя публикация требует отдельного подключения и подтверждения"),
        "route": "/dashboard/content",
        "status": "available",
    },
    {
        "key": "finance",
        "title": "Финансы",
        "aliases": ("финансы", "выручка", "доход", "расход", "продажа", "продажи", "маржа", "прибыль", "импорт продаж"),
        "summary": "Показывает финансовую сводку, KPI и импортирует подтверждённые доходы, расходы и списки продаж.",
        "can_do": ("посчитать доходы, расходы и баланс за период", "подготовить одну финансовую операцию", "распознать список продаж, показать preview и записать после подтверждения"),
        "boundaries": ("финансовая запись всегда проходит отдельное подтверждение", "неоднозначные даты, суммы и валюты требуют уточнения", "LocalOS не является CRM для клиентских записей"),
        "route": "/dashboard/finance",
        "status": "available",
    },
    {
        "key": "average_ticket",
        "title": "Средний чек и допродажи",
        "aliases": ("средний чек", "допродажа", "допродажи", "апселл", "кросс-селл", "пакет услуг"),
        "summary": "Связывает цены и структуру услуг с возможностями роста среднего чека.",
        "can_do": ("показать сохранённые показатели среднего чека", "показать идеи допродаж и пакетов", "открыть детальный расчёт"),
        "boundaries": ("рекомендации не являются фактом продажи и требуют проверки владельцем",),
        "route": "/dashboard/average-ticket",
        "status": "available",
    },
    {
        "key": "progress",
        "title": "Прогресс и CRM-показатели",
        "aliases": ("прогресс", "crm", "записи", "бронирования", "загрузка", "неявки", "no-show", "rebooking", "динамика"),
        "summary": "Показывает динамику карточки, загрузки, записей и импортированных CRM-показателей.",
        "can_do": ("показать сохранённую аналитику и результаты", "прочитать записи на выбранную дату, если источник подключён", "открыть проблемную область"),
        "boundaries": ("LocalOS не заменяет CRM: клиентские записи ведутся во внешней CRM",),
        "route": "/dashboard/progress",
        "status": "available",
    },
    {
        "key": "web_analytics",
        "title": "Аналитика сайта",
        "aliases": ("аналитика сайта", "tracker", "посетители сайта", "сессии", "страницы", "источники трафика", "источниками трафика", "трафик на сайте", "cta", "конверсии сайта"),
        "summary": "Beta-трекер показывает анонимные сессии, страницы, источники и безопасные целевые действия за 7, 30 или 90 дней.",
        "can_do": ("показать посетителей, сессии, страницы и популярные пути", "показать CTA и факты начала или отправки формы", "использовать агрегаты как сигналы роста"),
        "boundaries": ("нет чтения значений полей, fingerprinting, session replay и heatmaps", "доступность зависит от feature flag и установленного tracker.js"),
        "route": "/dashboard/web-analytics",
        "status": "beta",
    },
    {
        "key": "partnerships",
        "title": "Партнёрства и supervised outreach",
        "aliases": ("партнер", "партнёр", "партнерство", "партнёрство", "outreach", "лид", "лиды", "контакты компаний", "совместная акция"),
        "summary": "Ищет подходящие компании, собирает evidence, готовит персонализированные цепочки и ведёт результаты касаний.",
        "can_do": ("показать лидов и найти кандидатов в LocalOS", "подготовить fit-обоснование и черновик сообщения", "вести версии, approvals, доставку и stop-on-reply для поддерживаемых каналов"),
        "boundaries": ("внешняя отправка всегда требует approval и runtime preflight", "WhatsApp, SMS и личный MAX остаются ручными без проверенного адаптера"),
        "route": "/dashboard/partnerships",
        "status": "beta",
    },
    {
        "key": "promotion",
        "title": "Продвижение и локальные авторы",
        "aliases": ("продвижение", "блогер", "инфлюенсер", "автор", "реклама у блогеров", "локальные авторы"),
        "summary": "Помогает находить локальных авторов и готовить контролируемые кампании продвижения.",
        "can_do": ("открыть поиск и реестр авторов", "подготовить условия и материалы кампании", "сохранить новую версию на проверку"),
        "boundaries": ("бюджет, права, сроки и внешние сообщения требуют явной проверки",),
        "route": "/dashboard/promotion",
        "status": "beta",
    },
    {
        "key": "telegram_radar",
        "title": "Telegram-радар",
        "aliases": ("telegram радар", "телеграм радар", "мониторинг telegram", "каналы telegram", "сигналы telegram", "telethon"),
        "summary": "Читает только выбранные разрешённые Telegram-источники через отдельную бизнес-сессию и сохраняет публичные сигналы.",
        "can_do": ("настроить источники радара", "показать найденные сигналы", "использовать публичные посты как evidence"),
        "boundaries": ("Bot API не читает личные контакты владельца", "radar_enabled не включает outreach_enabled", "секреты и 2FA не должны появляться в ответе Оператора"),
        "route": "/dashboard/telegram-radar",
        "status": "beta",
    },
    {
        "key": "telegram_control",
        "title": "Telegram owner-bot и Mini App",
        "aliases": ("owner bot", "owner-bot", "localospro bot", "@localospro_bot", "mini app", "мини апп", "управление через telegram", "уведомления владельцу"),
        "summary": "Глобальный бот LocalOS и Mini App дают владельцу доступ к сводкам, approvals, уведомлениям и безопасным переходам с тем же tenant scope, что и web-кабинет.",
        "can_do": ("показать клиентское меню и сводки", "принять решение по ожидающему approval", "уведомить владельца", "передать подтверждённый пост в явно подключённый канал, если бот имеет право"),
        "boundaries": ("Bot API не читает личные контакты и не пишет от имени пользовательского аккаунта", "owner-bot не заменяет бизнес-сессию Telegram-радара и outreach"),
        "route": "/telegram/control",
        "status": "available",
    },
    {
        "key": "customer_bot",
        "title": "Брендированный бот бизнеса",
        "aliases": ("бот бизнеса", "брендированный бот", "telegram_bot_token", "бот для клиентов", "клиентский бот", "ии бот бизнеса"),
        "summary": "Отдельный Bot API token бизнеса используется только для брендированного клиентского бота и его webhook-сценариев.",
        "can_do": ("подключить отдельного бота бизнеса", "обрабатывать поддерживаемые клиентские webhook-сценарии", "использовать фирменное имя бота в клиентском контакте"),
        "boundaries": ("не заменяет owner-bot LocalOS", "не заменяет пользовательскую MTProto-сессию для радара или outreach", "подключение не даёт доступ к личным контактам"),
        "route": "/dashboard/settings/integrations",
        "status": "beta",
    },
    {
        "key": "ai_visibility",
        "title": "Продвижение в AI-чатах",
        "aliases": ("ai-чаты", "ии-чаты", "ai visibility", "видимость в ии", "ответы нейросетей", "гео продвижение"),
        "summary": "Проверяет присутствие бизнеса в AI-ответах и помогает подготовить рекомендации по видимости.",
        "can_do": ("открыть проверки и сохранённые результаты", "показать рекомендации по присутствию бизнеса"),
        "boundaries": ("результаты зависят от конкретной проверяемой системы и времени", "LocalOS не гарантирует позицию в ответах внешней модели"),
        "route": "/dashboard/ai-chat-promotion",
        "status": "beta",
    },
    {
        "key": "agents",
        "title": "Агенты",
        "aliases": ("агент", "агенты", "ии-сотрудник", "ии сотрудники", "автоматизация", "compiled ai", "сценарий агента", "расписание агента"),
        "summary": "Создаёт управляемых ИИ-сотрудников из проверяемых compiled workflows с версиями, расписанием, журналом и approvals.",
        "can_do": ("показать состояние агентов и последние запуски", "создать или настроить сценарий в интерфейсе", "запускать certified beta read, draft и safe-internal workflows"),
        "boundaries": ("production runtime ограничен beta cohort и сертифицированными capability", "внешние действия и рискованные изменения требуют approval", "preview и рабочий запуск имеют разные правила биллинга"),
        "route": "/dashboard/agents",
        "status": "beta",
    },
    {
        "key": "chats",
        "title": "Чаты и сообщения",
        "aliases": ("чат", "чаты", "сообщение", "напоминание", "песочница аутрича", "симуляция ответа"),
        "summary": "Готовит сообщения, показывает рабочие диалоги и предоставляет dry-run песочницу аутрича.",
        "can_do": ("подготовить черновик сообщения", "симулировать outreach без production-записей", "подготовить поддерживаемую отправку к подтверждению"),
        "boundaries": ("черновик не означает отправку", "внешняя отправка и чтение ответов возможны только через реально подключённый scoped provider"),
        "route": "/dashboard/chats",
        "status": "beta",
    },
    {
        "key": "network",
        "title": "Сеть и локации",
        "aliases": ("сеть", "локация", "локации", "филиал", "филиалы", "точки", "network"),
        "summary": "Объединяет несколько точек, показывает сетевую сводку и позволяет сравнить проблемные локации.",
        "can_do": ("показать состояние сети и проблемные точки", "переключить рабочий scope", "открыть сетевые отзывы и метрики"),
        "boundaries": ("доступ сотрудника определяется отдельно для сети и конкретных бизнесов",),
        "route": "/dashboard/network",
        "status": "available",
    },
    {
        "key": "integrations",
        "title": "Настройки и интеграции",
        "aliases": ("настройки", "интеграция", "подключение", "oauth", "yclients", "telegram bot", "vk", "google business", "ошибка подключения"),
        "summary": "Управляет подключениями карт, CRM, Telegram, VK и другими tenant-scoped источниками.",
        "can_do": ("показать активность, последнюю синхронизацию и ошибки", "открыть настройку подключения", "объяснить различия разрешений и каналов"),
        "boundaries": ("Оператор не показывает токены, ключи и session strings", "подключение источника само по себе не разрешает публикацию или outreach"),
        "route": "/dashboard/settings/integrations",
        "status": "available",
    },
    {
        "key": "billing",
        "title": "Подписка, кредиты и биллинг",
        "aliases": ("подписка", "тариф", "кредиты", "баланс", "биллинг", "оплата", "лимит кредитов"),
        "summary": "Показывает доступ, баланс и стоимость платных действий Оператора и агентов.",
        "can_do": ("объяснить, почему действие платное", "показать необходимость пополнения или тарифа", "учесть лимиты, reserve, charge и release"),
        "boundaries": ("платёж и изменение доступа не выполняются без явного пользовательского действия", "наличие кредитов не отменяет approval для внешних и рискованных действий"),
        "route": "/dashboard/settings",
        "status": "available",
    },
    {
        "key": "public_materials",
        "title": "Публичные аудиты, статьи, кейсы и sales rooms",
        "aliases": ("публичный аудит", "sales room", "sales-room", "комната сделки", "статья", "статьи", "кейс", "кейсы", "документ", "публичные материалы", "audit offer"),
        "summary": "LocalOS хранит публичные статьи, кейсы, документы, audit-offer страницы и приватные relationship/sales-room материалы.",
        "can_do": ("открыть опубликованные статьи, кейсы и документы", "подготовить audit или relationship material в поддерживаемом workflow", "переиспользовать подтверждённый материал в отношениях"),
        "boundaries": ("создание черновика не делает материал публичным", "публичный доступ и внешняя отправка требуют отдельных явных действий", "sales room не должна раскрывать tenant-private данные"),
        "route": "/documents",
        "status": "beta",
    },
)


FEATURE_BY_KEY = {str(feature["key"]): feature for feature in FEATURES}


def _normalize(value: Any) -> str:
    text = str(value or "").casefold().replace("ё", "е")
    return re.sub(r"[^a-zа-я0-9]+", " ", text).strip()


def resolve_product_feature(query: Any, feature_key: Any = None) -> dict[str, Any] | None:
    requested_key = str(feature_key or "").strip()
    if requested_key in FEATURE_BY_KEY:
        return FEATURE_BY_KEY[requested_key]
    normalized = _normalize(query)
    if not normalized:
        return None
    candidates: list[tuple[int, dict[str, Any]]] = []
    for feature in FEATURES:
        score = 0
        for alias in feature.get("aliases") or ():
            normalized_alias = _normalize(alias)
            if normalized_alias and normalized_alias in normalized:
                score = max(score, len(normalized_alias.split()) * 10 + len(normalized_alias))
        if score:
            candidates.append((score, feature))
    if not candidates:
        return None
    candidates.sort(key=lambda item: (-item[0], str(item[1].get("key") or "")))
    return candidates[0][1]


def _result_ref(feature: dict[str, Any]) -> dict[str, Any]:
    return {
        "entity_type": "localos.feature",
        "entity_id": str(feature.get("key") or ""),
        "label": f"Открыть «{feature.get('title')}»",
        "href": str(feature.get("route") or "/dashboard/operator"),
    }


def build_product_feature_explanation(query: Any, feature_key: Any = None) -> dict[str, Any]:
    feature = resolve_product_feature(query, feature_key)
    if not feature:
        return {
            "status": "clarification_required",
            "intent": "operator.product_explain",
            "chat_response": "Какую функцию LocalOS объяснить: карты, услуги, отзывы, контент, финансы, партнёрства, аналитику, агентов или подключения?",
            "clarification": {"question": "Какую функцию LocalOS объяснить?"},
            "feature_count": len(FEATURES),
            "external_writes_performed": False,
        }
    can_do = [str(item) for item in feature.get("can_do") or ()]
    boundaries = [str(item) for item in feature.get("boundaries") or ()]
    response = f"{feature['title']}. {feature['summary']}"
    if can_do:
        response += "\n\nЧто можно:\n- " + "\n- ".join(can_do)
    if boundaries:
        response += "\n\nВажно:\n- " + "\n- ".join(boundaries)
    return {
        "status": "completed",
        "intent": "operator.product_explain",
        "feature": {
            "key": feature.get("key"),
            "title": feature.get("title"),
            "summary": feature.get("summary"),
            "status": feature.get("status"),
            "can_do": can_do,
            "boundaries": boundaries,
            "route": feature.get("route"),
            "sources": list(PRODUCT_SOURCES),
        },
        "chat_response": response,
        "result_ref": _result_ref(feature),
        "external_writes_performed": False,
        "paid_actions_performed": False,
        "credit_charged": False,
    }


def build_product_catalog_response() -> dict[str, Any]:
    groups = [
        {"key": feature.get("key"), "title": feature.get("title"), "status": feature.get("status"), "route": feature.get("route")}
        for feature in FEATURES
    ]
    titles = [str(feature.get("title") or "") for feature in FEATURES]
    return {
        "status": "completed",
        "intent": "operator_help",
        "chat_response": (
            "Можно описать задачу своими словами. Я знаю основные рабочие области LocalOS: "
            + ", ".join(titles)
            + ".\n\nЯ либо выполню безопасное доступное действие, либо покажу сохранённые данные, либо объясню ограничение и открою нужный раздел. Публикации, отправки, финансовые и массовые изменения требуют предусмотренного подтверждения."
        ),
        "features": groups,
        "feature_count": len(groups),
        "sources": list(PRODUCT_SOURCES),
        "external_writes_performed": False,
        "paid_actions_performed": False,
        "credit_charged": False,
    }


def classify_product_explanation_intent(message: Any) -> bool:
    normalized = _normalize(message)
    if not normalized or not resolve_product_feature(normalized):
        return False
    markers = (
        "что такое",
        "как работает",
        "расскажи про",
        "объясни",
        "для чего",
        "что умеет",
        "можно ли в localos",
        "есть ли в localos",
    )
    return any(marker in normalized for marker in markers)


def _row_to_dict(cursor: Any, row: Any) -> dict[str, Any]:
    if isinstance(row, dict):
        return dict(row)
    if hasattr(row, "keys"):
        try:
            return dict(row)
        except Exception:
            return {}
    description = getattr(cursor, "description", None) or []
    columns = [column[0] for column in description]
    if isinstance(row, (tuple, list)):
        return {columns[index]: row[index] for index in range(min(len(columns), len(row)))}
    return {}


def _competitor_list(value: Any) -> list[dict[str, Any]]:
    raw = value
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except Exception:
            raw = []
    result = []
    for index, item in enumerate(raw if isinstance(raw, list) else []):
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or item.get("title") or item.get("business_name") or "").strip()
        if not name:
            name = f"Конкурент {index + 1}"
        result.append(
            {
                "id": item.get("id") or item.get("external_id"),
                "name": name,
                "rating": item.get("rating"),
                "reviews_count": item.get("reviews_count") or item.get("reviewsCount"),
                "address": item.get("address"),
                "url": item.get("url") or item.get("maps_url"),
            }
        )
    return result


def read_saved_competitors(cursor: Any, *, business_id: str, name: Any = None) -> dict[str, Any]:
    cursor.execute(
        """
        SELECT competitors, created_at, updated_at
        FROM cards
        WHERE business_id = %s
          AND competitors IS NOT NULL
        ORDER BY created_at DESC NULLS LAST
        LIMIT 1
        """,
        (business_id,),
    )
    row = _row_to_dict(cursor, cursor.fetchone())
    competitors = _competitor_list(row.get("competitors"))
    requested = _normalize(name)
    if requested:
        selected = [item for item in competitors if requested in _normalize(item.get("name"))]
        if selected:
            competitors = selected
        else:
            names = [str(item.get("name") or "") for item in competitors[:8]]
            return {
                "status": "clarification_required",
                "intent": "competitors.read",
                "chat_response": "Не нашёл такого конкурента в сохранённом списке." + (" Доступны: " + ", ".join(names) + "." if names else " Добавьте конкурента в разделе «Конкуренты»."),
                "clarification": {"question": "Какого конкурента проверить?", "options": names},
                "competitors": competitors,
                "result_ref": _result_ref(FEATURE_BY_KEY["competitors"]),
                "external_writes_performed": False,
            }
    if not competitors:
        return {
            "status": "completed",
            "intent": "competitors.read",
            "chat_response": "В последнем сохранённом снимке нет конкурентов. Добавьте или проверьте их в разделе «Конкуренты».",
            "competitors": [],
            "count": 0,
            "result_ref": _result_ref(FEATURE_BY_KEY["competitors"]),
            "external_writes_performed": False,
        }
    if not requested and len(competitors) > 1:
        names = [str(item.get("name") or "") for item in competitors[:8]]
        return {
            "status": "clarification_required",
            "intent": "competitors.read",
            "chat_response": "Нашёл несколько сохранённых конкурентов: " + ", ".join(names) + ". Кого вы называете соседом?",
            "clarification": {"question": "Какого конкурента проверить?", "options": names},
            "competitors": competitors[:8],
            "count": len(competitors),
            "snapshot_at": row.get("updated_at") or row.get("created_at"),
            "result_ref": _result_ref(FEATURE_BY_KEY["competitors"]),
            "external_writes_performed": False,
        }
    selected = competitors[0]
    rating = selected.get("rating")
    reviews_count = selected.get("reviews_count")
    facts = [str(selected.get("name") or "Конкурент")]
    if rating is not None:
        facts.append(f"рейтинг {rating}")
    if reviews_count is not None:
        facts.append(f"отзывов {reviews_count}")
    return {
        "status": "completed",
        "intent": "competitors.read",
        "chat_response": "Последний сохранённый снимок: " + ", ".join(facts) + ". Это сохранённые данные, новая внешняя проверка не запускалась.",
        "competitors": [selected],
        "count": 1,
        "snapshot_at": row.get("updated_at") or row.get("created_at"),
        "fresh_external_check_performed": False,
        "result_ref": _result_ref(FEATURE_BY_KEY["competitors"]),
        "external_writes_performed": False,
    }
