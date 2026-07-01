import re
import uuid
from collections import Counter
from typing import Any


SERVICE_CATALOG_GENERAL_RECOMMENDATIONS = [
    "Сократите список до понятных клиенту направлений, а варианты оставьте внутри описания: зона, длина, пол, объём препарата, размер рубца.",
    "Не держите акции как обычные услуги: сезонные предложения лучше вынести в новости, акции или выделенные блоки.",
    "Для SEO оставляйте отдельными только услуги, которые клиент реально ищет как самостоятельный запрос.",
    "Внутри категории показывайте 5-12 ключевых позиций, остальное группируйте как варианты.",
    "Цены лучше показывать диапазоном или таблицей вариантов, а не десятками почти одинаковых строк.",
]


COMPRESSION_RULES = [
    {
        "id": "laser_epilation",
        "title": "Лазерная эпиляция",
        "pattern": re.compile(r"эпиляц|бикини|подмыш|голен|бедр|ноги|руки|усики|ареол|пальц|зона mini|тотальное", re.I),
        "recommended_count": 8,
        "reason": "Много строк отличаются только зоной, полом клиента или размером комплекса.",
        "action_text": "Свернуть в группы по зонам и добавить варианты “женщины/мужчины” внутри услуги.",
        "apply_action": "apply",
        "target_name": "Лазерная эпиляция по зонам",
        "target_category": "Лазерная эпиляция",
    },
    {
        "id": "injectable_cosmetology",
        "title": "Инъекционная косметология",
        "pattern": re.compile(r"биоревитализац|ботулинотерап|токсин|гипергидроз|коллагенотерап|collost|контурная пластика|филлер|мезотерап|belarti|bellarti|revi|plinest|meso", re.I),
        "recommended_count": 12,
        "reason": "Часть строк описывает одну процедуру разными препаратами или объёмами.",
        "action_text": "Оставить семьи процедур, а препараты и ml вынести в варианты или описание.",
        "apply_action": "apply",
        "target_name": "Инъекционная косметология",
        "target_category": "Косметология",
    },
    {
        "id": "seasonal_offers",
        "title": "Сезонные предложения",
        "pattern": re.compile(r"сезонное\s+предложение", re.I),
        "recommended_count": 0,
        "reason": "Акционные формулировки смешаны с постоянным меню услуг.",
        "action_text": "Вынести сезонные позиции в акции, новости или выделенные предложения.",
        "apply_action": "promotion",
        "target_name": "Сезонные предложения",
        "target_category": "Акции",
    },
    {
        "id": "hair_services",
        "title": "Волосы: завивка, окрашивание, уходы и дети",
        "pattern": re.compile(r"биозавив|афро|окрашив|балаяж|шатуш|air touch|эйр|блонд|тонирован|контуринг|выход из темного|выход из тёмного|биксипласт|ботокс для волос|кератин|счастье для волос|уход за волос|детск|стрижка", re.I),
        "recommended_count": 14,
        "reason": "Строки дробятся по длине волос, возрасту или сложности.",
        "action_text": "Объединить по базовой услуге, а длину, возраст и сложность показать как варианты.",
        "apply_action": "apply",
        "target_name": "Услуги для волос",
        "target_category": "Волосы",
    },
    {
        "id": "scar_aesthetics",
        "title": "Эстетика рубцов",
        "pattern": re.compile(r"рубц|растяж|стрии|абдоминопласт|блефаропласт|брахиопласт|хейлопласт|ареол", re.I),
        "recommended_count": 6,
        "reason": "Похожие процедуры отличаются размером зоны или типом рубца.",
        "action_text": "Сгруппировать по типу процедуры и размеру рубца.",
        "apply_action": "apply",
        "target_name": "Коррекция рубцов и растяжек",
        "target_category": "Эстетика рубцов",
    },
    {
        "id": "permanent_makeup",
        "title": "Перманентный макияж",
        "pattern": re.compile(r"перманент|пудров|межреснич|стрелк|татуаж|ремувер|акварель|помада", re.I),
        "recommended_count": 6,
        "reason": "Позиции можно понятнее собрать по зоне и технике.",
        "action_text": "Группировать по зонам: брови, губы, веки, коррекция и удаление.",
        "apply_action": "apply",
        "target_name": "Перманентный макияж",
        "target_category": "Перманентный макияж",
    },
    {
        "id": "podology_treatment",
        "title": "Подология",
        "pattern": re.compile(r"подолог|вросш|биоматериал|титанов|мозол|гиперкератоз|диабетическ|протезирован|обработка\s+ногт|комплексная\s+обработка\s+стоп|забор\s+биоматериала", re.I),
        "exclude_pattern": re.compile(r"\bманикюр\b|гигиеническ.*педикюр|мужской\s+педикюр|педикюр\s+с\s+покрыт|японский\s+маникюр|парафинотерап", re.I),
        "recommended_count": 4,
        "reason": "Лечебные подологические процедуры лучше отделить от обычного маникюра и педикюра.",
        "action_text": "Сгруппировать лечебные процедуры по проблеме: консультация, обработка стоп, вросший ноготь, протезирование и коррекция ногтя.",
        "apply_action": "apply",
        "target_name": "Подологические процедуры",
        "target_category": "Подология",
    },
    {
        "id": "nail_service",
        "title": "Маникюр и педикюр",
        "pattern": re.compile(r"маникюр|педикюр|гель[\s-]?лак|покрыти|парафинотерап|японский\s+маникюр", re.I),
        "recommended_count": 5,
        "reason": "Обычные ногтевые услуги можно оставить отдельной категорией с вариантами покрытия и пола клиента.",
        "action_text": "Сгруппировать по базовой услуге: маникюр, педикюр, покрытие, уходы и мужские варианты.",
        "apply_action": "apply",
        "target_name": "Маникюр и педикюр",
        "target_category": "Маникюр и педикюр",
    },
]


