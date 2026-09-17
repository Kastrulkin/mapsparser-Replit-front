import json
import pytest
from tests.test_operator_voice_pg import pg
from tests.test_operator_editorial_pg import editorial
from services import operator_followups, operator_chat_service, operator_tool_billing, operator_tool_loop, operator_audio


@pytest.mark.parametrize('channel',['web','telegram','telegram_mini_app'])
@pytest.mark.parametrize('voice',[False,True])
@pytest.mark.parametrize('prefix',['','Пожалуйста, '])
def test_selected_post_followup_persists_and_deduplicates(editorial,monkeypatch,channel,voice,prefix):
    conn,c=editorial
    from services import operator_social_post_generation,operator_news_generation,work_journal
    monkeypatch.setattr(work_journal,'enabled',lambda b:False)
    monkeypatch.setattr(operator_news_generation,'_load_business_context',lambda *a:{})
    monkeypatch.setattr(operator_social_post_generation,'_default_social_post_generator',lambda *a,**kw:json.dumps({'post':'Рекламный пост о путешествии на Пхукет. Подробности поездки уточняйте при бронировании.'}))
    def paid(cursor,**kwargs):
        return operator_tool_loop.run_operator_tool_loop(**kwargs)
    monkeypatch.setattr(operator_tool_billing,'run_paid_operator_tool_loop',paid)
    monkeypatch.setattr(operator_audio,'consume_transcription',lambda *a:None)
    def router(cursor,**kw):
        if kw['message']=='Покажи пост':
            return {'status':'completed','resource':'content','items':[{'kind':'content_plan_item','id':'i','plan_id':'p'}],'chat_response':'Предыдущий текст'},{}
        return operator_followups.route(cursor,business_id='b',user_id='u',channel=channel,message=kw['message'],history=kw['conversation_history'],conversation_id=kw['conversation_id'],payload=kw['action_payload'],actor={},access=None)
    common=dict(business_id='b',user_id='u',channel=channel,router=router)
    first=operator_chat_service._process_chat(c,**common,message='Покажи пост',payload={'request_id':'read'})
    assert first['selected_item']['item_id']=='i'
    payload={'request_id':'rewrite','conversation_id':first['conversation_id']}
    if voice:payload['transcription_id']='fixture-transcript'
    result=operator_chat_service._process_chat(c,**common,message=prefix+'Придумай вместо него рекламный пост про Пхукет',payload=payload)
    assert result['status']=='completed'
    assert result['selected_item']['item_id']=='i'
    duplicate=operator_chat_service._process_chat(c,**common,message=prefix+'Придумай вместо него рекламный пост про Пхукет',payload=payload)
    assert duplicate['idempotent'] is True
    c.execute("SELECT draft_text,metadata_json FROM contentplanitems WHERE id='i'")
    row=c.fetchone();assert 'Пхукет' in row['draft_text']
    assert len(row['metadata_json']['operator_edit_history'])==1
    restored=operator_chat_service._process_chat(c,**common,message=prefix+'Верни предыдущую версию этого поста',payload={'request_id':'restore','conversation_id':first['conversation_id']})
    assert restored['status']=='completed'
    c.execute("SELECT draft_text FROM contentplanitems WHERE id='i'")
    assert c.fetchone()['draft_text']=='Предыдущий текст'


def test_selection_version_rejects_concurrent_edit(editorial,monkeypatch):
    from services import operator_editorial,work_journal
    _,c=editorial
    value={'resource':'content','items':[{'kind':'content_plan_item','id':'i','plan_id':'p'}]}
    operator_followups.remember_selection(c,'b',value)
    c.execute("UPDATE contentplanitems SET goal='Другой автор изменил пост' WHERE id='i'")
    result=operator_editorial.rewrite_item(c,'b','u','Перепиши этот пост',value['selected_item'])
    assert result['status']=='blocked'
    c.execute("SELECT draft_text FROM contentplanitems WHERE id='i'")
    assert c.fetchone()['draft_text']=='Предыдущий текст'


def test_multiple_posts_do_not_set_implicit_selection(editorial):
    _,c=editorial
    result={'resource':'content','items':[{'kind':'content_plan_item','id':'i','plan_id':'p'},{'kind':'content_plan_item','id':'j','plan_id':'p'}]}
    operator_followups.remember_selection(c,'b',result)
    assert 'selected_item' not in result


def test_rewrite_preserves_booking_url_in_saved_draft(editorial,monkeypatch):
    from services import operator_editorial,operator_social_post_generation,operator_news_generation
    _,c=editorial
    url='https://riderra.com/ru?lang=ru'
    c.execute("UPDATE contentplanitems SET draft_text=%s WHERE id='i'",('Закажите трансфер: '+url,))
    monkeypatch.setattr(operator_news_generation,'_load_business_context',lambda *a:{})
    monkeypatch.setattr(operator_social_post_generation,'_default_social_post_generator',lambda *a,**kw:json.dumps({'post':'Закажите трансфер заранее. Бронирование: [ссылка для бронирования].'}))
    target=operator_editorial._items(c,'b','p',item_id='i')[0]
    result=operator_editorial.rewrite_item(c,'b','u','Перепиши короче, оставь ссылку для бронирования',{'plan_id':'p','item_id':'i','version':operator_editorial._version(target)})
    assert result['status']=='completed'
    c.execute("SELECT draft_text,metadata_json FROM contentplanitems WHERE id='i'")
    saved=c.fetchone()
    assert url in saved['draft_text'] and '[ссылка' not in saved['draft_text']
    assert url in saved['metadata_json']['operator_edit_history'][0]['draft_text']


def test_translation_retry_writes_one_version(editorial,monkeypatch):
    from services import operator_editorial,operator_social_post_generation,operator_news_generation
    _,c=editorial
    monkeypatch.setattr(operator_news_generation,'_load_business_context',lambda *a:{})
    answers=iter(['Русский текст вместо перевода, это неверный язык и это должно быть отвергнуто.', 'Book your appointment with our beauty salon and discover a carefully selected treatment.'])
    monkeypatch.setattr(operator_social_post_generation,'_default_social_post_generator',lambda *a,**kw:json.dumps({'post':next(answers)}))
    row=operator_editorial._items(c,'b','p',item_id='i')[0]
    value=operator_editorial.rewrite_item(c,'b','u','Переведи этот пост на английский язык',{'item_id':'i','plan_id':'p','version':operator_editorial._version(row)})
    assert value['status']=='completed'
    c.execute("SELECT draft_text,metadata_json FROM contentplanitems WHERE id='i'")
    saved=c.fetchone()
    assert saved['draft_text'].startswith('Book your')
    assert len(saved['metadata_json']['operator_edit_history'])==1
