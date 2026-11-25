from services import initial_business_setup, operator_core


def test_explicit_initial_setup_command_bypasses_paid_tool_planner(monkeypatch):
    calls = []
    planner_calls = []

    def start(_cursor, **arguments):
        calls.append(arguments)
        return {
            'status': 'queued',
            'chat_response': 'Первичная настройка начата.',
            'external_writes_performed': False,
            'credit_charged': False,
        }

    monkeypatch.setattr(initial_business_setup, 'start_from_operator', start)
    result, pending = operator_core.route_operator_message(
        object(),
        business_id='business-1',
        user_id='user-1',
        message=(
            'https://yandex.ru/maps/org/mimika/236225549064/ '
            'Добавь компанию, проведи первичную настройку'
        ),
        channel='web',
        actor_context={'is_superadmin': True},
        tool_planner=lambda state: planner_calls.append(state) or {'action': 'final', 'message': 'unused'},
    )

    assert result['status'] == 'queued'
    assert result['capability'] == 'business.initial_setup'
    assert result['credit_charged'] is False
    assert calls[0]['business_id'] == 'business-1'
    assert calls[0]['actor_context'] == {'is_superadmin': True}
    assert planner_calls == []
    assert pending == {}


def test_initial_setup_intent_requires_link_and_explicit_setup_wording():
    assert operator_core._is_initial_setup_intent(
        'https://yandex.ru/maps/org/example/1 Начни первичную настройку'
    )
    assert not operator_core._is_initial_setup_intent('Начни первичную настройку')
    assert not operator_core._is_initial_setup_intent('https://yandex.ru/maps/org/example/1 Обнови отзывы')


def test_operator_setup_reuses_staged_setup_and_queues_its_source(monkeypatch):
    from services import business_permissions

    row = {'business_id': 'business-1', 'data': {'sources': {}}}
    saved = []
    permission_checks = []
    monkeypatch.setattr(business_permissions, 'load_actor', lambda _cursor, _user_id: {'user_id': 'user-1'})
    monkeypatch.setattr(
        business_permissions,
        'require_permission',
        lambda _cursor, business_id, _actor, permission: permission_checks.append((business_id, permission)),
    )
    monkeypatch.setattr(initial_business_setup, 'actor_allowed', lambda *_args: True)
    monkeypatch.setattr(initial_business_setup, 'read_business', lambda *_args, **_kwargs: {'id': 'business-1'})
    monkeypatch.setattr(initial_business_setup, 'load', lambda *_args, **_kwargs: row)
    monkeypatch.setattr(initial_business_setup, 'seed_profile_sources', lambda *_args: None)

    def add_source(_cursor, current, _actor, _profile, payload):
        current['data']['sources']['map'] = {'status': 'queued'}
        assert '236225549064' in payload['message']
        return 'Ссыла добавлена.'

    monkeypatch.setattr(initial_business_setup, 'message', add_source)
    monkeypatch.setattr(initial_business_setup, 'persist', lambda _cursor, current: saved.append(current))
    result = initial_business_setup.start_from_operator(
        object(),
        'business-1',
        'user-1',
        'https://yandex.ru/maps/org/mimika/236225549064/ Проведи первичную настройку',
        {'is_superadmin': True},
    )

    assert result['status'] == 'queued'
    assert result['credit_charged'] is False
    assert result['result_ref']['href'].endswith('business_id=business-1')
    assert row['data']['started'] is True
    assert saved == [row]
    assert permission_checks == [('business-1', 'business.settings.write')]