def normalize_service_text(value: Any) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]+", " ", str(value or "").lower().replace("ё", "е"), flags=re.U)).strip()


def _service_text(service: dict[str, Any]) -> str:
    return " ".join([
        str(service.get("name") or ""),
        str(service.get("description") or ""),
    ])


def _service_id(service: dict[str, Any]) -> str:
    return str(service.get("id") or "").strip()


def _keyword_list(services: list[dict[str, Any]]) -> list[str]:
    seen = set()
    result = []
    for service in services:
        raw = service.get("keywords") or []
        items = raw if isinstance(raw, list) else str(raw or "").split(",")
        for item in items:
            keyword = str(item or "").strip()
            key = normalize_service_text(keyword)
            if keyword and key and key not in seen:
                seen.add(key)
                result.append(keyword)
    return result[:12]


def _price_range(services: list[dict[str, Any]]) -> str:
    values = []
    text_values = []
    for service in services:
        raw = str(service.get("price") or "").strip()
        if not raw:
            continue
        number_text = re.sub(r"[^\d.,]", "", raw).replace(",", ".")
        try:
            values.append(float(number_text))
        except Exception:
            text_values.append(raw)
    if values:
        low = int(min(values))
        high = int(max(values))
        if low == high:
            return str(low)
        return f"{low}-{high}"
    return text_values[0] if text_values else ""


def _variant_lines(services: list[dict[str, Any]]) -> list[str]:
    lines = []
    for service in services[:30]:
        name = str(service.get("name") or "").strip()
        price = str(service.get("price") or "").strip()
        if name and price:
            lines.append(f"- {name}: {price}")
        elif name:
            lines.append(f"- {name}")
    return lines


def _build_description(action_text: str, services: list[dict[str, Any]]) -> str:
    variants = _variant_lines(services)
    if not variants:
        return action_text
    return action_text + "\n\nВарианты из исходного меню:\n" + "\n".join(variants)


def _cluster_key(value: Any) -> str:
    return normalize_service_text(value)


