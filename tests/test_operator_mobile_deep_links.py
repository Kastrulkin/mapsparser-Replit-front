from services.operator_mobile_deep_links import resolve_mobile_deep_link


class DeepLinkCursor:
    def __init__(self, rows=None):
        self.rows = list(rows or [])
        self.current = []

    def execute(self, query, params=()):
        normalized = " ".join(query.lower().split())
        if "from externalbusinessreviews" in normalized or "from aiagentconversations" in normalized:
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


def test_client_conversation_link_resolves_only_in_business_scope():
    nav=[{"key":"today","status":"available"},{"key":"client_handoffs","status":"available"}]
    cursor=DeepLinkCursor([{"id":"dialogue","business_id":"ras"}])
    for business,expected in [("ras","client_handoffs"),("foreign","today")]:
        result=resolve_mobile_deep_link(cursor,scope={"kind":"business","id":business,"business_ids":[business]},navigation=nav,screen="client_handoffs",item_type="client_conversation",item_id="dialogue")
        assert result["screen"]==expected
        assert result["item_id"]==("dialogue" if business=="ras" else None)


def test_bootstrap_caller_can_pass_authenticated_user_id():
    result=resolve_mobile_deep_link(DeepLinkCursor(),scope={'kind':'business','id':'ras','business_ids':['ras']},navigation=[{'key':'today','status':'available'}],screen='today',item_type='',item_id='',user_id='me')
    assert result['screen']=='today'


def test_existing_production_startup_aliases_are_preserved():
    nav=[{'key':'today','status':'available'},{'key':'finance','status':'available'},{'key':'work_journal','status':'available'}]
    scope={'kind':'business','id':'ras','business_ids':['ras']}
    assert resolve_mobile_deep_link(DeepLinkCursor(),scope=scope,navigation=nav,screen='finance_import',item_type='',item_id='',user_id='me')['screen']=='finance_import'
    result=resolve_mobile_deep_link(DeepLinkCursor(),scope=scope,navigation=nav,screen='work_journal',item_type='day_brief',item_id='',user_id='me')
    assert result['screen']=='work_journal' and result['item_type']=='day_brief'
