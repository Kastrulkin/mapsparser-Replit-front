"""Company facts are retained separately from a previously generated plan."""
import uuid
import pytest
from tests.test_operator_voice_pg import pg
from tests.test_operator_editorial_pg import editorial
from services import operator_audio,operator_chat_service,operator_core

@pytest.mark.parametrize('channel',['web','telegram','telegram_mini_app','max_bot','max_mini_app'])
@pytest.mark.parametrize('kind,quote',[('company_fact','Шьём одежду для команд по согласованным образцам.'),('founder_story','Я начинала с мастерской и лично проверяю каждый образец.')])
def test_explicit_facts_in_selected_post_discussion_never_recreate_or_rewrite_plan(editorial,monkeypatch,channel,kind,quote):
 conn,c=editorial;identifier=str(uuid.uuid4());c.execute("UPDATE contentplanitems SET id=%s WHERE id='i'",(identifier,))
 def authorize(cursor,user_id,business_id,**kwargs):
  if user_id!='u' or business_id!='b':raise PermissionError('Foreign business')
  return {'role':'business_owner'},{'capabilities':['operator','social_content']}
 monkeypatch.setattr(operator_audio,'authorize_actor',authorize)
 c.execute('SELECT id,theme,draft_text,metadata_json FROM contentplanitems ORDER BY id');before=c.fetchall()
 c.execute('SELECT to_jsonb(plan) value FROM contentplans plan ORDER BY id');plans_before=c.fetchall()
 calls=[]
 def planner(state):calls.append(state);return {'action':'tool_call','tool':'content.remember','arguments':{'kind':kind,'quote':quote}}
 def router(cursor,**kwargs):return operator_core.route_operator_message(cursor,tool_planner=planner,**kwargs)
 args=dict(business_id='b',user_id='u',channel=channel,message='Запомни для будущих текстов: '+quote,payload={'request_id':'remember-one','selected_object':{'type':'content_item','id':identifier}},router=router)
 result=operator_chat_service.process_chat(c,**args);conn.commit();repeat=operator_chat_service.process_chat(c,**args)
 assert result['status']=='completed' and result['message_id']==repeat['message_id'] and len(calls)==1
 c.execute('SELECT preferences_json FROM content_voice_profiles WHERE business_id=%s',('b',));notes=c.fetchone()['preferences_json']['editorial_notes']
 assert len([note for note in notes if note['kind']==kind and note['text']==quote])==1
 c.execute('SELECT id,theme,draft_text,metadata_json FROM contentplanitems ORDER BY id');assert c.fetchall()==before
 c.execute('SELECT to_jsonb(plan) value FROM contentplans plan ORDER BY id');assert c.fetchall()==plans_before
