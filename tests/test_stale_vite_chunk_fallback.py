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


def test_existing_page_chunk_is_served_without_replacement(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import ast
    import os
    from flask import Flask, send_from_directory

    route_source = Path(__file__).resolve().parents[1] / "src/legacy_routes/core_public.py"
    tree = ast.parse(route_source.read_text())
    route = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "serve_assets")
    route.decorator_list = []
    app = Flask(__name__)
    namespace = {"os": os, "FRONTEND_DIST_DIR": str(tmp_path), "send_from_directory": send_from_directory, "resolve_current_lazy_chunk": resolve_current_lazy_chunk}
    exec(compile(ast.Module(body=[route], type_ignores=[]), str(route_source), "exec"), namespace)
    app.add_url_rule("/assets/<path:filename>", view_func=namespace["serve_assets"])

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
    response = app.test_client().get("/assets/ContentPage-Oldhash12.js")

    assert response.status_code == 200
    assert response.get_data(as_text=True) == "OLD"
    assert "X-LocalOS-Asset-Fallback" not in response.headers


def test_existing_public_chunk_is_not_replaced_by_private_build(tmp_path: Path) -> None:
    assets = tmp_path / "assets"
    assets.mkdir()
    (tmp_path / "index.html").write_text('<script src="/assets/index-private1.js"></script>')
    (tmp_path / "public-seo-index.html").write_text('<script src="/assets/index-public12.js"></script>')
    (assets / "index-private1.js").write_text('import("./Header-Private12.js")')
    (assets / "index-public12.js").write_text('import("./Header-Public123.js")')
    (assets / "Header-Private12.js").write_text('import "./router-private1.js"')
    (assets / "Header-Public123.js").write_text('import "./router-public12.js"')
    assert resolve_current_lazy_chunk(str(tmp_path), "Header-Public123.js") is None
