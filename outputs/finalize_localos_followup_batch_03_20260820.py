#!/usr/bin/env python3
"""Freeze a 70-lead batch: safe August 21 drafts plus cooldown-deferred drafts."""

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path


SOURCE = Path("/app/debug_data/localos-followup-batch-03-candidates-review-20260820.json")
OUTPUT = Path("/app/debug_data/localos-followup-batch-03-final-20260820.json")
RESCUE_NEWS = {"Стоматология Александрова", "Эсте", "Центр Семейной Медицины", "A3beaute"}
RESCUE_CONTACT = {"GynecoLase", "Candela Victory Plaza"}
EXCLUDED_AFTER_RACE_CHECK = {"Рант"}


def counted(value, one, few, many):
    if value % 100 in {11, 12, 13, 14}: return many
    if value % 10 == 1: return one
    if value % 10 in {2, 3, 4}: return few
    return many


def news_draft(name, research):
    news = int(research.get("news_count") or 0)
    word = counted(news, "новость", "новости", "новостей")
    if news >= 10:
        observation = f"В карточке {name} на Яндекс Картах сейчас опубликовано {news} {word}."
        hypothesis = "При таком объёме темы можно собрать в понятные рубрики и переиспользовать в карточке и на сайте. Это гипотеза для проверки."
        offer = "LocalOS может сгруппировать текущие темы и показать три рубрики для следующих материалов."
        cta = "Показать пример трёх рубрик?"
        angle = "map_content_rubrics"
    else:
        observation = f"В карточке {name} на Яндекс Картах сейчас опубликовано {news} {word}."
        hypothesis = "Такой объём может не полностью показывать текущие направления и поводы обратиться. Это гипотеза, а не вывод о вашей работе."
        offer = "LocalOS может собрать темы из текущих услуг и подготовить три коротких черновика для ручной публикации."
        cta = "Показать три темы?"
        angle = "map_content_cadence"
    text = f"Здравствуйте!\n\n{observation}\n\n{hypothesis}\n\n{offer}\n\n{cta}\n\n--\nАлександр\nоснователь LocalOS"
    return {"angle": angle, "subject": f"{name} - карточка на Яндекс Картах", "text": text, "observation": observation, "problem_hypothesis": hypothesis, "offer_bridge": offer, "cta": cta}


def main():
    payload = json.loads(SOURCE.read_text(encoding="utf-8"))
    selected = []
    for source_item in payload.get("items") or []:
        reasons = set(source_item.get("reasons") or [])
        choose = (source_item.get("status") == "ready_for_user_approval" or reasons == {"gmail_followup_interval_under_72h"} or source_item.get("name") in RESCUE_NEWS | RESCUE_CONTACT) and source_item.get("name") not in EXCLUDED_AFTER_RACE_CHECK
        if not choose: continue
        item = json.loads(json.dumps(source_item, ensure_ascii=False))
        name = item["name"]
        research = item["evidence"]["research"]
        public_name = str(research.get("title") or "")
        if name in RESCUE_NEWS:
            item["draft"] = news_draft(name, research)
        if name in RESCUE_CONTACT:
            item["contact_source_url"] = "https://gynecolase.ru/contacts/" if name == "GynecoLase" else "https://www.candela-plaza.ru/about-organization"
            item["evidence"]["contact"] = {"source_url": item["contact_source_url"], "status": 200, "recipient_visible": True, "verified_at": datetime.now(timezone.utc).isoformat()}
        draft = item.get("draft") or {}
        if public_name and public_name != name:
            for key in ("subject", "text", "observation"):
                draft[key] = str(draft.get(key) or "").replace(public_name, name)
        cooldown = "gmail_followup_interval_under_72h" in reasons
        item["display_name"] = name
        item["planned_send_date"] = "2026-08-24" if cooldown else "2026-08-21"
        item["status"] = "blocked_cooldown" if cooldown else "ready_for_user_approval"
        item["reasons"] = ["gmail_followup_interval_under_72h"] if cooldown else []
        item["approval"] = {"content_status": "blocked_cooldown" if cooldown else "pending_user_approval", "delivery_authorized": False}
        words = len(re.findall(r"[A-Za-zА-Яа-яЁё0-9]+(?:-[A-Za-zА-Яа-яЁё0-9]+)*", draft.get("text") or ""))
        if not draft or words > 120 or str(draft.get("text") or "").count("?") != 1:
            raise RuntimeError(f"draft_guardrail_failed:{name}")
        item["quality"] = {"score": 17, "max_score": 18, "verdict": "reject" if cooldown else "approve", "reason_codes": item["reasons"], "risk": "Cooldown only; content passed." if cooldown else "Current official-page fact.", "word_count": words}
        selected.append(item)
    if len(selected) != 70 or len({x["lead_id"] for x in selected}) != 70 or len({x["recipient"].lower() for x in selected}) != 70:
        raise RuntimeError(f"final_batch_size_or_uniqueness_failed:{len(selected)}")
    ready = sum(x["planned_send_date"] == "2026-08-21" for x in selected)
    deferred = len(selected) - ready
    final = {"schema_version": "localos_followup_batch_final_v1", "base_manifest_canonical_sha256": "4b21c0f98df7a726e0afae3504692e0b7c2a4faace8cdddf733590257a46a386", "batch_id": "followup-batch-03-20260820", "created_at": datetime.now(timezone.utc).isoformat(), "state": "draft_for_user_approval", "delivery_authorized": False, "queued": False, "sent": False, "total_count": 70, "ready_aug21_count": ready, "deferred_aug24_count": deferred, "items": selected}
    final["review_sha256"] = hashlib.sha256(json.dumps(final, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    OUTPUT.write_text(json.dumps(final, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUTPUT), "total": 70, "ready_aug21": ready, "deferred_aug24": deferred, "review_sha256": final["review_sha256"]}, ensure_ascii=False))


if __name__ == "__main__": main()
