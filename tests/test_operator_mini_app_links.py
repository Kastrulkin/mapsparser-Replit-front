from urllib.parse import urlsplit, parse_qs
from services.operator_mini_app_links import result_mini_app_url


def test_result_link_preserves_business_and_partner_filters():
    result={'business_id':'qa-business','result_ref':{'href':'/dashboard/partnerships?section=drafts&draft_id=qa-draft&search_task_id=qa-search'}}
    url=result_mini_app_url(result,public_base='https://localos.pro',mini_app_base='https://localos.pro/telegram/control')
    params=parse_qs(urlsplit(url).query)
    assert params == {'screen':['partnerships'],'scope_type':['business'],'scope_id':['qa-business'],
                      'filter_section':['drafts'],'filter_draft_id':['qa-draft'],'filter_search_task_id':['qa-search']}


def test_service_and_review_links_do_not_open_the_map_parser():
    for tab in ['services','reviews']:
        url=result_mini_app_url({'result_ref':{'href':'/dashboard/card?tab='+tab}},public_base='https://localos.pro',mini_app_base='https://localos.pro/telegram/control')
        assert parse_qs(urlsplit(url).query)['screen']==[tab]


def test_foreign_and_unknown_result_destinations_do_not_become_miniapp_links():
    for href in ['https://foreign.invalid/dashboard/content','/admin/settings','javascript:alert(1)']:
        assert result_mini_app_url({'result_ref':{'href':href}},public_base='https://localos.pro',mini_app_base='https://localos.pro/telegram/control') is None


def test_selected_post_result_opens_that_post_in_the_correct_business():
    item='11111111-2222-4333-8444-555555555555'
    url=result_mini_app_url({'result_ref':{'href':'/dashboard/content?business_id=qa-business&plan_id=qa-plan&item_id='+item}},
        public_base='https://localos.pro',mini_app_base='https://localos.pro/telegram/control')
    params=parse_qs(urlsplit(url).query)
    assert params['item_type']==['content_item']
    assert params['item_id']==[item]
    assert params['scope_id']==['qa-business']
