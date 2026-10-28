from services.operator_mobile_deep_links import resolve_mobile_deep_link
from services.operator_mini_app_links import result_mini_app_url
from urllib.parse import urlsplit,parse_qs

class Cursor:
    def execute(self,query,params):
        assert 'FROM usernews' in query
    def fetchone(self):return {'id':'draft-1','business_id':'b1'}

def test_saved_post_link_retains_native_draft_type_and_business():
    url=result_mini_app_url({'result_ref':{'href':'/dashboard/content?business_id=b1&item_type=news_draft&item_id=draft-1'}})
    query=parse_qs(urlsplit(url).query)
    assert query['screen']==['content']
    assert query['scope_id']==['b1']
    assert query['item_type']==['news_draft']
    assert query['item_id']==['draft-1']

def test_news_draft_cannot_cross_business_scope():
    args={'navigation':[{'key':'content','status':'available'}],'screen':'content','item_type':'news_draft','item_id':'draft-1'}
    allowed=resolve_mobile_deep_link(Cursor(),scope={'kind':'business','business_ids':['b1']},**args)
    assert allowed['item_id']=='draft-1'
    denied=resolve_mobile_deep_link(Cursor(),scope={'kind':'business','business_ids':['b2']},**args)
    assert denied['fallback_reason']=='object_forbidden'
    assert not denied['item_id']


def test_empty_brief_link_opens_briefing_tab_without_inventing_an_object():
    from services.operator_work_handoff import mobile_work_url
    for platform in ('telegram','max'):
        query=parse_qs(urlsplit(mobile_work_url('b1',platform=platform,screen='work_journal',item_type='day_brief')).query)
        assert query['item_type']==['day_brief']
        assert 'item_id' not in query
        link=resolve_mobile_deep_link(Cursor(),scope={'kind':'business','business_ids':['b1']},
            navigation=[{'key':'work_journal','status':'available'}], screen='work_journal',item_type='day_brief',item_id='')
        assert link['screen']=='work_journal' and link['item_type']=='day_brief'
        assert link['item_id'] is None and not link['fallback_applied']


def test_empty_brief_cannot_open_unavailable_work_screen():
    link=resolve_mobile_deep_link(Cursor(),scope={'kind':'business','business_ids':['b1']},
        navigation=[{'key':'today','status':'available'}],screen='work_journal',item_type='day_brief',item_id='')
    assert link['screen']=='today' and link['item_type'] is None
    assert link['fallback_reason']=='screen_unavailable'
