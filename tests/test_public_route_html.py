"""Exercise the actual SPA HTML renderer without app startup or database access."""

import ast
import html
import json
import logging
import os
from pathlib import Path
import re
from typing import Any, Dict, List, Optional

from flask import Flask, Response, jsonify, request, send_from_directory
import pytest

from core.html_head import replace_or_insert_tag
from core.public_page_html import load_public_page, load_public_shell, replace_public_page_body


ROOT = Path(__file__).resolve().parents[1]
SHELL = '''<!doctype html><html lang="ru"><head><title>Homepage</title>
<meta name="description" content="Homepage description">
</head><body><div id="root"><main data-localos-static-fallback>
<div><h1>Homepage fallback</h1></div></main></div>
<script type="module" src="/assets/index-frozen.js"></script></body></html>'''


def page_data(heading):
    return {
        "title": heading + " | LocalOS",
        "description": "Описание: " + heading,
        "heading": heading,
        "intro": ["Карты, отзывы и услуги локального бизнеса."],
        "sections": [{
            "heading": "Следующий шаг",
            "paragraphs": ["Внешние действия — только после подтверждения."],
            "items": ["Карты — 1 200 ₽ в месяц"],
            "links": [{"href": "/about#pricing", "label": "Выбрать тариф"}],
        }],
    }


@pytest.fixture
def renderer(tmp_path):
    (tmp_path / "index.html").write_text(SHELL, encoding="utf-8")
    (tmp_path / "content-seo.json").write_text(json.dumps({
        "default": {"title": "Homepage", "description": "Homepage description"},
        "routes": {"/articles/kept": {"title": "Existing article", "description": "Article metadata"}},
    }), encoding="utf-8")
    routes = {
        route: page_data(heading)
        for route, heading in [
            ("/", "LocalOS для локального бизнеса"),
            ("/about", "О продукте LocalOS"),
            ("/pricing", "Тарифы LocalOS"),
            ("/cases", "Кейсы LocalOS"),
            ("/cases/example", "Результат работы с картами"),
        ]
    }
    (tmp_path / "public-page-fallbacks.json").write_text(json.dumps({"version": 1, "routes": routes}), encoding="utf-8")
    names = {
        "_normalize_content_route", "_read_frontend_index_html", "_load_content_seo_data",
        "_escape_head_value", "_route_article_schema", "_schema_for_route",
        "_set_named_meta", "_set_canonical", "_set_jsonld", "_render_spa_index",
    }
    source = ROOT / "src/legacy_routes/core_public.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
    assert len(functions) == len(names)
    namespace = {
        "os": os, "json": json, "html": html, "re": re, "Response": Response,
        "Any": Any, "Dict": Dict, "List": List, "Optional": Optional,
        "logger": logging.getLogger(__name__), "FRONTEND_DIST_DIR": str(tmp_path),
        "CONTENT_SEO_FILE": "content-seo.json", "SITE_URL": "https://localos.pro",
        "DEFAULT_OG_IMAGE": "https://localos.pro/favicon.svg",
        "_replace_or_insert_tag": replace_or_insert_tag,
        "load_public_page": load_public_page, "replace_public_page_body": replace_public_page_body,
        "load_public_shell": load_public_shell,
    }
    exec(compile(ast.Module(body=functions, type_ignores=[]), str(source), "exec"), namespace)
    app = Flask(__name__)
    app.config["TEST_RENDER_NAMESPACE"] = namespace
    app.add_url_rule("/", endpoint="home", view_func=lambda: namespace["_render_spa_index"]("/"))
    app.add_url_rule("/<path:path>", endpoint="public_page", view_func=lambda path: namespace["_render_spa_index"](path))
    return app.test_client(), tmp_path, routes


@pytest.mark.parametrize("route", ["/", "/about", "/pricing", "/cases", "/cases/example"])
def test_public_response_contains_its_own_visible_body_and_metadata(renderer, route):
    client, _, routes = renderer
    response = client.get(route)
    source = response.get_data(as_text=True)
    page = routes[route]
    assert response.status_code == 200
    assert f'>{page["heading"]}</h1>' in source
    assert f'<title>{page["title"]}</title>' in source
    assert f'content="{page["description"]}"' in source
    assert f'href="https://localos.pro{route}"' in source
    assert source.count("<h1") == 1
    assert "Homepage fallback" not in source
    assert "1 200 ₽" in source
    assert 'href="/about#pricing"' in source
    assert 'src="/assets/index-frozen.js"' in source
    assert "display:none" not in source and "hidden" not in source
    assert "no-store" in response.headers["Cache-Control"]


def test_query_and_trailing_slash_keep_same_public_page(renderer):
    client, _, _ = renderer
    response = client.get("/pricing/?utm_source=example")
    assert ">Тарифы LocalOS</h1>" in response.get_data(as_text=True)
    assert 'href="https://localos.pro/pricing"' in response.get_data(as_text=True)


