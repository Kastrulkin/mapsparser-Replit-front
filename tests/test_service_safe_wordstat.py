from core.service_duplicate_grouping import attach_duplicate_group_metadata, build_service_duplicate_key
from core.service_safe_wordstat import (
    build_safe_seed_queries,
    extract_service_attributes,
    filter_wordstat_candidates,
)


def test_afro_builds_safe_hair_seeds_without_raw_ambiguous_seed() -> None:
    service = {"category": "Биозавивка", "name": "Афро на длинные волосы"}

    seeds = build_safe_seed_queries(service)

    assert "афро" not in seeds
    assert "афрокудри" in seeds
    assert "биозавивка афрокудри" in seeds
    assert "афрокудри на длинные волосы" in seeds


def test_regular_biozavivka_does_not_get_afro_seed() -> None:
    service = {"category": "Биозавивка", "name": "Биозавивка Экстра длинные волосы"}

    seeds = build_safe_seed_queries(service)

    assert "биозавивка" in seeds
    assert "афрокудри" not in seeds


def test_brows_without_lashes_do_not_get_lash_seed() -> None:
    service = {"category": "Брови", "name": "Окрашивание бровей+коррекция бровей"}

    seeds = build_safe_seed_queries(service)

    assert "коррекция бровей" in seeds
    assert "окрашивание бровей" in seeds
    assert "ламинирование ресниц" not in seeds


def test_afro_filter_blocks_adult_and_allows_hair_anchor() -> None:
    candidates = [
        {"keyword": "афро порно", "views": 1000},
        {"keyword": "афро девушки", "views": 900},
        {"keyword": "афрокудри на длинные волосы", "views": 800},
        {"keyword": "биозавивка афрокудри", "views": 700},
    ]

    result = filter_wordstat_candidates(candidates, "biozavivka")

    allowed = [item["keyword"] for item in result["allowed"]]
    blocked = {item["keyword"]: item["reason"] for item in result["blocked"]}
    assert "афрокудри на длинные волосы" in allowed
    assert "биозавивка афрокудри" in allowed
    assert blocked["афро порно"] == "unsafe_blacklist"
    assert blocked["афро девушки"] == "missing_category_anchor"


def test_extract_preserves_critical_attributes() -> None:
    service = {
        "category": "Инъекционная косметология",
        "name": "Биоревитализация, препарат Belarti lift 1 ml",
    }

    attributes = extract_service_attributes(service)

    assert attributes["category"] == "injection_cosmetology"
    assert attributes["brand_or_drug"] == "belarti lift"
    assert attributes["volume"] == "1 ml"


def test_botulinum_between_brows_is_not_classified_as_brows_lashes() -> None:
    service = {
        "category": "Инъекционная косметология",
        "name": "Ботулинотерапия. Девушки. Комплекс Лоб+межбровье",
    }

    seeds = build_safe_seed_queries(service)

    assert seeds[0] == "ботулинотерапия"
    assert "коррекция бровей" not in seeds
    assert "ламинирование ресниц" not in seeds


def test_injection_filter_blocks_wrong_beauty_and_info_queries() -> None:
    candidates = [
        {"keyword": "коррекция бровей", "views": 1000},
        {"keyword": "биоревитализация отзывы", "views": 900},
        {"keyword": "ботулинотерапия что", "views": 850},
        {"keyword": "ботулинотерапия", "views": 800},
        {"keyword": "ботулинотерапия гипергидроз", "views": 700},
    ]

    result = filter_wordstat_candidates(candidates, "injection_cosmetology")

    allowed = [item["keyword"] for item in result["allowed"]]
    blocked = {item["keyword"]: item["reason"] for item in result["blocked"]}
    assert "ботулинотерапия" in allowed
    assert "ботулинотерапия гипергидроз" in allowed
    assert blocked["коррекция бровей"] == "missing_category_anchor"
    assert blocked["биоревитализация отзывы"] == "informational_query"
    assert blocked["ботулинотерапия что"] == "informational_query"


def test_injection_subtypes_get_specific_seeds() -> None:
    contour = build_safe_seed_queries({
        "category": "Инъекционная косметология",
        "name": "Контурная пластика губ - Jufora M 1 ml",
    })
    collagen = build_safe_seed_queries({
        "category": "Инъекционная косметология",
        "name": "Коллагенотерапия - Collost (Micro 150 мг)",
    })

    assert contour[0] == "контурная пластика губ"
    assert collagen[0] == "коллагенотерапия"
    assert "инъекционная косметология" not in contour
    assert "инъекционная косметология" not in collagen


def test_duplicate_grouping_uses_canonical_service_key() -> None:
    services = [
        {"id": "1", "category": "Брови", "name": "Коррекция бровей Мужская", "price": "1000"},
        {"id": "2", "category": "брови", "name": "Коррекция бровей мужская", "price": "1000"},
        {"id": "3", "category": "Волосы", "name": "Афро на экстра длинные волосы", "price": "3000"},
    ]

    attach_duplicate_group_metadata(services)

    assert build_service_duplicate_key(services[0]) == build_service_duplicate_key(services[1])
    assert services[0]["duplicate_group"]["count"] == 2
    assert services[1]["duplicate_group"]["count"] == 2
    assert services[2]["duplicate_group"]["count"] == 1
