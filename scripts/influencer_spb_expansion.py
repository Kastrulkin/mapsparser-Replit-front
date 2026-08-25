#!/usr/bin/env python3
"""Expand the public Saint Petersburg influencer base from LocalOS lead seeds."""

from __future__ import annotations

import argparse
import csv
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from influencer_youtube_discovery import discover_query, verify


CITY = "Санкт-Петербург"

# Public business names/categories read from the saved LocalOS partnership lead base.
LEAD_SEEDS = [
    "33-й Зуб", "Детский мир", "HIT FITNESS", "DESALU", "Level UP",
    "Borneo Beauty", "Newfit", "Watsons", "Happy City", "ТРК Атмосфера",
    "Naomi beauty", "MedSwiss", "FITNESSBAR", "Gulliver", "Sma-r-t class",
    "Прибавление товары для детей", "Лак студия маникюра", "Miller Center",
    "ТК Орион", "ТК Променад", "FunCity", "Viva mare", "Wonderfit",
    "Театр Кот Вильям", "Роббо Клуб", "Fitness House", "Все свои стоматология",
    "РениДент", "Первая семейная клиника Петербурга", "Acoola", "Джи Клиник",
    "Oceankid", "MBC School", "Токио жилой комплекс", "Фотограф Коробейникова Евгения",
    "Jadan Dental", "Dental Place", "S&b студия EMS-фитнеса", "Интан",
    "Stockholm жилой комплекс", "Cream Shop", "Legenda Яхтенная", "Legenda Оптиков",
    "Три ветра жилой комплекс", "Лыжный 2", "ПироШоу СПб", "Медный Всадник жилой комплекс",
    "LIFE Приморский", "Дом с курантами", "Lotos Tower",
]

DISTRICTS = [
    "Адмиралтейский район", "Василеостровский район", "Выборгский район",
    "Калининский район", "Кировский район", "Колпинский район", "Красногвардейский район",
    "Красносельский район", "Кронштадт", "Курортный район", "Московский район",
    "Невский район", "Петроградский район", "Петродворцовый район", "Приморский район",
    "Пушкинский район", "Фрунзенский район", "Центральный район", "Мурино", "Кудрово",
    "Парнас", "Комендантский проспект", "Озерки", "Проспект Просвещения", "Купчино",
    "Рыбацкое", "Сестрорецк", "Петергоф", "Пушкин", "Шушары", "Васильевский остров",
    "Петроградка", "Новая Голландия", "Лахта", "Черная речка", "Удельная",
]

NICHES = [
    "кафе", "рестораны", "кофейни", "стритфуд", "кондитерские", "доставка еды",
    "салоны красоты", "парикмахерские", "барбершопы", "маникюр", "косметология",
    "массаж и SPA", "фитнес", "йога", "танцы", "стоматологии", "частные клиники",
    "детские центры", "детские кружки", "школы", "семейный досуг", "детские праздники",
    "театры", "музеи", "выставки", "концерты", "афиша", "городские события",
    "локальная мода", "магазины одежды", "винтаж", "дизайн интерьера", "ремонт",
    "новостройки", "жилые комплексы", "районные новости", "городские прогулки",
    "экскурсии", "туризм", "отели", "фотографы", "организаторы мероприятий",
    "домашние животные", "ветклиники", "спорт", "бег", "велосипеды", "образование",
    "книжные магазины", "локальные бренды", "малый бизнес", "маркетологи",
]

BASE_QUERIES = [
    "Петербург блогер", "Питер блогер", "СПб инфлюенсер", "Петербург микроинфлюенсер",
    "Питер локальный автор", "СПб авторский канал", "Петербург городской блог",
    "Питер обзорщик", "Петербург рекомендации", "СПб полезный блог",
    "Петербург мама блог", "Питер папа блог", "СПб семейный блог",
    "Петербург бьюти блог", "Питер фуд блог", "СПб lifestyle vlog",
    "Петербург Shorts", "Питер Reels", "СПб куда сходить", "Петербург что посмотреть",
    "Питер необычные места", "СПб новые места", "Петербург локальные бренды",
]


