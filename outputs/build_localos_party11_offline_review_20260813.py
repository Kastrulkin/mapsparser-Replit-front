#!/usr/bin/env python3
"""Build Party 11 review copy from current public Yandex facts, without writes."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path


REPO_OUTPUTS = Path(__file__).resolve().parent
BASE = REPO_OUTPUTS / "build_localos_party10_offline_review_20260813.py"
ROOT = Path("/Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Obsidian/Obsidian Vault/outputs")


def load_base():
    spec = importlib.util.spec_from_file_location("party10_builder", BASE)
    if spec is None or spec.loader is None:
        raise RuntimeError("party10_builder_import_failed")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> None:
    base = load_base()
    base.SELECTION = ROOT / "localos-party11-medical-beauty-20260813.json"
    base.LIVE = ROOT / "localos-party11-live-yandex-20260813.json"
    base.OUTPUT = ROOT / "localos-party11-review-v1-20260813.json"
    base.MARKDOWN = ROOT / "localos-party11-review-v1-20260813.md"
    base_second_touch = base.second_touch

    def first_touch(item, live, channel):
        name = item["name"]
        has_news = bool(live.get("news_module_present")) and int(live.get("news_count") or 0) > 0
        start = base.greeting(channel)
        audit = base.audit_paragraph(item)
        if has_news:
            body = (
                f"{start}\n\nВижу, вы ведёте карточку {name} на Яндекс Картах и публикуете новости.\n\n"
                "Часто на посты не хватает времени: надо собраться и написать пост, одну тему приходится "
                "переделывать для каждой площадки. Публикации помогают рассказывать об услугах и "
                "привлекать клиентов онлайн.\n\n"
                "LocalOS составит контент-план и подготовит тексты для Telegram, VK и Яндекс Карт. "
                "Сотруднику останется подтвердить и опубликовать их."
                f"{audit}\n\nПодготовить пример контент-плана на неделю?"
            )
            angle = "active_map_news"
        else:
            body = (
                f"{start}\n\nВ карточке {name} на Яндекс Картах нет новостей.\n\n"
                "Возможно, на публикации просто не хватает времени: надо собраться и написать пост, "
                "одну тему приходится переделывать для каждой площадки. Публикации помогают рассказывать "
                "об услугах и привлекать клиентов онлайн.\n\n"
                "LocalOS составит контент-план и подготовит тексты для Telegram, VK и Яндекс Карт. "
                "Сотруднику останется подтвердить и опубликовать их."
                f"{audit}\n\nПодготовить пример контент-плана на неделю?"
            )
            angle = "map_content_gap"
        return body + base.signature(channel), angle

    def second_touch(item, live, channel):
        name = item["name"]
        visible = int(live.get("visible_service_count") or 0)
        priced = int(live.get("visible_service_priced_count") or 0)
        if visible >= 3:
            if priced == visible:
                fact = (
                    f"В карточке {name} на Яндекс Картах видны {visible} "
                    f"{base.counted_word(visible, 'услуга', 'услуги', 'услуг')}, и у каждой указана цена."
                )
            else:
                fact = (
                    f"В карточке {name} на Яндекс Картах видны {visible} "
                    f"{base.counted_word(visible, 'услуга', 'услуги', 'услуг')}, но цена указана у {priced}."
                )
            body = (
                f"{base.greeting(channel)}\n\n{fact}\n\n"
                "Владельцы часто говорят: работы много, а средний чек всё равно маленький. "
                "Не знаю, актуально ли это для вас.\n\n"
                "LocalOS по вашему прайсу соберёт матрицу услуг и допродаж, подготовит подсказки "
                "для администратора и поможет отследить результат.\n\n"
                "Вам было бы интересно увеличить средний чек?"
            )
            return body + base.signature(channel), "average_ticket"
        return base_second_touch(item, live, channel)

    live_by_id = {
        item["lead_id"]: item
        for item in json.loads(base.LIVE.read_text(encoding="utf-8"))["results"]
    }
    base.first_touch = first_touch
    base.second_touch = second_touch
    base.main()

    payload = json.loads(base.OUTPUT.read_text(encoding="utf-8"))
    payload["schema_version"] = "localos_party11_offline_review_v1"
    payload["party"] = "Партия 11"
    payload["canonical_sha256"] = base.canonical_sha(payload["results"])
    base.OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown = base.MARKDOWN.read_text(encoding="utf-8").replace(
        "# Партия 10 - цепочки на проверку",
        "# Партия 11 - цепочки на проверку",
        1,
    )
    base.MARKDOWN.write_text(markdown, encoding="utf-8")


if __name__ == "__main__":
    main()
