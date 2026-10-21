import json
from unittest.mock import Mock

import pytest
import requests
from services.operator_speechkit import SpeechKit


def response(status, value):
    result = requests.Response()
    result.status_code = status
    result.encoding = 'utf-8'
    result._content = value.encode('utf-8')
    return result


def recognizer(monkeypatch, operation, result):
    provider = SpeechKit.__new__(SpeechKit)
    provider.headers = {'Authorization': 'Api-Key test-only'}
    provider._json = Mock(return_value=operation)
    get = Mock(return_value=result)
    monkeypatch.setattr(requests, 'get', get)
    return provider, get


def final(text):
    return json.dumps({'result': {'audioCursors': {'finalIndex': '0'}, 'final': {'alternatives': [{'text': text}]}}})


def test_ready_transcript_is_not_blocked_by_delayed_operation_metadata(monkeypatch):
    provider, get = recognizer(monkeypatch, {'done': False}, response(200, final('Проверяем чистоту окон')))
    assert provider.result('existing-operation') == 'Проверяем чистоту окон'
    get.assert_called_once()


def test_ready_transcript_survives_unavailable_operation_metadata(monkeypatch):
    provider, _ = recognizer(monkeypatch, {}, response(200, final('Фокус дня')))
    provider._json.side_effect = ValueError('Сервис речи временно недоступен')
    assert provider.result('existing-operation') == 'Фокус дня'


@pytest.mark.parametrize('status', [400, 404, 409, 425, 503])
def test_pending_recognition_remains_pending_for_known_running_operation(monkeypatch, status):
    provider, get = recognizer(monkeypatch, {'done': False}, response(status, '{}'))
    assert provider.result('existing-operation') is None
    get.assert_called_once()


def test_pending_metadata_does_not_hide_authentication_failure(monkeypatch):
    provider, _ = recognizer(monkeypatch, {'done': False}, response(403, '{}'))
    with pytest.raises(ValueError, match='получить расшифровку'):
        provider.result('existing-operation')


def test_confirmed_provider_error_is_not_overridden_by_transcript(monkeypatch):
    provider, get = recognizer(monkeypatch, {'done': True, 'error': {'code': 7}}, response(200, final('text')))
    with pytest.raises(ValueError, match='Не удалось распознать'):
        provider.result('existing-operation')
    get.assert_not_called()


def test_final_refinement_replaces_original_text(monkeypatch):
    normalized = {'result': {'finalRefinement': {'finalIndex': '0', 'normalizedText': {'alternatives': [{'text': 'Выручка 500 рублей'}]}}}}
    provider, _ = recognizer(monkeypatch, {'done': True}, response(200, final('выручка пятьсот рублей')+'\n'+json.dumps(normalized)))
    assert provider.result('existing-operation') == 'Выручка 500 рублей'


def test_completed_empty_result_is_distinct_from_pending_empty_result(monkeypatch):
    provider, _ = recognizer(monkeypatch, {'done': True}, response(200, ''))
    assert provider.result('existing-operation') == ''
    provider._json.return_value = {'done': False}
    assert provider.result('existing-operation') is None


def test_bad_recognition_json_is_not_success(monkeypatch):
    provider, _ = recognizer(monkeypatch, {'done': True}, response(200, '{broken'))
    with pytest.raises(ValueError, match='получить расшифровку'):
        provider.result('existing-operation')
