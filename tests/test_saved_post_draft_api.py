import ast
from pathlib import Path
from flask import Flask,Blueprint,jsonify
import pytest

@pytest.fixture
def endpoint():
    app=Flask(__name__);bp=Blueprint('draft_test',__name__)
    state={'user':{'id':'u'},'scope':{'kind':'business','id':'b1','business_ids':['b1']},'row':{'id':'draft','business_id':'b1','generated_text':'Текст черновика','created_at':None,'updated_at':None},'access':True}
    class Cursor:
        def execute(self,query,params):
            if 'photo_assets' in query:assert params[0]=='b1'
            self.query=query
        def fetchone(self):
            if 'FROM usernews' in self.query:return state['row']
            return {'photos':['p1']}
        def fetchall(self):return [{'id':'p1'}]
    cursor=Cursor()
    class Database:
        conn=type('Connection',(),{'cursor':lambda self:cursor})()
        def close(self):pass
    module=ast.parse(Path('src/api/operator_api.py').read_text())
    node=next(node for node in module.body if isinstance(node,ast.FunctionDef) and node.name=='operator_mobile_saved_post_draft')
    env={'operator_bp':bp,'require_auth_from_request':lambda:state['user'],'DatabaseManager':Database,'_resolve_mobile_scope':lambda *args:state['scope'],'_mobile_scope_allows_business':lambda scope,business:business in scope['business_ids'],'_scope_capability_access':lambda *args:{'allowed':state['access']},'_mobile_payment_required_response':lambda access:(jsonify({'success':False}),403),'jsonify':jsonify}
    exec(compile(ast.Module(body=[node],type_ignores=[]),'saved_draft_endpoint','exec'),env)
    app.register_blueprint(bp)
    return app.test_client(),state

def test_saved_draft_returns_text_and_only_business_photos(endpoint):
    client,state=endpoint
    response=client.get('/mobile/content/drafts/draft')
    assert response.status_code==200
    assert response.json['draft']['text']=='Текст черновика'
    assert response.json['draft']['photos']==[{'asset_id':'p1','name':'Фото к посту'}]

@pytest.mark.parametrize('change,status',[({'user':None},401),({'row':None},404),({'scope':{'business_ids':['other']}},403),({'access':False},403)])
def test_saved_draft_access_and_missing_states(endpoint,change,status):
    client,state=endpoint;state.update(change)
    assert client.get('/mobile/content/drafts/draft').status_code==status
