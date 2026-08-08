from pathlib import Path

from services.photo_analysis_quota import (
    finalize_network_photo_analysis_quota,
    get_network_photo_analysis_quota,
    reserve_network_photo_analysis_quota,
)


class QuotaCursor:
    def __init__(self, granted=100, consumed=0, reserved=0):
        self.quota = {
            "network_id": "network-1",
            "granted_analyses": granted,
            "consumed_analyses": consumed,
            "reserved_analyses": reserved,
        }
        self.reservation = None
        self.fetchone_value = None
        self.queries = []

    def execute(self, query, params=None):
        normalized = " ".join(str(query or "").lower().split())
        values = params or ()
        self.queries.append(normalized)
        self.fetchone_value = None
        if "join network_photo_analysis_quotas" in normalized:
            self.fetchone_value = dict(self.quota)
        elif "from network_photo_analysis_quota_reservations" in normalized:
            if self.reservation:
                self.fetchone_value = dict(self.reservation)
        elif "insert into network_photo_analysis_quota_reservations" in normalized:
            self.reservation = {
                "id": values[0],
                "network_id": values[1],
                "status": "reserved",
            }
        elif "update network_photo_analysis_quota_reservations" in normalized:
            if "set status = 'reserved'" in normalized:
                self.reservation["status"] = "reserved"
            else:
                self.reservation["status"] = values[0]
        elif "update network_photo_analysis_quotas" in normalized:
            if "reserved_analyses = reserved_analyses + 1" in normalized:
                self.quota["reserved_analyses"] += 1
                self.fetchone_value = dict(self.quota)
            else:
                self.quota["reserved_analyses"] = max(self.quota["reserved_analyses"] - 1, 0)
                self.quota["consumed_analyses"] += values[0]
        elif "from network_photo_analysis_quotas" in normalized:
            self.fetchone_value = dict(self.quota)

    def fetchone(self):
        return self.fetchone_value


def test_network_quota_reservation_is_atomic_and_idempotent():
    cursor = QuotaCursor()

    first = reserve_network_photo_analysis_quota(
        cursor,
        business_id="business-1",
        user_id="user-1",
        asset_id="asset-1",
        asset_version=1,
        idempotency_key="same-request",
    )
    second = reserve_network_photo_analysis_quota(
        cursor,
        business_id="business-1",
        user_id="user-1",
        asset_id="asset-1",
        asset_version=1,
        idempotency_key="same-request",
    )

    assert first["status"] == "reserved"
    assert second["status"] == "reserved"
    assert first["reservation_id"] == second["reservation_id"]
    assert cursor.quota["reserved_analyses"] == 1
    assert first["quota"]["remaining_analyses"] == 99
    assert any("for update of q" in query for query in cursor.queries)


def test_network_quota_consume_moves_one_reserved_analysis_to_consumed():
    cursor = QuotaCursor()
    reservation = reserve_network_photo_analysis_quota(
        cursor,
        business_id="business-1",
        user_id="user-1",
        asset_id="asset-1",
        asset_version=1,
        idempotency_key="consume-request",
    )

    quota = finalize_network_photo_analysis_quota(
        cursor,
        reservation_id=reservation["reservation_id"],
        mode="consume",
    )

    assert cursor.reservation["status"] == "consumed"
    assert quota["consumed_analyses"] == 1
    assert quota["reserved_analyses"] == 0
    assert quota["remaining_analyses"] == 99


def test_network_quota_release_restores_remaining_analysis():
    cursor = QuotaCursor()
    reservation = reserve_network_photo_analysis_quota(
        cursor,
        business_id="business-1",
        user_id="user-1",
        asset_id="asset-1",
        asset_version=1,
        idempotency_key="release-request",
    )

    quota = finalize_network_photo_analysis_quota(
        cursor,
        reservation_id=reservation["reservation_id"],
        mode="release",
    )

    assert cursor.reservation["status"] == "released"
    assert quota["consumed_analyses"] == 0
    assert quota["reserved_analyses"] == 0
    assert quota["remaining_analyses"] == 100


def test_exhausted_network_quota_does_not_create_reservation():
    cursor = QuotaCursor(granted=100, consumed=100)

    result = reserve_network_photo_analysis_quota(
        cursor,
        business_id="business-1",
        user_id="user-1",
        asset_id="asset-1",
        asset_version=1,
        idempotency_key="exhausted-request",
    )

    assert result["status"] == "exhausted"
    assert result["quota"]["remaining_analyses"] == 0
    assert cursor.reservation is None


def test_quota_migration_has_count_guard_and_unique_idempotency_key():
    migration = Path("alembic_migrations/versions/20260808_add_network_photo_analysis_quotas.py").read_text()

    assert "consumed_analyses + reserved_analyses <= granted_analyses" in migration
    assert "UNIQUE (network_id, idempotency_key)" in migration


def test_quota_read_is_network_scoped():
    cursor = QuotaCursor(granted=100, consumed=7, reserved=2)

    quota = get_network_photo_analysis_quota(cursor, "business-1")

    assert quota["network_id"] == "network-1"
    assert quota["remaining_analyses"] == 91
