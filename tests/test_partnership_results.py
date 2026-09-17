import pytest
from services.partnership_results import change_agreement, instruction_draft, is_confirmed_partner, result_counts


def test_existing_partner_counts_without_approving_unknown_terms():
    partner = {'id': 'w1', 'company_id': 'c1', 'agreement_json': {'relationship_status': 'confirmed', 'status': 'needs_confirmation'}}
    assert is_confirmed_partner(partner)
    counts = result_counts([partner, {**partner, 'id': 'w2'}, {'id': 'candidate', 'agreement_json': {}}])
    assert counts['partners'] == 1
    assert counts['launched'] == 0
    assert counts['launch_unrecorded'] == 2
    assert counts['needs_decision'] == 2
    with pytest.raises(ValueError):
        change_agreement(partner['agreement_json'], 'prepare_instruction', {'revision': 0}, 'owner')


def test_editing_terms_does_not_erase_existing_partnership():
    old = {'status': 'confirmed', 'revision': 1, 'terms_version': 1, 'terms': {'details': 'Old'}}
    updated = change_agreement(old, 'save', {'revision': 1, 'terms': {'details': 'New'}}, 'owner')
    assert is_confirmed_partner({'agreement_json': updated})
    assert updated['status'] == 'needs_confirmation'


def test_confirmation_is_explicit_and_replay_safe():
    saved = change_agreement({}, 'save', {'revision': 0, 'terms': {'details': 'Обмен рекомендациями'}}, 'owner')
    assert saved['status'] == 'needs_confirmation'
    confirmed = change_agreement(saved, 'confirm', {'revision': 1}, 'owner')
    assert confirmed['status'] == 'confirmed'
    assert change_agreement(confirmed, 'confirm', {'revision': 2}, 'owner') == confirmed
    with pytest.raises(ValueError):
        change_agreement(confirmed, 'save', {'revision': 0}, 'owner')


def test_terms_change_invalidates_instruction_without_losing_history():
    saved = change_agreement({}, 'save', {'revision': 0, 'terms': {'details': 'Условия'}}, 'owner')
    confirmed = change_agreement(saved, 'confirm', {'revision': 1}, 'owner')
    draft = change_agreement(confirmed, 'prepare_instruction', {'revision': 2}, 'owner')
    approved = change_agreement(draft, 'approve_instruction', {'revision': 3}, 'owner')
    updated = change_agreement(approved, 'save', {'revision': 4, 'terms': {'details': 'Новые условия'}}, 'owner')
    assert updated['instruction'] == approved['instruction']
    assert updated['instruction_terms_version'] != updated['terms_version']
    assert updated['history'][-1]['previous']['instruction']
    with pytest.raises(ValueError):
        change_agreement(updated, 'approve_instruction', {'revision': 5}, 'owner')


def test_draft_does_not_invent_terms():
    draft = instruction_draft({'our_actions': 'Выдать купон', 'client_benefit': 'Скидка 5% на массаж'})
    assert 'Скидка 5%' in draft
    assert 'Не указано' in draft
    assert '10%' not in draft
