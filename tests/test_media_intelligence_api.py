from api.media_intelligence_api import _invalidate_social_approvals_for_photo_usage


class FakeCursor:
    def __init__(self, rowcount=0):
        self.rowcount = rowcount
        self.query = ""
        self.params = ()

    def execute(self, query, params=None):
        self.query = " ".join(str(query).split())
        self.params = params or ()


def test_photo_selection_resets_approval_for_unpublished_platform_posts():
    cursor = FakeCursor(rowcount=3)

    changed = _invalidate_social_approvals_for_photo_usage(
        cursor,
        business_id="biz-1",
        content_plan_item_id="item-1",
        photo_asset_id="photo-1",
    )

    assert changed == 3
    assert "SET status = 'needs_review'" in cursor.query
    assert "approved_at = NULL" in cursor.query
    assert "status NOT IN ('published', 'publishing')" in cursor.query
    assert cursor.params == ("photo-1", "biz-1", "item-1")


def test_platform_photo_selection_only_resets_that_platform():
    cursor = FakeCursor(rowcount=1)

    changed = _invalidate_social_approvals_for_photo_usage(
        cursor,
        business_id="biz-1",
        content_plan_item_id="item-1",
        photo_asset_id="photo-1",
        target_platform="telegram",
    )

    assert changed == 1
    assert "AND platform = %s" in cursor.query
    assert cursor.params == ("photo-1", "biz-1", "item-1", "telegram")
