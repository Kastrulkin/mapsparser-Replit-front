import pytest
from cryptography.fernet import Fernet

from services.pii_protection import operator_context
from services.pii_protection.gateway import MemoryStore, PIIProtectionError, ProtectionService, Scope
from services.pii_protection.admission import AdmissionLimiter
from services.pii_protection.engines import EngineResult


class Cursor:
    def __init__(self, rows):
        self.rows = rows
        self.queries = []

    def execute(self, sql, parameters):
        self.queries.append((sql, parameters))

    def fetchall(self):
        return self.rows


def test_public_source_is_authorized_bound_and_not_a_profile_or_payload(monkeypatch):
    from services import operator_audio
    calls = []
    monkeypatch.setattr(operator_audio, 'authorize_actor', lambda *args, **kwargs: calls.append((args, kwargs)))
    rows = [{'id': 'synthetic-card', 'business_id': 'synthetic-b', 'url': 'https://yandex.ru/maps/org/123/',
             'title': 'Louis Vuitton', 'address': 'Пушкинская улица, 1', 'phone': '+79990000000'}]
    cursor = Cursor(rows)
    values = operator_context.load_public_cards(cursor, 'synthetic-b', 'synthetic-u')
    assert [v.kind for v in values] == ['ORGANIZATION', 'ADDRESS']
    assert calls[0][0][1:] == ('synthetic-u', 'synthetic-b')
    assert cursor.queries[0][1] == ('synthetic-b', 'synthetic-b')
    assert 'JOIN businessmaplinks' in cursor.queries[0][0]
    assert all(v.source_id == 'cards:synthetic-card' for v in values)
    for change in [{'business_id': 'foreign'}, {'url': 'https://evil.invalid/maps/'},
                   {'url': 'https://yandex.ru.evil.invalid/maps/'}, {'url': 'http://yandex.ru/maps/'},
                   {'url': 'https://user:pass@yandex.ru/maps/'}, {'id': 'unsafe\nsource'}]:
        assert not operator_context.load_public_cards(Cursor([{**rows[0], **change}]), 'synthetic-b', 'synthetic-u')


def test_denied_actor_never_loads_cards(monkeypatch):
    from services import operator_audio
    def denied(*args, **kwargs):
        raise PermissionError('synthetic denial')
    monkeypatch.setattr(operator_audio, 'authorize_actor', denied)
    cursor = Cursor([])
    with pytest.raises(PermissionError):
        operator_context.load_public_cards(cursor, 'synthetic-b', 'synthetic-u')
    assert cursor.queries == []


def test_public_ranges_only_cover_inserted_source_and_are_request_bound(monkeypatch):
    monkeypatch.setenv('PII_PROTECTION_ENABLED', 'true')
    value = operator_context.PublicCardValue('synthetic-b', 'cards:1', 'ORGANIZATION', 'Louis Vuitton')
    token = operator_context.PUBLIC_CARDS.set(('synthetic-b', 'synthetic-u', (value,)))
    try:
        original = 'Private client: Louis Vuitton'
        prompt, spans = operator_context.public_planner_prompt(original, 'synthetic-b', 'synthetic-u')
        assert len(spans) == 1 and spans[0].start > len(original)
        assert prompt[spans[0].start:spans[0].end] == 'Louis Vuitton'
        assert operator_context.public_planner_prompt(original, 'foreign', 'synthetic-u') == (original, ())
        assert operator_context.public_planner_prompt(original, 'synthetic-b', 'foreign') == (original, ())
        monkeypatch.setenv('PII_PROTECTION_ENABLED', 'false')
        assert operator_context.public_planner_prompt(original, 'synthetic-b', 'synthetic-u') == (original, ())
    finally:
        operator_context.PUBLIC_CARDS.reset(token)


@pytest.mark.parametrize('name,risk,approval,field', [
    ('communications.draft', 'draft_only', False, 'message'),
    ('communications.prepare_send', 'external_send_request', True, 'message'),
    ('settings.prepare_user', 'access_change', True, 'email'),
    ('finance.prepare_transaction', 'financial_write_request', True, 'description'),
])
def test_restoration_rules_are_tied_to_exact_contract(name, risk, approval, field):
    tool = {'name': name, 'risk_class': risk, 'approval_required': approval,
            'input_schema': {'properties': {field: {'type': 'string'}, 'url': {'type': 'string'}}},
            'pii_restore_fields': ('url', 'business_id')}
    assert operator_context.tool_restore_fields(tool) == (field,)
    assert operator_context.tool_restore_fields({**tool, 'name': 'unreviewed'}) == ()
    assert operator_context.tool_restore_fields({**tool, 'risk_class': 'external_write'}) == ()
    assert operator_context.tool_restore_fields({**tool, 'input_schema': {'properties': {field: {'type': 'object'}}}}) == ()


def test_nested_values_cannot_smuggle_routing_inside_allowed_text_field():
    class Engine:
        def scan(self, text):
            return EngineResult(text, [])
    service = ProtectionService(Engine(), MemoryStore(), Fernet.generate_key())
    scope = Scope('synthetic-b', 'synthetic-u', 'synthetic-s')
    token = service.issue(scope, 'EMAIL', 'synthetic@example.invalid')
    from services.pii_protection.gateway import Exchange
    exchange = Exchange(service, scope, token, frozenset({token}), 1)
    with pytest.raises(PIIProtectionError, match='PII_TOOL_ARGUMENT_DENIED'):
        exchange.restore_tool('communications.draft', {'message': {'url': token}}, scope=scope,
                              allowed_fields=('message',), authorized=True, operation='preview')


def test_contact_references_cannot_bypass_privacy_restoration():
    from services.operator_context import PlannerContext
    context = PlannerContext('email', contact_references=False)
    email = 'synthetic@example.invalid'
    assert context.encode(email) == email
    assert context.decode('@ref1') == '@ref1'
    legacy = PlannerContext('email')
    assert legacy.encode(email) == '@ref1' and legacy.decode('@ref1') == email


def test_global_and_business_limits_refill_without_tenant_identifiers():
    now = [0.0]
    limit = AdmissionLimiter({'bearer_token': 'synthetic-only', 'protect_rps': 4, 'protect_burst': 2,
                              'business_protect_rps': 2, 'business_protect_burst': 1}, clock=lambda: now[0])
    assert limit.admit('synthetic-one')
    assert not limit.admit('synthetic-one')
    assert limit.admit('synthetic-two')
    assert not limit.admit('synthetic-three')
    now[0] = 0.5
    assert limit.admit('synthetic-one')
    assert limit.status()['rate_limited'] == 2
    assert all(isinstance(key, bytes) and len(key) == 32 for key in limit.businesses)


@pytest.mark.parametrize('changes', [{'protect_rps': True}, {'protect_rps': float('nan')},
    {'protect_rps': 0}, {'protect_burst': 0}, {'business_protect_rps': 101}, {'business_protect_burst': 51}])
def test_bad_limit_configuration_fails_closed(changes):
    with pytest.raises(PIIProtectionError, match='PII_RUNTIME_CONFIGURATION_REQUIRED'):
        AdmissionLimiter({'bearer_token': 'synthetic-only', **changes})


def test_admission_identity_table_is_bounded_and_old_entries_expire():
    now = [0.0]
    limit = AdmissionLimiter({'bearer_token': 'synthetic-only'}, clock=lambda: now[0])
    for number in range(1100):
        limit.admit('synthetic-' + str(number))
    assert len(limit.businesses) == 1024
    now[0] = 61
    assert limit.admit('synthetic-new')
    assert len(limit.businesses) == 1
