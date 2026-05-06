from __future__ import annotations

import re
from typing import Any


PATTERN_VERSION = "2026-05-06.v1"


GLOBAL_PROFILE: dict[str, Any] = {
    "industry_key": "global",
    "label": "Общие правила LocalOS",
    "markers": (),
    "service_patterns": (
        "Название = конкретная услуга или товар + важный атрибут.",
        "Описание короткое: что это и для какого сценария, без рекламной воды.",
        "Если данных мало, оставить нейтральную формулировку вместо выдуманных фактов.",
    ),
    "news_patterns": (
        "Пост должен иметь конкретный повод: услуга, продукт, обновление, сезонный спрос или локальный контекст.",
        "Не выдумывать акции, цены, адреса, график, мастеров, врачей или товары.",
        "Для сети адаптировать тему под конкретную точку, если известен адрес или город.",
    ),
    "review_reply_patterns": (
        "Коротко поблагодарить или проявить эмпатию.",
        "Использовать деталь из отзыва, если она есть.",
        "Не обещать исправление, компенсацию или результат без фактов.",
    ),
    "forbidden_claims": (
        "лучший",
        "гарантия результата",
        "гарантируем",
        "навсегда",
        "без вреда",
        "безболезненно",
        "мгновенный эффект",
    ),
    "forbidden_industry_drifts": (
        "Не переносить темы одной индустрии в другую без исходного факта.",
    ),
    "positive_signals": (
        "конкретика",
        "атрибуты",
        "локальный контекст",
        "деталь из отзыва",
    ),
    "examples": (
        "Маникюр с покрытием гель-лак",
        "Круассан с ветчиной",
        "УЗИ молочных желез",
    ),
    "version": PATTERN_VERSION,
}


