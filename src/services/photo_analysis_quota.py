from __future__ import annotations

import uuid
from typing import Any


PHOTO_ANALYSIS_QUOTA_SOURCE = "network_photo_quota"


def _row_to_dict(cursor: Any, row: Any) -> dict[str, Any] | None:
    if row is None:
        return None
    if isinstance(row, dict):
        return dict(row)
    if hasattr(row, "keys"):
        try:
            return dict(row)
        except Exception:
            pass
    columns = [column[0] for column in (getattr(cursor, "description", None) or [])]
    if isinstance(row, (list, tuple)) and columns:
        return {columns[index]: row[index] for index in range(min(len(columns), len(row)))}
    return None


def _quota_payload(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if not row:
        return None
    granted = max(int(row.get("granted_analyses") or 0), 0)
    consumed = max(int(row.get("consumed_analyses") or 0), 0)
    reserved = max(int(row.get("reserved_analyses") or 0), 0)
    return {
        "source": PHOTO_ANALYSIS_QUOTA_SOURCE,
        "network_id": str(row.get("network_id") or ""),
        "granted_analyses": granted,
        "consumed_analyses": consumed,
        "reserved_analyses": reserved,
        "remaining_analyses": max(granted - consumed - reserved, 0),
    }


def get_network_photo_analysis_quota(cursor: Any, business_id: str) -> dict[str, Any] | None:
    cursor.execute(
        """
        SELECT q.network_id, q.granted_analyses, q.consumed_analyses, q.reserved_analyses
        FROM businesses b
        JOIN network_photo_analysis_quotas q ON q.network_id = b.network_id
        WHERE b.id = %s
        LIMIT 1
        """,
        (business_id,),
    )
    return _quota_payload(_row_to_dict(cursor, cursor.fetchone()))


def reserve_network_photo_analysis_quota(
    cursor: Any,
    *,
    business_id: str,
    user_id: str,
    asset_id: str,
    asset_version: int,
    idempotency_key: str,
) -> dict[str, Any]:
    cursor.execute(
        """
        SELECT q.network_id, q.granted_analyses, q.consumed_analyses, q.reserved_analyses
        FROM businesses b
        JOIN network_photo_analysis_quotas q ON q.network_id = b.network_id
        WHERE b.id = %s
        LIMIT 1
        FOR UPDATE OF q
        """,
        (business_id,),
    )
    quota_row = _row_to_dict(cursor, cursor.fetchone())
    if not quota_row:
        return {"status": "not_configured", "quota": None}

    network_id = str(quota_row.get("network_id") or "")
    cursor.execute(
        """
        SELECT id, status
        FROM network_photo_analysis_quota_reservations
        WHERE network_id = %s AND idempotency_key = %s
        LIMIT 1
        FOR UPDATE
        """,
        (network_id, idempotency_key),
    )
    existing = _row_to_dict(cursor, cursor.fetchone())
    if existing and str(existing.get("status") or "") in {"reserved", "consumed"}:
        return {
            "status": str(existing.get("status")),
            "reservation_id": str(existing.get("id") or ""),
            "quota": _quota_payload(quota_row),
        }

    quota = _quota_payload(quota_row) or {}
    if int(quota.get("remaining_analyses") or 0) <= 0:
        return {"status": "exhausted", "quota": quota}

    reservation_id = str(existing.get("id") or "") if existing else str(uuid.uuid4())
    if existing:
        cursor.execute(
            """
            UPDATE network_photo_analysis_quota_reservations
            SET status = 'reserved', user_id = %s, business_id = %s, asset_id = %s,
                asset_version = %s, released_at = NULL, updated_at = NOW()
            WHERE id = %s
            """,
            (user_id, business_id, asset_id, asset_version, reservation_id),
        )
    else:
        cursor.execute(
            """
            INSERT INTO network_photo_analysis_quota_reservations (
                id, network_id, business_id, user_id, asset_id, asset_version,
                idempotency_key, status, created_at, updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'reserved', NOW(), NOW())
            """,
            (reservation_id, network_id, business_id, user_id, asset_id, asset_version, idempotency_key),
        )
    cursor.execute(
        """
        UPDATE network_photo_analysis_quotas
        SET reserved_analyses = reserved_analyses + 1, updated_at = NOW()
        WHERE network_id = %s
        RETURNING network_id, granted_analyses, consumed_analyses, reserved_analyses
        """,
        (network_id,),
    )
    updated_quota = _row_to_dict(cursor, cursor.fetchone())
    return {
        "status": "reserved",
        "reservation_id": reservation_id,
        "quota": _quota_payload(updated_quota),
    }


def finalize_network_photo_analysis_quota(
    cursor: Any,
    *,
    reservation_id: str,
    mode: str,
) -> dict[str, Any] | None:
    if not reservation_id or mode not in {"consume", "release"}:
        return None
    cursor.execute(
        """
        SELECT id, network_id, status
        FROM network_photo_analysis_quota_reservations
        WHERE id = %s
        LIMIT 1
        """,
        (reservation_id,),
    )
    reservation = _row_to_dict(cursor, cursor.fetchone())
    if not reservation:
        return None
    network_id = str(reservation.get("network_id") or "")
    cursor.execute(
        """
        SELECT network_id
        FROM network_photo_analysis_quotas
        WHERE network_id = %s
        FOR UPDATE
        """,
        (network_id,),
    )
    cursor.fetchone()
    cursor.execute(
        """
        SELECT id, network_id, status
        FROM network_photo_analysis_quota_reservations
        WHERE id = %s
        LIMIT 1
        FOR UPDATE
        """,
        (reservation_id,),
    )
    reservation = _row_to_dict(cursor, cursor.fetchone())
    if not reservation:
        return None
    status = str(reservation.get("status") or "")
    if status == "reserved":
        next_status = "consumed" if mode == "consume" else "released"
        timestamp_column = "consumed_at" if mode == "consume" else "released_at"
        cursor.execute(
            f"""
            UPDATE network_photo_analysis_quota_reservations
            SET status = %s, {timestamp_column} = NOW(), updated_at = NOW()
            WHERE id = %s
            """,
            (next_status, reservation_id),
        )
        cursor.execute(
            """
            UPDATE network_photo_analysis_quotas
            SET reserved_analyses = GREATEST(reserved_analyses - 1, 0),
                consumed_analyses = consumed_analyses + %s,
                updated_at = NOW()
            WHERE network_id = %s
            """,
            (1 if mode == "consume" else 0, network_id),
        )
    cursor.execute(
        """
        SELECT network_id, granted_analyses, consumed_analyses, reserved_analyses
        FROM network_photo_analysis_quotas
        WHERE network_id = %s
        LIMIT 1
        """,
        (network_id,),
    )
    return _quota_payload(_row_to_dict(cursor, cursor.fetchone()))
