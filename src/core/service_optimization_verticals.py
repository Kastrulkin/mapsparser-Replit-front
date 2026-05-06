"""Vertical rules for service optimization prompts."""

from __future__ import annotations

from typing import Any

from core.industry_patterns import (
    detect_industry_key,
    format_industry_pattern_prompt,
    get_industry_pattern_profile,
)


_VERTICALS: dict[str, dict[str, Any]] = {
    "school": {
        "label": "Образование / школа",
        "markers": ("school", "школ", "образован", "обучен", "курс", "дет", "гимназ", "academy", "intellectum"),
        "rules": (
            "Писать языком родителя или ученика: формат занятия, возраст, навык, результат.",
            "Уточнять город/район, если это помогает локальному поиску.",
            "Для детских услуг указывать возраст, подготовку, развитие навыков и понятный результат.",
            "Не добавлять beauty/салон/процедуры, если исходная услуга не обучает именно этой отрасли.",
        ),
        "examples": (
            "Английский для дошкольников",
            "Подготовка к школе для детей 5-6 лет",
            "Курс по нейросетям и искусственному интеллекту",
        ),
        "categories": "education|kids|courses|language|it|other",
    },
    "beauty": {
        "label": "Бьюти / салон красоты",
        "markers": ("beauty_salon", "barbershop", "nail_studio", "cosmetology", "brows_lashes", "makeup", "tanning", "салон красоты", "парикмах", "маник", "педик", "космет", "бров", "ресниц", "эпиля"),
        "rules": (
            "Это beauty-specific профиль: применять только для салонов красоты, косметологии, волос, ногтей, бровей, ресниц, визажа и эпиляции.",
            "Название услуги должно быть коротким: базовая услуга + зона/длина/тип/объем/аудитория/возраст/число зон, если эти атрибуты есть в исходнике.",
            "Сохранять критические beauty-атрибуты: зона обработки, длина волос, пол клиента, возраст, препарат/бренд препарата, объем/дозировка, число зон, число сеансов, уровень/класс/формат, техника или тип процедуры.",
            "Описание должно быть одним коротким предложением и начинаться с ключа услуги.",
            "Не добавлять бренд, гео, адрес или категорию, если их нет в исходной услуге или профиле бизнеса.",
            "Не добавлять рекламную воду и обещания: профессиональный, премиум, натуральный, идеальный, лучший, без вреда, безболезненно, безопасно, стойкий результат, до полугода, мгновенный эффект, омоложение кожи.",
            "Не сужать общую услугу до другой зоны: ваксинг/депиляция 1 зона не превращается в брови, лицо или бикини без исходного указания.",
            "Не обещать медицинский эффект без исходных данных.",
        ),
        "examples": (
            "Биозавивка афрокудри на экстра длинные волосы",
            "Ваксинг (восковая депиляция) - 1 зона",
            "Биоревитализация Belarti lift 1 ml",
        ),
        "categories": "hair|nails|spa|barber|massage|makeup|brows|lashes|other",
    },
    "gas_station": {
        "label": "АЗС / топливо",
        "markers": ("gas_station", "азс", "заправ", "лукойл", "топлив"),
        "rules": (
            "Писать для водителя: топливо, адрес, удобный заезд, маршрут, сервисы на станции.",
            "Не добавлять кафе, выпечку, мойку или магазин, если этого нет в исходной услуге.",
            "Фокус на практической пользе и локальном поиске рядом с маршрутом.",
        ),
        "examples": (
            "АЗС с бензином АИ-95",
            "Заправка дизельным топливом",
            "Топливная карта для водителей",
        ),
        "categories": "fuel|car|road_service|other",
    },
    "cafe": {
        "label": "Кафе / общепит",
        "markers": ("cafe", "кафе", "ресторан", "кофейн", "шаверм", "пицц", "food"),
        "rules": (
            "Писать про блюдо, формат, вкус, состав, время подачи или сценарий заказа.",
            "Не добавлять доставку, завтраки, бизнес-ланч или акции, если их нет в исходной услуге.",
            "Формулировки должны помогать выбрать блюдо или место.",
        ),
        "examples": (
            "Кофе с собой",
            "Завтраки в кафе",
            "Шаверма с курицей",
        ),
        "categories": "food|drink|delivery|breakfast|other",
    },
    "auto_service": {
        "label": "Автосервис",
        "markers": ("auto_service", "автосервис", "сто", "ремонт авто", "шиномонтаж", "диагностик"),
        "rules": (
            "Писать для владельца автомобиля: марка/узел/работа/результат/срок, если это есть.",
            "Не добавлять продажу запчастей, эвакуатор или мойку без исходных данных.",
            "Фокус на конкретной операции и понятном результате.",
        ),
        "examples": (
            "Диагностика подвески",
            "Замена масла в двигателе",
            "Шиномонтаж легковых авто",
        ),
        "categories": "repair|diagnostics|tires|maintenance|other",
    },
    "fitness": {
        "label": "Фитнес / спорт",
        "markers": ("gym", "fitness", "фитнес", "спортзал", "трениров", "йога", "пилатес"),
        "rules": (
            "Писать про формат тренировки, уровень подготовки, цель и результат.",
            "Не обещать медицинское лечение или гарантированное похудение.",
        ),
        "examples": (
            "Персональная тренировка",
            "Групповые занятия йогой",
            "Фитнес для начинающих",
        ),
        "categories": "fitness|training|yoga|kids|other",
    },
    "food": {
        "label": "Еда / пекарни / кафе",
        "markers": ("food", "bakery", "пекар", "кофейн", "кондитер", "кафе", "ресторан", "бар", "быстрое питание"),
        "rules": (
            "Писать про продукт, блюдо, состав, вкус, свежесть, кофе, завтрак или сценарий заказа.",
            "Не добавлять доставку, акции, скидки или завтраки, если их нет в исходной услуге.",
            "Не использовать beauty, medical или auto темы без факта.",
        ),
        "examples": (
            "Круассан с ветчиной",
            "Эклер фисташковый",
            "Латте",
        ),
        "categories": "food|drink|bakery|breakfast|dessert|delivery|other",
    },
    "medical": {
        "label": "Медицина / клиники",
        "markers": ("medical", "медцентр", "клиник", "врач", "доктор", "лаборатор", "диагност", "стоматолог"),
        "rules": (
            "Писать точно: процедура + область, метод или специализация.",
            "Не обещать лечение, результат, отсутствие боли или безопасность без исходных данных.",
            "Не добавлять beauty или food темы без факта.",
        ),
        "examples": (
            "Консультация дерматолога",
            "УЗИ молочных желез",
            "Лазерное удаление новообразований",
        ),
        "categories": "consultation|diagnostics|procedure|lab|dentistry|other",
    },
    "hospitality": {
        "label": "Отели / гостиницы",
        "markers": ("hotel", "отель", "гостиниц", "апартамент", "номер", "завтрак"),
        "rules": (
            "Писать про тип номера, вместимость, питание, расположение или удобство, если это есть.",
            "Не добавлять гарантированный вид, скидки или услуги без исходного факта.",
        ),
        "examples": (
            "Стандарт двухместный с завтраком",
            "Семейный номер",
            "Номер с двумя кроватями",
        ),
        "categories": "room|breakfast|family|parking|nearby|other",
    },
    "retail": {
        "label": "Retail / магазины",
        "markers": ("retail", "магазин", "товары", "плать", "двер", "букет", "цвет", "парфюмер"),
        "rules": (
            "Писать про товар, модель, размер, материал, наличие или цену, если они указаны.",
            "Не добавлять услуги другой индустрии без факта.",
        ),
        "examples": (
            "Свадебное платье Габриэлла",
            "Межкомнатная дверь Шелтон",
            "Букет Комплимент",
        ),
        "categories": "product|model|size|collection|flowers|doors|other",
    },
    "local_business": {
        "label": "Локальный бизнес",
        "markers": (),
        "rules": (
            "Писать строго по исходной услуге: что это, для кого, какой результат.",
            "Не добавлять отраслевые слова, которых нет в бизнес-профиле или исходной услуге.",
            "Если данных мало, лучше оставить короткую нейтральную формулировку.",
        ),
        "examples": (
            "Консультация специалиста",
            "Выездная услуга",
            "Запись на услугу",
        ),
        "categories": "service|consultation|other",
    },
}


