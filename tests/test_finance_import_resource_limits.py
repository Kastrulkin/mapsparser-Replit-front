from io import BytesIO
from types import SimpleNamespace

import pytest
from flask import Flask

from api import finance_api


FINANCE_UPLOAD_MAX_BYTES = 10 * 1024 * 1024


class BoundedReadUpload:
    filename = "finance.csv"

    def __init__(self):
        self.read_sizes = []

    def read(self, size=-1):
        self.read_sizes.append(size)
        if size < 0:
            raise AssertionError("finance upload was read without a byte bound")
        return b"date,type,amount\n2026-09-18,revenue,100\n"


def test_finance_import_bounds_upload_read_before_parser(monkeypatch):
    upload = BoundedReadUpload()
    parse_calls = []
    monkeypatch.setattr(
        finance_api,
        "request",
        SimpleNamespace(files={"file": upload}, form={}),
    )
    monkeypatch.setattr(finance_api, "default_period_range", lambda: ("2026-09-01", "2026-09-30"))
    monkeypatch.setattr(
        finance_api.finance_imports,
        "parse_finance_file",
        lambda filename, content: parse_calls.append((filename, content)) or [],
    )
    monkeypatch.setattr(
        finance_api.finance_imports,
        "normalize_finance_import_rows",
        lambda rows, mapping, period_start, period_end: {"rows": rows},
    )

    filename, content, normalized = finance_api._finance_import_payload_from_request()

    assert upload.read_sizes == [FINANCE_UPLOAD_MAX_BYTES + 1]
    assert filename == "finance.csv"
    assert content == b"date,type,amount\n2026-09-18,revenue,100\n"
    assert parse_calls == [(filename, content)]
    assert normalized == {"rows": []}


@pytest.mark.parametrize("filename", ["finance.csv", "finance.xlsx"])
def test_finance_parser_rejects_over_limit_before_format_parse(monkeypatch, filename):
    format_calls = []
    monkeypatch.setattr(finance_api.finance_imports, "MAX_FINANCE_IMPORT_BYTES", 64)
    monkeypatch.setattr(finance_api.finance_imports, "_parse_csv", lambda _content: format_calls.append("csv") or [])
    monkeypatch.setattr(finance_api.finance_imports, "_parse_excel", lambda _content: format_calls.append("xlsx") or [])

    with pytest.raises(finance_api.finance_imports.FinanceImportLimitError):
        finance_api.finance_imports.parse_finance_file(filename, b"x" * 65)

    assert format_calls == []


def test_finance_parser_accepts_under_limit_csv(monkeypatch):
    content = b"date,type,amount\n2026-09-18,revenue,100" + (b" " * 25)
    monkeypatch.setattr(finance_api.finance_imports, "MAX_FINANCE_IMPORT_BYTES", 64)

    assert len(content) == 64
    assert finance_api.finance_imports.parse_finance_file("finance.csv", content) == [
        {"date": "2026-09-18", "type": "revenue", "amount": "100"}
    ]


@pytest.mark.parametrize("path", ["/api/finance/import-preview", "/api/finance/import-file"])
def test_finance_routes_reject_over_limit_before_parser_or_database(monkeypatch, path):
    parser_calls = []
    normalizer_calls = []
    database_calls = []
    monkeypatch.setattr(finance_api.finance_imports, "MAX_FINANCE_IMPORT_BYTES", 64)
    monkeypatch.setattr(
        finance_api,
        "_require_finance_user_and_business",
        lambda: ({"user_id": "owner-1"}, "business-1", None),
    )
    monkeypatch.setattr(
        finance_api.finance_imports,
        "parse_finance_file",
        lambda *_args: parser_calls.append("parse") or [],
    )
    monkeypatch.setattr(
        finance_api.finance_imports,
        "normalize_finance_import_rows",
        lambda *_args: normalizer_calls.append("normalize") or {},
    )
    monkeypatch.setattr(
        finance_api,
        "DatabaseManager",
        lambda: database_calls.append("database") or None,
    )
    app = Flask(__name__)
    app.register_blueprint(finance_api.finance_bp)

    response = app.test_client().post(
        path,
        data={"file": (BytesIO(b"x" * 65), "finance.csv")},
    )

    assert response.status_code == 413
    assert response.get_json() == {"error": "Файл слишком большой. Максимальный размер — 10 МБ."}
    assert parser_calls == []
    assert normalizer_calls == []
    assert database_calls == []
