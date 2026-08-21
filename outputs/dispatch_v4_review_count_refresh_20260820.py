#!/usr/bin/env python3
"""Dispatch user-approved v4 first touches with review-count-only refreshes."""

from __future__ import annotations

import copy
import re
from datetime import datetime, timezone

from psycopg2.extras import Json

import dispatch_v4_email_queue_20260820 as dispatch


APPROVED_REVIEW_COUNTS = {
    "1470ea46-26a2-4701-b546-95b02d21139e": (82, 83),
    "eac7c297-8ed0-4446-8aeb-14607798d9d6": (213, 215),
    "8389acfd-6b2b-448a-a454-d0cf8adc4166": (96, 97),
    "b7be136f-dba9-4d60-82e1-43d1e9668a09": (798, 800),
    "dd69f3db-d450-4e5a-ac85-1b531ff5dbe5": (710, 725),
    "1b203376-7ac5-4933-a7f8-23d67b89fb5b": (209, 219),
    "f486494d-95dd-4455-996d-4214e45cb958": (93, 107),
    "6dedaefd-5f2b-4436-a5cc-ee5c2f889c78": (90, 91),
    "7380a904-bd90-4c1c-ac63-98aaaa3cbe03": (1194, 1204),
    "3260fa95-c4d4-4327-9990-7ec84ea5b081": (359, 361),
    "f5ce1642-1bb1-4f56-b9b1-14e0dbf8d751": (106, 108),
    "24f1921e-9d37-442e-bdf3-73cff9f8bd94": (1953, 1955),
    "8f33f548-4805-4970-8188-3929b6948d09": (1291, 1313),
}

original_manifest_rows = dispatch.manifest_rows
original_record_sent = dispatch.record_sent


def review_word(count: int) -> str:
    if count % 10 == 1 and count % 100 != 11:
        return "отзыв"
    if count % 10 in {2, 3, 4} and count % 100 not in {12, 13, 14}:
        return "отзыва"
    return "отзывов"


def refreshed_manifest_rows():
    rows, blocked_touch_ids = original_manifest_rows()
    refreshed = []
    for source_item in rows:
        touch_id = str(source_item.get("touch_id") or "")
        if touch_id not in APPROVED_REVIEW_COUNTS:
            continue
        old_count, new_count = APPROVED_REVIEW_COUNTS[touch_id]
        item = copy.deepcopy(source_item)
        old_pattern = re.compile(
            rf"опубликовано\s+{old_count}\s+отзыв(?:а|ов)?",
            flags=re.IGNORECASE,
        )
        replacement = f"опубликовано {new_count} {review_word(new_count)}"
        item["text"], replacements = old_pattern.subn(replacement, str(item.get("text") or ""), count=1)
        if replacements != 1:
            raise RuntimeError(f"approved_review_count_source_text_mismatch:{touch_id}")
        brief = copy.deepcopy(item.get("message_brief_json") or {})
        brief["observation"] = (
            f"В карточке {item.get('name')} на Яндекс Картах {replacement}."
        )
        brief["editorial_correction"] = {
            "type": "review_count_refresh",
            "old_count": old_count,
            "new_count": new_count,
            "authorized_at": "2026-08-20",
            "authorization": "explicit_user_approval",
        }
        item["message_brief_json"] = brief
        refreshed.append(item)
    if len(refreshed) != len(APPROVED_REVIEW_COUNTS):
        raise RuntimeError("approved_review_count_touch_set_incomplete")
    return refreshed, blocked_touch_ids


def record_refreshed_sent(cursor, runtime, item, delivery, source):
    original_record_sent(
        cursor,
        runtime,
        item,
        delivery,
        "v4_numeric_fact_refresh_user_authorized",
    )
    correction = (item.get("message_brief_json") or {}).get("editorial_correction") or {}
    cursor.execute(
        """
        UPDATE outreach_campaign_touches
        SET message_brief_json=%s,
            strategy_json=COALESCE(strategy_json, '{}'::jsonb) || %s,
            updated_at=%s
        WHERE id=%s
        """,
        (
            Json(item.get("message_brief_json") or {}),
            Json({"editorial_correction": correction}),
            datetime.now(timezone.utc),
            runtime.get("id"),
        ),
    )


dispatch.manifest_rows = refreshed_manifest_rows
dispatch.record_sent = record_refreshed_sent


if __name__ == "__main__":
    raise SystemExit(dispatch.main())
