from __future__ import annotations

from typing import Any


DISK_MANUAL_PUBLISH_MESSAGE = (
    "Видео хранится на Диске. Откройте оригинал и разместите материал вручную."
)


def disk_video_requires_manual_publish(cursor: Any, post: dict[str, Any]) -> bool:
    from services.disk_import_media import selected

    return bool(selected(cursor, post.get("business_id"), post.get("content_plan_item_id")))


def assert_supervised_publish_supported(cursor: Any, post: dict[str, Any]) -> None:
    if disk_video_requires_manual_publish(cursor, post):
        raise ValueError(
            "Видео с Диска размещается вручную. Откройте оригинал в материале контент-плана."
        )


def validate_content_rules(cursor: Any, post: dict[str, Any], user_id: str) -> None:
    from services.content_rules import validate
    from services.operator_social_post_generation import _default_social_post_generator

    try:
        validate(
            cursor,
            str(post["business_id"]),
            user_id,
            str(post.get("platform_text") or post.get("base_text") or ""),
            _default_social_post_generator,
        )
    except Exception:
        raise ValueError(
            "Публикация остановлена: текст не прошёл проверку актуальных правил бизнеса. "
            "Исправьте и подтвердите черновик заново."
        ) from None