INDUSTRY_PROFILES: dict[str, dict[str, Any]] = {
    "beauty": {
        "industry_key": "beauty",
        "label": "Beauty / салон / косметология",
        "markers": (
            "beauty",
            "beauty_salon",
            "салон красоты",
            "парикмах",
            "маник",
            "педик",
            "космет",
            "бров",
            "ресниц",
            "эпиля",
            "массаж",
            "spa",
            "спа",
        ),
        "service_patterns": (
            "Услуга + зона, если зона есть в исходнике.",
            "Услуга + длина волос, если длина есть в исходнике.",
            "Услуга + препарат или бренд + объем, если они есть в исходнике.",
            "Услуга + пол, возраст, число зон или сеансов, если они указаны.",
        ),
        "news_patterns": (
            "Тема услуги, сезонный спрос, запись, мастер или фото результата только при наличии факта.",
            "Не обещать медицинский или гарантированный результат.",
            "Подчеркнуть комфорт, аккуратность, консультацию или запись без громких обещаний.",
        ),
        "review_reply_patterns": (
            "Поблагодарить за отзыв и упомянуть мастера, процедуру, аккуратность, результат или комфорт, если это есть в отзыве.",
            "Для негатива: эмпатия + предложение связаться, без медицинских обещаний.",
        ),
        "forbidden_claims": (
            "омоложение кожи",
            "стойкий результат",
            "до полугода",
            "без боли",
            "идеальный результат",
            "лечит",
            "избавит от",
        ),
        "forbidden_industry_drifts": (
            "Не превращать общую депиляцию или ваксинг в брови, лицо или бикини без исходной зоны.",
            "Не добавлять препарат, бренд, объем, пол, возраст или длину волос без исходника.",
        ),
        "positive_signals": (
            "мастер",
            "аккуратно",
            "результат",
            "комфорт",
            "зона",
            "препарат",
        ),
        "examples": (
            "Коррекция и окрашивание бровей",
            "Биоревитализация Belarti Lift 1 ml",
            "Детская стрижка 12-15 лет",
            "Афрокудри на экстра длинные волосы",
        ),
        "version": PATTERN_VERSION,
    },
    "food": {
        "industry_key": "food",
        "label": "Еда / пекарни / кафе",
        "markers": ("food", "пекар", "кофейн", "кондитер", "кафе", "ресторан", "бар", "быстрое питание"),
        "service_patterns": (
            "Продукт + основной состав или вкус.",
            "Короткое название блюда без рекламных эпитетов.",
            "Если есть цена, порция или формат подачи, сохранять их.",
        ),
        "news_patterns": (
            "Продукт дня, свежая выпечка, кофе + продукт, завтрак или локальный повод точки.",
            "Не выдумывать скидки, бесплатные позиции, доставку или график.",
        ),
        "review_reply_patterns": (
            "Упомянуть блюдо, кофе, свежесть, атмосферу или обслуживание, если это есть в отзыве.",
            "Пригласить зайти снова коротко и естественно.",
        ),
        "forbidden_claims": ("самый вкусный", "лучший кофе", "скидка", "бесплатно"),
        "forbidden_industry_drifts": (
            "Не добавлять beauty, medical или auto темы.",
        ),
        "positive_signals": ("кофе", "свежая выпечка", "вкус", "чисто", "персонал", "завтрак"),
        "examples": ("Круассан с ветчиной", "Эклер фисташковый", "Латте", "Пирог с лососем"),
        "version": PATTERN_VERSION,
    },
    "medical": {
        "industry_key": "medical",
        "label": "Медицина / клиники",
        "markers": ("medical", "медцентр", "клиник", "врач", "доктор", "лаборатор", "диагност", "стоматолог"),
        "service_patterns": (
            "Процедура + область или метод.",
            "Консультация + специализация врача.",
            "Точность важнее продающего тона.",
        ),
        "news_patterns": (
            "Объяснить процедуру, подготовку, запись или доступный формат приема без гарантий.",
            "Не обещать лечение, результат или отсутствие боли без исходного факта.",
        ),
        "review_reply_patterns": (
            "Упомянуть врача, доверие, отношение, объяснение или прием, если это есть в отзыве.",
            "Не давать медицинские советы в ответе.",
        ),
        "forbidden_claims": ("вылечим", "гарантируем лечение", "без осложнений", "без боли", "избавим от"),
        "forbidden_industry_drifts": ("Не добавлять beauty или food темы."),
        "positive_signals": ("врач", "доктор", "отношение", "объяснили", "лечение", "быстро приняли"),
        "examples": ("Консультация дерматолога", "УЗИ молочных желез", "Лазерное удаление новообразований"),
        "version": PATTERN_VERSION,
    },
    "hospitality": {
        "industry_key": "hospitality",
        "label": "Отели / гостиницы",
        "markers": ("hotel", "отель", "гостиниц", "апартамент", "номер", "завтрак"),
        "service_patterns": (
            "Тип номера + вместимость.",
            "Тип номера + питание или удобство, если указано.",
        ),
        "news_patterns": (
            "Номер, завтрак, семейное размещение, парковка, расположение или nearby tips только по фактам.",
        ),
        "review_reply_patterns": (
            "Упомянуть номер, чистоту, завтрак, расположение или персонал, если это есть в отзыве.",
        ),
        "forbidden_claims": ("лучший отель", "гарантированный вид", "скидка"),
        "forbidden_industry_drifts": ("Не добавлять клинические, beauty или cafe услуги без факта."),
        "positive_signals": ("номер", "чисто", "завтрак", "персонал", "расположение", "парковка"),
        "examples": ("Стандарт двухместный с завтраком", "Семейный номер", "Номер с двумя кроватями"),
        "version": PATTERN_VERSION,
    },
    "retail": {
        "industry_key": "retail",
        "label": "Retail / магазины",
        "markers": ("retail", "магазин", "товары", "плать", "двер", "букет", "цвет", "парфюмер"),
        "service_patterns": (
            "Товар + модель, размер, вариант или комплект.",
            "Сохранять цену, наличие, размер и материал, если указаны.",
        ),
        "news_patterns": (
            "Наличие, новая коллекция, подборка, товар недели или помощь консультанта только по фактам.",
        ),
        "review_reply_patterns": (
            "Упомянуть выбор, консультанта, качество, размер или товар, если это есть в отзыве.",
        ),
        "forbidden_claims": ("самые низкие цены", "скидка", "бесплатно"),
        "forbidden_industry_drifts": ("Не добавлять услуги другой индустрии без факта."),
        "positive_signals": ("выбор", "наличие", "размер", "консультант", "качество", "цена"),
        "examples": ("Свадебное платье Габриэлла", "Межкомнатная дверь Шелтон", "Букет Комплимент"),
        "version": PATTERN_VERSION,
    },
    "gas_station": {
        "industry_key": "gas_station",
        "label": "АЗС / топливо",
        "markers": ("gas_station", "азс", "заправ", "топлив", "бензин", "дизель"),
        "service_patterns": (
            "Топливо или сервис + практическое удобство.",
            "Не добавлять магазин, кафе, мойку или кофе без исходного факта.",
        ),
        "news_patterns": (
            "Топливо, маршрут, сервис станции, чистота, кофе или магазин только по фактам.",
        ),
        "review_reply_patterns": (
            "Упомянуть топливо, скорость, чистоту, кофе, кассу или сервис, если это есть в отзыве.",
        ),
        "forbidden_claims": ("лучшее топливо", "гарантия качества", "скидка"),
        "forbidden_industry_drifts": ("Не добавлять пекарню, салон красоты, медицину или ресторан без факта."),
        "positive_signals": ("топливо", "быстро", "чисто", "кофе", "персонал", "туалет"),
        "examples": ("Кофе с собой на АЗС", "Магазин при АЗС", "Топливо и сервисы АЗС"),
        "version": PATTERN_VERSION,
    },
    "auto_service": {
        "industry_key": "auto_service",
        "label": "Автосервис",
        "markers": ("auto_service", "автосервис", "сто", "ремонт авто", "шиномонтаж", "диагностик"),
        "service_patterns": (
            "Операция + узел автомобиля.",
            "Сохранять марку, тип авто, срок или формат, если указаны.",
        ),
        "news_patterns": ("Сезонная проверка, диагностика, запись или конкретная услуга без выдуманных акций.",),
        "review_reply_patterns": ("Упомянуть скорость, диагностику, ремонт, мастера или объяснение, если есть в отзыве.",),
        "forbidden_claims": ("ремонт за час", "гарантия без фактов", "самый дешевый"),
        "forbidden_industry_drifts": ("Не добавлять АЗС или мойку без факта."),
        "positive_signals": ("ремонт", "быстро", "диагностика", "мастер", "объяснили", "качество"),
        "examples": ("Диагностика подвески", "Замена масла в двигателе", "Шиномонтаж легковых авто"),
        "version": PATTERN_VERSION,
    },
    "fitness": {
        "industry_key": "fitness",
        "label": "Фитнес / спорт",
        "markers": ("gym", "fitness", "фитнес", "спортзал", "трениров", "йога", "пилатес"),
        "service_patterns": ("Формат тренировки + уровень или цель, если указаны.",),
        "news_patterns": ("Групповое занятие, запись, расписание или формат тренировки только по фактам.",),
        "review_reply_patterns": ("Упомянуть тренера, зал, атмосферу или занятие, если есть в отзыве.",),
        "forbidden_claims": ("гарантированное похудение", "лечит", "результат за неделю"),
        "forbidden_industry_drifts": ("Не добавлять medical обещания."),
        "positive_signals": ("тренер", "зал", "атмосфера", "занятие", "результат"),
        "examples": ("Персональная тренировка", "Групповые занятия йогой", "Фитнес для начинающих"),
        "version": PATTERN_VERSION,
    },
    "school": {
        "industry_key": "school",
        "label": "Образование / школа",
        "markers": ("school", "школ", "образован", "обучен", "курс", "дет", "гимназ", "academy"),
        "service_patterns": ("Формат занятия + возраст, навык или уровень.",),
        "news_patterns": ("Занятие, набор группы, открытый урок или учебный навык только по фактам.",),
        "review_reply_patterns": ("Упомянуть преподавателя, занятие, ребенка, навык или атмосферу, если есть в отзыве.",),
        "forbidden_claims": ("гарантия поступления", "100% результат", "лучшие преподаватели"),
        "forbidden_industry_drifts": ("Не добавлять beauty или medical темы без факта."),
        "positive_signals": ("преподаватель", "ребенок", "занятия", "курс", "результат", "понятно"),
        "examples": ("Английский для дошкольников", "Подготовка к школе для детей 5-6 лет"),
        "version": PATTERN_VERSION,
    },
    "local_business": {
        "industry_key": "local_business",
        "label": "Локальный бизнес",
        "markers": (),
        "service_patterns": ("Писать строго по исходной услуге.",),
        "news_patterns": ("Нейтральный апдейт карточки без выдуманных деталей.",),
        "review_reply_patterns": ("Короткая благодарность или эмпатия с привязкой к отзыву.",),
        "forbidden_claims": (),
        "forbidden_industry_drifts": ("Не добавлять отрасль, которой нет в профиле или фактах.",),
        "positive_signals": ("конкретика", "деталь", "понятный следующий шаг"),
        "examples": ("Консультация специалиста", "Запись на услугу"),
        "version": PATTERN_VERSION,
    },
}


