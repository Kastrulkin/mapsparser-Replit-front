import json
from contextvars import copy_context

import pytest

from services.pii_protection import activation, gateway


@pytest.fixture
def config(tmp_path, monkeypatch):
    path = tmp_path/'activation.json'
    path.write_text(json.dumps({'version': 1, 'enabled': True, 'scope': 'operator_text', 'mode': 'enforce'}))
    path.chmod(0o600)
    monkeypatch.setenv('PII_ACTIVATION_CONFIG_FILE', str(path))
    monkeypatch.setenv('PII_ACTIVATION_REQUIRED', 'true')
    monkeypatch.setenv('PII_PROTECTION_ENABLED', 'false')
    return path


def test_operator_only_activation_and_copied_shadow_context(config):
    assert activation.configuration()['enabled'] and not gateway.enabled()
    token = activation.enter_operator_request()
    try:
        assert gateway.enabled()
        shadow = copy_context()
    finally:
        activation.exit_operator_request(token)
    assert not gateway.enabled() and shadow.run(gateway.enabled)


def test_channel_payload_cannot_disable_operator_protection(config, monkeypatch):
    from services import operator_chat_service
    monkeypatch.setattr(operator_chat_service, '_process_chat_private', lambda *args, **kwargs: gateway.enabled())
    assert operator_chat_service.process_chat(None, channel='max_bot')
    assert not gateway.enabled()


def test_request_exception_resets_activation(config, monkeypatch):
    from services import operator_chat_service
    def failed(*args, **kwargs):
        assert gateway.enabled()
        raise ValueError('synthetic')
    monkeypatch.setattr(operator_chat_service, '_process_chat_private', failed)
    with pytest.raises(ValueError):
        operator_chat_service.process_chat(None)
    assert not gateway.enabled()


def test_enabling_during_an_operator_request_protects_later_attempts(config):
    value = json.loads(config.read_text())
    value['enabled'] = False
    config.write_text(json.dumps(value))
    token = activation.enter_operator_request()
    try:
        assert not gateway.enabled()
        value['enabled'] = True
        config.write_text(json.dumps(value))
        assert gateway.enabled()
    finally:
        activation.exit_operator_request(token)
    assert not gateway.enabled()


def test_missing_required_file_cannot_fall_back_to_plaintext(config):
    config.unlink()
    with pytest.raises(gateway.PIIProtectionError, match='PII_RUNTIME_CONFIGURATION_REQUIRED'):
        activation.enter_operator_request()


def test_copied_container_marker_requires_config_without_environment(config, monkeypatch):
    marker = config.with_name(config.name+'.required')
    marker.write_text('required')
    monkeypatch.delenv('PII_ACTIVATION_REQUIRED')
    config.unlink()
    with pytest.raises(gateway.PIIProtectionError):
        activation.enter_operator_request()


def test_blocked_activation_never_executes_provider(config):
    value = json.loads(config.read_text());value['mode'] = 'blocked';config.write_text(json.dumps(value))
    calls = []
    token = activation.enter_operator_request()
    try:
        result = gateway.run_with_privacy(None, lambda: calls.append('provider'))
    finally:
        activation.exit_operator_request(token)
    assert result.status == 'policy_blocked' and result.fallback_reason == 'PII_ACTIVATION_BLOCKED'
    assert calls == []


def test_recreated_container_without_privacy_profile_fails_closed(config, tmp_path, monkeypatch):
    marker = tmp_path/'deployment-required'
    marker.write_text('operator_text\n')
    monkeypatch.setattr(activation, 'DEPLOYMENT_REQUIRED_FILE', str(marker))
    monkeypatch.delenv('PII_ACTIVATION_REQUIRED')
    monkeypatch.delenv('PII_PROTECTION_ENABLED')
    config.unlink()
    assert not gateway.enabled()
    with pytest.raises(gateway.PIIProtectionError, match='PII_RUNTIME_CONFIGURATION_REQUIRED'):
        activation.enter_operator_request()
    assert not activation.OPERATOR_REQUEST.get()
    assert not gateway.enabled()


@pytest.mark.parametrize('changes', [{'enabled': 'true'}, {'scope': 'arbitrary'}, {'mode': 'plaintext'}, {'extra': True}])
def test_invalid_configuration_fails_closed(config, changes):
    value = json.loads(config.read_text());value.update(changes);config.write_text(json.dumps(value))
    with pytest.raises(gateway.PIIProtectionError, match='PII_ACTIVATION_CONFIGURATION_INVALID'):
        activation.enter_operator_request()


def test_explicit_off_configuration_retains_previous_behavior(config, monkeypatch):
    value = json.loads(config.read_text());value['enabled'] = False;config.write_text(json.dumps(value))
    monkeypatch.setenv('PII_PROTECTION_ENABLED', 'true')
    token = activation.enter_operator_request()
    try:
        assert not gateway.enabled()
    finally:
        activation.exit_operator_request(token)
