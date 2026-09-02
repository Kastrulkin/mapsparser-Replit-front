from datetime import datetime, timedelta

from subscription_manager import build_subscription_capabilities, capability_access_payload


def capabilities(tier: str, status: str = 'active', ends_at=None, is_superadmin: bool = False) -> set[str]:
    access = build_subscription_capabilities(
        tier=tier,
        status=status,
        subscription_ends_at=ends_at,
        is_superadmin=is_superadmin,
    )
    return set(access['capabilities'])


def test_starter_only_opens_maps_radar_and_web_analytics():
    available = capabilities('starter')
    assert {'maps', 'maps.news', 'telegram_radar', 'web_analytics'} <= available
    assert {'partnerships', 'influencers', 'automation', 'average_ticket'}.isdisjoint(available)


def test_professional_adds_acquisition_without_management():
    available = capabilities('professional')
    assert {'maps', 'partnerships', 'influencers', 'ai_visibility'} <= available
    assert {'finance', 'average_ticket', 'agents', 'operator'}.isdisjoint(available)


def test_concierge_elite_promo_and_legacy_enterprise_open_management():
    for tier in ('concierge', 'elite', 'promo', 'enterprise'):
        assert {'finance', 'average_ticket', 'agents', 'operator', 'social_content'} <= capabilities(tier)


def test_inactive_and_expired_subscriptions_only_receive_preview():
    assert capabilities('professional', 'inactive') == set()
    assert capabilities('professional', ends_at=datetime.now() - timedelta(minutes=1)) == set()


def test_superadmin_bypasses_subscription_state():
    assert 'management' in capabilities('trial', 'inactive', is_superadmin=True)


def test_demo_tier_does_not_bypass_real_subscription_permissions():
    assert capabilities('demo') == set()


def test_payment_required_payload_names_minimum_tier():
    payload = capability_access_payload({'capabilities': ['maps']}, 'influencers')
    assert payload['allowed'] is False
    assert payload['required_tier'] == 'professional'
    assert payload['required_tier_name'] == 'Привлечение'
