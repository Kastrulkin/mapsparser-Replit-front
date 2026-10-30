from services.client_agent_settings import saved_client_settings

def test_saved_preferences_override_legacy_and_select_enabled_role():
    value = saved_client_settings({'booking_agent': {'enabled': False}, 'marketing_agent': {'enabled': True, 'agent_id': 'm', 'tone': 'friendly', 'language': 'en', 'variables': {'text': 'No discounts'}}})
    assert value['agent_type'] == 'marketing'
    assert value['tone'] == 'friendly'
    assert value['restrictions']['text'] == 'No discounts'

def test_sandbox_resolves_selected_disabled_agent_without_enabling_it():
    value = saved_client_settings({'booking_agent': {'enabled': False, 'agent_id': 'b', 'language': 'en'}}, agent_id='b')
    assert value['language'] == 'en'
    assert saved_client_settings({'booking_agent': {'enabled': False, 'agent_id': 'b'}}) is None

def test_invalid_config_and_unknown_selection_do_not_choose_another_agent():
    assert saved_client_settings('{') is None
    assert saved_client_settings({'booking_agent': {'enabled': True, 'agent_id': 'b'}}, agent_id='other') is None
