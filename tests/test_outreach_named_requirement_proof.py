from services.outreach_continuation import named_requirement_supported, effective_qualification, qualified_contact_ids

NETTOURS = ('Outbound Tours from India. Our neighboring countries, South East Asia, Europe, '
            'South Africa and Mauritius. Network Air Private Limited with headquarters in Delhi.')


def qualification(fact):
    return {'status': 'qualified', 'criteria': {'requirement_1': {
        'status': 'verified', 'label': 'продаёт туры на Пхукет',
        'quote': 'Outbound Tours from India',
        'evidence': {'fact': fact, 'source_url': 'https://example.com/outbound'}}}}


def test_broad_outbound_region_cannot_prove_named_destination():
    assert not named_requirement_supported('продаёт туры на Пхукет', {'fact': NETTOURS})
    original = qualification(NETTOURS)
    effective = effective_qualification(original)
    assert effective['status'] == 'needs_evidence'
    assert effective['criteria']['requirement_1']['status'] == 'not_verified'
    assert original['status'] == 'qualified'  # preserve model audit
    assert qualified_contact_ids({'qualifications': {'ws': original},
                                  'verified_contact_workstream_ids': ['ws']}) == []


def test_explicit_name_in_cited_fact_can_pass_necessary_check():
    assert named_requirement_supported('продаёт туры на Пхукет', {'fact': 'Phuket tour packages from India'})
    assert named_requirement_supported('поставляет продукцию Acme', {'fact': 'Distributor of Acme cosmetics'})
    assert not named_requirement_supported('поставляет продукцию Acme', {'fact': 'Distributor of cosmetics'})
    assert not named_requirement_supported('sells Phuket packages', {'fact': 'Thailand travel'})
    assert not named_requirement_supported('sells Phuket packages', {'source_url': 'https://example.com/phuket'})


def test_no_inference_from_url_and_no_changed_generic_conditions():
    assert not named_requirement_supported('продаёт туры на Пхукет', {})
    generic = {'status':'qualified','criteria':{'requirement_0':{'label':'есть публичный email','status':'verified'}}}
    assert effective_qualification(generic) is generic


def test_model_true_with_exact_but_irrelevant_quote_is_not_qualification():
    from services.outreach_continuation import qualify_audience
    from services.llm.contracts import LLMTaskResult
    config = {'audience':'tour agencies', 'search_geography':[],
              'requirements':['продаёт туры на Пхукет']}
    def model(_):
        return LLMTaskResult(status='completed',provider='deepseek',parsed_data={
            'matches':True, 'criteria': {
                'audience':{'matches':True,'evidence_id':'e','quote':'Outbound Tours from India'},
                'requirement_0':{'matches':True,'evidence_id':'e','quote':'Outbound Tours from India'}}})
    result = qualify_audience(config,[{'id':'e','fact':NETTOURS,'source_url':'https://example.com/outbound'}],
                              business_id='b',user_id='u',runner=model)
    assert result['status'] == 'needs_evidence'
    assert result['criteria']['requirement_0']['reason'] == 'named_requirement_missing_from_source'
