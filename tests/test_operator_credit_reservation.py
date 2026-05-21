from services.operator_credit_reservation import (
    build_credit_finalization_plan,
    build_credit_reservation_plan,
    build_stale_reservation_recovery_plan,
    finalize_reserved_action_credits,
    release_stale_reserved_credits,
    reserve_paid_action_credits,
)


class FakeCursor:
    def __init__(self, *, table_available=True, balance=100, active_reserved=0, reservation=None, stale_candidates=None):
        self.table_available = table_available
        self.balance = balance
        self.active_reserved = active_reserved
        self.reservation = reservation
        self.stale_candidates = list(stale_candidates or [])
        self.last_query = ""
        self.last_params = ()
        self.inserted = []
        self.user_updates = []
        self.ledger_entries = []
        self.reservation_updates = []
        self.stale_release_updates = []

    def execute(self, query, params=None):
        self.last_query = " ".join(str(query or "").lower().split())
        self.last_params = params or ()
        if "insert into operatorcreditreservations" in self.last_query:
            self.inserted.append(params or ())
        if "update users" in self.last_query:
            self.user_updates.append(params or ())
        if "insert into credit_ledger" in self.last_query:
            self.ledger_entries.append(params or ())
        if "update operatorcreditreservations" in self.last_query:
            self.reservation_updates.append(params or ())
            if "status = 'released'" in self.last_query:
                self.stale_release_updates.append(params or ())

    def fetchone(self):
        query = self.last_query
        if "to_regclass" in query:
            if self.table_available:
                return {"to_regclass": "operatorcreditreservations"}
            return {"to_regclass": None}
        if "information_schema.columns" in query:
            return {"?column?": 1}
        if "from users" in query:
            return {"credits_balance": self.balance}
        if "from operatorcreditreservations" in query and "sum" in query:
            return {"reserved_credits": self.active_reserved}
        if "from operatorcreditreservations" in query:
            return self.reservation
        if "returning id" in query:
            params = self.inserted[-1]
            return {"id": params[0], "status": "reserved", "reserved_credits": params[6]}
        return None

    def fetchall(self):
        query = self.last_query
        if "from operatorcreditreservations" in query and "order by created_at" in query:
            return self.stale_candidates
        return []


def test_credit_reservation_plan_accounts_for_active_reservations() -> None:
    cursor = FakeCursor(balance=100, active_reserved=30)

    plan = build_credit_reservation_plan(
        cursor,
        business_id="biz-1",
        user_id="user-1",
        action_key="map_reviews_refresh",
        estimated_credits=50,
        idempotency_key="idem-1",
    )

    assert plan["status"] == "ready"
    assert plan["idempotency_key"] == "idem-1"
    assert plan["balance_credits"] == 100
    assert plan["active_reserved_credits"] == 30
    assert plan["available_after_reservations"] == 70
    assert plan["reservation_would_be_created"] is True
    assert plan["side_effects"]["credit_reserved"] is False


def test_credit_reservation_plan_blocks_when_unreserved_balance_is_low() -> None:
    cursor = FakeCursor(balance=100, active_reserved=95)

    plan = build_credit_reservation_plan(
        cursor,
        business_id="biz-1",
        user_id="user-1",
        action_key="map_reviews_refresh",
        estimated_credits=10,
    )

    assert plan["status"] == "blocked"
    assert "insufficient_unreserved_balance" in plan["blocked_reasons"]
    assert plan["reservation_would_be_created"] is False


def test_credit_reservation_plan_blocks_when_schema_is_unavailable() -> None:
    cursor = FakeCursor(table_available=False, balance=100)

    plan = build_credit_reservation_plan(
        cursor,
        business_id="biz-1",
        user_id="user-1",
        action_key="map_reviews_refresh",
        estimated_credits=10,
    )

    assert plan["status"] == "blocked"
    assert "reservation_ledger_unavailable" in plan["blocked_reasons"]


def test_reserve_paid_action_credits_records_reservation_when_ready() -> None:
    cursor = FakeCursor(balance=100, active_reserved=0)

    result = reserve_paid_action_credits(
        cursor,
        business_id="biz-1",
        user_id="user-1",
        action_key="map_reviews_refresh",
        estimated_credits=10,
        idempotency_key="idem-1",
    )

    assert result["status"] == "reserved"
    assert result["reserved_credits"] == 10
    assert result["side_effects"]["reservation_created"] is True
    assert result["side_effects"]["credit_reserved"] is True
    assert len(cursor.inserted) == 1


