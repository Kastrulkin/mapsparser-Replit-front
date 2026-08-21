#!/usr/bin/env python3
"""Build Party 10 review copy from current public Yandex facts, without writes."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from services.outreach_campaign_service import _quality_gate
from services.outreach_human_language import review_human_language


ROOT = Path("/Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Obsidian/Obsidian Vault/outputs")
SELECTION = ROOT / "localos-party10-local-commerce-20260813.json"
LIVE = ROOT / "localos-party10-live-yandex-20260813.json"
DETAILED = ROOT / "localos-parties9-11-detailed-signals-20260813.json"
OUTPUT = ROOT / "localos-party10-review-v2-20260813.json"
MARKDOWN = ROOT / "localos-party10-review-v2-20260813.md"
detailed_by_id: dict[str, dict[str, Any]] = {}


def canonical_sha(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def rating_text(value: float) -> str:
    return f"{value:.1f}".replace(".", ",")


def counted_word(count: int, one: str, few: str, many: str) -> str:
    if count % 10 == 1 and count % 100 != 11:
        return one
    if count % 10 in {2, 3, 4} and count % 100 not in {12, 13, 14}:
        return few
    return many


def signature(channel: str) -> str:
    if channel == "email":
        return "\n\n--\nАлександр\nоснователь ЛокалОС"
    return ""


def greeting(channel: str) -> str:
    if channel == "email":
        return "Здравствуйте!"
    return "Здравствуйте! Я Александр Демьянов, основатель LocalOS."


def route_value(item: dict[str, Any], channel: str) -> tuple[str | None, str | None]:
    key_prefix = f"{channel}:"
    allowed = [key for key in item.get("verified_route_keys") or [] if key.startswith(key_prefix)]
    if not allowed:
        return None, None
    normalized = allowed[0].split(":", 1)[1]
    for contact in item.get("contacts") or []:
        if contact.get("contact_type") == channel and contact.get("normalized_value") == normalized:
            return str(contact.get("id")), normalized
    return None, normalized


def route_plan(item: dict[str, Any]) -> list[tuple[str, str, str | None]]:
    available: list[tuple[str, str, str | None]] = []
    for channel in ("email", "vk", "whatsapp", "phone"):
        contact_id, value = route_value(item, channel)
        if value:
            available.append((channel, value, contact_id))
    if not available:
        raise RuntimeError(f"no_safe_route:{item['name']}")
    # Keep three distinct pain angles even when the business exposes only one route.
    return [available[index] if index < len(available) else available[-1] for index in range(3)]


def audit_paragraph(item: dict[str, Any]) -> str:
    if not item.get("audit_active") or not item.get("audit_slug"):
        return ""
    return (
        "\n\nПомимо этого, мы подготовили аудит карточки с конкретными изменениями. "
        f"Их можно внедрить самостоятельно или поручить нам: https://localos.pro/{item['audit_slug']}"
    )


def first_touch(item: dict[str, Any], live: dict[str, Any], channel: str) -> tuple[str, str]:
    name = item["name"]
    rating = float(live.get("rating") or 0)
    reviews = int(live.get("review_count") or 0)
    has_news = bool(live.get("news_module_present")) and int(live.get("news_count") or 0) > 0
    start = greeting(channel)
    audit = audit_paragraph(item)
    if 1 <= rating < 4.5:
        body = (
            f"{start}\n\nУ карточки {name} на Яндекс Картах рейтинг {rating_text(rating)}"
            + (
                f" при {reviews} {counted_word(reviews, 'отзыве', 'отзывах', 'отзывах')}."
                if reviews
                else "."
            )
            + " При таком рейтинге часть клиентов может выбрать компанию с более сильной карточкой.\n\n"
            "LocalOS поможет исправить карточку: покажет, что стоит изменить, отследит новые отзывы "
            "и подготовит ответы.\n\nСтоимость - от 1200 рублей в месяц."
            f"{audit}\n\nВам может быть это интересно?"
        )
        angle = "weak_map_rating"
    elif not has_news:
        body = (
            f"{start}\n\nВ карточке {name} на Яндекс Картах нет новостей.\n\n"
            "Возможно, на публикации просто не хватает времени: надо собраться и написать пост, "
            "одну тему приходится переделывать для каждой площадки. Публикации помогают рассказывать "
            "о предложениях и привлекать клиентов онлайн.\n\n"
            "LocalOS составит контент-план и подготовит тексты для Telegram, VK и Яндекс Карт. "
            "Сотруднику останется подтвердить и опубликовать их."
            f"{audit}\n\nПодготовить пример контент-плана на неделю?"
        )
        angle = "map_content_gap"
    else:
        body = (
            f"{start}\n\n{name} ведёт карточку на Яндекс Картах и публикует новости.\n\n"
            "Часто на посты не хватает времени: надо собраться и написать пост, одну тему приходится "
            "переделывать для каждой площадки. Публикации помогают рассказывать о предложениях и "
            "привлекать клиентов онлайн.\n\n"
            "LocalOS составит контент-план и подготовит тексты для Telegram, VK и Яндекс Карт. "
            "Сотруднику останется подтвердить и опубликовать их."
            f"{audit}\n\nПодготовить пример контент-плана на неделю?"
        )
        angle = "active_map_news"
    return body + signature(channel), angle


def second_touch(item: dict[str, Any], live: dict[str, Any], channel: str) -> tuple[str, str]:
    name = item["name"]
    visible = int(live.get("visible_service_count") or 0)
    priced = int(live.get("visible_service_priced_count") or 0)
    start = greeting(channel)
    if visible >= 3:
        body = (
            f"{start}\n\nВ карточке {name} на Яндекс Картах видны {visible} "
            f"{counted_word(visible, 'позиция', 'позиции', 'позиций')}, "
            f"у {priced} из них указана цена.\n\n"
            "Когда предложений много, сотрудникам приходится держать в голове, что можно предложить вместе. "
            "Из-за этого часть допродаж просто не происходит.\n\n"
            "LocalOS соберёт из прайса матрицу основных и дополнительных предложений, подготовит подсказки "
            "для сотрудников и поможет отметить результат.\n\n"
            "Вам было бы интересно увеличить средний чек?"
        )
        angle = "average_ticket"
    else:
        reviews = int(live.get("review_count") or 0)
        review_fact = (
            f"У карточки {name} на Яндекс Картах уже {reviews} "
            f"{counted_word(reviews, 'отзыв', 'отзыва', 'отзывов')}."
            if reviews
            else f"У {name} есть карточка на Яндекс Картах, где клиенты могут оставлять отзывы."
        )
        body = (
            f"{start}\n\n{review_fact}\n\n"
            "Отзывы читают перед выбором, но разбирать их по темам и отвечать на каждый вручную - ещё одна задача для команды.\n\n"
            "LocalOS сгруппирует темы из отзывов и подготовит ответы. Сотруднику останется проверить и опубликовать их.\n\n"
            "Вам было бы интересно сэкономить время на работе с отзывами?"
        )
        angle = "reviews"
    return body + signature(channel), angle


def third_touch(item: dict[str, Any], channel: str) -> tuple[str, str]:
    name = item["name"]
    category = str(item.get("category") or item.get("segment") or "локального бизнеса")
    segment = str(item.get("segment") or "")
    partner_targets = {
        "Дети и образование": "семейными кафе, детскими магазинами и жилыми комплексами",
        "Фитнес и спорт": "местными спортивными магазинами, клиниками и жилыми комплексами",
        "Гостиницы и отдых": "ресторанами, организаторами мероприятий и туристическими проектами",
        "Еда и гостеприимство": "отелями, организаторами мероприятий и ближайшими бизнес-центрами",
        "Ритейл": "жилыми комплексами, локальными сервисами и компаниями с похожей аудиторией",
        "Профессиональные услуги": "организаторами мероприятий, локальными брендами и бизнес-сообществами",
        "Недвижимость": "дизайнерами, ремонтными компаниями и мебельными салонами",
        "Туризм и досуг": "отелями, кафе и организаторами мероприятий",
        "Дом и ремонт": "застройщиками, дизайнерами и ремонтными компаниями",
        "Животные": "зоомагазинами, грумерами и жилыми комплексами",
        "B2B и производство": "интеграторами, поставщиками оборудования и отраслевыми сообществами",
        "Стоматология": "детскими центрами, фитнес-клубами и компаниями-работодателями",
        "Медицина": "фитнес-клубами, семейными центрами и компаниями-работодателями",
        "Красота и косметология": "фитнес-клубами, магазинами одежды и свадебными проектами",
    }.get(segment, "местными бизнесами с похожей аудиторией")
    category_lower = category.lower()
    if segment in {"Ритейл", "Дом и ремонт"} and any(
        word in category_lower for word in ("детск", "коляск", "автокрес", "игруш")
    ):
        partner_targets = "семейными центрами, клиниками для семей с детьми и жилыми комплексами"
    observation = f"В карточке {name} на Яндекс Картах указано направление: {category}."
    bridge = (
        "Если клиенты приходят в основном из привычных каналов, можно проверить ещё один - "
        f"партнёрства с {partner_targets}. Это пока только гипотеза, а не вывод о вашей текущей работе."
    )
    body = (
        f"{greeting(channel)}\n\n{observation}\n\n{bridge}\n\n"
        "LocalOS подготовит список местных бизнесов со смежной аудиторией и черновик предложения о партнёрстве. "
        "Вы сами решите, кому его отправить.\n\n"
        "Вам было бы интересно находить новых клиентов через партнёрства?"
    )
    return body + signature(channel), "partnerships"


def main() -> None:
    global detailed_by_id
    selection = json.loads(SELECTION.read_text(encoding="utf-8"))
    live_by_id = {item["lead_id"]: item for item in json.loads(LIVE.read_text(encoding="utf-8"))["results"]}
    detailed_by_id = {
        item["lead_id"]: item
        for item in json.loads(DETAILED.read_text(encoding="utf-8"))["results"]
    }
    results: list[dict[str, Any]] = []
    for item in selection["selected"]:
        live = live_by_id[item["lead_id"]]
        routes = route_plan(item)
        generators = (
            lambda channel: first_touch(item, live, channel),
            lambda channel: second_touch(item, live, channel),
            lambda channel: third_touch(item, channel),
        )
        touches: list[dict[str, Any]] = []
        for index, ((channel, recipient, contact_id), generator) in enumerate(zip(routes, generators)):
            text, angle = generator(channel)
            language = review_human_language(text, require_signal_flow=True)
            content_text = text.split("\n\n--\n", 1)[0]
            paragraphs = [part.strip() for part in content_text.split("\n\n") if part.strip()]
            observed_fact = paragraphs[1]
            pain_bridge = paragraphs[2]
            localos_action = next(part for part in paragraphs if part.startswith("LocalOS "))
            next_step = paragraphs[-1]
            candidate = {
                "recipient": item["name"],
                "sender_mode": "localos",
                "channel": channel,
                "observed_fact": observed_fact,
                "bridge": pain_bridge,
                "localos_action": localos_action,
                "trust_statement": localos_action,
                "next_step": next_step,
                "evidence_status": "approved",
                "evidence_kind": "current_map_fact",
                "freshness": "current",
                "source_url": live["url"],
                "pain_hypothesis": pain_bridge,
                "problem_hypothesis_status": "segment_hypothesis_only",
            }
            quality = _quality_gate(
                text,
                candidate,
                None,
                channel=channel,
                channel_status="ready" if channel == "email" else "manual",
                suppressed=False,
                angle=angle,
            )
            touches.append({
                "sequence_index": index,
                "day_offset": (0, 7, 18)[index],
                "channel": channel,
                "recipient": recipient,
                "contact_point_id": contact_id,
                "subject": f"{item['name']} | ЛокалОС | Сотрудничество" if channel == "email" else None,
                "angle": angle,
                "source_url": live["url"],
                "source_observed_at": live["fetched_at"],
                "text": text,
                "human_language_review": language,
                "quality_gate": quality,
            })
        results.append({
            "party": "Партия 10",
            "name": item["name"],
            "segment": item["segment"],
            "lead_id": item["lead_id"],
            "workstream_id": item.get("workstream_id"),
            "source_url": live["url"],
            "live_facts": live,
            "audit_url": f"https://localos.pro/{item['audit_slug']}" if item.get("audit_active") else None,
            "touch_count": len(touches),
            "channels": [touch["channel"] for touch in touches],
            "classification": "content_ready" if all(
                t["human_language_review"]["passed"] and t["quality_gate"]["passed"]
                for t in touches
            ) else "revise",
            "touches": touches,
        })

    payload = {
        "schema_version": "localos_party10_offline_review_v2",
        "party": "Партия 10",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "selection_sha256": selection.get("canonical_sha256"),
        "chains": len(results),
        "touches": sum(len(item["touches"]) for item in results),
        "content_ready": sum(item["classification"] == "content_ready" for item in results),
        "revise": sum(item["classification"] == "revise" for item in results),
        "database_mutations": 0,
        "gmail_drafts": 0,
        "approved": 0,
        "queued": 0,
        "sent": 0,
        "results": results,
    }
    payload["canonical_sha256"] = canonical_sha(results)
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Партия 10 - цепочки на проверку",
        "",
        f"- Лидов: {payload['chains']}",
        f"- Касаний: {payload['touches']}",
        f"- Антинейрослоп PASS: {payload['content_ready']}",
        f"- Требуют правки: {payload['revise']}",
        "- Записей в LocalOS / Gmail / очередей / отправок: 0 / 0 / 0 / 0",
        "",
    ]
    for result in results:
        lines.extend((f"## {result['name']}", "", f"Маршрут: {' -> '.join(result['channels'])}", ""))
        if result.get("audit_url"):
            lines.extend((f"Аудит: {result['audit_url']}", ""))
        for touch in result["touches"]:
            heading = f"### Касание {touch['sequence_index'] + 1} - {touch['channel']}"
            lines.extend((heading, ""))
            if touch.get("subject"):
                lines.extend((f"Тема: {touch['subject']}", ""))
            lines.extend((touch["text"], ""))
    MARKDOWN.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({key: payload[key] for key in (
        "chains", "touches", "content_ready", "revise", "database_mutations", "gmail_drafts", "queued", "sent", "canonical_sha256"
    )}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
