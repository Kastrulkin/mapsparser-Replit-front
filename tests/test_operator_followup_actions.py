from services.operator_tool_loop import run_operator_tool_loop
from services.operator_finance_amounts import daily_statement
from services.llm.policy import prepare_prompt_for_provider
from services.operator_tool_loop import _planner_prompt
import json


def test_privacy_filter_preserves_planner_catalog_and_redacts_sensitive_values():
    state={'message':'Перенеси напоминание на завтра','tools':[{'name':'finance.prepare','description':'Вносит транзакцию','input_schema':{'type':'object','properties':{'amount':{'type':'integer'}}}}, {'name':'work.read_owner_actions','input_schema':{'type':'object','properties':{}}}], 'observations':[{'bank_details':'Банковский счёт 123456789','email':'anna@example.com'}]}
    result=prepare_prompt_for_provider(_planner_prompt(state),provider='deepseek',data_class='business_internal')
    parsed=json.loads(result.prompt.splitlines()[-1])
    assert parsed['message']==state['message']
    assert parsed['tools'][1]['name']=='work.read_owner_actions'
    assert parsed['tools'][0]['input_schema']==state['tools'][0]['input_schema']
    assert '123456789' not in result.prompt and 'anna@example.com' not in result.prompt
    assert parsed['observations'][0]['bank_details']=='[SENSITIVE_CONTEXT_REDACTED]'


def test_compound_does_not_end_after_first_deterministic_write():
    calls=[]
    def planner(state):
        if not state['observations']:
            return {'action':'tool_call','tool':'save','arguments':{},'remaining_actions':['Подготовить пост']}
        if len(state['observations'])==1:
            return {'action':'tool_call','tool':'post','arguments':{},'remaining_actions':[]}
        return {'action':'final','message':'Оба шага выполнены','remaining_actions':[]}
    def handler(name):
        def execute(args):
            calls.append(name)
            return {'status':'completed','chat_response':name}
        return execute
    tools=[{'name':name,'risk_class':'internal_observation_write','deterministic_response':True,'execute':handler(name)} for name in ('save','post')]
    result=run_operator_tool_loop(business_id='b',user_id='u',message='Сохрани кресла и подготовь пост',tools=tools,planner=planner)
    assert calls==['save','post'] and result['status']=='completed'


def test_requested_mutation_does_not_stop_at_read():
    decisions=iter([{'action':'tool_call','tool':'read','arguments':{}},{'action':'clarification','message':'Какую задачу?'}])
    result=run_operator_tool_loop(business_id='b',user_id='u',message='Закрой задачу',tools=[{'name':'read','risk_class':'read_only','deterministic_response':True,'execute':lambda args:{'status':'completed','chat_response':'Список'}}],planner=lambda state:next(decisions))
    assert result['status']=='clarification_required'


def test_finance_correction_uses_new_values():
    value=daily_statement('Я ошибся: за сегодня выручка 15000 рублей и 7 чеков, а не 12000 рублей и 6 чеков. Исправь дневной итог, не добавляй вторую продажу.')
    assert value['values']['revenue']=='15000' and value['values']['checks']=='7' and value['mode']=='set'
    value=daily_statement('Исправь и сохрани дневной итог за 2026-10-09: выручка 15000 RUB, 7 чеков. Это замена сохранённого итога 12000 RUB и 6 чеков.')
    assert value['date']=='2026-10-09' and value['values']['checks']=='7'


def test_compound_prepares_draft_before_approval():
    calls=[]
    decisions=iter([{'action':'tool_call','tool':'approve','arguments':{},'remaining_actions':['Создать пост']},{'action':'tool_call','tool':'post','arguments':{},'remaining_actions':['Подготовить подтверждение']},{'action':'tool_call','tool':'approve','arguments':{},'remaining_actions':[]}])
    tools=[{'name':'approve','approval_required':True,'prepare_approval':lambda args:calls.append('approve') or {'status':'approval_required','chat_response':'Подтвердите'}},{'name':'post','risk_class':'paid_compute','deterministic_response':True,'execute':lambda args:calls.append('post') or {'status':'completed','chat_response':'Черновик создан'}}]
    result=run_operator_tool_loop(business_id='b',user_id='u',message='Создай пост и напоминание',tools=tools,planner=lambda state:next(decisions))
    assert calls==['post','approve']
    assert result['status']=='approval_required' and 'Черновик создан' in result['chat_response']


