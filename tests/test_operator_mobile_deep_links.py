from services.operator_mobile_deep_links import resolve_mobile_deep_link


class DeepLinkCursor:
    def __init__(self, rows=None):
        self.rows = list(rows or [])
        self.current = []

    def execute(self, query, params=()):
        normalized = " ".join(query.lower().split())
        if "from externalbusinessreviews" in normalized:
            item_id = str(params[0])
            self.current = [item for item in self.rows if str(item.get("id")) == item_id]
        else:
            raise AssertionError(f"Unexpected query: {normalized}")

    def fetchone(self):
        return self.current[0] if self.current else None


def navigation():
    return [
        {"key": "today", "status": "available"},
        {"key": "reviews", "status": "available"},
        {"key": "finance", "status": "available"},
        {"key": "diagnostics", "status": "hidden"},
    ]


def test_review_deep_link_resolves_only_inside_scope():
    cursor = DeepLinkCursor([{"id": "review-1", "business_id": "business-1"}])
    scope = {"kind": "business", "id": "business-1", "business_ids": ["business-1"]}

    result = resolve_mobile_deep_link(
        cursor,
        scope=scope,
        navigation=navigation(),
        screen="reviews",
        item_type="review",
        item_id="review-1",
    )

    assert result["screen"] == "reviews"
    assert result["item_id"] == "review-1"
    assert result["fallback_applied"] is False


def test_review_deep_link_cannot_cross_business_scope():
    cursor = DeepLinkCursor([{"id": "review-1", "business_id": "business-2"}])
    scope = {"kind": "business", "id": "business-1", "business_ids": ["business-1"]}

    result = resolve_mobile_deep_link(
        cursor,
        scope=scope,
        navigation=navigation(),
        screen="reviews",
        item_type="review",
        item_id="review-1",
    )

    assert result["screen"] == "today"
    assert result["item_id"] is None
    assert result["fallback_reason"] == "object_forbidden"


def test_legacy_analytics_link_opens_finance():
    result = resolve_mobile_deep_link(
        DeepLinkCursor(),
        scope={"kind": "business", "business_ids": ["business-1"]},
        navigation=navigation(),
        screen="analytics",
        item_type="",
        item_id="",
    )

    assert result["screen"] == "finance"
    assert result["fallback_applied"] is False


def test_hidden_screen_falls_back_to_today():
    result = resolve_mobile_deep_link(
        DeepLinkCursor(),
        scope={"kind": "business", "business_ids": ["business-1"]},
        navigation=navigation(),
        screen="diagnostics",
        item_type="",
        item_id="",
    )

    assert result["screen"] == "today"
    assert result["fallback_reason"] == "screen_unavailable"
