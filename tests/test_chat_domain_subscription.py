import pytest

from services.operator_core import operator_subscription_block, route_operator_message
from subscription_manager import build_subscription_capabilities


@pytest.mark.parametrize('tier', ['none', 'starter', 'professional', 'concierge'])
def test_chat_help_is_available_on_every_plan(tier):
    access = build_subscription_capabilities(tier=tier, status='active')
    assert operator_subscription_block(access, 'operator.help') is None


@pytest.mark.parametrize('tier,capability,blocked', [
    ('none', 'reviews.reply.draft', True),
    ('starter', 'reviews.reply.draft', False),
    ('starter', 'social_post.generate', True),
    ('starter', 'finance.read', True),
    ('professional', 'partnerships.prepare_message', False),
    ('professional', 'agents.read', True),
    ('concierge', 'finance.read', False),
    ('starter', 'operator.query', True),
])
def test_tools_keep_domain_access(tier, capability, blocked):
    access = build_subscription_capabilities(tier=tier, status='active')
    assert bool(operator_subscription_block(access, capability)) is blocked


def test_unpaid_service_change_is_blocked_before_querying_or_writing():
    result, _ = route_operator_message(
        object(), business_id='test', user_id='owner',
        message='Измени цену услуги Маникюр на 1500', channel='web',
        subscription_access=build_subscription_capabilities(tier='none', status='inactive'),
    )
    assert result['status'] == 'blocked'
    assert result['access']['required_tier'] == 'starter'


def test_maps_plan_cannot_create_social_content_in_chat(monkeypatch):
    def unexpected(**kwargs):
        raise AssertionError('Closed domain handler was called')
    monkeypatch.setattr('services.operator_core._create_content_plan', unexpected)
    result, _ = route_operator_message(
        object(), business_id='test', user_id='owner',
        message='Составь контент-план на 30 дней', channel='web',
        subscription_access=build_subscription_capabilities(tier='starter', status='active'),
    )
    assert result['access']['required_tier'] == 'concierge'


def test_pending_action_rechecks_access_after_downgrade(monkeypatch):
    from services.operator_core import confirm_pending_operator_action
    monkeypatch.setattr('services.operator_core.get_operator_action', lambda *args, **kwargs: {
        'status': 'pending', 'capability': 'social_post.generate', 'envelope_json': {},
    })
    result, replay = confirm_pending_operator_action(
        object(), action_id='pending', business_id='test', user_id='owner',
        subscription_access=build_subscription_capabilities(tier='starter', status='active'),
    )
    assert result['status'] == 'blocked'
    assert result['external_writes_performed'] is False
    assert replay is False