def test_post_cannot_offer_capacity_outside_opening_hours():
    import pytest
    from services.operator_social_post_generation import validate_operating_window
    hours={'time':'11:00','end':'16:00'}
    validate_operating_window('Свободны два кресла с 14:00 до 16:00',hours)
    with pytest.raises(ValueError):validate_operating_window('Свободны два кресла с 14:00 до 17:00',hours)
    with pytest.raises(ValueError):validate_operating_window('Свободны два кресла',{'closed':True})


def test_validation_feedback_revises_preview_without_applying():
    def prepare(args):
        if args['theme']=='Скидка':return {'status':'error','retryable_preparation':True,'chat_response':'После окончания нужен совет'}
        return {'status':'approval_required','chat_response':'Совет: подтвердите'}
    decisions=iter([{'action':'tool_call','tool':'prepare','arguments':{'theme':'Скидка'}},{'action':'tool_call','tool':'prepare','arguments':{'theme':'Совет'}}])
    result=run_operator_tool_loop(business_id='b',user_id='u',message='Исправь план',tools=[{'name':'prepare','approval_required':True,'deterministic_preparation_response':True,'input_schema':{'properties':{'theme':{'type':'string'}}},'prepare_approval':prepare}],planner=lambda state:next(decisions))
    assert result['status']=='approval_required' and result['tool_calls']==2


def test_plan_constraint_is_not_a_request_to_write_a_permanent_rule():
    result=run_operator_tool_loop(business_id='b',user_id='u',message='Дай план на два часа. Не предлагай окна вне графика.',tools=[{'name':'plan','risk_class':'read_only','deterministic_response':True,'execute':lambda args:{'status':'completed','chat_response':'План на 120 минут'}}],planner=lambda state:({'action':'final','message':'План на 120 минут','remaining_actions':[]} if state['observations'] else {'action':'tool_call','tool':'plan','arguments':{},'remaining_actions':[]}))
    assert result['status']=='completed' and result['chat_response']=='План на 120 минут'


def test_selected_context_does_not_change_literal_command():
    message='Прочитай выбранный файл'
    def planner(state):
        assert state['message']==message
        assert state['input_context']['attachment_ids']==['attachment-1']
        return {'action':'final','message':'Данные файла','remaining_actions':[]} if state['observations'] else {'action':'tool_call','tool':'read','arguments':{},'remaining_actions':[]}
    result=run_operator_tool_loop(business_id='b',user_id='u',message=message,input_context={'attachment_ids':['attachment-1']},tools=[{'name':'read','risk_class':'read_only','deterministic_response':True,'execute':lambda args:{'status':'completed','chat_response':'Данные файла'}}],planner=planner)
    assert result['status']=='completed'


def test_current_preview_is_not_an_unfinished_followup():
    result=run_operator_tool_loop(business_id='b',user_id='u',message='Исправь черновики',tools=[{'name':'prepare','approval_required':True,'prepare_approval':lambda args:{'status':'approval_required','chat_response':'Проверьте изменения'}}],planner=lambda state:{'action':'tool_call','tool':'prepare','arguments':{},'remaining_actions':['prepare']})
    assert result['status']=='approval_required' and result['remaining_actions']==[]


def test_remaining_steps_are_constrained_to_catalog_names(monkeypatch):
    from services import operator_tool_loop
    from services.llm import LLMTaskResult
    captured=[]
    monkeypatch.setattr(operator_tool_loop,'run_llm_task',lambda request:captured.append(request) or LLMTaskResult(status='completed',parsed_data={'action':'final','message':'Готово','remaining_actions':[]}))
    operator_tool_loop.plan_operator_step({'tools':[{'name':'read'},{'name':'prepare'}]})
    assert captured[0].response_schema['properties']['remaining_actions']['items']['enum']==['read','prepare']


def test_compound_reads_do_not_finish_after_first_deterministic_result():
    calls=[]
    decisions=iter([{'action':'tool_call','tool':'tasks','arguments':{},'remaining_actions':[]},
                    {'action':'tool_call','tool':'finance','arguments':{},'remaining_actions':[]},
                    {'action':'final','message':'Задача завершена; 15000 рублей, 7 чеков','remaining_actions':[]}])
    def execute(name):
        def call(args):
            calls.append(name)
            return {'status':'completed','chat_response':name}
        return call
    result=run_operator_tool_loop(business_id='b',user_id='u',message='Покажи продажи и задачи',tools=[{'name':name,'risk_class':'read_only','deterministic_response':True,'execute':execute(name)} for name in ['tasks','finance']],planner=lambda state:next(decisions))
    assert calls==['tasks','finance']
    assert result['status']=='completed'
    assert '15000' in result['chat_response']
