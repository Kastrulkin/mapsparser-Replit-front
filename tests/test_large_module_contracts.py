from pathlib import Path


def test_critical_flask_routes_keep_their_public_contract() -> None:
    import main

    expected = {
        ("/api/admin/prospecting/search", "POST"): "admin_prospecting.search_businesses",
        ("/api/partnership/health", "GET"): "admin_prospecting.partnership_health",
        ("/api/partnership/send-batches", "GET"): "admin_prospecting.partnership_send_batches",
        ("/api/partnership/send-batches", "POST"): "admin_prospecting.partnership_create_send_batch",
        ("/api/auth/login", "POST"): "login",
        ("/api/news/generate", "POST"): "news_generate",
        ("/api/networks", "GET"): "get_user_networks",
        ("/api/networks", "POST"): "create_network",
        ("/api/social-posts/dispatch/preview", "POST"): "social_posts.social_posts_dispatch_preview",
    }

    actual = {}
    for rule in main.app.url_map.iter_rules():
        for method in rule.methods - {"HEAD", "OPTIONS"}:
            actual[(rule.rule, method)] = rule.endpoint

    for route_contract, endpoint in expected.items():
        assert actual.get(route_contract) == endpoint


def test_large_module_compatibility_entrypoints_remain_available() -> None:
    from api.admin_prospecting import admin_prospecting_bp
    from services.social_post_service import (
        collect_due_social_post_metrics,
        dispatch_due_social_posts,
    )

    assert admin_prospecting_bp.name == "admin_prospecting"
    assert callable(dispatch_due_social_posts)
    assert callable(collect_due_social_post_metrics)


def test_frontend_route_and_component_exports_remain_stable() -> None:
    app_source = Path("frontend/src/App.tsx").read_text(encoding="utf-8")
    agents_source = Path("frontend/src/pages/dashboard/AgentBlueprintsPage.tsx").read_text(encoding="utf-8")
    content_source = Path("frontend/src/components/content-plan/ContentPlanTab.tsx").read_text(encoding="utf-8")

    assert 'path="agents"' in app_source
    assert 'path="content"' in app_source
    assert 'to="/dashboard/content"' in app_source
    assert "export const AgentBlueprintsPage" in agents_source
    assert "export default function ContentPlanTab" in content_source