def _normalize(value: Any) -> str:
    return str(value or "").strip().lower().replace("ё", "е")


def detect_service_optimization_vertical(
    *,
    business_name: Any = "",
    business_type: Any = "",
    industry: Any = "",
    categories: Any = "",
) -> str:
    industry_key = detect_industry_key(
        business_name=business_name,
        business_type=business_type,
        industry=industry,
        categories=categories,
    )
    if industry_key in _VERTICALS and industry_key != "local_business":
        return industry_key

    normalized_business_type = _normalize(business_type)
    if normalized_business_type in {"spa", "spa/wellness"}:
        return "beauty"

    identity = " ".join(
        item
        for item in (
            _normalize(business_name),
            _normalize(business_type),
            _normalize(industry),
            _normalize(categories),
        )
        if item
    )
    if not identity:
        return "local_business"

    for key, config in _VERTICALS.items():
        if key == "local_business":
            continue
        markers = config.get("markers") or ()
        for marker in markers:
            normalized_marker = _normalize(marker)
            if normalized_marker and normalized_marker in identity:
                return key

    return "local_business"


def get_service_optimization_vertical_context(vertical_key: str) -> dict[str, Any]:
    key = str(vertical_key or "").strip()
    config = _VERTICALS.get(key) or _VERTICALS["local_business"]
    industry_profile = get_industry_pattern_profile(key)
    profile_rules = list(industry_profile.get("service_patterns") or [])
    profile_restrictions = list(industry_profile.get("forbidden_industry_drifts") or [])
    profile_claims = [
        f"Не использовать без исходного факта: {item}"
        for item in list(industry_profile.get("forbidden_claims") or [])
    ]
    merged_rules: list[str] = []
    for item in list(config["rules"]) + profile_rules + profile_restrictions + profile_claims:
        text = str(item or "").strip()
        if text and text not in merged_rules:
            merged_rules.append(text)
    merged_examples: list[str] = []
    for item in list(config["examples"]) + list(industry_profile.get("examples") or []):
        text = str(item or "").strip()
        if text and text not in merged_examples:
            merged_examples.append(text)
    return {
        "key": key if key in _VERTICALS else "local_business",
        "label": config["label"],
        "rules": merged_rules,
        "examples": merged_examples,
        "categories": config["categories"],
        "industry_patterns": format_industry_pattern_prompt(key, mode="service"),
    }


def format_service_optimization_vertical_prompt(context: dict[str, Any]) -> str:
    rules = context.get("rules") if isinstance(context.get("rules"), list) else []
    examples = context.get("examples") if isinstance(context.get("examples"), list) else []
    rule_lines = "\n".join(f"- {item}" for item in rules if str(item).strip())
    example_lines = "\n".join(f"- {item}" for item in examples if str(item).strip())
    return (
        f"Вертикаль бизнеса: {context.get('label') or 'Локальный бизнес'}\n"
        f"Допустимые категории ответа: {context.get('categories') or 'other'}\n"
        f"Правила вертикали:\n{rule_lines or '- Писать строго по исходной услуге.'}\n"
        f"Примеры направления формулировок:\n{example_lines or '- Короткая понятная услуга.'}\n"
        f"Industry pattern context:\n{context.get('industry_patterns') or '-'}"
    )
