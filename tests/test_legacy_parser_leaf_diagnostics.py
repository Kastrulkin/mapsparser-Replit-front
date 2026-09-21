"""AST-isolated regressions for legacy parser leaf diagnostic value handling."""

from __future__ import annotations

import ast
import copy
from contextlib import redirect_stdout
import io
from pathlib import Path
import re
import sys
import unittest


SOURCE_PATH = Path(__file__).parents[1] / "src" / "yandex_maps_scraper.py"
SYNTHETIC_MARKER = "synthetic-private-legacy-leaf-marker"

# (function, immutable-parent diagnostic fragment, final fixed-event fragment)
CHANGED_SINKS = (
    ("parse_reviews_from_main_page", "Ошибка при парсинге рейтинга с главной", "Ошибка при парсинге рейтинга с главной"),
    ("parse_overview_data", "✅ Найдено название из meta tag", "✅ Название извлечено из meta tag"),
    ("parse_overview_data", "✅ Найдено название из page title", "✅ Название извлечено из page title"),
    ("parse_overview_data", "Ошибка получения названия", "Ошибка получения названия"),
    ("parse_overview_data", "Ошибка проверки верификации", "Ошибка проверки верификации"),
    ("parse_overview_data", "✅ Найден адрес:", "✅ Адрес извлечен"),
    ("parse_overview_data", "⚠️ Адрес взят из мета-описания", "⚠️ Адрес извлечен из мета-описания"),
    ("parse_overview_data", "Ошибка при парсинге адреса", "Ошибка при парсинге адреса"),
    ("parse_overview_data", "Ошибка при попытке кликнуть по кнопке телефона", "Ошибка при попытке кликнуть по кнопке телефона"),
    ("parse_overview_data", "✅ Найден телефон (href)", "✅ Телефон извлечен из href"),
    ("parse_overview_data", "✅ Найден телефон (текст)", "✅ Телефон извлечен из текста"),
    ("parse_overview_data", "✅ Найден телефон (хедер)", "✅ Телефон извлечен из хедера"),
    ("parse_overview_data", "Ошибка при парсинге телефона", "Ошибка при парсинге телефона"),
    ("parse_overview_data", "Найдены основные категории бизнеса", "Основные категории бизнеса извлечены"),
    ("parse_overview_data", "✅ Найден рейтинг:", "✅ Рейтинг извлечен (селектор:"),
    ("parse_overview_data", "✅ Найден рейтинг в заголовке", "✅ Рейтинг извлечен из заголовка"),
    ("parse_overview_data", "Найдены часы работы (regex)", "Часы работы извлечены через regex"),
    ("parse_overview_data", "Найдены часы работы в общем поиске", "Часы работы извлечены в общем поиске"),
    ("parse_overview_data", "Ошибка при парсинге краткого времени работы", "Ошибка при парсинге краткого времени работы"),
    ("parse_overview_data", "Ошибка при попытке кликнуть по кнопке 'График'", "Ошибка при попытке кликнуть по кнопке 'График'"),
    ("parse_overview_data", "День:", "Строка расписания извлечена"),
    ("parse_overview_data", "Все дни одинаковые, краткая форма", "Часы работы нормализованы в краткую форму"),
    ("parse_overview_data", "Часы работы по дням", "Часы работы извлечены по дням"),
    ("parse_overview_data", "Ошибка при парсинге полного расписания", "Ошибка при парсинге полного расписания"),
    ("parse_overview_data", "Ссылка из блока мессенджеров", "Ссылка из блока мессенджеров извлечена"),
    ("parse_overview_data", "Ошибка при парсинге блока мессенджеров", "Ошибка при парсинге блока мессенджеров"),
    ("parse_overview_data", "Ошибка при альтернативном парсинге услуг", "Ошибка при альтернативном парсинге услуг"),
    ("parse_reviews", "Ошибка при подсчете отзывов", "Ошибка при подсчете отзывов"),
    ("parse_reviews", "ℹ️ Дата не найдена для отзыва", "ℹ️ Дата для отзыва не найдена"),
    ("parse_reviews", "Ошибка при клике по кнопке ответа", "Ошибка при клике по кнопке ответа"),
    ("parse_reviews", "✅ Найден ответ организации (HTML парсинг)", "✅ Ответ организации извлечен (HTML парсинг)"),
    ("parse_reviews", "⚠️ Ошибка при парсинге ответа организации", "⚠️ Ошибка при парсинге ответа организации"),
    ("parse_reviews", "ℹ️ Ответ организации не найден для отзыва", "ℹ️ Ответ организации для отзыва не найден"),
    ("parse_news", "Ошибка при парсинге новостей", "Ошибка при парсинге новостей"),
    ("parse_features", "Ошибка при парсинге особенностей", "Ошибка при парсинге особенностей"),
    ("parse_products", "Ошибка при клике/скролле услуг", "Ошибка при клике/скролле услуг"),
    ("parse_products", "Ошибка парсинга категории", "Ошибка парсинга категории"),
    ("parse_products", "Ошибка при парсинге услуг", "Ошибка при парсинге услуг"),
    ("parse_competitors", "[parse_competitors] Error:", "[parse_competitors] Error:"),
)


def _source_text():
    if "--source-stdin" in sys.argv:
        sys.argv.remove("--source-stdin")
        return sys.stdin.read()
    return SOURCE_PATH.read_text(encoding="utf-8")


SOURCE_TEXT = _source_text()
CURRENT_SOURCE_TEXT = SOURCE_PATH.read_text(encoding="utf-8")


