#!/usr/bin/env python3
"""Local, read-only review of a built site. Never delivers contact requests."""
import argparse
import ast
import html
import json
import logging
import os
from pathlib import Path
import re
import sys
from typing import Any, Dict, List, Optional

from flask import Flask, Response, jsonify, request, send_from_directory

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from core.public_page_html import (
    is_known_spa_route, load_public_page, load_public_shell,
    replace_public_page_body, should_noindex_spa_route,
)


def create_preview(dist):
    """Use the real public HTML renderer without booting production integrations."""
    names = {
        '_normalize_content_route', '_read_frontend_index_html', '_load_content_seo_data',
        '_escape_head_value', '_route_article_schema', '_schema_for_route',
        '_set_named_meta', '_set_canonical', '_set_jsonld', '_render_spa_index',
    }
    source = ROOT / 'src/legacy_routes/core_public.py'
    tree = ast.parse(source.read_text(encoding='utf-8'))
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
    if len(functions) != len(names):
        raise RuntimeError('Public renderer contract changed; review preview loader')

    def replace_tag(text, pattern, replacement):
        result, count = re.subn(pattern, lambda match: replacement, text, count=1, flags=re.IGNORECASE)
        return result if count else text.replace('</head>', replacement + '\n</head>', 1)

    namespace = dict(
        os=os, json=json, html=html, re=re, Response=Response,
        Any=Any, Dict=Dict, List=List, Optional=Optional,
        logger=logging.getLogger(__name__), FRONTEND_DIST_DIR=str(dist),
        CONTENT_SEO_FILE='content-seo.json', SITE_URL='https://localos.pro',
        DEFAULT_OG_IMAGE='https://localos.pro/favicon.svg',
        _replace_or_insert_tag=replace_tag, request=request,
        load_public_page=load_public_page, load_public_shell=load_public_shell,
        replace_public_page_body=replace_public_page_body,
        is_known_spa_route=is_known_spa_route, should_noindex_spa_route=should_noindex_spa_route,
    )
    exec(compile(ast.Module(body=functions, type_ignores=[]), str(source), 'exec'), namespace)
    app = Flask(__name__, static_folder=None)

    @app.after_request
    def review_headers(response):
        if response.mimetype == 'text/html':
            body = response.get_data(as_text=True)
            body = re.sub(r'<script id="localos-public-tracking-consent">.*?</script>', '', body, flags=re.DOTALL)
            body = re.sub(r'<script[^>]+src="/tracker.js"[^>]*></script>', '', body)
            response.set_data(body)
        response.headers['X-Robots-Tag'] = 'noindex, nofollow'
        response.headers['Cache-Control'] = 'no-store'
        return response

    @app.route('/api/<path:path>', methods=['GET', 'POST', 'OPTIONS', 'PUT', 'DELETE'])
    def disabled_api(path):
        return jsonify(error='Локальный просмотр: отправка заявок и внешние действия отключены.'), 503

    @app.route('/')
    @app.route('/<path:path>')
    def page(path=''):
        candidate = (dist / path).resolve()
        if candidate.is_relative_to(dist) and candidate.is_file():
            return send_from_directory(dist, path)
        route = '/' + path
        seo = namespace['_load_content_seo_data']()
        status = 200 if is_known_spa_route(route, seo.get('routes', {})) else 404
        return namespace['_render_spa_index'](route, status)

    return app


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dist', type=Path, required=True)
    parser.add_argument('--port', type=int, default=4178)
    args = parser.parse_args()
    dist = args.dist.resolve()
    if not (dist / 'public-page-fallbacks.json').is_file():
        parser.error('Build the frontend into --dist first')
    create_preview(dist).run(host='127.0.0.1', port=args.port, debug=False)
