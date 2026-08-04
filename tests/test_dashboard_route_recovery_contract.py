from pathlib import Path
import re


REPO_ROOT = Path(__file__).resolve().parents[1]
APP_SOURCE = REPO_ROOT / "frontend" / "src" / "App.tsx"


def test_content_page_uses_lazy_route_recovery() -> None:
    source = APP_SOURCE.read_text(encoding="utf-8")
    match = re.search(
        r"const ContentPage = lazy\(\(\) =>(?P<body>.*?)\n\);",
        source,
        flags=re.DOTALL,
    )

    assert match is not None, "Не найден lazy-маршрут ContentPage в frontend/src/App.tsx"
    assert "loadRouteWithRecovery(" in match.group("body"), (
        "ContentPage загружается без восстановления после исчезновения старого "
        "Vite-чанка. Открытая до выкладки вкладка получает HTTP 404 и падает "
        "с Failed to fetch dynamically imported module."
    )
