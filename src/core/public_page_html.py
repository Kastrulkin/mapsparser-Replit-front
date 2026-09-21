"""Visible, escaped public-page content from the frontend build's shared data."""

import html
import json
from pathlib import Path
import re


MANIFEST_NAME = "public-page-fallbacks.json"
PUBLIC_SHELL_NAME = "public-seo-index.html"


def load_public_shell(dist_dir, fallback_html):
    """Allow public-only releases without replacing the private application's entry."""
    try:
        manifest = json.loads((Path(dist_dir) / MANIFEST_NAME).read_text(encoding="utf-8"))
        if not isinstance(manifest, dict) or manifest.get("publicShell") != PUBLIC_SHELL_NAME:
            return fallback_html
        shell = (Path(dist_dir) / PUBLIC_SHELL_NAME).read_text(encoding="utf-8")
    except (OSError, ValueError):
        return fallback_html
    return shell if shell.strip() else fallback_html


def _text_list(value):
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def _local_href(value):
    return (
        isinstance(value, str)
        and value.startswith("/")
        and not value.startswith("//")
        and not any(character.isspace() or character == "\\" for character in value)
    )


def _valid_page(page):
    if not isinstance(page, dict):
        return False
    if not all(isinstance(page.get(key), str) and page[key].strip() for key in ("title", "description", "heading")):
        return False
    if not _text_list(page.get("intro")) or not isinstance(page.get("sections"), list):
        return False
    for section in page["sections"]:
        if not isinstance(section, dict) or not isinstance(section.get("heading"), str):
            return False
        if not all(_text_list(section.get(key, [])) for key in ("paragraphs", "items")):
            return False
        links = section.get("links", [])
        if not isinstance(links, list) or not all(
            isinstance(link, dict) and isinstance(link.get("label"), str) and _local_href(link.get("href"))
            for link in links
        ):
            return False
    return True


def load_public_page(dist_dir, route_path):
    """Missing/old builds retain their existing HTML; never derive a file path from a URL."""
    try:
        manifest = json.loads((Path(dist_dir) / MANIFEST_NAME).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(manifest, dict) or manifest.get("version") != 1:
        return None
    routes = manifest.get("routes")
    if not isinstance(routes, dict):
        return None
    page = routes.get(route_path)
    return page if _valid_page(page) else None


def render_public_page(page):
    """The same visible body goes to people and crawlers; no user-agent branching."""
    escape = html.escape
    fragments = [
        '<main data-localos-static-fallback class="min-h-screen bg-background px-5 py-10 text-foreground sm:px-8">',
        '<div class="mx-auto max-w-5xl">',
        '<nav aria-label="Основная навигация" class="flex flex-wrap gap-6 text-sm font-semibold">',
        '<a href="/" aria-label="LocalOS — главная"><img src="/localos-logo.png" alt="LocalOS" class="h-10 w-auto" /></a>',
        '<a href="/about">О продукте</a>',
        '<a href="/pricing">Тарифы</a><a href="/cases">Кейсы</a><a href="/contact">Контакты</a>',
        '</nav><header class="py-12">',
        f'<h1 class="text-balance text-4xl font-bold sm:text-5xl">{escape(page["heading"])}</h1>',
    ]
    for paragraph in page["intro"]:
        fragments.append(f'<p class="mt-6 text-lg leading-8 text-muted-foreground">{escape(paragraph)}</p>')
    fragments.append('</header>')
    for section in page["sections"]:
        fragments.append('<section class="border-t border-border py-8">')
        fragments.append(f'<h2 class="text-2xl font-bold">{escape(section["heading"])}</h2>')
        for paragraph in section.get("paragraphs", []):
            fragments.append(f'<p class="mt-4 leading-7 text-muted-foreground">{escape(paragraph)}</p>')
        if section.get("items"):
            fragments.append('<ul class="mt-4 list-disc space-y-3 pl-6 leading-7">')
            fragments.extend(f'<li>{escape(item)}</li>' for item in section["items"])
            fragments.append('</ul>')
        if section.get("links"):
            fragments.append('<ul class="mt-4 flex flex-wrap gap-6">')
            fragments.extend(
                f'<li><a class="inline-flex min-h-11 items-center font-semibold underline" '
                f'href="{escape(link["href"], quote=True)}">{escape(link["label"])}</a></li>'
                for link in section["links"]
            )
            fragments.append('</ul>')
        fragments.append('</section>')
    fragments.append('</div></main>')
    return "\n".join(fragments)


def replace_public_page_body(index_html, page):
    body = render_public_page(page)
    updated, count = re.subn(
        r'<main\b[^>]*\bdata-localos-static-fallback\b[^>]*>.*?</main\s*>',
        lambda _match: body,
        index_html,
        count=1,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if count:
        return updated
    # Compatibility with older, empty SPA shells; never replace arbitrary nested DOM.
    return re.sub(
        r'(<div\b[^>]*\bid=["\']root["\'][^>]*>)\s*(</div\s*>)',
        lambda match: match.group(1) + body + match.group(2),
        index_html,
        count=1,
        flags=re.IGNORECASE,
    )
