"""Owner-reviewed journal requests reuse the existing partnership search and CRM."""
import json
import uuid
from services import work_journal, work_review
from services.operator_conversations import _row


def source_entry(cursor,business,user,entry_id,version):
    work_review.require_review(cursor,business,user)
    work_journal.scope(cursor,business,user,write=True)
    cursor.execute('SELECT * FROM business_work_journal WHERE id=%s AND business_id=%s FOR UPDATE',(entry_id,business))
    entry=_row(cursor,cursor.fetchone())
    if not entry or entry['is_voided']:raise ValueError('Запись журнала недоступна.')
    if type(version) is not int or entry['version']!=version:raise ValueError('Запись изменилась. Проверьте её и подготовьте поиск заново.')
    if entry['review_status']!='in_progress':raise ValueError('Сначала примите запись в работу.')
    return entry


def prepare(cursor,business,user,entry_id,args):
    entry=source_entry(cursor,business,user,entry_id,args.get('version'))
    from services.operator_audio import authorize_actor
    from subscription_manager import capability_access_payload
    _,access=authorize_actor(cursor,user,business)
    entitlement=capability_access_payload(access,'partnerships')
    if not entitlement['allowed']:
        return {'status':'blocked','chat_response':'Планёрка и журнал доступны на любом тарифе. Для поиска исполнителей нужен тариф «Привлечение» или «Управление».','blocked_reasons':['payment_required']}
    from services import outreach_continuation
    if not outreach_continuation.continuation_enabled(business):
        return {'status':'blocked','chat_response':'Поиск исполнителей пока не включён для этого бизнеса. Запись и решение сохранены; поиск и отправка не запускались.','blocked_reasons':['feature_disabled']}
    audience=str(args.get('audience') or '').strip()
    geography=str(args.get('geography') or '').strip()
    requirements=args.get('requirements') or []
    count=args.get('target_count',3)
    mode=args.get('mode','find_only')
    offer=str(args.get('offer') or '').strip()
    language=args.get('language','ru')
    if not audience or len(audience)>500 or not geography or len(geography)>120:raise ValueError('Укажите, кого найти, и город или район поиска.')
    if not isinstance(requirements,list) or len(requirements)>10 or any(not isinstance(value,str) or not value.strip() or len(value)>300 for value in requirements):raise ValueError('Укажите до десяти условий, каждое до 300 символов.')
    if type(count) is not int or not 1<=count<=10:raise ValueError('Для поручения выберите от 1 до 10 исполнителей.')
    if mode not in {'find_only','prepare_only'} or language not in {'ru','en'}:raise ValueError('Выберите поиск или подготовку обращений без отправки.')
    if mode=='prepare_only' and not offer:raise ValueError('Укажите, о чём написать исполнителю.')
    if len(offer)>2000:raise ValueError('Сократите обращение до 2000 символов.')
    request_id=str(args.get('request_id') or '')
    uuid.UUID(request_id)
    maximum=max(10,count*3)
    result=outreach_continuation.prepare_new_task_approval({
        'search_source':'web','audience':audience,'search_geography':[geography],
        'requirements':requirements,'target_count':count,'mode':mode,'offer':offer,'language':language,
        'queries':[{'query':audience,'city':geography}],'max_search_calls':1,
        'max_candidates':maximum,'max_qualification_calls':maximum,'max_draft_attempts':count,'batch_size':min(count,10),
    },business_id=business,request_id=request_id)
    if result.get('status')!='approval_required':return result
    envelope=result['approval']['envelope']
    envelope['source_work_journal']={'entry_id':entry_id,'version':entry['version']}
    excerpt=str(entry['facts_json'].get('quote') or entry['original_text'])[:400]
    result['chat_response']='По записи сотрудника: «'+excerpt+'»\n\n'+result['chat_response']+'\nОбращения не отправляются. Договорённости и расходы на услуги требуют вашего отдельного решения.'
    result['approval']['summary']=result['chat_response']
    # A newer reviewed request supersedes the previous unconfirmed one, including another messenger.
    cursor.execute("""UPDATE operatoractions SET status='rejected',updated_at=NOW()
        WHERE business_id=%s AND user_id=%s AND capability='partnerships.continue_outreach'
          AND status IN ('pending','pending_approval') AND envelope_json->'source_work_journal'->>'entry_id'=%s
          AND envelope_json<>%s::jsonb""",(business,user,entry_id,json.dumps(envelope,ensure_ascii=False)))
    return result


def validate_confirmation(cursor,business,user,envelope):
    source=envelope.get('source_work_journal') or {}
    if envelope.get('operation')!='create_and_start' or (envelope.get('config') or {}).get('mode') not in {'find_only','prepare_only'}:
        raise ValueError('По записи журнала можно согласовать поиск и черновики, без отправки.')
    return source_entry(cursor,business,user,source.get('entry_id'),source.get('version'))


def link_search(cursor,business,user,envelope,result,action_id):
    entry=validate_confirmation(cursor,business,user,envelope)
    task_id=(result.get('task') or {}).get('id') or result.get('job_id')
    cursor.execute("SELECT id FROM operator_async_jobs WHERE id=%s AND business_id=%s AND kind='outreach_continue'",(task_id,business))
    if not cursor.fetchone():raise ValueError('Поиск не найден в этом бизнесе.')
    config=envelope['config']
    action=work_review.create_action(cursor,business,user,entry['id'],{
        'request_id':'journal-search:'+action_id,'version':entry['version'],'kind':'task',
        'title':('Найти исполнителя: '+config['audience'])[:250],
        'text':'Где ищем: '+'; '.join(config['search_geography'])+'\n'+'; '.join(config['requirements']),
    })
    payload={**action['payload_json'],'search_task_id':str(task_id),'execution_mode':'search','approved_external':False}
    from urllib.parse import urlencode
    href='/dashboard/partnerships?'+urlencode({'business_id':business,'search_task_id':str(task_id),'section':'companies'})
    cursor.execute("UPDATE journey_actions SET payload_json=%s::jsonb,cta_label='Открыть поиск',cta_target_json=%s::jsonb WHERE id=%s",(json.dumps(payload),json.dumps({'href':href}),action['id']))
    return str(action['id'])