def _specialized_clusters(rule: dict[str, Any], matches: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rule_id = str(rule.get("id") or "")
    clusters: list[dict[str, Any]] = []

    def add_cluster(key: str, title: str, target_name: str, target_category: str, action_text: str, pattern: str) -> None:
        regex = re.compile(pattern, re.I)
        services = [service for service in matches if regex.search(str(service.get("name") or ""))]
        if len(services) < 2:
            return
        clusters.append({
            "key": key,
            "title": title,
            "target_name": target_name,
            "target_category": target_category,
            "action_text": action_text,
            "services": services,
        })

    if rule_id == "scar_aesthetics":
        add_cluster(
            "scar_by_size",
            "Рубцы по размеру",
            "Коррекция рубцов по размеру",
            "Эстетика рубцов",
            "Объединить коррекцию рубцов в одну услугу с вариантами по длине рубца.",
            r"коррекция\s+рубцов:\s+до",
        )
        add_cluster(
            "scar_after_surgery",
            "Рубцы после пластических операций",
            "Коррекция рубцов после операций",
            "Эстетика рубцов",
            "Сгруппировать рубцы после пластических операций, а тип операции оставить вариантом.",
            r"абдоминопласт|блефаропласт|брахиопласт|хейлопласт|т-рубц|якорн",
        )
        add_cluster(
            "scar_skin_marks",
            "Рубцы кожи и постакне",
            "Коррекция рубцов кожи и постакне",
            "Эстетика рубцов",
            "Оставить одну понятную услугу для постакне, селфхарма и небольших рубцов кожи.",
            r"постакне|селфхарм|родинок|папиллом",
        )
        return clusters

    if rule_id == "podology_treatment":
        add_cluster(
            "podology_foot_processing",
            "Подологическая обработка стоп",
            "Подологическая обработка стоп",
            "Подология",
            "Объединить лечебную обработку стоп, а состояние стопы оставить вариантом.",
            r"обработка\s+стоп|диабетическ",
        )
        add_cluster(
            "podology_nail_correction",
            "Коррекция ногтей у подолога",
            "Коррекция ногтей у подолога",
            "Подология",
            "Объединить процедуры коррекции ногтевой пластины и вросшего ногтя.",
            r"вросш|протезирован|титанов",
        )
        return clusters

    if rule_id == "nail_service":
        add_cluster(
            "nail_manicure",
            "Маникюр",
            "Маникюр",
            "Маникюр и педикюр",
            "Объединить варианты маникюра, а пол клиента и технику оставить вариантами.",
            r"маникюр",
        )
        add_cluster(
            "nail_pedicure",
            "Педикюр",
            "Педикюр",
            "Маникюр и педикюр",
            "Объединить варианты педикюра, а покрытие и пол клиента оставить вариантами.",
            r"педикюр",
        )
        return clusters

    return []


def _build_group(rule: dict[str, Any], matches: list[dict[str, Any]], overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    overrides = overrides or {}
    action = str(rule["apply_action"])
    recommended_count = 0 if action == "promotion" else 1
    action_text = str(overrides.get("action_text") or rule["action_text"])
    title = str(overrides.get("title") or rule["title"])
    target_name = str(overrides.get("target_name") or rule["target_name"])
    target_category = str(overrides.get("target_category") or rule["target_category"])

    return {
        "id": str(uuid.uuid4()),
        "rule_id": str(overrides.get("rule_id") or rule["id"]),
        "title": title,
        "reason": rule["reason"],
        "action": action,
        "action_text": action_text,
        "source_service_ids": [_service_id(service) for service in matches],
        "current_count": len(matches),
        "recommended_count": recommended_count,
        "target": {
            "category": target_category,
            "name": target_name,
            "description": _build_description(action_text, matches),
            "keywords": _keyword_list(matches),
            "price": _price_range(matches),
        },
        "examples": [str(service.get("name") or "").strip() for service in matches[:5] if str(service.get("name") or "").strip()],
    }


def build_service_catalog_compression_draft(services: list[dict[str, Any]]) -> dict[str, Any]:
    active_services = [service for service in services if _service_id(service) and not service.get("is_external")]
    before_count = len(active_services)
    category_counts = Counter(str(service.get("category") or "Без категории").strip() or "Без категории" for service in active_services)
    used_service_ids = set()
    groups = []

    for rule in COMPRESSION_RULES:
        matches = [
            service
            for service in active_services
            if _service_id(service) not in used_service_ids and rule["pattern"].search(_service_text(service))
            and not (rule.get("exclude_pattern") and rule["exclude_pattern"].search(_service_text(service)))
        ]
        if len(matches) < 3:
            continue
        specialized = _specialized_clusters(rule, matches)
        if specialized:
            clustered_ids = set()
            for cluster in specialized:
                cluster_services = [
                    service
                    for service in cluster["services"]
                    if _service_id(service) not in clustered_ids
                ]
                if len(cluster_services) < 2:
                    continue
                clustered_ids.update(_service_id(service) for service in cluster_services)
                groups.append(_build_group(rule, cluster_services, {
                    "rule_id": f"{rule['id']}_{cluster['key']}",
                    "title": cluster["title"],
                    "target_name": cluster["target_name"],
                    "target_category": cluster["target_category"],
                    "action_text": cluster["action_text"],
                }))
            used_service_ids.update(clustered_ids)
            continue

        source_ids = [_service_id(service) for service in matches]
        used_service_ids.update(source_ids)
        groups.append(_build_group(rule, matches))

    for category, count in category_counts.most_common():
        if count <= 25:
            continue
        category_services = [
            service
            for service in active_services
            if _service_id(service) not in used_service_ids
            and (str(service.get("category") or "Без категории").strip() or "Без категории") == category
        ]
        if len(category_services) < 8:
            continue
        source_ids = [_service_id(service) for service in category_services]
        used_service_ids.update(source_ids)
        groups.append({
            "id": str(uuid.uuid4()),
            "rule_id": "overloaded_category",
            "title": category,
            "reason": "В категории слишком много равнозначных строк, клиенту трудно быстро выбрать.",
            "action": "apply",
            "action_text": "Оставить ключевые направления, а редкие или технические варианты перенести внутрь описаний.",
            "source_service_ids": source_ids,
            "current_count": len(category_services),
            "recommended_count": 12,
            "target": {
                "category": category,
                "name": category,
                "description": _build_description("Сгруппированная услуга по перегруженной категории.", category_services),
                "keywords": _keyword_list(category_services),
                "price": _price_range(category_services),
            },
            "examples": [str(service.get("name") or "").strip() for service in category_services[:5] if str(service.get("name") or "").strip()],
        })

    apply_groups = [group for group in groups if group.get("action") in {"apply", "promotion"}]
    archived_count = sum(len(group.get("source_service_ids") or []) for group in apply_groups)
    created_count = sum(1 for group in apply_groups if group.get("action") == "apply")
    after_count = max(0, before_count - archived_count + created_count)
    return {
        "before_count": before_count,
        "after_count": after_count,
        "high_priority": before_count >= 150,
        "category_counts": [{"category": category, "count": count} for category, count in category_counts.most_common()],
        "groups": groups,
        "general_recommendations": SERVICE_CATALOG_GENERAL_RECOMMENDATIONS,
    }
