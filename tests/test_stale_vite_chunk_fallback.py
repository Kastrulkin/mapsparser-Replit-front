from pathlib import Path

from src.core.frontend_asset_compatibility import resolve_current_lazy_chunk


def test_stale_page_chunk_resolves_to_current_build_chunk(tmp_path: Path) -> None:
    assets_dir = tmp_path / "assets"
    assets_dir.mkdir()
    (tmp_path / "index.html").write_text(
        '<script type="module" src="/assets/index-current1.js"></script>',
        encoding="utf-8",
    )
    (assets_dir / "index-current1.js").write_text(
        'const radar = () => import("./TelegramRadarPage-B4sHoisZ.js");',
        encoding="utf-8",
    )
    (assets_dir / "TelegramRadarPage-B4sHoisZ.js").write_text(
        "export default function TelegramRadarPage() {}",
        encoding="utf-8",
    )

    resolved = resolve_current_lazy_chunk(
        str(tmp_path),
        "TelegramRadarPage-D9FqvOsj.js",
    )

    assert resolved == "TelegramRadarPage-B4sHoisZ.js"


def test_shared_or_unsafe_asset_does_not_receive_compatibility_fallback(tmp_path: Path) -> None:
    assets_dir = tmp_path / "assets"
    assets_dir.mkdir()
    (tmp_path / "index.html").write_text(
        '<script type="module" src="/assets/index-current1.js"></script>',
        encoding="utf-8",
    )
    (assets_dir / "index-current1.js").write_text(
        'import "./vendor-current1.js";',
        encoding="utf-8",
    )
    (assets_dir / "vendor-current1.js").write_text("export {};", encoding="utf-8")

    assert resolve_current_lazy_chunk(str(tmp_path), "vendor-oldhash1.js") is None
    assert resolve_current_lazy_chunk(str(tmp_path), "../TelegramRadarPage-D9FqvOsj.js") is None


def test_existing_stale_page_chunk_is_replaced_with_current_build_chunk(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import main
    from legacy_routes import core_public

    assets_dir = tmp_path / "assets"
    assets_dir.mkdir()
    (tmp_path / "index.html").write_text(
        '<script type="module" src="/assets/index-current1.js"></script>',
        encoding="utf-8",
    )
    (assets_dir / "index-current1.js").write_text(
        'const content = () => import("./ContentPage-Current123.js");',
        encoding="utf-8",
    )
    (assets_dir / "ContentPage-Current123.js").write_text("CURRENT", encoding="utf-8")
    (assets_dir / "ContentPage-Oldhash12.js").write_text("OLD", encoding="utf-8")
    monkeypatch.setattr(main, "FRONTEND_DIST_DIR", str(tmp_path))
    monkeypatch.setattr(core_public, "FRONTEND_DIST_DIR", str(tmp_path))

    response = main.app.test_client().get("/assets/ContentPage-Oldhash12.js")

    assert response.status_code == 200
    assert response.get_data(as_text=True) == "CURRENT"
    assert response.headers["X-LocalOS-Asset-Fallback"] == "ContentPage-Current123.js"
