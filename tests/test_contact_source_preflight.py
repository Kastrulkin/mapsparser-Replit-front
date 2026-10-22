from unittest.mock import Mock
import pytest
from services import contact_intelligence_service as service

@pytest.mark.parametrize('fact',['Page title: QA Clinic','Public contact/company context from source HTML:','Main page content: <html>','://example.invalid/contact'])
def test_rejects_saved_source_metadata_before_ai(monkeypatch,fact):
    generator=Mock();reviewer=Mock();generation=Mock()
    monkeypatch.setattr(service,'build_first_message',lambda *args:'Not sent')
    monkeypatch.setattr(service,'generate_personalized_sequence',generation)
    with pytest.raises(service.MessageQualityError,match='содержательный факт'):
        service.prepare_first_message({'name':'QA'},{},{'source_urls':['https://example.invalid']},{},{},{'observed_fact':fact,'source_url':'https://example.invalid'},use_ai=True,generator=generator,reviewer=reviewer)
    generation.assert_not_called();generator.assert_not_called();reviewer.assert_not_called()