def test_unknown_private_and_existing_article_routes_keep_previous_behavior(renderer):
    client, _, _ = renderer
    for route in ("/login", "/dashboard/agents", "/not-a-public-page"):
        source = client.get(route).get_data(as_text=True)
        assert "Homepage fallback" in source
        assert "1 200 ₽" not in source
    source = client.get("/articles/kept").get_data(as_text=True)
    assert "<title>Existing article</title>" in source


def test_missing_or_invalid_manifest_keeps_working_shell(renderer):
    client, dist, _ = renderer
    for malformed in ('{}', '{"version":2}', 'not json', '{"version":1,"routes":{"/pricing":{"heading":[]}}}'):
        (dist / "public-page-fallbacks.json").write_text(malformed, encoding="utf-8")
        source = client.get("/pricing").get_data(as_text=True)
        assert "Homepage fallback" in source
        assert 'src="/assets/index-frozen.js"' in source
    assert load_public_page(dist / "absent", "/pricing") is None


def test_separate_public_bundle_does_not_change_private_or_article_entry(renderer):
    client, dist, _ = renderer
    public_shell = SHELL.replace("/assets/index-frozen.js", "/seo-assets-release/index-public.js")
    (dist / "public-seo-index.html").write_text(public_shell, encoding="utf-8")
    # A stale sidecar from an older release must not override a normal new build.
    assert 'src="/assets/index-frozen.js"' in client.get("/pricing").get_data(as_text=True)
    manifest_path = dist / "public-page-fallbacks.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["publicShell"] = "public-seo-index.html"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    for route in ("/", "/about", "/pricing", "/cases", "/cases/example"):
        source = client.get(route).get_data(as_text=True)
        assert 'src="/seo-assets-release/index-public.js"' in source
        assert 'src="/assets/index-frozen.js"' not in source
    for route in ("/login", "/dashboard/agents", "/articles/kept"):
        source = client.get(route).get_data(as_text=True)
        assert 'src="/assets/index-frozen.js"' in source
        assert 'src="/seo-assets-release/index-public.js"' not in source
    (dist / "public-seo-index.html").write_text("", encoding="utf-8")
    assert 'src="/assets/index-frozen.js"' in client.get("/pricing").get_data(as_text=True)


def test_manifest_text_is_escaped_and_unsafe_links_are_rejected(renderer):
    client, dist, _ = renderer
    page = page_data('Example <script>alert("test")</script>')
    page["sections"][0]["items"] = ["<img src=x onerror=alert(1)>"]
    manifest_path = dist / "public-page-fallbacks.json"
    manifest_path.write_text(json.dumps({"version": 1, "routes": {"/cases": page}}), encoding="utf-8")
    source = client.get("/cases").get_data(as_text=True)
    assert "&lt;script&gt;" in source and "&lt;img" in source
    assert "<script>alert" not in source and "<img src=x" not in source
    for href in ("javascript:alert(1)", "//outside.example", "/\\outside.example", "/x\ny"):
        page["sections"][0]["links"][0]["href"] = href
        manifest_path.write_text(json.dumps({"version": 1, "routes": {"/cases": page}}), encoding="utf-8")
        assert load_public_page(dist, "/cases") is None


def test_legacy_empty_root_is_supported_without_touching_other_dom():
    page = page_data("Public heading")
    shell = '<div id="root"></div><script src="/assets/index-current.js"></script>'
    source = replace_public_page_body(shell, page)
    assert ">Public heading</h1>" in source
    assert source.endswith('<script src="/assets/index-current.js"></script>')
    unrelated = '<div id="root"><div>Unrelated application</div></div>'
    assert replace_public_page_body(unrelated, page) == unrelated


def test_known_public_routes_do_not_query_offer_database(renderer):
    client, _, _ = renderer
    namespace = client.application.config["TEST_RENDER_NAMESPACE"]
    source = ROOT / "src/legacy_routes/core_public.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    fallback = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "spa_fallback")
    fallback.decorator_list = []
    lookup_calls = []

    def offer_lookup(path):
        lookup_calls.append(path)
        return False

    namespace.update({
        "request": request, "jsonify": jsonify, "send_from_directory": send_from_directory,
        "_is_sensitive_probe_path": lambda path: False,
        "_is_public_offer_slug": offer_lookup,
    })
    exec(compile(ast.Module(body=[fallback], type_ignores=[]), str(source), "exec"), namespace)
    for path in ("about", "pricing", "cases", "cases/example"):
        with client.application.test_request_context("/" + path):
            response = namespace["spa_fallback"](path)
            assert response.status_code == 200
    assert lookup_calls == []

    with client.application.test_request_context("/actual-offer"):
        namespace["spa_fallback"]("actual-offer")
    assert lookup_calls == ["actual-offer"]
