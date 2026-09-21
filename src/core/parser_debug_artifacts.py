"""Value-free diagnostics for authenticated parser sessions.

Provider fields, HTML, URLs and screenshots may contain credentials or private
content even when their names look harmless. Persist structure, not raw values.
These helpers do not mutate the data the parser consumes.
"""

from urllib.parse import urlsplit


_DIAGNOSTIC_FIELDS = (
    "data", "result", "results", "items", "features", "properties", "settings",
    "organization", "organizations", "company", "business", "id", "name",
    "title", "address", "address_name", "fullAddress", "rating", "score",
    "ratingData", "rubrics", "categories", "rubric", "reviews", "photos",
    "services", "phone", "site", "hours", "description", "_meta", "error",
    "hittoken", "aesKey", "clientKey", "ordToken", "headers", "cookies",
)


def debug_value_shape(value: object) -> dict[str, object]:
    """Describe a bounded schema without retaining arbitrary keys or values."""
    remaining = 120

    def visit(node: object, depth: int) -> dict[str, object]:
        nonlocal remaining
        if remaining <= 0:
            return {"type": "omitted"}
        remaining -= 1
        if isinstance(node, dict):
            result: dict[str, object] = {"type": "object", "field_count": len(node)}
            if depth >= 5:
                result["truncated"] = True
                return result
            fields = {}
            for key in _DIAGNOSTIC_FIELDS:
                if remaining <= 0:
                    break
                if key in node:
                    fields[key] = visit(node[key], depth + 1)
            result["fields"] = fields
            result["omitted_field_count"] = len(node) - len(fields)
            return result
        if isinstance(node, list):
            result = {"type": "array", "item_count": len(node)}
            if depth >= 5:
                result["truncated"] = True
                return result
            items = []
            for item in node[:3]:
                if remaining <= 0:
                    break
                items.append(visit(item, depth + 1))
            result["sample_shapes"] = items
            return result
        if isinstance(node, str):
            return {"type": "string", "length": len(node)}
        if node is None:
            return {"type": "null"}
        if isinstance(node, bool):
            return {"type": "boolean"}
        if isinstance(node, (int, float)):
            return {"type": "number"}
        return {"type": "unsupported"}

    return visit(value, 0)


def debug_url_summary(value: object) -> dict[str, object]:
    """Keep route categories, never hosts, userinfo, paths, query or fragment."""
    if not isinstance(value, str):
        return {"kind": "invalid"}
    try:
        parsed = urlsplit(value)
        host = parsed.hostname or ""
    except ValueError:
        return {"kind": "invalid"}
    is_yandex = any(
        host == domain or host.endswith("." + domain)
        for domain in ("yandex.ru", "yandex.net", "yandex.com", "yandex.kz")
    )
    route = "other"
    for category, marker in (("captcha", "showcaptcha"), ("organization", "/org/"),
                             ("reviews", "reviews"), ("prices", "/prices")):
        if marker in parsed.path.lower():
            route = category
            break
    return {
        "provider": "yandex" if is_yandex else "other",
        "https": parsed.scheme == "https", "route": route,
        "has_query": bool(parsed.query), "has_fragment": bool(parsed.fragment),
        "has_userinfo": "@" in parsed.netloc,
    }


def debug_html_placeholder(value: object) -> str:
    """A compatible HTML artifact with no captured text, attributes or scripts."""
    length = len(value) if isinstance(value, str) else 0
    return (
        "<!doctype html><title>Parser diagnostic</title>"
        "<p>Raw HTML omitted to protect session and private data.</p>"
        f"<p>Source character count: {length}</p>\n"
    )
