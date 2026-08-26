#!/usr/bin/env python3
"""Discover active public authors posting about Saint Petersburg.

The collector uses public YouTube search results for the activity/evidence layer and
keeps public cross-platform links exposed by the author's YouTube profile. It does
not send messages, enter private areas, or infer a home district without evidence.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import re
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import parse_qs, quote_plus, unquote, urlparse


CITY = "Санкт-Петербург"
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/127 Safari/537.36"
CITY_MARKERS = ("санкт-петербург", "санкт петербург", "петербург", "питер", "спб", "saint petersburg", "st petersburg")
DISTRICTS = (
    "адмиралтейский", "василеостровский", "выборгский", "калининский", "кировский",
    "колпинский", "красногвардейский", "красносельский", "кронштадтский", "курортный",
    "московский", "невский", "петроградский", "петродворцовый", "приморский", "пушкинский",
    "фрунзенский", "центральный",
)
LOCATIONS = (
    "Санкт-Петербург", "Петербург", "Питер", "СПб",
    "Адмиралтейский район", "Василеостровский район", "Выборгский район", "Калининский район",
    "Кировский район", "Колпинский район", "Красногвардейский район", "Красносельский район",
    "Кронштадт", "Курортный район", "Московский район", "Невский район", "Петроградский район",
    "Петродворцовый район", "Приморский район", "Пушкинский район", "Фрунзенский район", "Центральный район",
    "Васильевский остров", "Петроградка", "Купчино", "Мурино", "Кудрово", "Парнас", "Рыбацкое", "Шушары",
    "Сестрорецк", "Зеленогорск", "Петергоф", "Пушкин", "Павловск", "Колпино", "Ломоносов", "Кронштадт",
    "Комендантский проспект", "Проспект Просвещения", "Озерки", "Удельная", "Черная речка", "Пионерская",
    "Беговая", "Старая Деревня", "Лесная", "Площадь Мужества", "Гражданский проспект", "Академическая",
    "Площадь Восстания", "Лиговский проспект", "Обводный канал", "Московские ворота", "Парк Победы", "Звездная", "Международная",
    "Елизаровская", "Ломоносовская", "Пролетарская", "Дыбенко", "Большевиков", "Новочеркасская", "Ладожская",
    "Новая Голландия", "Севкабель Порт", "Елагин остров", "Крестовский остров", "Лахта", "Смольный", "Охта", "Ухта молл",
)
EXTRA_LOCATIONS = (
    "Невский проспект", "Садовая улица", "улица Рубинштейна", "Большая Конюшенная", "Малая Садовая",
    "Гороховая улица", "Литейный проспект", "Владимирский проспект", "Загородный проспект", "Московский проспект",
    "Каменноостровский проспект", "Большой проспект Петроградской", "Средний проспект ВО", "Большой проспект ВО", "6 линия ВО",
    "Приморский проспект", "Богатырский проспект", "Парашютная улица", "Туристская улица", "Кораблестроителей",
    "Ленинский проспект", "Проспект Ветеранов", "Петергофское шоссе", "Стачек", "Нарвская застава",
    "Проспект Славы", "Бухарестская улица", "Софийская улица", "Дальневосточный проспект", "Индустриальный проспект",
    "Проспект Наставников", "Гражданский проспект", "Проспект Культуры", "Выборгское шоссе", "Суздальский проспект",
    "Ушаковская набережная", "Пискаревский проспект", "Шоссе Революции", "Большеохтинский проспект", "Синопская набережная",
    "Набережная реки Фонтанки", "канал Грибоедова", "набережная Мойки", "Крюков канал", "Карповка",
    "Таврический сад", "Летний сад", "Марсово поле", "Михайловский сад", "Парк 300-летия",
    "Удельный парк", "Сосновка парк", "Полюстровский парк", "Парк Екатерингоф", "Парк Александрино",
    "Муринский парк", "Парк Интернационалистов", "Парк Городов-героев", "Парк Авиаторов", "Юнтоловский заказник",
    "Галерея торговый центр", "Европолис", "Питер Радуга", "МЕГА Дыбенко", "МЕГА Парнас",
    "Охта Молл", "Атлантик Сити", "Гранд Каньон", "Лондон Молл", "Невский центр",
    "Василеостровский рынок", "Кузнечный рынок", "Сенной рынок", "Никольские ряды", "Брусницын лофт",
    "Новая Голландия", "Остров Фортов", "Порт Севкабель", "Дизайн Дистрикт ДАА", "Этажи лофт",
    "Бертгольд Центр", "Анненкирхе", "Третье место", "Вокзал 1853", "Ленполиграфмаш",
    "Манежная площадь", "Исаакиевская площадь", "Дворцовая площадь", "Площадь Островского", "Площадь Труда",
)
INTENTS = (
    "блог", "vlog", "shorts", "обзор", "отзыв", "рекомендую", "куда сходить", "прогулка", "новые места", "любимые места",
    "кафе", "кофейня", "ресторан", "еда", "стритфуд", "завтрак", "десерты", "с детьми", "мама блог", "папа блог", "семейный досуг",
    "детские места", "красота", "бьюти", "салон красоты", "парикмахерская", "маникюр", "косметология", "спорт", "бег", "фитнес", "йога",
    "танцы", "мода", "стиль", "винтаж", "покупки", "локальные бренды", "фотограф", "видеограф", "искусство", "музеи", "выставки", "театр",
    "концерты", "афиша", "события", "история", "архитектура", "экскурсия", "туризм", "отель", "жизнь района", "новости района", "соседи", "малый бизнес",
    "домашние животные", "собаки", "образование", "школы", "кружки", "недвижимость", "новостройки", "интерьер", "ремонт", "садоводство", "дача",
)
PLATFORM_PATTERNS = {
    "instagram": re.compile(r"https?://(?:www\.)?instagram\.com/[A-Za-z0-9_.]+/?", re.IGNORECASE),
    "threads": re.compile(r"https?://(?:www\.)?threads\.(?:net|com)/@[A-Za-z0-9_.]+/?", re.IGNORECASE),
    "tiktok": re.compile(r"https?://(?:www\.)?tiktok\.com/@[A-Za-z0-9_.]+/?", re.IGNORECASE),
    "telegram": re.compile(r"https?://(?:t\.me|telegram\.me)/[A-Za-z0-9_]+/?", re.IGNORECASE),
    "vk": re.compile(r"https?://(?:www\.)?vk\.com/[A-Za-z0-9_.-]+/?", re.IGNORECASE),
}
EXCLUDED_SOCIAL_PATHS = {"p", "reel", "reels", "explore", "accounts", "stories", "video", "wall", "feed", "share", "albums", "away.php", "boost"}


def fetch(url: str, timeout: int = 18) -> str:
    for attempt in range(3):
        try:
            result = subprocess.run(
                ["curl", "--compressed", "-L", "--max-time", str(timeout), "-A", USER_AGENT, "-s", url],
                capture_output=True,
                check=False,
                timeout=timeout + 4,
            )
        except (OSError, subprocess.SubprocessError):
            time.sleep(0.25 * (attempt + 1))
            continue
        if result.returncode == 0 and result.stdout:
            return result.stdout.decode("utf-8", errors="replace")
        time.sleep(0.25 * (attempt + 1))
    return ""


def post_json(url: str, payload: dict[str, Any], timeout: int = 18) -> str:
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    for attempt in range(3):
        try:
            result = subprocess.run(
                ["curl", "--compressed", "-L", "--max-time", str(timeout), "-A", USER_AGENT, "-s", "-H", "Content-Type: application/json", "--data-binary", body, url],
                capture_output=True,
                check=False,
                timeout=timeout + 4,
            )
        except (OSError, subprocess.SubprocessError):
            time.sleep(0.25 * (attempt + 1))
            continue
        if result.returncode == 0 and result.stdout:
            return result.stdout.decode("utf-8", errors="replace")
        time.sleep(0.25 * (attempt + 1))
    return ""


def walk(value: Any) -> Iterator[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


def text_value(value: dict[str, Any] | None) -> str:
    if not value:
        return ""
    if value.get("simpleText"):
        return str(value["simpleText"])
    return "".join(str(run.get("text", "")) for run in value.get("runs", []))


def initial_data(document: str) -> dict[str, Any]:
    for marker in ("var ytInitialData = ", "ytInitialData = "):
        start = document.find(marker)
        if start < 0:
            continue
        try:
            value, _ = json.JSONDecoder().raw_decode(document[start + len(marker):])
            return value if isinstance(value, dict) else {}
        except json.JSONDecodeError:
            continue
    return {}


def is_recent(label: str) -> bool:
    lowered = label.casefold().replace("streamed", "").strip()
    if not lowered:
        return False
    if any(marker in lowered for marker in ("минут", "час", "ден", "дня", "дней", "недел", "месяц", "minute", "hour", "day", "week", "month", "live", "эфир")):
        return True
    year_match = re.search(r"(\d+)\s*(?:год|года|лет|year)", lowered)
    return bool(year_match and int(year_match.group(1)) <= 1)


def query_specs(offset: int, max_queries: int) -> list[tuple[str, str]]:
    base = [(location, intent) for location in (*LOCATIONS, *EXTRA_LOCATIONS) for intent in INTENTS]
    specs = [(f"{location} {intent}", location) for location, intent in base]
    specs.extend((f"{intent} {location}", location) for location, intent in base)
    specs.extend((f"{location} {intent} 2025", location) for location, intent in base)
    specs.extend((f"{location} {intent} 2026", location) for location, intent in base)
    specs.extend((f"{intent} {location} 2026", location) for location, intent in base)
    start = max(0, offset)
    return specs[start:start + max_queries] if max_queries > 0 else specs[start:]


def continuation_token(data: dict[str, Any]) -> str:
    for node in walk(data):
        endpoint = node.get("continuationEndpoint")
        if not isinstance(endpoint, dict):
            continue
        token = endpoint.get("continuationCommand", {}).get("token")
        if token:
            return str(token)
    return ""


def parse_search_data(data: dict[str, Any], query: str, location: str, search_url: str) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    location_markers = tuple({location.casefold(), *CITY_MARKERS})
    for node in walk(data):
        renderer = node.get("videoRenderer")
        if not isinstance(renderer, dict):
            continue
        title = text_value(renderer.get("title"))
        snippets = " ".join(text_value(item.get("snippetText")) for item in renderer.get("detailedMetadataSnippets", []))
        evidence_text = f"{title} {snippets}".casefold()
        matched = next((marker for marker in location_markers if marker and marker in evidence_text), "")
        if not matched:
            continue
        published_label = text_value(renderer.get("publishedTimeText"))
        if not is_recent(published_label):
            continue
        owner_runs = (renderer.get("ownerText") or {}).get("runs", [])
        if not owner_runs:
            continue
        endpoint = owner_runs[0].get("navigationEndpoint", {}).get("browseEndpoint", {})
        channel_id = str(endpoint.get("browseId") or "").strip()
        if not channel_id:
            continue
        video_id = str(renderer.get("videoId") or "").strip()
        found.append({
            "query": query,
            "location": location,
            "matched_marker": matched,
            "search_url": search_url,
            "channel_id": channel_id,
            "canonical_path": endpoint.get("canonicalBaseUrl"),
            "channel_title": str(owner_runs[0].get("text") or "").strip(),
            "evidence_title": title,
            "evidence_url": f"https://www.youtube.com/watch?v={video_id}" if video_id else search_url,
            "published_label": published_label or "date unavailable; current search result",
            "view_count_label": text_value(renderer.get("viewCountText")),
        })
    return found


def discover_query(spec: tuple[str, str], continuation_pages: int) -> list[dict[str, Any]]:
    query, location = spec
    search_url = f"https://www.youtube.com/results?search_query={quote_plus(query)}&hl=ru"
    document = fetch(search_url)
    data = initial_data(document)
    found = parse_search_data(data, query, location, search_url)
    api_key_match = re.search(r'"INNERTUBE_API_KEY":"([^"]+)"', document)
    version_match = re.search(r'"INNERTUBE_CLIENT_VERSION":"([^"]+)"', document)
    token = continuation_token(data)
    if not api_key_match or not version_match:
        return found
    api_url = f"https://www.youtube.com/youtubei/v1/search?key={api_key_match.group(1)}"
    for _ in range(max(0, continuation_pages)):
        if not token:
            break
        payload = {
            "context": {"client": {"clientName": "WEB", "clientVersion": version_match.group(1), "hl": "ru"}},
            "continuation": token,
        }
        response = post_json(api_url, payload)
        try:
            page_data = json.loads(response)
        except json.JSONDecodeError:
            break
        found.extend(parse_search_data(page_data, query, location, search_url))
        token = continuation_token(page_data)
    return found


def parse_subscribers(document: str) -> int | None:
    matches = re.findall(r'"subscriberCountText"\s*:\s*(?:\{"simpleText":"([^"]+)"|"([^"]+)")', document, flags=re.IGNORECASE)
    if not matches:
        return None
    label = html.unescape(matches[0][0] or matches[0][1]).replace("\u00a0", " ")
    match = re.search(r"([\d.,]+)\s*([KMB]|тыс|млн|млрд)?", label, flags=re.IGNORECASE)
    if not match:
        return None
    raw = match.group(1)
    raw = raw.replace(",", ".") if "," in raw and "." not in raw else raw.replace(",", "")
    number = float(raw)
    suffix = (match.group(2) or "").casefold()
    if suffix in {"k", "тыс"}:
        number *= 1_000
    elif suffix in {"m", "млн"}:
        number *= 1_000_000
    elif suffix in {"b", "млрд"}:
        number *= 1_000_000_000
    return round(number)


def canonical_social_url(platform: str, value: str) -> str | None:
    decoded = html.unescape(unquote(value)).replace("\\/", "/").rstrip("/.,);]}")
    parsed = urlparse(decoded)
    if "youtube.com/redirect" in decoded:
        redirected = parse_qs(parsed.query).get("q", [])
        if redirected:
            return canonical_social_url(platform, redirected[0])
    parts = [part for part in parsed.path.split("/") if part]
    if not parts or parts[0].casefold() in EXCLUDED_SOCIAL_PATHS:
        return None
    if platform == "instagram":
        return f"https://www.instagram.com/{parts[0].lstrip('@')}"
    if platform == "threads":
        return f"https://www.threads.com/@{parts[0].lstrip('@')}"
    if platform == "tiktok":
        return f"https://www.tiktok.com/@{parts[0].lstrip('@')}"
    if platform == "telegram":
        return f"https://t.me/{parts[0].lstrip('@')}"
    if platform == "vk":
        return f"https://vk.com/{parts[0]}"
    return None


def linked_channels(document: str) -> list[dict[str, Any]]:
    decoded = html.unescape(unquote(document)).replace("\\/", "/")
    channels: dict[tuple[str, str], dict[str, Any]] = {}
    for platform, pattern in PLATFORM_PATTERNS.items():
        for match in pattern.findall(decoded):
            url = canonical_social_url(platform, match)
            if not url:
                continue
            key = (platform, url.casefold())
            channels[key] = {
                "platform": platform,
                "canonical_url": url,
                "username": url.rstrip("/").rsplit("/", 1)[-1].lstrip("@"),
                "verification_status": "source_verified",
                "source_url": url,
                "discovery_source_url": "youtube_about_public_link",
            }
    return list(channels.values())


def meta(document: str, name: str) -> str:
    patterns = (
        rf'<meta[^>]+property="{re.escape(name)}"[^>]+content="([^"]*)"',
        rf'<meta[^>]+content="([^"]*)"[^>]+property="{re.escape(name)}"',
    )
    for pattern in patterns:
        match = re.search(pattern, document, flags=re.IGNORECASE)
        if match:
            return html.unescape(match.group(1)).strip()
    return ""


def verify_channel(item: dict[str, Any]) -> dict[str, Any] | None:
    canonical_path = str(item.get("canonical_path") or "").strip()
    profile_url = f"https://www.youtube.com{canonical_path}" if canonical_path else f"https://www.youtube.com/channel/{item['channel_id']}"
    about_url = f"{profile_url}/about?hl=en"
    document = fetch(about_url)
    display_name = meta(document, "og:title")
    if not display_name:
        return None
    subscriber_count = parse_subscribers(document)
    observed_at = datetime.now(timezone.utc).isoformat()
    evidence_items = sorted(item["evidence"], key=lambda value: str(value.get("published_label")))[:5]
    geography_terms = sorted({str(value["location"]) for value in evidence_items if value.get("location")})
    district_values = sorted({term for term in geography_terms if any(marker in term.casefold() for marker in DISTRICTS)})
    channel_handle = unquote(canonical_path.removeprefix("/@")) if canonical_path.startswith("/@") else str(item["channel_id"])
    channels = [{
        "platform": "youtube",
        "canonical_url": profile_url,
        "username": channel_handle,
        "follower_count": subscriber_count,
        "audience_band": "nano" if subscriber_count is not None and subscriber_count < 10_000 else "micro" if subscriber_count is not None and subscriber_count < 100_000 else "mid" if subscriber_count is not None else "unknown",
        "verification_status": "original_profile_opened",
        "source_url": profile_url,
        "discovery_source_url": evidence_items[0]["search_url"],
        "evidence_url": evidence_items[0]["evidence_url"],
        "researched_at": observed_at,
    }]
    channels.extend(linked_channels(document))
    description = meta(document, "og:description")
    entity_id = hashlib.sha256(f"spb-active:{item['channel_id']}".encode()).hexdigest()[:20]
    return {
        "entity_id": entity_id,
        "display_name": display_name,
        "profile_type": "author",
        "primary_handle": channel_handle,
        "primary_city": CITY,
        "cities": [CITY],
        "districts": district_values,
        "description": description,
        "topics": [],
        "contactability": "manual_only",
        "preferred_contact": None,
        "channels": channels,
        "evidence": [{
            "observed": f"Свежая публичная публикация «{value['evidence_title']}» содержит географический маркер «{value['matched_marker']}»; YouTube показывает давность: {value['published_label']}.",
            "source_url": value["evidence_url"],
            "source_type": "recent_public_video",
            "researched_at": observed_at,
            "confidence": 0.85,
        } for value in evidence_items],
        "research": {
            "researched_at": observed_at,
            "activity_status": "recent_publication_observed",
            "recent_publication_evidence_count": len(evidence_items),
            "content_geographies": geography_terms,
            "district_status": "publicly_observed_in_content" if district_values else "ask_creator",
            "outreach_status": "not_contacted",
            "messages_sent": 0,
        },
        "limitations": [
            "Публикация о Петербурге подтверждает связь контента с городом, но не место жительства автора и не долю аудитории в городе.",
            "Район, если он не назван в публикации, нужно уточнить у автора.",
            "Перед кампанией нужны brand-safety review и проверка актуальных охватов.",
        ],
    }


def load_existing_urls(path: Path | None) -> set[str]:
    if path is None or not path.exists():
        return set()
    return {line.strip().casefold().rstrip("/") for line in path.read_text(encoding="utf-8").splitlines() if line.strip()}


def write_outputs(entities: list[dict[str, Any]], json_path: Path, csv_path: Path, stats: dict[str, Any]) -> None:
    platform_counts: dict[str, int] = {}
    for entity in entities:
        for channel in entity["channels"]:
            platform = str(channel["platform"])
            platform_counts[platform] = platform_counts.get(platform, 0) + 1
    payload = {
        "schema_version": "1.0",
        "title": "Активные публичные авторы с контентом о Санкт-Петербурге",
        "status": "public_research_reviewed_no_messages_sent",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "entity_count": len(entities),
        "channel_count": sum(platform_counts.values()),
        "platform_counts": platform_counts,
        "city_counts": {CITY: len(entities)},
        "research_stats": stats,
        "entities": entities,
        "limitations": [
            "База расширена до активных публикующих авторов; это не утверждённый shortlist.",
            "Никакие сообщения, черновики или очереди отправки не создавались.",
        ],
    }
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    stream = csv_path.open("w", newline="", encoding="utf-8")
    try:
        fields = ["entity_id", "display_name", "primary_handle", "primary_city", "districts", "platforms", "channel_count", "subscriber_count", "activity_status", "evidence_url", "published_label"]
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for entity in entities:
            youtube = next(channel for channel in entity["channels"] if channel["platform"] == "youtube")
            first_evidence = entity["evidence"][0]
            published_match = re.search(r"давность: (.+)\.$", first_evidence["observed"])
            writer.writerow({
                "entity_id": entity["entity_id"],
                "display_name": entity["display_name"],
                "primary_handle": entity["primary_handle"],
                "primary_city": entity["primary_city"],
                "districts": ", ".join(entity["districts"]),
                "platforms": ", ".join(channel["platform"] for channel in entity["channels"]),
                "channel_count": len(entity["channels"]),
                "subscriber_count": youtube.get("follower_count"),
                "activity_status": entity["research"]["activity_status"],
                "evidence_url": first_evidence["source_url"],
                "published_label": published_match.group(1) if published_match else "",
            })
    finally:
        stream.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-json", type=Path, default=Path("outputs/influencer-spb-active-wave3-20260826.json"))
    parser.add_argument("--output-csv", type=Path, default=Path("outputs/influencer-spb-active-wave3-20260826.csv"))
    parser.add_argument("--existing-urls", type=Path)
    parser.add_argument("--workers", type=int, default=24)
    parser.add_argument("--max-queries", type=int, default=0)
    parser.add_argument("--query-offset", type=int, default=0)
    parser.add_argument("--continuation-pages", type=int, default=0)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--checkpoint-json", type=Path)
    parser.add_argument("--resume-checkpoint", type=Path)
    arguments = parser.parse_args()
    specs = query_specs(arguments.query_offset, arguments.max_queries)
    discovered: dict[str, dict[str, Any]] = {}
    if arguments.resume_checkpoint:
        checkpoint_items = json.loads(arguments.resume_checkpoint.read_text(encoding="utf-8"))
        discovered = {str(item["channel_id"]): item for item in checkpoint_items}
        print(json.dumps({"phase": "discovery_resumed", "unique_channels": len(discovered)}, ensure_ascii=False), flush=True)
    else:
        executor = ThreadPoolExecutor(max_workers=max(1, min(arguments.workers, 48)))
        try:
            futures = [executor.submit(discover_query, spec, arguments.continuation_pages) for spec in specs]
            for completed, future in enumerate(as_completed(futures), start=1):
                try:
                    results = future.result()
                except Exception:
                    results = []
                for result in results:
                    channel_id = str(result["channel_id"])
                    target = discovered.setdefault(channel_id, {**result, "evidence": []})
                    evidence_key = str(result["evidence_url"])
                    if all(str(item["evidence_url"]) != evidence_key for item in target["evidence"]):
                        target["evidence"].append(result)
                if completed % 250 == 0:
                    if arguments.checkpoint_json:
                        arguments.checkpoint_json.write_text(json.dumps(list(discovered.values()), ensure_ascii=False), encoding="utf-8")
                    print(json.dumps({"phase": "discovery", "queries_completed": completed, "queries_total": len(futures), "unique_channels": len(discovered)}, ensure_ascii=False), flush=True)
        finally:
            executor.shutdown(wait=True)
        if arguments.checkpoint_json:
            arguments.checkpoint_json.write_text(json.dumps(list(discovered.values()), ensure_ascii=False), encoding="utf-8")
            print(json.dumps({"phase": "checkpoint_written", "path": str(arguments.checkpoint_json), "unique_channels": len(discovered)}, ensure_ascii=False), flush=True)
    existing_urls = load_existing_urls(arguments.existing_urls)
    pending = [item for item in discovered.values() if f"https://www.youtube.com/channel/{item['channel_id']}".casefold() not in existing_urls]
    entities: list[dict[str, Any]] = []
    executor = ThreadPoolExecutor(max_workers=max(1, min(arguments.workers, 48)))
    try:
        futures = [executor.submit(verify_channel, item) for item in pending]
        for completed, future in enumerate(as_completed(futures), start=1):
            try:
                entity = future.result()
            except Exception:
                entity = None
            if entity:
                youtube_url = next(channel["canonical_url"] for channel in entity["channels"] if channel["platform"] == "youtube")
                overlaps_existing = any(
                    str(channel["canonical_url"]).casefold().rstrip("/") in existing_urls
                    for channel in entity["channels"]
                )
                if youtube_url.casefold().rstrip("/") not in existing_urls and not overlaps_existing:
                    entities.append(entity)
            if completed % 250 == 0:
                print(json.dumps({"phase": "verification", "profiles_completed": completed, "profiles_total": len(futures), "selected": len(entities)}, ensure_ascii=False), flush=True)
    finally:
        executor.shutdown(wait=True)
    entities.sort(key=lambda item: (-int(item["research"]["recent_publication_evidence_count"]), str(item["display_name"]).casefold()))
    if arguments.limit > 0:
        entities = entities[:arguments.limit]
    stats = {
        "query_count": len(specs),
        "unique_channels_discovered": len(discovered),
        "channels_verified_and_selected": len(entities),
        "existing_urls_loaded": len(existing_urls),
        "messages_sent": 0,
    }
    write_outputs(entities, arguments.output_json, arguments.output_csv, stats)
    print(json.dumps({**stats, "platform_counts": json.loads(arguments.output_json.read_text(encoding="utf-8"))["platform_counts"]}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
