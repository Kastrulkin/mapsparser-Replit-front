import ast
import hashlib
import unittest
import uuid
from datetime import datetime,timedelta,timezone
from pathlib import Path

SOURCE=Path(__file__).with_name('author_pool_wave.py')
function=next(n for n in ast.parse(SOURCE.read_text()).body if isinstance(n,ast.FunctionDef) and n.name=='ensure_saved_channel_evidence')
namespace={'datetime':datetime,'timedelta':timedelta,'timezone':timezone,'uuid':uuid,'Json':lambda x:x,
    '_stable_evidence_key':lambda p,u,s:hashlib.sha256(f'{p}\n{u}\n{s}'.encode()).hexdigest(),'log':lambda *a,**k:None}
exec(compile(ast.Module(body=[function],type_ignores=[]),str(SOURCE),'exec'),namespace)
materialize=namespace['ensure_saved_channel_evidence']

class Cursor:
    def __init__(self,matching=None):self.matching=matching;self.calls=[]
    def execute(self,sql,params):self.calls.append((sql,params))
    def fetchone(self):
        sql,params=self.calls[-1]
        if 'catalog_evidence_key' in sql:return self.matching
        return {'id':'wrong-channel-a','observed_at':datetime.now(timezone.utc),'stale_after':datetime.now(timezone.utc)+timedelta(days=30),'confidence':.9}

class SnapshotTest(unittest.TestCase):
    def setUp(self):
        self.observed=datetime.now(timezone.utc)-timedelta(days=7)
        self.source={'canonical_url':'https://t.me/channel_b','channel_metadata':{'observed_identity':{'title':'Анна Иванова','description':'Сохранённое описание'}},'channel_observed_at':self.observed,'channel_verified_at':self.observed+timedelta(days=1)}
        self.proof={'confidence':.9,'source_channel_id':'channel-b','status':'public_explicit','researched_at':self.observed.isoformat()}
    def test_other_channel_same_platform_does_not_satisfy_selected_channel(self):
        cur=Cursor();result=materialize(cur,'profile','channel-b',self.source,self.proof)
        self.assertNotEqual(result[0],'wrong-channel-a')
        self.assertEqual(len(cur.calls),2)
        self.assertIn('catalog_evidence_key',cur.calls[0][0])
        params=cur.calls[1][1]
        self.assertEqual(params[2],'https://t.me/channel_b')
        self.assertEqual(params[5],self.observed)
        self.assertEqual(params[6],self.observed+timedelta(days=90))
        self.assertEqual(params[7]['source_channel_id'],'channel-b')
        self.assertFalse(params[7]['network_research_performed'])
    def test_same_stable_key_is_idempotent(self):
        cur=Cursor({'id':'existing-b','observed_at':self.observed,'stale_after':self.observed+timedelta(days=90),'confidence':.9})
        result=materialize(cur,'profile','channel-b',self.source,self.proof)
        self.assertEqual(result[0],'existing-b');self.assertEqual(len(cur.calls),1)
    def test_missing_original_time_does_not_create_freshness(self):
        self.source['channel_observed_at']=None;cur=Cursor()
        with self.assertRaisesRegex(ValueError,'original_time_missing'):materialize(cur,'profile','channel-b',self.source,self.proof)
        self.assertEqual(cur.calls,[])

if __name__=='__main__':unittest.main()
