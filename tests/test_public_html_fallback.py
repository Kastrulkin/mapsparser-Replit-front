from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
INDEX_HTML = REPO_ROOT / "frontend" / "index.html"
MAIN_SOURCE = REPO_ROOT / "frontend" / "src" / "main.tsx"


def test_public_index_contains_crawlable_product_fallback() -> None:
    source = INDEX_HTML.read_text(encoding="utf-8")

    assert '<html lang="ru"' in source
    assert '<meta name="description"' in source
    assert "data-localos-static-fallback" in source
    assert "<h1" in source
    assert "LocalOS снимает регулярную работу с владельца бизнеса" in source
    assert "Карты и услуги" in source
    assert "Отзывы и контент" in source
    assert "Финансы и средний чек" in source
    assert "Партнёрства и автоматизация" in source
    assert 'href="/cases"' in source


def test_chunk_preload_failure_recovers_before_error_overlay() -> None:
    index_source = INDEX_HTML.read_text(encoding="utf-8")
    main_source = MAIN_SOURCE.read_text(encoding="utf-8")

    assert "vite:preloadError" in index_source
    assert "vite:preloadError" in main_source
    assert "event.preventDefault()" in index_source
    assert "event.preventDefault()" in main_source
    assert "reloadLocalOSAfterChunkError" in index_source
    assert "reloadAfterDynamicImportError" in main_source
