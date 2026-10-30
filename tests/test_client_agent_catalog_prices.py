import pytest
from types import SimpleNamespace
import ai_agent

@pytest.mark.parametrize('duration',[True,False])
@pytest.mark.parametrize('price',['2000','2000.0',2000,0,None,''])
def test_dialogue_keeps_catalog_major_currency_units(monkeypatch,duration,price):
    class Cursor:
        def execute(self,sql,args=None): self.schema='information_schema' in sql
        def fetchall(self):
            if self.schema: return [{'column_name':'price'}]+([{'column_name':'duration'}] if duration else [])
            return [{'id':'s','name':'Массаж спины','price':price,'duration':30,'description':'Локальный массаж'}]
    cursor=Cursor()
    db=SimpleNamespace(conn=SimpleNamespace(cursor=lambda:cursor),close=lambda:None)
    monkeypatch.setattr(ai_agent,'DatabaseManager',lambda:db)
    monkeypatch.setattr(ai_agent,'_active_predicate',lambda *args:'is_active=true')
    services=ai_agent.get_business_services('organika')
    assert services[0]['price']==(None if price=='' else price)

def test_unconfigured_business_does_not_inherit_latest_custom_persona(monkeypatch):
    captured=[]
    class Cursor:
        def execute(self,sql,args=None): self.sql=sql; captured.append((sql,args))
        def fetchone(self):
            if 'to_jsonb' in self.sql:return {'config':None}
            if 'FROM Businesses' in self.sql:return {'ai_agent_type':'booking'}
            return None
    cursor=Cursor();db=SimpleNamespace(conn=SimpleNamespace(cursor=lambda:cursor),close=lambda:None)
    monkeypatch.setattr(ai_agent,'DatabaseManager',lambda:db)
    monkeypatch.setattr(ai_agent,'_table_columns',lambda *args:{'ai_agent_type'})
    monkeypatch.setattr(ai_agent,'_active_predicate',lambda *args:'1=1')
    result=ai_agent.get_agent_config('unconfigured-business')
    assert result['task']==''
    sql,args=captured[-1]
    assert args==('booking','booking_agent_default')
    assert 'id = %s' in sql
