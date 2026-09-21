"""Causal privacy contracts for the supported legacy Yandex parser fallback."""

import ast
import builtins
import os
from pathlib import Path
import sys
import traceback
import types

ROOT = Path(os.environ.get("LEGACY_PARSER_PRIVACY_SOURCE_ROOT", Path(__file__).resolve().parents[1]))
MARKER = "legacy-parser-private-marker"


def _function(path, name, namespace):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    node = next(item for item in tree.body if isinstance(item, ast.FunctionDef) and item.name == name)
    future = ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0)
    exec(compile(ast.fix_missing_locations(ast.Module(body=[future, node], type_ignores=[])), str(path), "exec"), namespace)
    return namespace[name]


def _formatted(error):
    return "".join(traceback.format_exception(error))


def test_interception_import_fallback_keeps_legacy_parser_without_exception_text(monkeypatch, capsys):
    path = ROOT / "src/parser_config.py"
    legacy = types.ModuleType("yandex_maps_scraper")

    def legacy_parser(url):
        return {"url": url}

    legacy.parse_yandex_card = legacy_parser
    original_import = builtins.__import__

    def controlled_import(name, *arguments, **keywords):
        if name == "parser_interception":
            raise ImportError(MARKER)
        if name == "yandex_maps_scraper":
            return legacy
        return original_import(name, *arguments, **keywords)

    monkeypatch.setattr(builtins, "__import__", controlled_import)
    get_parser = _function(path, "get_parser", {"PARSER_MODE": "interception"})

    selected = get_parser()
    assert selected is legacy_parser
    assert selected(f"https://maps.example.test/{MARKER}") == {"url": f"https://maps.example.test/{MARKER}"}
    output = capsys.readouterr().out
    assert "Переключаемся на legacy парсер" in output
    assert MARKER not in output


def test_legacy_invalid_url_keeps_value_error_without_url_value(capsys):
    path = ROOT / "src/yandex_maps_scraper.py"
    admissions = []
    parse_yandex_card = _function(
        path,
        "parse_yandex_card",
        {"sync_playwright": lambda: admissions.append(True)},
    )
    error = None
    try:
        parse_yandex_card(MARKER)
    except ValueError:
        error = sys.exception()

    assert isinstance(error, ValueError)
    assert "Некорректная ссылка" in str(error)
    output = capsys.readouterr().out
    assert "Начинаем legacy-парсинг" in output
    assert admissions == []
    assert MARKER not in str(error)
    assert MARKER not in output
    assert MARKER not in _formatted(error)


def _playwright_error(marker_error):
    path = ROOT / "src/yandex_maps_scraper.py"
    closed = []

    class Browser:
        def new_context(self, **keywords):
            raise marker_error

        def close(self):
            closed.append(True)

    class PlaywrightContext:
        def __enter__(self):
            return object()

        def __exit__(self, *arguments):
            return False

    parser_cookies = types.ModuleType("parser_config_cookies")
    parser_cookies.get_yandex_cookies = lambda: []
    previous = sys.modules.get("parser_config_cookies")
    sys.modules["parser_config_cookies"] = parser_cookies
    error = None
    try:
        parse_yandex_card = _function(
            path,
            "parse_yandex_card",
            {
                "sync_playwright": lambda: PlaywrightContext(),
                "PlaywrightTimeoutError": TimeoutError,
                "_launch_browser": lambda playwright: (Browser(), "fake"),
            },
        )
        parse_yandex_card("https://maps.example.test/valid")
    except Exception:
        error = sys.exception()
    finally:
        if previous is None:
            sys.modules.pop("parser_config_cookies", None)
        else:
            sys.modules["parser_config_cookies"] = previous
    return error, closed


def test_legacy_playwright_timeout_closes_browser_without_exception_text(capsys):
    error, closed = _playwright_error(TimeoutError(MARKER))

    assert isinstance(error, Exception)
    assert "Тайм-аут при загрузке страницы" in str(error)
    assert closed == [True]
    assert MARKER not in str(error)
    assert MARKER not in capsys.readouterr().out
    assert MARKER not in _formatted(error)


def test_legacy_playwright_error_closes_browser_without_exception_text(capsys):
    error, closed = _playwright_error(RuntimeError(MARKER))

    assert isinstance(error, Exception)
    assert "Ошибка при парсинге" in str(error)
    assert closed == [True]
    assert MARKER not in str(error)
    assert MARKER not in capsys.readouterr().out
    assert MARKER not in _formatted(error)