def queries() -> list[str]:
    result = list(BASE_QUERIES)
    result.extend(f"{name} Санкт-Петербург обзор" for name in LEAD_SEEDS)
    for district in DISTRICTS:
        result.extend([
            f"{district} Санкт-Петербург блог",
            f"{district} куда сходить",
            f"{district} обзор мест",
            f"{district} семейный обзор",
            f"{district} кафе обзор",
        ])
    for niche in NICHES:
        result.extend([
            f"{niche} Санкт-Петербург обзор",
            f"{niche} СПб блогер",
            f"{niche} Питер shorts",
            f"лучшие {niche} Петербург",
        ])
    return list(dict.fromkeys(result))


def collect(workers: int) -> tuple[list[dict[str, Any]], dict[str, int]]:
    discovered: dict[str, dict[str, Any]] = {}
    query_list = queries()
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(discover_query, CITY, query): query for query in query_list}
        for future in as_completed(futures):
            try:
                items = future.result()
            except Exception:
                continue
            for item in items:
                channel_id = str(item["channel_id"])
                existing = discovered.get(channel_id)
                if existing is None:
                    item["directory_queries"] = [item["query"]]
                    discovered[channel_id] = item
                else:
                    existing.setdefault("directory_queries", []).append(item["query"])

    verified: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(verify, item): item for item in discovered.values()}
        for future in as_completed(futures):
            try:
                candidate = future.result()
            except Exception:
                continue
            if candidate:
                source = futures[future]
                candidate["directory_queries"] = sorted(set(source.get("directory_queries", [])))
                candidate["lead_seeded"] = any(seed.lower() in " ".join(candidate["directory_queries"]).lower() for seed in LEAD_SEEDS)
                verified.append(candidate)
    stats = {"query_count": len(query_list), "discovered_channels": len(discovered), "verified_channels": len(verified)}
    return sorted(verified, key=lambda item: str(item["display_name"]).lower()), stats


def write(candidates: list[dict[str, Any]], stats: dict[str, int], json_path: Path, csv_path: Path) -> None:
    report = {
        "schema_version": "1.0",
        "title": "Расширение базы инфлюенсеров Санкт-Петербурга из графа LocalOS-лидов",
        "status": "public_research_only_needs_manual_shortlist",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "candidate_count": len(candidates),
        "city_counts": {CITY: len(candidates)},
        "platform_counts": {"youtube": len(candidates)},
        "lead_seed_count": len(LEAD_SEEDS),
        "research_stats": stats,
        "candidates": candidates,
        "limitations": [
            "Локальность подтверждена конкретным публичным видео о Санкт-Петербурге, а не местом жительства автора.",
            "Перед кампанией нужны ручная проверка аудитории, активности, brand safety и условий сотрудничества.",
            "Сохранённые лиды использованы только как поисковые семена; записи LocalOS не изменялись.",
        ],
    }
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    columns = ["candidate_id", "display_name", "platform", "canonical_url", "username", "city", "subscriber_count", "audience_band", "contactability", "verification_status", "source_url", "discovery_source_url", "evidence_url", "evidence_summary", "lead_seeded", "directory_queries", "researched_at"]
    with csv_path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for candidate in candidates:
            row = dict(candidate)
            row["directory_queries"] = " | ".join(candidate.get("directory_queries", []))
            writer.writerow(row)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-json", default="outputs/influencer-spb-youtube-expansion-20260823.json")
    parser.add_argument("--output-csv", default="outputs/influencer-spb-youtube-expansion-20260823.csv")
    parser.add_argument("--workers", type=int, default=24)
    args = parser.parse_args()
    candidates, stats = collect(args.workers)
    write(candidates, stats, Path(args.output_json), Path(args.output_csv))
    print(json.dumps({"candidate_count": len(candidates), **stats}, ensure_ascii=False))


if __name__ == "__main__":
    main()