def test_finalization_plan_charges_actual_and_releases_unused() -> None:
    cursor = FakeCursor(
        reservation={
            "id": "res-1",
            "business_id": "biz-1",
            "user_id": "user-1",
            "action_key": "map_reviews_refresh",
            "status": "reserved",
            "reserved_credits": 10,
            "charged_credits": 0,
            "released_credits": 0,
        }
    )

    plan = build_credit_finalization_plan(
        cursor,
        reservation_id="res-1",
        business_id="biz-1",
        user_id="user-1",
        actual_credits=7,
    )

    assert plan["status"] == "ready"
    assert plan["charge_credits"] == 7
    assert plan["release_credits"] == 3
    assert plan["side_effects"]["credit_charged"] is False


def test_finalization_plan_can_release_full_reservation() -> None:
    cursor = FakeCursor(
        reservation={
            "id": "res-1",
            "business_id": "biz-1",
            "user_id": "user-1",
            "action_key": "map_reviews_refresh",
            "status": "reserved",
            "reserved_credits": 10,
            "charged_credits": 0,
            "released_credits": 0,
        }
    )

    plan = build_credit_finalization_plan(
        cursor,
        reservation_id="res-1",
        business_id="biz-1",
        user_id="user-1",
        finalization_mode="release",
    )

    assert plan["status"] == "ready"
    assert plan["charge_credits"] == 0
    assert plan["release_credits"] == 10


def test_finalization_plan_blocks_actual_over_reserved() -> None:
    cursor = FakeCursor(
        reservation={
            "id": "res-1",
            "business_id": "biz-1",
            "user_id": "user-1",
            "action_key": "map_reviews_refresh",
            "status": "reserved",
            "reserved_credits": 10,
            "charged_credits": 0,
            "released_credits": 0,
        }
    )

    plan = build_credit_finalization_plan(
        cursor,
        reservation_id="res-1",
        business_id="biz-1",
        user_id="user-1",
        actual_credits=12,
    )

    assert plan["status"] == "blocked"
    assert "actual_exceeds_reserved" in plan["blocked_reasons"]


def test_finalization_plan_blocks_when_current_balance_is_low() -> None:
    cursor = FakeCursor(
        balance=5,
        reservation={
            "id": "res-1",
            "business_id": "biz-1",
            "user_id": "user-1",
            "action_key": "map_reviews_refresh",
            "status": "reserved",
            "reserved_credits": 10,
            "charged_credits": 0,
            "released_credits": 0,
        },
    )

    plan = build_credit_finalization_plan(
        cursor,
        reservation_id="res-1",
        business_id="biz-1",
        user_id="user-1",
        actual_credits=7,
    )

    assert plan["status"] == "blocked"
    assert "insufficient_balance_at_finalization" in plan["blocked_reasons"]


def test_finalization_plan_blocks_non_reserved_status() -> None:
    cursor = FakeCursor(
        reservation={
            "id": "res-1",
            "business_id": "biz-1",
            "user_id": "user-1",
            "action_key": "map_reviews_refresh",
            "status": "pending",
            "reserved_credits": 10,
            "charged_credits": 0,
            "released_credits": 0,
        }
    )

    plan = build_credit_finalization_plan(
        cursor,
        reservation_id="res-1",
        business_id="biz-1",
        user_id="user-1",
        actual_credits=7,
    )

    assert plan["status"] == "blocked"
    assert "reservation_not_reserved" in plan["blocked_reasons"]


def test_finalize_reserved_action_credits_creates_credit_ledger_and_updates_reservation() -> None:
    cursor = FakeCursor(
        reservation={
            "id": "res-1",
            "business_id": "biz-1",
            "user_id": "user-1",
            "action_key": "map_reviews_refresh",
            "status": "reserved",
            "reserved_credits": 10,
            "charged_credits": 0,
            "released_credits": 0,
        }
    )

    result = finalize_reserved_action_credits(
        cursor,
        reservation_id="res-1",
        business_id="biz-1",
        user_id="user-1",
        actual_credits=7,
    )

    assert result["status"] == "charged"
    assert result["side_effects"]["credit_charged"] is True
    assert result["side_effects"]["credit_released"] is True
    assert len(cursor.user_updates) == 1
    assert len(cursor.ledger_entries) == 1
    assert len(cursor.reservation_updates) == 1
    assert cursor.user_updates[0][0] == 7
    assert cursor.ledger_entries[0][2] == -7
    assert cursor.reservation_updates[0][0] == "charged"
    assert cursor.reservation_updates[0][1] == 7
    assert cursor.reservation_updates[0][2] == 3