def _tree(source_text=SOURCE_TEXT):
    return ast.parse(source_text, filename=str(SOURCE_PATH))


def _function(tree, name):
    return next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == name)


def _prints(function):
    return [
        node
        for node in ast.walk(function)
        if isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Name)
        and node.value.func.id == "print"
    ]


def _sink_print(source_text, function_name, fragment):
    matches = [node for node in _prints(_function(_tree(source_text), function_name)) if fragment in ast.unparse(node)]
    if len(matches) != 1:
        raise AssertionError(f"expected one {function_name} sink for {fragment!r}, found {len(matches)}")
    return matches[0]


def _capture(callback):
    output = io.StringIO()
    with redirect_stdout(output):
        result = callback()
    return result, output.getvalue()


def _print_probe(statement):
    function = ast.parse(
        """
def exercise(marker):
    data = {"title": marker, "address": marker, "phone": marker, "rating": marker,
            "hours_short": marker, "hours": marker}
    e = RuntimeError(marker)
    addr_text = marker
    selector = "source-proven-selector"
    categories = [marker]
    day = marker
    interval = marker
    href = marker
    text = marker
    reply = marker
    return marker
"""
    ).body[0]
    assert isinstance(function, ast.FunctionDef)
    function.body[-1:-1] = [copy.deepcopy(statement)]
    module = ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[]))
    namespace = {}
    exec(compile(module, str(SOURCE_PATH), "exec"), namespace)
    return namespace["exercise"]


class _Element:
    def __init__(self, marker, href=""):
        self.marker = marker
        self.href = href

    def inner_text(self):
        return self.marker

    def get_attribute(self, name):
        if name == "content":
            return self.marker
        if name == "href":
            return self.href
        return ""

    def is_visible(self):
        return False


class _OverviewPage:
    def __init__(self, marker):
        self.marker = marker

    def query_selector(self, selector):
        if selector == "meta[property='og:title']":
            return _Element(self.marker)
        if selector.startswith("div.orgpage-header-view__contacts > a"):
            return _Element(self.marker)
        return None

    def query_selector_all(self, selector):
        if selector == "a[href^='tel:']":
            return [_Element(self.marker, href=f"tel:{self.marker}")]
        if "vk.com" in selector:
            return [_Element(self.marker, href=self.marker)]
        return []

    def wait_for_timeout(self, _milliseconds):
        return None


class LegacyParserLeafDiagnosticLogsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        def deny_external_side_effects(event, _args):
            if event in {
                "socket.connect",
                "subprocess.Popen",
                "os.system",
                "os.posix_spawn",
                "os.spawn",
                "sqlite3.connect",
            }:
                raise AssertionError(f"unexpected external side effect: {event}")

        sys.addaudithook(deny_external_side_effects)

    def test_all_declared_changed_leaf_sinks_are_fixed_nonempty_events(self):
        leaked = {}
        missing_fixed_event = {}
        for function_name, old_fragment, final_fragment in CHANGED_SINKS:
            source_fragment = final_fragment if SOURCE_TEXT == CURRENT_SOURCE_TEXT else old_fragment
            statement = _sink_print(SOURCE_TEXT, function_name, source_fragment)
            _, stdout = _capture(lambda statement=statement: _print_probe(statement)(SYNTHETIC_MARKER))
            sink = f"{function_name}:{old_fragment}"
            if SYNTHETIC_MARKER in stdout:
                leaked[sink] = stdout
            if final_fragment not in stdout:
                missing_fixed_event[sink] = stdout

        self.assertEqual(leaked, {})
        self.assertEqual(missing_fixed_event, {})

    def test_overview_fake_page_keeps_private_fields_without_console_values(self):
        function = copy.deepcopy(_function(_tree(), "parse_overview_data"))
        module = ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[]))
        namespace = {"re": re, "_close_dialogs": lambda _page: None}
        exec(compile(module, str(SOURCE_PATH), "exec"), namespace)

        result, stdout = _capture(lambda: namespace["parse_overview_data"](_OverviewPage(SYNTHETIC_MARKER)))

        self.assertEqual(result["title"], SYNTHETIC_MARKER)
        self.assertEqual(result["address"], SYNTHETIC_MARKER)
        self.assertEqual(result["phone"], SYNTHETIC_MARKER)
        self.assertEqual(result["social_links"], [SYNTHETIC_MARKER])
        self.assertNotIn(SYNTHETIC_MARKER, stdout)
        self.assertIn("✅ Название извлечено из meta tag", stdout)
        self.assertIn("✅ Адрес извлечен", stdout)
        self.assertIn("✅ Телефон извлечен из href", stdout)

    def test_main_page_review_fallback_keeps_default_result_when_page_raises(self):
        function = copy.deepcopy(_function(_tree(), "parse_reviews_from_main_page"))
        module = ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[]))
        namespace = {}
        exec(compile(module, str(SOURCE_PATH), "exec"), namespace)

        class FailingPage:
            def query_selector(self, _selector):
                raise RuntimeError(SYNTHETIC_MARKER)

        result, stdout = _capture(lambda: namespace["parse_reviews_from_main_page"](FailingPage()))

        self.assertEqual(result, {"rating": "", "reviews_count": 0, "items": []})
        self.assertNotIn(SYNTHETIC_MARKER, stdout)
        self.assertIn("Ошибка при парсинге рейтинга с главной", stdout)


if __name__ == "__main__":
    unittest.main()
