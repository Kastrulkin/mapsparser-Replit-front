from services import operator_business_management
from services import business_member_directory

def test_named_branches_are_read_in_one_call(monkeypatch):
    seen=[]
    monkeypatch.setattr(operator_business_management,'load_actor',lambda *args:{'id':'owner'})
    monkeypatch.setattr(operator_business_management.business_chat_changes,'resolve_target',lambda c,a,r,b:r or b)
    monkeypatch.setattr(operator_business_management,'require_permission',lambda c,b,a,p:seen.append(b))
    monkeypatch.setattr(operator_business_management.business_chat_changes,'read_profile',lambda c,b:{'name':b})
    monkeypatch.setattr(business_member_directory,'list_business_members',lambda c,b:[{'name':b+' owner'}])
    tool=next(t for t in operator_business_management.tools(None,'selected','owner','покажи пользователей','web') if t['name']=='settings.list_users')
    result=tool['execute']({'businesses':['Купчино','Озерки','Купчино']})
    assert [g['business_id'] for g in result['businesses']]==['Купчино','Озерки']
    assert result['businesses'][1]['members']==[{'name':'Озерки owner'}]
    assert result['external_writes_performed'] is False
    assert 'Озерки' in seen

def test_single_business_retains_members_contract(monkeypatch):
    monkeypatch.setattr(operator_business_management,'load_actor',lambda *args:{'id':'owner'})
    monkeypatch.setattr(operator_business_management.business_chat_changes,'resolve_target',lambda c,a,r,b:r or b)
    monkeypatch.setattr(operator_business_management,'require_permission',lambda *args:None)
    monkeypatch.setattr(operator_business_management.business_chat_changes,'read_profile',lambda c,b:{'name':b})
    monkeypatch.setattr(business_member_directory,'list_business_members',lambda c,b:[{'name':'owner'}])
    tool=next(t for t in operator_business_management.tools(None,'selected','owner','покажи пользователей','web') if t['name']=='settings.list_users')
    assert tool['execute']({})['members']==[{'name':'owner'}]

def test_denied_branch_prevents_partial_team_disclosure(monkeypatch):
    import pytest
    reads=[]
    actors=[]
    monkeypatch.setattr(operator_business_management,'load_actor',lambda *args:{'id':'owner'})
    monkeypatch.setattr(operator_business_management.business_chat_changes,'resolve_target',lambda c,a,r,b:actors.append(dict(a)) or r)
    def allow(c,b,a,p):
        if b=='denied':raise PermissionError('Forbidden')
    monkeypatch.setattr(operator_business_management,'require_permission',allow)
    monkeypatch.setattr(business_member_directory,'list_business_members',lambda c,b:reads.append(b) or [])
    tool=next(t for t in operator_business_management.tools(None,'selected','owner','покажи пользователей','web',session={'session_kind':'business','scope_business_id':'selected'}) if t['name']=='settings.list_users')
    with pytest.raises(PermissionError):tool['execute']({'businesses':['allowed','denied']})
    assert reads==[]
    assert actors[0]['scope_business_id']=='selected'
