#!/usr/bin/env python3
import importlib.util
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TEST_FIXTURE_PATH = REPO_ROOT / "tests" / "test_operator_review_reply_bulk.py"


def load_fixture_module():
    spec = importlib.util.spec_from_file_location("operator_review_reply_bulk_fixture", TEST_FIXTURE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load fixture module from {TEST_FIXTURE_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    if str(REPO_ROOT / "src") not in sys.path:
        sys.path.insert(0, str(REPO_ROOT / "src"))

    fixture = load_fixture_module()
    cursor = fixture.FakeCursor(balance=100)
    result = fixture.generate_review_reply_drafts_for_unanswered_reviews(
        cursor,
        business_id="biz-1",
        user_id="user-1",
        limit=5,
        channel="smoke",
        reply_generator=fixture.fake_reply_generator,
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
