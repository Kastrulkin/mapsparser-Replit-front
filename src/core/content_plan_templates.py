from __future__ import annotations

import re
from typing import Any


TEMPLATE_VERSION = "2026-05-29.v1"


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _normalize(value: Any) -> str:
    text = _safe_text(value).lower().replace("ё", "е")
    text = re.sub(r"[^0-9a-zа-я\s]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _business_blob(business: dict[str, Any]) -> str:
    return _normalize(
        " ".join(
            _safe_text(business.get(key))
            for key in ("name", "business_type", "industry", "categories", "description", "site", "address", "city")
        )
    )


CONTENT_PLAN_TEMPLATES: dict[str, dict[str, Any]] = {
    "kids_hair_salon": {
        "label": "Детская парикмахерская",
        "industry_key": "beauty",
        "markers": ("детский салон парикмахерская", "детская парикмахерская", "веселая расческа"),
        "topics": (
            {
                "content_type": "service",
                "theme": "Детская стрижка без стресса",
                "goal": "Показать родителям, как проходит детская стрижка и почему ребенку будет спокойно.",
                "seo_keyword": "детская стрижка",
                "cta_hint": "Расскажите, как подготовить ребенка к визиту и как записаться.",
            },
            {
                "content_type": "seasonal",
                "theme": "Стрижка перед школой, отпуском или праздником",
                "goal": "Связать запись с понятным семейным поводом и напомнить записаться заранее.",
                "seo_keyword": "детская стрижка запись",
                "cta_hint": "Укажите повод, возраст и простой следующий шаг.",
            },
            {
                "content_type": "service",
                "theme": "Выстриг или яркая деталь в образе",
                "goal": "Показать выстриг как аккуратный способ обновить образ ребенка.",
                "seo_keyword": "выстриг ребенку",
                "cta_hint": "Дайте 2-3 безопасных варианта без обещаний и выдуманных цен.",
            },
        ),
    },
    "culture_event_center": {
        "label": "Культурный центр / пространство событий",
        "industry_key": "culture",
        "markers": ("культурный центр", "художественная галерея", "каток", "афиша", "лекция", "концерт"),
        "topics": (
            {
                "content_type": "event",
                "theme": "Ближайшее событие в афише",
                "goal": "Дать понятный анонс события: что будет, кому подойдет, дата, время и как попасть.",
                "seo_keyword": "афиша",
                "cta_hint": "Используйте только подтвержденные дату, время, формат и название события.",
            },
            {
                "content_type": "space",
                "theme": "Атмосфера одного вечера",
                "goal": "Показать, зачем люди приходят на культурные события: через свет, музыку, разговоры и ощущение вечера.",
                "seo_keyword": "культурный центр",
                "cta_hint": "Не перечисляйте афишу и не описывайте площадку; передайте одно ощущение.",
            },
            {
                "content_type": "behind_scenes",
                "theme": "За кулисами подготовки события",
                "goal": "Показать живой процесс: люди, репетиция, свет, звук, детали перед событием.",
                "seo_keyword": "мероприятия",
                "cta_hint": "Пишите только о подготовке без выдуманных участников и деталей.",
            },
            {
                "content_type": "author_story",
                "theme": "История участника события",
                "goal": "Заинтересовать личностью артиста, лектора, музыканта или гостя без пересказа биографии.",
                "seo_keyword": "афиша",
                "cta_hint": "Покажите одну деталь, которая делает человека интересным.",
            },
            {
                "content_type": "community",
                "theme": "Итоги прошедшего события",
                "goal": "Поддержать живую карточку через короткий рассказ о прошедшем мероприятии и следующем поводе прийти.",
                "seo_keyword": "мероприятия",
                "cta_hint": "Опирайтесь на факты: название, формат, фото, дату или будущий анонс.",
            },
            {
                "content_type": "faq",
                "theme": "Один вопрос перед визитом",
                "goal": "Снять одно сомнение посетителя: дети, вход, парковка, билеты или время начала.",
                "seo_keyword": "афиша",
                "cta_hint": "Ответьте только на один вопрос и не объединяйте FAQ в список.",
            },
            {
                "content_type": "quote",
                "theme": "Одна сильная мысль события",
                "goal": "Построить публикацию вокруг цитаты лектора, артиста или гостя, если такая мысль есть в фактах.",
                "seo_keyword": "мероприятия",
                "cta_hint": "Не объясняйте цитату полностью; оставьте пространство для интереса.",
            },
        ),
    },
    "airport_transfer": {
        "label": "Транспортная компания / трансферы",
        "industry_key": "local_business",
        "markers": ("riderra", "трансфер", "transfer", "airport", "аэропорт", "такси в аэропорт"),
        "topics": (
            {
                "content_type": "service",
                "theme": "Трансфер Vilnius / Kaunas: поездка в аэропорт и обратно",
                "goal": (
                    "Рассказать об услуге как о конкретной поездке: трансфер в Vilnius или Kaunas, маршрут "
                    "до Vilnius Airport или Kaunas Airport, поездка из аэропорта в город и онлайн-бронирование на riderra.com."
                ),
                "seo_keyword": "Vilnius airport transfer",
                "cta_hint": "Сохраните маршрут, аэропорт, формат поездки и riderra.com; не добавляйте цены, тарифы или гарантии времени.",
            },
            {
                "content_type": "service",
                "theme": "Phuket: private transfer to and from the airport",
                "goal": (
                    "Рассказать об услуге как о поездке: private transfer in Phuket, маршрут до Phuket International Airport "
                    "или из аэропорта до места назначения, онлайн-бронирование на riderra.com."
                ),
                "seo_keyword": "Phuket airport transfer",
                "cta_hint": "Сохраните Phuket, Phuket International Airport, private transfer и riderra.com; не добавляйте цены или неподтвержденный класс авто.",
            },
            {
                "content_type": "service",
                "theme": "Zanzibar: private transfer to and from the airport",
                "goal": (
                    "Рассказать об услуге как о поездке: private transfer in Zanzibar, маршрут до Zanzibar Airport "
                    "или из аэропорта до отеля/адреса, онлайн-бронирование на riderra.com."
                ),
                "seo_keyword": "Zanzibar airport transfer",
                "cta_hint": "Сохраните Zanzibar, Zanzibar Airport, private transfer и riderra.com; не добавляйте цены или условия, которых нет в данных.",
            },
            {
                "content_type": "service",
                "theme": "Трансфер в аэропорт без лишней суеты",
                "goal": "Показать сценарий поездки: встреча, багаж, время подачи и понятный способ заказа.",
                "seo_keyword": "трансфер в аэропорт",
                "cta_hint": "Не обещайте время в пути без данных; дайте чек-лист, что указать при заказе.",
            },
            {
                "content_type": "seo",
                "theme": "Как заказать трансфер заранее",
                "goal": "Закрыть спрос клиента, который сравнивает такси, трансфер и встречу в аэропорту.",
                "seo_keyword": "заказать трансфер",
                "cta_hint": "Объясните, какие данные нужны: рейс, адрес, время, пассажиры и багаж.",
            },
            {
                "content_type": "trust",
                "theme": "Встреча пассажира и поездка с багажом",
                "goal": "Снять тревогу перед поездкой: где встречают, как связаться и что делать при задержке рейса.",
                "seo_keyword": "встреча в аэропорту",
                "cta_hint": "Используйте только реальные условия сервиса.",
            },
        ),
    },
    "fast_food_kebab": {
        "label": "Фастфуд / кафе кебаб",
        "industry_key": "food",
        "markers": ("кафе кебаб", "кебаб", "шаурма", "шаверма", "быстрое питание"),
        "topics": (
            {
                "content_type": "product",
                "theme": "Что взять на быстрый обед",
                "goal": "Помочь гостю быстро выбрать блюдо и зайти без долгого сравнения.",
                "seo_keyword": "кебаб рядом",
                "cta_hint": "Назовите конкретные блюда только если они есть в меню или карточке.",
            },
            {
                "content_type": "local",
                "theme": "Кебаб рядом с работой, учебой или по пути",
                "goal": "Связать точку с быстрым маршрутом и понятным поводом зайти.",
                "seo_keyword": "быстрое питание рядом",
                "cta_hint": "Укажите локальный ориентир только если он известен из адреса или карточки.",
            },
            {
                "content_type": "trust",
                "theme": "Свежесть, скорость и понятный выбор",
                "goal": "Усилить доверие к фастфуду через чистоту, скорость, состав и понятный формат заказа.",
                "seo_keyword": "кафе кебаб",
                "cta_hint": "Не выдумывайте скидки, доставку, вес порций или состав.",
            },
        ),
    },
    "gas_station": {
        "label": "АЗС",
        "industry_key": "gas_station",
        "markers": ("азс", "заправка", "топливо", "сургутнефтегаз", "киришиавтосервис", "лукойл"),
        "topics": (
            {
                "content_type": "service",
                "theme": "АЗС по пути: топливо и быстрый заезд",
                "goal": "Показать практическую пользу станции для водителя на маршруте.",
                "seo_keyword": "азс рядом",
                "cta_hint": "Не добавляйте виды топлива, магазин или кафе, если этого нет в данных.",
            },
            {
                "content_type": "trust",
                "theme": "Чистота, скорость и удобство на станции",
                "goal": "Усилить доверие к точке через сервисные факты: чистота, касса, навигация, заезд.",
                "seo_keyword": "заправка рядом",
                "cta_hint": "Опирайтесь на фото, отзывы или проверенные атрибуты карточки.",
            },
            {
                "content_type": "local",
                "theme": "Когда удобно заехать на эту АЗС",
                "goal": "Связать карточку с локальным маршрутом и регулярным спросом водителей.",
                "seo_keyword": "топливо рядом",
                "cta_hint": "Пишите про удобство маршрута без неподтвержденных обещаний.",
            },
        ),
    },
}


def detect_content_plan_template_key(business: dict[str, Any]) -> str:
    blob = _business_blob(business)
    if not blob:
        return ""
    for key, template in CONTENT_PLAN_TEMPLATES.items():
        for marker in template.get("markers") or ():
            normalized_marker = _normalize(marker)
            if normalized_marker and normalized_marker in blob:
                return key
    return ""


def get_content_plan_template_profile(business: dict[str, Any]) -> dict[str, Any]:
    key = detect_content_plan_template_key(business)
    if not key:
        return {}
    template = CONTENT_PLAN_TEMPLATES.get(key) or {}
    return {
        "template_key": key,
        "label": str(template.get("label") or "").strip(),
        "industry_key": str(template.get("industry_key") or "local_business").strip(),
        "version": TEMPLATE_VERSION,
        "topics": [dict(item) for item in template.get("topics") or ()],
    }


def build_template_candidates(context: dict[str, Any], recent_blob: str = "") -> list[dict[str, Any]]:
    business = context.get("business") if isinstance(context.get("business"), dict) else {}
    profile = get_content_plan_template_profile(business)
    if not profile:
        return []
    candidates: list[dict[str, Any]] = []
    for index, topic in enumerate(profile.get("topics") or []):
        theme = _safe_text(topic.get("theme"))
        if not theme:
            continue
        coverage_bonus = -6 if _normalize(theme) and _normalize(theme) in _normalize(recent_blob) else 14
        candidates.append(
            {
                "content_type": _safe_text(topic.get("content_type")) or "industry",
                "theme": theme,
                "goal": _safe_text(topic.get("goal")),
                "source_kind": "industry_template",
                "source_ref": profile["template_key"],
                "seo_keyword": _safe_text(topic.get("seo_keyword")),
                "cta_hint": _safe_text(topic.get("cta_hint")),
                "strength_score": 72 - index * 4 + coverage_bonus,
                "template_key": profile["template_key"],
                "template_label": profile["label"],
                "template_version": profile["version"],
                "ranking_reasons": [
                    {"label": "industry_content_template", "score": 72 - index * 4},
                    {"label": "undercovered_template_topic", "score": coverage_bonus},
                ],
            }
        )
    return candidates