_ALIASES = {
    "cafe": "food",
    "bakery": "food",
    "food/bakery/cafe": "food",
    "medical_clinic": "medical",
    "hotel": "hospitality",
    "spa": "beauty",
}


def normalize_pattern_text(value: Any) -> str:
    text = str(value or "").strip().lower().replace("ё", "е")
    text = re.sub(r"[^0-9a-zа-я\s]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def normalize_industry_key(value: Any) -> str:
    key = normalize_pattern_text(value).replace(" ", "_")
    return _ALIASES.get(key, key if key in INDUSTRY_PROFILES else "local_business")


def detect_industry_key(
    *,
    business_name: Any = "",
    business_type: Any = "",
    industry: Any = "",
    categories: Any = "",
    service_text: Any = "",
) -> str:
    direct_key = normalize_industry_key(business_type)
    if direct_key != "local_business":
        return direct_key
    joined = normalize_pattern_text(
        " ".join(
            str(item or "")
            for item in (business_name, business_type, industry, categories, service_text)
            if str(item or "").strip()
        )
    )
    if not joined:
        return "local_business"
    for key, profile in INDUSTRY_PROFILES.items():
        if key == "local_business":
            continue
        for marker in profile.get("markers") or ():
            normalized_marker = normalize_pattern_text(marker)
            if normalized_marker and normalized_marker in joined:
                return key
    return "local_business"


def get_industry_pattern_profile(industry_key: Any) -> dict[str, Any]:
    key = normalize_industry_key(industry_key)
    profile = INDUSTRY_PROFILES.get(key) or INDUSTRY_PROFILES["local_business"]
    return {
        "industry_key": profile["industry_key"],
        "label": profile["label"],
        "markers": list(profile.get("markers") or ()),
        "service_patterns": list(profile.get("service_patterns") or ()),
        "news_patterns": list(profile.get("news_patterns") or ()),
        "review_reply_patterns": list(profile.get("review_reply_patterns") or ()),
        "forbidden_claims": list(profile.get("forbidden_claims") or ()),
        "forbidden_industry_drifts": list(profile.get("forbidden_industry_drifts") or ()),
        "positive_signals": list(profile.get("positive_signals") or ()),
        "examples": list(profile.get("examples") or ()),
        "version": profile.get("version") or PATTERN_VERSION,
    }


def _lines(items: list[str], prefix: str = "- ") -> str:
    clean_items = [str(item or "").strip() for item in items if str(item or "").strip()]
    if not clean_items:
        return "- нет"
    return "\n".join(prefix + item for item in clean_items)


def format_industry_pattern_prompt(industry_key: Any, mode: str = "service") -> str:
    profile = get_industry_pattern_profile(industry_key)
    global_rules = GLOBAL_PROFILE
    if mode == "news":
        pattern_key = "news_patterns"
    elif mode == "review_reply":
        pattern_key = "review_reply_patterns"
    else:
        pattern_key = "service_patterns"
    return (
        f"Industry patterns version: {profile['version']}\n"
        f"Индустрия: {profile['label']} ({profile['industry_key']})\n"
        "Приоритет: исходные факты -> guardrails -> запреты индустрии -> SEO -> рабочие паттерны -> стиль.\n"
        "Общие рабочие паттерны:\n"
        f"{_lines(list(global_rules.get(pattern_key) or []))}\n"
        "Рабочие паттерны индустрии:\n"
        f"{_lines(profile.get(pattern_key) or [])}\n"
        "Запрещенные обещания и рискованные формулировки:\n"
        f"{_lines(list(global_rules.get('forbidden_claims') or []) + list(profile.get('forbidden_claims') or []))}\n"
        "Запрещенный drift:\n"
        f"{_lines(list(global_rules.get('forbidden_industry_drifts') or []) + list(profile.get('forbidden_industry_drifts') or []))}\n"
        "Примеры направления, не копировать дословно:\n"
        f"{_lines(profile.get('examples') or [])}"
    )


def evaluate_pattern_fit(text: Any, industry_key: Any, mode: str = "service") -> dict[str, Any]:
    profile = get_industry_pattern_profile(industry_key)
    normalized = normalize_pattern_text(text)
    issue_codes: list[str] = []
    positive_hits: list[str] = []
    forbidden_hits: list[str] = []

    if not normalized:
        issue_codes.append("empty_text")

    for phrase in list(GLOBAL_PROFILE.get("forbidden_claims") or []) + list(profile.get("forbidden_claims") or []):
        clean_phrase = normalize_pattern_text(phrase)
        if clean_phrase and clean_phrase in normalized:
            forbidden_hits.append(str(phrase))

    for signal in profile.get("positive_signals") or ():
        clean_signal = normalize_pattern_text(signal)
        if clean_signal and clean_signal in normalized:
            positive_hits.append(str(signal))

    if forbidden_hits:
        issue_codes.append("forbidden_claim")

    if mode == "service":
        has_specificity = bool(re.search(r"\d|[а-яa-z]{4,}\s+[а-яa-z]{4,}", normalized))
        if not has_specificity:
            issue_codes.append("low_specificity")
    if mode == "news":
        if not positive_hits and len(normalized) < 120:
            issue_codes.append("weak_industry_context")
    if mode == "review_reply":
        if "спасибо" not in normalized and "благодар" not in normalized and "жаль" not in normalized:
            issue_codes.append("missing_reply_acknowledgement")

    score = 100
    score -= len(issue_codes) * 20
    score += min(len(positive_hits) * 5, 15)
    score = max(0, min(score, 100))
    return {
        "industry_key": profile["industry_key"],
        "mode": mode,
        "score": score,
        "status": "ok" if not issue_codes else "needs_review",
        "issue_codes": issue_codes,
        "positive_hits": positive_hits,
        "forbidden_hits": forbidden_hits,
        "version": profile["version"],
    }
