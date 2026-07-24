from datetime import datetime, timezone

from api.operator_api import _normalize_finance_transaction_date


def test_finance_recognition_normalizes_common_russian_dates():
    assert _normalize_finance_transaction_date("24.07.2026") == "2026-07-24"
    assert _normalize_finance_transaction_date("24/07/2026") == "2026-07-24"
    assert _normalize_finance_transaction_date("24-07-2026") == "2026-07-24"


def test_finance_recognition_preserves_iso_date():
    assert _normalize_finance_transaction_date("2026-07-24") == "2026-07-24"


def test_finance_recognition_uses_current_year_for_short_russian_date():
    current_year = datetime.now(timezone.utc).year
    assert _normalize_finance_transaction_date("23.07") == f"{current_year}-07-23"
