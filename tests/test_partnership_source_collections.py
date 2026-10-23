import importlib.util
from pathlib import Path
import unittest
import sys
from types import ModuleType
from unittest.mock import patch
spec = importlib.util.spec_from_file_location('source_collections',Path(__file__).parents[1]/'src/services/partnership_source_collections.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
class Cursor:
    def __init__(self, rows): self.rows=rows
    def execute(self, query, params): self.query=query;self.params=params
    def fetchall(self): return self.rows
class Collections(unittest.TestCase):
    def test_only_completed_collections_in_business(self):
        c=Cursor([{'id':'one'}]);self.assertEqual(module.load_collections(c,business_id='tenant'),[{'id':'one'}])
        self.assertIn("status='completed'",c.query);self.assertIn('business_id=%s',c.query)
        self.assertEqual(c.params,('partnership_source_collection','tenant'))
    def test_detail_is_scoped_and_bound(self):
        c=Cursor([]);self.assertEqual(module.load_collections(c,business_id='tenant',task_id='other'),[])
        self.assertIn('AND id=%s',c.query);self.assertEqual(c.params,('partnership_source_collection','tenant','other'))
    def test_disabled_search_returns_collections_without_enabling(self):
        c=Cursor([]);result,status=module.saved_collection_response(c,business_id='tenant',viewer_id='user')
        self.assertEqual(status,200);self.assertFalse(result['enabled']);self.assertTrue(result['read_only_collections']);self.assertEqual(result['items'],[])
    def test_foreign_or_missing_id_is_not_visible(self):
        result,status=module.saved_collection_response(Cursor([]),business_id='tenant',viewer_id='user',task_id='foreign')
        self.assertEqual(status,404);self.assertEqual(result,{'error':'task_not_found'})
    def test_current_campaigns_are_loaded_only_for_group_members(self):
        native = ModuleType('services.outreach_continuation')
        native.view = lambda row: {'state': row['result_json'], 'report': {}}
        native.delivery_report = lambda cursor, task: {}
        groups = ModuleType('services.partnership_group_view')
        groups.enrich_group = lambda cursor, task, viewer_id: None
        row = {'business_id':'tenant', 'result_json': {'lead_ids':['lead'], 'campaign_results':{'old':{'campaign_id':'stale'}}}}
        c = Cursor([{'id':'new','workstream_id':'work','lead_id':'lead','status':'draft'}])
        with patch.dict(sys.modules, {'services.outreach_continuation':native,'services.partnership_group_view':groups}):
            result = module.collection_view(c,row,viewer_id='user')
        self.assertEqual(c.params, ('tenant','lead'))
        self.assertIn('c.business_id=%s', c.query)
        self.assertEqual(set(result['state']['campaign_results']),{'work'})
        self.assertEqual(result['state']['campaign_results']['work']['status'],'needs_manual_review')
        self.assertNotIn('work',row['result_json']['campaign_results'])
    def test_empty_membership_cannot_show_old_campaigns(self):
        native = ModuleType('services.outreach_continuation')
        native.view = lambda row: {'state':row['result_json'],'report':{}}
        native.delivery_report = lambda cursor, task: {}
        groups = ModuleType('services.partnership_group_view')
        groups.enrich_group = lambda cursor, task, viewer_id: None
        row = {'business_id':'tenant','result_json':{'lead_ids':[],'campaign_results':{'old':{'campaign_id':'stale'}}}}
        with patch.dict(sys.modules, {'services.outreach_continuation':native,'services.partnership_group_view':groups}):
            result = module.collection_view(Cursor([]),row,viewer_id='user')
        self.assertEqual(result['state']['campaign_results'],{})
    def test_endpoint_guards_precede_saved_read_and_post_stays_disabled(self):
        s=(Path(__file__).parents[1]/'src/api/partnership_leads_api.py').read_text();s=s[s.index('def partnership_continuations'):]
        self.assertLess(s.index('business_id != requested'),s.index('saved_collection_response'))
        self.assertLess(s.index('if denied:'),s.index('saved_collection_response'))
        self.assertIn("if request.method != 'GET':\n                return jsonify({'error': 'feature_disabled'}), 404",s)
if __name__=='__main__':unittest.main()


def test_collection_summary_uses_authorized_points_and_current_campaign_counts(monkeypatch):
    requested = []
    def load(cursor, *, business_id):
        requested.append(business_id)
        return [{'id':'group-' + business_id,'business_id':business_id,'result_json':{'lead_ids':['lead','lead']}}]
    monkeypatch.setattr(module,'load_collections',load)
    monkeypatch.setattr(module,'collection_state',lambda cursor,row:{'lead_ids':['lead','lead'],'campaign_results':{'work':{'campaign_id':'campaign-'+row['business_id']}}})
    class SummaryCursor:
        def execute(self,query,params):
            assert 'campaign_id IN (%s)' in query
            assert params in [('campaign-one',),('campaign-two',)]
        def fetchone(self):return {'count':4}
    result=module.collection_summaries(SummaryCursor(),locations=[{'id':'one','name':'Сеть','address':'Первая улица'},{'id':'two','name':'Сеть','address':'Вторая улица'}])
    assert requested==['one','two']
    assert [item['business_address'] for item in result]==['Первая улица','Вторая улица']
    assert all(item['company_count']==1 and item['touch_count']==4 for item in result)
    assert all('lead_ids' not in item and 'contacts' not in item for item in result)


def test_empty_authorized_locations_do_not_query_collections():
    class NoQuery:
        def execute(self,*args):raise AssertionError('No accessible locations')
    assert module.collection_summaries(NoQuery(),locations=[])==[]
