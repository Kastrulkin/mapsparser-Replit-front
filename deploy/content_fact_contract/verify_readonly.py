"""PostgreSQL/provider-free smoke of the contract using existing records only."""
import argparse
import hashlib
import json
from pathlib import Path
from services import content_plan_service as content


def verify(assets=None):
    namespace = dict(content.__dict__)
    if assets:
        exec(compile(Path(assets).read_text(), assets, 'exec'), namespace)
    db = content.DatabaseManager()
    cursor = db.conn.cursor()
    try:
        cursor.execute('SET TRANSACTION READ ONLY')
        cursor.execute('SELECT * FROM contentplanitems WHERE id=%s', ('f3577e71-0508-4d58-ba4d-1d221058fe22',))
        item = content._row_to_dict(cursor, cursor.fetchone())
        metadata = item['metadata_json']
        if isinstance(metadata, str):
            metadata = json.loads(metadata)
        business_id = str(item['business_id'])
        cursor.execute('SELECT name,city,business_type,industry,categories,address,description,site,website FROM businesses WHERE id=%s', (business_id,))
        row = content._row_to_dict(cursor, cursor.fetchone())
        facts = content._content_plan_business_facts(row, item, metadata.get('website_source'))
        facts['service_sources'] = namespace['_load_content_plan_service_sources'](cursor, business_id, limit=12)
        brief = namespace['_with_content_fact_sources'](metadata['content_brief_v1'], facts, business_id)
        services = [source for source in brief['fact_sources'] if 'диплом' in source['fact'].lower() and source.get('table') == 'userservices']
        assert services, 'Known service description must reach the snapshot'
        assert all(source.get('record_id') and source.get('origin') for source in services)
        text = 'Первая стрижка. Сохраним локон в конверте и подарим диплом. Адрес: Энгельса, 154.'
        candidate = {'text': text, 'used_fact_ids': [services[0]['id'], 'business_profile:address']}
        score = namespace['_score_content_candidate'](candidate, brief, {})
        assert score['factual_gate_passed'], score['issues']
        block = namespace['_content_brief_prompt_block'](brief)
        assert services[0]['id'] in block and 'диплом' in block.lower() and '154' in block
        assert namespace['_unsupported_candidate_claims']('Стоимость стрижки 999999 рублей.', brief)
        candidate['used_fact_ids'] = ['unknown-source']
        assert not namespace['_score_content_candidate'](candidate, brief, {})['factual_gate_passed']
        plain = '{"candidates":[{"text":"Первая стрижка","used_fact_ids":["services"]}]}'
        assert namespace['_parse_content_candidates']('```json\n'+plain+'\n```') == namespace['_parse_content_candidates'](plain)
        assert namespace['_parse_content_candidates']("```json\n{'candidates': []}\n```") == []
        assert not namespace['_unsupported_candidate_claims']('Атмосфера праздника.', brief)
        print(json.dumps({'postgres_readonly': 'passed', 'sources': len(brief['fact_sources']),
                          'service_provenance': 'passed', 'address_diploma': 'passed',
                          'unknown_source_price': 'rejected', 'markdown': 'passed',
                          'module_sha256': hashlib.sha256(Path(content.__file__).read_bytes()).hexdigest()}))
    finally:
        db.conn.rollback()
        db.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--assets')
    verify(parser.parse_args().assets)
