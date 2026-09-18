"""Durable social publication claim, provider exclusion and finalization."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import sys
from typing import Any

from database_manager import DatabaseManager


def _publish_attempt_fingerprint(post: dict[str, Any]) -> str:
    payload = {
        "platform": str(post.get("platform") or "").strip(),
        "target": str(post.get("business_id") or "").strip(),
        "text": str(post.get("platform_text") or post.get("base_text") or "").strip(),
    }
    return hashlib.sha256(_json_dumps(payload).encode("utf-8")).hexdigest()


def _publish_outcome(result: dict[str, Any]) -> str:
    outcome = str(result.get("publish_outcome") or "").strip()
    if outcome not in {"accepted", "not_attempted", "rejected", "uncertain"}:
        return "uncertain"
    if outcome == "accepted" and not (
        str(result.get("provider_post_id") or "").strip()
        or str(result.get("provider_post_url") or "").strip()
    ):
        return "uncertain"
    return outcome


def _publish_claim_conflict(cursor: Any, user_id: str, post_id: str) -> dict[str, Any]:
    current = _load_post_for_user(cursor, user_id, post_id)
    if str(current.get("status") or "").strip() == "publishing":
        current["next_action"] = "reconcile_publication"
    return current


def _publish_advisory_key(post_id: str) -> str:
    return f"social-publish:{str(post_id or '').strip()}"


def _advisory_lock_granted(row: Any) -> bool:
    if hasattr(row, "keys"):
        return bool(row.get("pg_try_advisory_lock") or row.get("pg_try_advisory_xact_lock"))
    return bool(row[0]) if row else False


def _claim_social_post_publish(user_id: str, post_id: str) -> dict[str, Any]:
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        ensure_social_post_tables(cursor)
        post = _load_post_for_write(cursor, user_id, post_id)
        current_status = str(post.get("status") or "").strip()
        if current_status == "published":
            return post
        if current_status == "publishing":
            post["next_action"] = "reconcile_publication"
            post["_publish_attempt_claimed_now"] = False
            return post
        if current_status not in {"approved", "queued"} or not post.get("approved_at") or not post.get("approval_id"):
            raise PermissionError("Перед внешней публикацией нужно подтверждение человека")
        if not _social_post_has_text(post):
            cursor.execute(
                """
                UPDATE social_posts
                SET status = 'needs_review',
                    approved_at = NULL,
                    approval_id = NULL,
                    last_error = %s,
                    updated_at = NOW()
                WHERE id = %s
                  AND status = %s
                  AND approved_at IS NOT NULL
                  AND approval_id = %s
                RETURNING *
                """,
                (
                    "Перед публикацией нужно заполнить текст и заново подтвердить preview",
                    post_id,
                    current_status,
                    str(post.get("approval_id") or "").strip(),
                ),
            )
            updated = _serialize_social_post(cursor, cursor.fetchone())
            if not updated:
                db.conn.rollback()
                return _publish_claim_conflict(cursor, user_id, post_id)
            db.conn.commit()
            return updated
        from services.social_posts.publish_guard import DISK_MANUAL_PUBLISH_MESSAGE, disk_video_requires_manual_publish, validate_content_rules
        if disk_video_requires_manual_publish(cursor, post):
            cursor.execute(
                "UPDATE social_posts SET status='needs_manual_publish',last_error=%s,updated_at=NOW() WHERE id=%s AND status=%s AND approved_at IS NOT NULL AND approval_id=%s RETURNING *",
                (
                    DISK_MANUAL_PUBLISH_MESSAGE,
                    post_id,
                    current_status,
                    str(post.get("approval_id") or "").strip(),
                ),
            )
            updated = _serialize_social_post(cursor, cursor.fetchone())
            if not updated:
                db.conn.rollback()
                return _publish_claim_conflict(cursor, user_id, post_id)
            db.conn.commit()
            return updated
        validate_content_rules(cursor, post, user_id)
        platform = str(post.get("platform") or "").strip()
        publish_mode = str(post.get("publish_mode") or "").strip()
        metadata = _json_dict(post.get("metadata_json"))
        if platform in BROWSER_OR_MANUAL_PLATFORMS:
            updated = _create_supervised_publish_task(cursor, post)
            db.conn.commit()
            return updated
        if publish_mode != "api":
            cursor.execute(
                """
                UPDATE social_posts
                SET status = 'needs_manual_publish',
                    last_error = %s,
                    updated_at = NOW()
                WHERE id = %s
                  AND status = %s
                  AND approved_at IS NOT NULL
                  AND approval_id = %s
                RETURNING *
                """,
                (
                    "Для канала не настроен API-адаптер",
                    post_id,
                    current_status,
                    str(post.get("approval_id") or "").strip(),
                ),
            )
            updated = _serialize_social_post(cursor, cursor.fetchone())
            if not updated:
                db.conn.rollback()
                return _publish_claim_conflict(cursor, user_id, post_id)
            db.conn.commit()
            return updated
        attempt_id = _new_id()
        metadata["publish_attempt"] = {
            "id": attempt_id,
            "state": "intent_committed",
            "actor_id": str(user_id or "").strip(),
            "approval_id": str(post.get("approval_id") or "").strip(),
            "content_business_fingerprint": _publish_attempt_fingerprint(post),
            "intent_committed_at": datetime.now(timezone.utc).isoformat(),
            "source": "social_post_publish",
        }
        cursor.execute(
            """
            UPDATE social_posts
            SET status = 'publishing',
                metadata_json = %s,
                last_error = NULL,
                updated_at = NOW()
            WHERE id = %s
              AND status IN ('approved', 'queued')
              AND approved_at IS NOT NULL
              AND approval_id = %s
              AND NULLIF(BTRIM(COALESCE(provider_post_id, '')), '') IS NULL
              AND NULLIF(BTRIM(COALESCE(provider_post_url, '')), '') IS NULL
            RETURNING *
            """,
            (_json_dumps(metadata), post_id, str(post.get("approval_id") or "").strip()),
        )
        claimed = _serialize_social_post(cursor, cursor.fetchone())
        if not claimed:
            db.conn.rollback()
            return _publish_claim_conflict(cursor, user_id, post_id)
        db.conn.commit()
        claimed["_publish_attempt_claimed_now"] = True
        return claimed
    except Exception:
        db.conn.rollback()
        raise sys.exc_info()[1]
    finally:
        db.close()


def _finalize_social_post_publish(user_id: str, post_id: str, attempt_id: str, publish_result: dict[str, Any]) -> dict[str, Any]:
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        post = _load_post_for_user(cursor, user_id, post_id)
        metadata = _json_dict(post.get("metadata_json"))
        attempt = _json_dict(metadata.get("publish_attempt"))
        if str(post.get("status") or "") != "publishing" or str(attempt.get("id") or "") != attempt_id:
            return post
        if str(attempt.get("approval_id") or "") != str(post.get("approval_id") or ""):
            return post
        if str(attempt.get("content_business_fingerprint") or "") != _publish_attempt_fingerprint(post):
            return post
        outcome = _publish_outcome(publish_result)
        attempt["state"] = outcome
        attempt["provider_outcome"] = outcome
        metadata["publish_attempt"] = attempt
        metadata.update(_json_dict(publish_result.get("metadata_json")))
        if outcome == "accepted":
            next_status = "published"
            published_at = datetime.now(timezone.utc)
            attempt["accepted_at"] = published_at.isoformat()
            attempt["receipt"] = {
                "provider_post_id": str(publish_result.get("provider_post_id") or "").strip(),
                "provider_post_url": str(publish_result.get("provider_post_url") or "").strip(),
            }
        elif outcome in {"rejected", "not_attempted"}:
            next_status = str(publish_result.get("status") or "failed")
            if next_status not in {"failed", "needs_manual_publish"}:
                next_status = "failed"
            published_at = None
        else:
            next_status = "publishing"
            published_at = None
            attempt["uncertain_at"] = datetime.now(timezone.utc).isoformat()
            metadata["publish_attempt"] = attempt
        cursor.execute(
            """
            UPDATE social_posts
            SET status = %s,
                published_at = COALESCE(published_at, %s),
                provider_post_id = COALESCE(NULLIF(%s, ''), provider_post_id),
                provider_post_url = COALESCE(NULLIF(%s, ''), provider_post_url),
                metadata_json = %s,
                last_error = %s,
                updated_at = NOW()
            WHERE id = %s
              AND status = 'publishing'
              AND metadata_json -> 'publish_attempt' ->> 'id' = %s
            RETURNING *
            """,
            (
                next_status,
                published_at,
                str(publish_result.get("provider_post_id") or "").strip() if outcome == "accepted" else "",
                str(publish_result.get("provider_post_url") or "").strip() if outcome == "accepted" else "",
                _json_dumps(metadata),
                str(publish_result.get("last_error") or "").strip() or None,
                post_id,
                attempt_id,
            ),
        )
        updated = _serialize_social_post(cursor, cursor.fetchone())
        if not updated:
            db.conn.rollback()
            current = _load_post_for_user(cursor, user_id, post_id)
            if str(current.get("status") or "").strip() == "publishing":
                current["next_action"] = "reconcile_publication"
            return current
        if outcome == "accepted":
            _record_knowledge_publish_event(cursor, updated, user_id, "provider_api")
        db.conn.commit()
        return updated
    except Exception:
        db.conn.rollback()
        raise sys.exc_info()[1]
    finally:
        db.close()


def publish_social_post(user_id: str, post_id: str) -> dict[str, Any]:
    claimed = _claim_social_post_publish(user_id, post_id)
    if str(claimed.get("status") or "") != "publishing":
        return claimed
    if claimed.get("_publish_attempt_claimed_now") is not True:
        claimed["next_action"] = "reconcile_publication"
        return claimed
    metadata = _json_dict(claimed.get("metadata_json"))
    attempt = _json_dict(metadata.get("publish_attempt"))
    attempt_id = str(attempt.get("id") or "").strip()
    if str(attempt.get("state") or "") != "intent_committed" or not attempt_id:
        claimed["next_action"] = "reconcile_publication"
        return claimed
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        db.conn.set_session(autocommit=True)
        advisory_key = _publish_advisory_key(post_id)
        cursor.execute("SELECT pg_try_advisory_lock(hashtextextended(%s, 0))", (advisory_key,))
        if not _advisory_lock_granted(cursor.fetchone()):
            current = _load_post_for_user(cursor, user_id, post_id)
            if str(current.get("status") or "").strip() == "publishing":
                current["next_action"] = "reconcile_publication"
            return current
        current = _load_post_for_user(cursor, user_id, post_id)
        current_metadata = _json_dict(current.get("metadata_json"))
        current_attempt = _json_dict(current_metadata.get("publish_attempt"))
        if (
            str(current.get("status") or "").strip() != "publishing"
            or str(current_attempt.get("id") or "").strip() != attempt_id
            or str(current_attempt.get("state") or "").strip() != "intent_committed"
            or str(current_attempt.get("approval_id") or "").strip() != str(current.get("approval_id") or "").strip()
            or str(current_attempt.get("content_business_fingerprint") or "") != _publish_attempt_fingerprint(current)
        ):
            if str(current.get("status") or "").strip() == "publishing":
                current["next_action"] = "reconcile_publication"
            return current
        try:
            publish_result = _publish_api_post(cursor, current)
        except Exception:
            publish_result = {"publish_outcome": "uncertain", "metadata_json": {"provider_status": "publish_exception"}}
        return _finalize_social_post_publish(user_id, post_id, attempt_id, publish_result)
    finally:
        try:
            cursor.execute("SELECT pg_advisory_unlock(hashtextextended(%s, 0))", (_publish_advisory_key(post_id),))
        except Exception:
            pass
        db.close()
