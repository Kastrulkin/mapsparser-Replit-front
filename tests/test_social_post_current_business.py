from services import operator_social_post_generation as social

def test_current_business_does_not_require_literal_nominative_in_user_message(monkeypatch):
    monkeypatch.setattr(social,'_load_business_context',lambda *args:{'name':'Органика'})
    monkeypatch.setattr(social,'build_paid_action_preflight',lambda *args,**kwargs:{'status':'blocked','blocked_reasons':['test_stop']})
    result=social.generate_social_post_draft_from_operator(object(),business_id='b',user_id='u',
        message='Создай пост для Органики',original_message='Создай пост для Органики',business_reference='Органика')
    assert result['status']=='blocked'
    assert result['blocked_reasons']==['test_stop']

def test_other_business_still_requires_explicit_reference(monkeypatch):
    monkeypatch.setattr(social,'_load_business_context',lambda *args:{'name':'Органика'})
    result=social.generate_social_post_draft_from_operator(object(),business_id='b',user_id='u',
        message='Создай пост для Органики',original_message='Создай пост для Органики',business_reference='Другой бизнес')
    assert result['status']=='clarification_required'


def test_original_post_task_has_priority_over_reference_topics(monkeypatch):
    import sys
    from types import SimpleNamespace
    from services import operator_editorial,content_rules
    content_generation_context=SimpleNamespace(generation_context=lambda *a,**kw:('',[]))
    monkeypatch.setitem(sys.modules,'services.content_generation_context',content_generation_context)
    monkeypatch.setattr(social,'build_paid_action_preflight',lambda *a,**kw:{'status':'ready'})
    monkeypatch.setattr(social,'reserve_paid_action_credits',lambda *a,**kw:{'status':'reserved','reservation_id':'r'})
    monkeypatch.setattr(social,'finalize_reserved_action_credits',lambda *a,**kw:{'status':'charged','charge_credits':1})
    monkeypatch.setattr(social,'_load_business_context',lambda *a:{'name':'Органика'})
    monkeypatch.setattr(social,'semantic_context_for_cursor',lambda *a,**kw:('Старая тема: расписание',{}))
    monkeypatch.setattr(operator_editorial,'editorial_prompt',lambda *a:'Старая тема: свободные кресла')
    monkeypatch.setattr(content_generation_context,'generation_context',lambda *a,**kw:('Справка о расписании',[]))
    monkeypatch.setattr(content_rules,'enforce',lambda *a:a[3])
    monkeypatch.setattr(social,'_insert_news_draft',lambda *a,**kw:{'id':'d','generated_text':kw['generated_text']})
    prompts=[]
    def generate(prompt,**kwargs):
        prompts.append(prompt)
        return '{"post":"Три шага: запишите задачи, выберите главное, проверьте результат."}'
    request='Для Органики: три шага, чтобы не держать задачи в голове.'
    result=social.generate_social_post_draft_from_operator(object(),business_id='b',user_id='u',message='Создай пост по теме управления задачами',original_message=request,post_generator=generate)
    assert result['status']=='completed'
    assert prompts[0].endswith(request)
    assert prompts[0].rfind(request)>prompts[0].find('Справка о расписании')
    assert 'item_type=news_draft' in result['result_ref']['href']
