from api.operator_api import _normalize_finance_transaction_date


def test_finance_recognition_normalizes_common_russian_dates():
    assert _normalize_finance_transaction_date("24.07.2026") == "2026-07-24"
    assert _normalize_finance_transaction_date("24/07/2026") == "2026-07-24"
    assert _normalize_finance_transaction_date("24-07-2026") == "2026-07-24"


def test_finance_recognition_preserves_iso_date():
    assert _normalize_finance_transaction_date("2026-07-24") == "2026-07-24"
