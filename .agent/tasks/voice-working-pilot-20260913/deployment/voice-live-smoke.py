import json,time,uuid,requests
from auth_system import create_session,logout_session
from database_manager import DatabaseManager
from services.operator_conversations import get_or_create_operator_conversation,_row
from services.operator_speechkit import SpeechKit
B='edbd961a-273f-4f15-836e-33aacc0aa0e3'
base='http://127.0.0.1:8000/api/operator'
db=DatabaseManager();cur=db.conn.cursor();cur.execute('SELECT owner_id FROM businesses WHERE id=%s',(B,));owner=_row(cur,cur.fetchone())['owner_id'];db.close()
token=create_session(owner,user_agent='LocalOS voice release verification deb0f637',expires_days=1)
assert token
session=requests.Session();session.headers['Authorization']='Bearer '+token
report=[]
def call(method,path,**kwargs):
 response=session.request(method,base+path,timeout=90,**kwargs)
 if response.status_code>=400:raise RuntimeError(path+' HTTP '+str(response.status_code)+' '+response.text[:250])
 return response.json()
def poll(jobid):
 for i in range(90):
  job=call('GET','/mobile/jobs/'+jobid,params={'business_id':B,'scope_kind':'business','scope_id':B})['job']
  if job['status'] in ['completed','waiting_for_review']:return job
  if job['status'] in ['failed','cancelled']:raise RuntimeError('audio job '+job['status'])
  time.sleep(2)
 raise RuntimeError('audio timeout')
try:
 config=call('GET','/audio/config',params={'business_id':B});assert config['input_enabled'] and config['output_enabled']
 assert requests.get(base+'/requests',params={'business_id':B},timeout=20).status_code==401
 audio=SpeechKit().synthesize('Что ты умеешь?')
 for channel in ['web','telegram_mini_app','telegram']:
  db=DatabaseManager();cur=db.conn.cursor()
  conv=get_or_create_operator_conversation(cur,business_id=B,user_id=owner,channel=channel,transport_key='release-check:deb0f637:'+channel)
  db.conn.commit();db.close()
  for kind in ['text','voice']:
   payload={'business_id':B,'channel':channel,'conversation_id':conv['id'],'request_id':'release-deb0f637:'+channel+':'+kind,'message':'Что ты умеешь?'}
   if kind=='voice':
    queued=call('POST','/audio/transcriptions',data={'business_id':B,'channel':channel,'conversation_id':conv['id'],'request_id':payload['request_id']},files={'file':('verification.ogg',audio,'audio/ogg')})
    job=poll(queued['job_id']);payload['message']=job['result']['transcript'];payload['transcription_id']=queued['asset_id']
    assert 'умеешь' in payload['message'].lower()
   result=call('POST','/chat',json=payload)['operator_result']
   assert result['status']=='completed',result.get('status')
   duplicate=call('POST','/chat',json=payload)['operator_result']
   assert result['message_id']==duplicate['message_id']
   receipt=call('GET','/requests/'+result['request_audit_id'],params={'business_id':B})
   assert receipt['metadata_json']['duplicates']>=1
   report.append({'channel':channel,'input':kind,'message_id':result['message_id'],'audit_id':result['request_audit_id'],'status':result['status'],'duplicate_suppressed':True})
   print(json.dumps(report[-1]),flush=True)
  speech=call('POST','/messages/'+result['message_id']+'/speech')
  if speech.get('job_id'):poll(speech['job_id'])
  download=session.get(base+'/audio/'+speech['asset_id'],timeout=30)
  assert download.status_code==200 and len(download.content)>100
  print(json.dumps({'channel':channel,'tts_download':True}),flush=True)
 print(json.dumps({'passed':len(report),'note':'server HTTP/common-channel checks; not physical Telegram/device tests'}),flush=True)
finally:
 logout_session(token)
