from services.outreach_web_search import _normalize
from services.outreach_personalization_ai import qualified_requirement_for_offer, qualified_offer_bridge


def test_discovery_preserves_exact_service_page_for_evidence_collection():
    url='https://agency.example/packages/phuket?lang=en'
    items=_normalize([{'url':url,'title':'Phuket package'},
                      {'url':'https://agency.example/about','title':'About agency'}], 'tavily', 6)
    assert len(items)==1
    assert items[0]['website']==items[0]['source_url']==url


def test_russian_offer_selects_service_evidence_instead_of_english_country_fact():
    def criterion(label,quote):
        return {'status':'verified','label':label,'quote':quote,
                'evidence':{'source_url':'https://agency.example/package','fact':quote}}
    q={'criteria':{'requirement_0':criterion('турагентство Индии','Our company is in New Delhi'),
                   'requirement_1':criterion('продаёт туры на Пхукет','Five day Phuket holiday package')}}
    assert qualified_requirement_for_offer(q,'трансферы Riderra на Пхукете')['quote']=='Five day Phuket holiday package'
    bridge=qualified_offer_bridge('трансферы Riderra на Пхукете','Five day Phuket holiday package')
    assert 'Five day Phuket' in bridge
    assert 'обсудить' not in bridge
    assert 'опубликованного на вашем сайте предложения' not in bridge
