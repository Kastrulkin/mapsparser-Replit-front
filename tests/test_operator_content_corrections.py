import pytest
from tests.test_operator_editorial_pg import editorial
from tests.test_operator_voice_pg import pg
from services import operator_content_corrections


def test_corrections_stale_preview_and_published_guard(editorial):
    _,c=editorial
    c.execute('CREATE TABLE usernews(id TEXT PRIMARY KEY,business_id TEXT,source_text TEXT,generated_text TEXT,approved INT DEFAULT 0,edited_before_approve BOOLEAN DEFAULT FALSE,updated_at TIMESTAMPTZ DEFAULT NOW(),created_at TIMESTAMPTZ DEFAULT NOW())')
    c.execute("INSERT INTO usernews(id,business_id,source_text,generated_text) VALUES ('n','b','Акция','Акция до 12 октября')")
    records=operator_content_corrections.context(c,'b','u',{})['drafts']
    news=next(row for row in records if row['id']=='n')
    item=next(row for row in records if row['id']=='i')
    message='Акция заканчивается 11 октября. Исправь черновики'
    args={'quote':message,'changes':[{'kind':'news','id':'n','version':news['version'],'text':'Акция до 11 октября'},{'kind':'item','id':'i','version':item['version'],'theme':'Совет по уходу'}]}
    preview=operator_content_corrections.prepare(c,'b','u',message,args)['approval']['envelope']
    c.execute("UPDATE usernews SET generated_text='Изменено другим пользователем' WHERE id='n'")
    with pytest.raises(ValueError,match='изменился'):operator_content_corrections.apply(c,'b','u',preview)
    c.execute("SELECT theme FROM contentplanitems WHERE id='i'");assert c.fetchone()['theme']=='Тема А'
    news=next(row for row in operator_content_corrections.context(c,'b','u',{})['drafts'] if row['id']=='n')
    args['changes'][0]['version']=news['version']
    preview=operator_content_corrections.prepare(c,'b','u',message,args)['approval']['envelope']
    operator_content_corrections.apply(c,'b','u',preview)
    c.execute("SELECT generated_text,approved FROM usernews WHERE id='n'");row=c.fetchone()
    assert row['generated_text']=='Акция до 11 октября' and row['approved']==0
    c.execute("SELECT theme,metadata_json FROM contentplanitems WHERE id='i'");row=c.fetchone()
    assert row['theme']=='Совет по уходу' and row['metadata_json']['operator_edit_history'][0]['draft_text']=='Предыдущий текст'
    with pytest.raises(ValueError):operator_content_corrections.load(c,'b',{'kind':'item','id':'pub'})


def test_expired_promotion_cannot_remain_in_later_plan_item(editorial):
    _,c=editorial
    c.execute("UPDATE contentplanitems SET scheduled_for='2026-10-12' WHERE id='i'")
    row=operator_content_corrections.load(c,'b',{'kind':'item','id':'i'})
    message='Акция заканчивается 11 октября 2026, а не 12 октября. Исправь план'
    args={'quote':message,'promotion_end':'2026-10-11','changes':[{'kind':'item','id':'i','version':operator_content_corrections.operator_editorial._version(row),'theme':'Последний день акции 11 октября со скидкой 10%'}]}
    preview=operator_content_corrections.prepare(c,'b','u',message,args)
    assert 'скидк' not in preview['approval']['envelope']['changes'][0]['theme'].lower()
    assert 'text' not in preview['approval']['envelope']['changes'][0]
    args['changes'][0]['theme']='Совет по уходу за шерстью'
    assert operator_content_corrections.prepare(c,'b','u',message,args)['status']=='approval_required'
