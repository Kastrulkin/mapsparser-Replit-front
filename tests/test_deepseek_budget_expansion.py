import pytest
from services import ai_spend_budget
budget = ai_spend_budget

def used():
    return {key:0 for key in ('daily_tokens','monthly_tokens','operation_tokens','daily_calls','monthly_calls','operation_calls')}

def test_expanded_deepseek_budget_preserves_other_provider_and_request_guards():
    policy = budget.limits('deepseek')
    assert policy['daily_tokens'] == 1000000
    assert policy['monthly_tokens'] == 3000000
    assert policy['daily_calls'] == 60
    assert policy['monthly_calls'] == 300
    assert policy['request_tokens'] == 150000
    assert budget.limits('gigachat') == budget.DEFAULT_LIMITS
    budget._check({**used(), 'daily_tokens':195472}, policy, 150000)
    with pytest.raises(budget.BudgetDenied):
        budget._check({**used(), 'daily_tokens':900000}, policy, 150000)
    with pytest.raises(budget.BudgetDenied):
        budget._check(used(), policy, 150001)


@pytest.mark.parametrize('key',['daily_tokens','monthly_tokens','operation_tokens','daily_calls','monthly_calls','operation_calls'])
def test_expanded_budget_still_blocks_at_each_limit(key):
    policy = budget.limits('deepseek')
    with pytest.raises(budget.BudgetDenied):
        budget._check({**used(),key:policy[key]},policy,100)
