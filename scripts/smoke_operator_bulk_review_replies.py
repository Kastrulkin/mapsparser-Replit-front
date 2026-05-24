#!/usr/bin/env python3
import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]


class FakeCursor:
    def __init__(self, *, balance=100):
        self.balance = balance
        self.reviews = [
            {
                "id": "review-1",
                "business_id": "biz-1",
                "source": "yandex",
                "external_review_id": "ext-1",
                "rating": 5,
                "author_name": "Клиент",
                "text": "Очень понравился сервис и массаж лица.",
                "published_at": "2026-05-23T10:00:00+00:00",
            },
            {
                "id": "review-2",
                "business_id": "biz-1",
                "source": "yandex",
                "external_review_id": "ext-2",
                "rating": 5,
                "author_name": "Клиент",
                "text": "Приятная команда, обязательно вернусь.",
                "published_at": "2026-05-23T11:00:00+00:00",
            },
        ]
        self.last_query = ""
        self.last_params = ()
        self.reservation = None
        self.current_reservation_lookup = False
        self.drafts = []
        self.ledger_entries = []
        self.user_updates = []
        self.reservation_updates = []

    def execute(self, query, params=None):
        self.last_query = " ".join(str(query or "").lower().split())
        self.last_params = params or ()
        self.current_reservation_lookup = "from operatorcreditreservations" in self.last_query and "where id =" in self.last_query
        if "insert into operatorcreditreservations" in self.last_query:
            self.reservation = {
                "id": params[0],
                "business_id": params[1],
                "user_id": params[2],
                "action_key": params[3],
                "idempotency_key": params[4],
                "status": "reserved",
                "estimated_credits": params[5],
                "reserved_credits": params[6],
                "charged_credits": 0,
                "released_credits": 0,
                "credit_ledger_id": None,
            }
        if "insert into reviewreplydrafts" in self.last_query:
            self.drafts.append(
                {
                    "id": params[0],
                    "business_id": params[1],
                    "review_id": params[2],
                    "user_id": params[3],
                    "source": params[4],
                    "rating": params[5],
                    "author_name": params[6],
                    "review_text": params[7],
                    "generated_text": params[8],
                    "status": "draft",
                }
            )
        if "update users" in self.last_query:
            self.user_updates.append(params or ())
        if "insert into credit_ledger" in self.last_query:
            self.ledger_entries.append(params or ())
        if "update operatorcreditreservations" in self.last_query:
            self.reservation_updates.append(params or ())
            if self.reservation:
                self.reservation["status"] = params[0] if params else self.reservation["status"]
                self.reservation["charged_credits"] = params[1] if len(params or ()) > 1 else 0
                self.reservation["released_credits"] = params[2] if len(params or ()) > 2 else 0

    def fetchone(self):
        query = self.last_query
        params = self.last_params
        if "information_schema.columns" in query:
            return {"?column?": 1}
        if "to_regclass" in query:
            table_ref = str(params[0] if params else "")
            if "externalbusinessreviews" in table_ref:
                return {"to_regclass": "externalbusinessreviews"}
            if "reviewreplydrafts" in table_ref:
                return {"to_regclass": "reviewreplydrafts"}
            if "operatorcreditreservations" in table_ref:
                return {"to_regclass": "operatorcreditreservations"}
            return {"table_ref": "operatorconsentpolicies"}
        if "from operatorconsentpolicies" in query:
            return {"mode": "ask_each_time"}
        if "from users" in query:
            return {"credits_balance": self.balance}
        if "from operatorcreditreservations" in query and "sum" in query:
            return {"reserved_credits": 0, "used_credits": 0}
        if self.current_reservation_lookup:
            return self.reservation
        if "returning id, status, reserved_credits" in query:
            return {
                "id": (self.reservation or {}).get("id"),
                "status": "reserved",
                "reserved_credits": (self.reservation or {}).get("reserved_credits"),
            }
        if "returning id, business_id, review_id" in query:
            return self.drafts[-1] if self.drafts else None
        return None

    def fetchall(self):
        if "from externalbusinessreviews" in self.last_query:
            return self.reviews
        return []


def fake_reply_generator(prompt: Any, *, business_id: str, user_id: str):
    return '{"reply": "Спасибо за отзыв. Нам очень приятно, что вы остались довольны. Будем рады видеть вас снова."}'


def main():
    if str(REPO_ROOT / "src") not in sys.path:
        sys.path.insert(0, str(REPO_ROOT / "src"))

    from services.operator_review_reply_bulk import generate_review_reply_drafts_for_unanswered_reviews

    cursor = FakeCursor(balance=100)
    result = generate_review_reply_drafts_for_unanswered_reviews(
        cursor,
        business_id="biz-1",
        user_id="user-1",
        limit=5,
        channel="smoke",
        reply_generator=fake_reply_generator,
    )

    failures = []
    if result.get("status") != "completed":
        failures.append(f"status={result.get('status')}")
    if len(result.get("drafts") or []) != 2:
        failures.append(f"draft_count={len(result.get('drafts') or [])}")
    if result.get("charged_credits") != 2:
        failures.append(f"charged_credits={result.get('charged_credits')}")
    if result.get("credit_charged") is not True:
        failures.append("credit_charged=false")
    if result.get("manual_publication_only") is not True:
        failures.append("manual_publication_only=false")
    if result.get("external_writes_performed") is not False:
        failures.append("external_writes_performed=true")
    if len(cursor.ledger_entries) != 1:
        failures.append(f"ledger_entries={len(cursor.ledger_entries)}")
    if len(cursor.drafts) != 2:
        failures.append(f"stored_drafts={len(cursor.drafts)}")

    output = {
        "success": not failures,
        "scenario": "operator_bulk_review_replies_paid_draft_path",
        "drafts": len(result.get("drafts") or []),
        "charged_credits": result.get("charged_credits"),
        "manual_publication_only": result.get("manual_publication_only"),
        "external_writes_performed": result.get("external_writes_performed"),
        "failures": failures,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