def test_finalize_release_does_not_create_credit_ledger() -> None:
    cursor = FakeCursor(
        reservation={
            "id": "res-1",
            "business_id": "biz-1",
            "user_id": "user-1",
            "action_key": "map_reviews_refresh",
            "status": "reserved",
            "reserved_credits": 10,
            "charged_credits": 0,
            "released_credits": 0,
        }
    )

    result = finalize_reserved_action_credits(
        cursor,
        reservation_id="res-1",
        business_id="biz-1",
        user_id="user-1",
        finalization_mode="release",
    )

    assert result["status"] == "released"
    assert result["side_effects"]["credit_charged"] is False
    assert result["side_effects"]["credit_released"] is True
    assert len(cursor.user_updates) == 0
    assert len(cursor.ledger_entries) == 0
    assert len(cursor.reservation_updates) == 1


def test_stale_reservation_recovery_plan_lists_release_candidates() -> None:
    cursor = FakeCursor(
        stale_candidates=[
            {
                "id": "res-1",
                "business_id": "biz-1",
                "user_id": "user-1",
                "action_key": "map_reviews_refresh",
                "status": "reserved",
                "reserved_credits": 10,
                "charged_credits": 0,
                "released_credits": 3,
                "created_at": "2026-05-21 06:00:00",
                "updated_at": "2026-05-21 06:00:00",
            },
            {
                "id": "res-2",
                "business_id": "biz-1",
                "user_id": "user-1",
                "action_key": "review_replies_generate",
                "status": "reserved",
                "reserved_credits": 4,
                "charged_credits": 0,
                "released_credits": 0,
                "created_at": "2026-05-21 06:05:00",
                "updated_at": "2026-05-21 06:05:00",
            },
        ]
    )

    plan = build_stale_reservation_recovery_plan(
        cursor,
        older_than_minutes=60,
        limit=10,
        business_id="biz-1",
    )

    assert plan["status"] == "ready"
    assert plan["candidate_count"] == 2
    assert plan["release_credits"] == 11
    assert plan["side_effects"]["reservations_released"] is False
    assert cursor.last_params == (60, "biz-1", 10)


def test_stale_reservation_recovery_plan_blocks_invalid_inputs() -> None:
    cursor = FakeCursor()

    plan = build_stale_reservation_recovery_plan(
        cursor,
        older_than_minutes=0,
        limit="bad",
    )

    assert plan["status"] == "blocked"
    assert "invalid_stale_window" in plan["blocked_reasons"]
    assert "invalid_limit" in plan["blocked_reasons"]


def test_release_stale_reserved_credits_updates_candidates_without_ledger() -> None:
    cursor = FakeCursor(
        stale_candidates=[
            {
                "id": "res-1",
                "business_id": "biz-1",
                "user_id": "user-1",
                "action_key": "map_reviews_refresh",
                "status": "reserved",
                "reserved_credits": 10,
                "charged_credits": 0,
                "released_credits": 3,
            },
            {
                "id": "res-2",
                "business_id": "biz-1",
                "user_id": "user-1",
                "action_key": "review_replies_generate",
                "status": "reserved",
                "reserved_credits": 4,
                "charged_credits": 0,
                "released_credits": 0,
            },
        ]
    )

    result = release_stale_reserved_credits(
        cursor,
        older_than_minutes=60,
        limit=10,
        business_id="biz-1",
    )

    assert result["status"] == "released"
    assert result["released_count"] == 2
    assert result["released_credits"] == 11
    assert result["released_reservation_ids"] == ["res-1", "res-2"]
    assert result["side_effects"]["reservations_released"] is True
    assert result["side_effects"]["credit_charged"] is False
    assert result["side_effects"]["credit_ledger_entries_created"] is False
    assert len(cursor.stale_release_updates) == 2
    assert cursor.stale_release_updates[0] == (7, "res-1")
    assert cursor.stale_release_updates[1] == (4, "res-2")
