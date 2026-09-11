"""Create a local service and track independent Google/manual distribution."""
import json
import os
import re
import sys
import uuid
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from difflib import SequenceMatcher
from services import operator_audio
from services.operator_conversations import _row
from services.operator_google_services import load_google, version


def authorize_actor(cursor,user_id,business_id):
    actor,access=operator_audio.authorize_actor(cursor,user_id,business_id)
    if actor.get('role')=='business_owner' or actor.get('is_superadmin'):
        return actor,access
    cursor.execute("SELECT role FROM business_members WHERE business_id=%s AND user_id=%s AND status='active'",(business_id,user_id))
    membership=_row(cursor,cursor.fetchone())
    if membership.get('role') not in {'manager','admin'}:
        raise PermissionError('Добавлять услуги и обновлять карты может владелец или управляющий бизнеса.')
    return actor,access


def service_input(message):
    if re.search(r'(?:добав|созда|завед)\w*\s+(?:нов\w*\s+)?услуг',message,re.I):
        return True
    if re.search(r'пост|контент|новост',message,re.I):
        return False
    return bool(re.search(r'услуг|прайс',message,re.I) and re.search(r'добав|созда|завед|нов\w*|статус|карт.*обнов|google|гугл|назнач|выполн',message,re.I))


def result(text,status='completed',**extra):
    return {'status':status,'capability':'services.create','chat_response':text,'external_writes_performed':False,
            'result_ref':{'href':'/dashboard/card?tab=services','label':'Открыть услуги'},**extra}


def normalize(value):
    return ' '.join(re.sub(r'[^\w\s]',' ',value.casefold().replace('ё','е')).split())


def context(cursor,business_id,user_id,args):
    authorize_actor(cursor,user_id,business_id)
    cursor.execute('SELECT to_jsonb(b) data FROM businesses b WHERE id=%s',(business_id,))
    business=_row(cursor,cursor.fetchone()).get('data') or {}
    cursor.execute('SELECT id,name,price,currency FROM userservices WHERE business_id=%s AND COALESCE(is_active,TRUE)=TRUE ORDER BY name LIMIT 300',(business_id,))
    services=[_row(cursor,row) for row in cursor.fetchall()]
    cursor.execute('''SELECT d.id,d.service_id,s.name,d.google_status,d.google_error,d.manual_task_id,j.status manual_status,j.user_id responsible_user_id
        FROM operator_service_distribution d JOIN userservices s ON s.id=d.service_id
        LEFT JOIN journey_actions j ON j.id=d.manual_task_id WHERE d.business_id=%s ORDER BY d.created_at DESC LIMIT 20''',(business_id,))
    distributions=[_row(cursor,row) for row in cursor.fetchall()]
    cursor.execute("SELECT m.user_id,u.name FROM business_members m JOIN users u ON u.id=m.user_id WHERE m.business_id=%s AND m.status='active' AND m.role IN ('admin','manager') AND u.is_active=TRUE",(business_id,))
    managers=[_row(cursor,row) for row in cursor.fetchall()]
    return result('Услуги и статусы обновления карт.',services=services,currency=business.get('currency'),distributions=distributions,managers=managers)


def manual_task(cursor,business_id,service):
    cursor.execute("SELECT DISTINCT source FROM externalbusinessaccounts WHERE business_id=%s AND source IN ('yandex_business','yandex_maps','2gis')",(business_id,))
    platforms=[_row(cursor,row)['source'] for row in cursor.fetchall()]
    cursor.execute('SELECT to_jsonb(b) data FROM businesses b WHERE id=%s',(business_id,))
    business=_row(cursor,cursor.fetchone()).get('data') or {}
    if business.get('yandex_url') and not any(p.startswith('yandex') for p in platforms):
        platforms.append('yandex_maps')
    cursor.execute("SELECT map_type,url FROM businessmaplinks WHERE business_id=%s AND COALESCE(BTRIM(url),'')<>''",(business_id,))
    for raw in cursor.fetchall():
        link=_row(cursor,raw)
        platform=(link.get('map_type') or '').lower()
        if platform in {'google','google_maps','google_business'}:
            continue
        platform={'yandex':'yandex_maps','2gis_maps':'2gis','two_gis':'2gis'}.get(platform,platform)
        if platform and platform not in platforms and not (platform.startswith('yandex') and any(p.startswith('yandex') for p in platforms)):
            platforms.append(platform)
    if not platforms:
        return None,'Другие карты не подключены; задача не создана.'
    cursor.execute("SELECT m.user_id FROM business_members m JOIN users u ON u.id=m.user_id WHERE m.business_id=%s AND m.status='active' AND m.role IN ('admin','manager') AND u.is_active=TRUE ORDER BY m.user_id",(business_id,))
    members=[_row(cursor,row)['user_id'] for row in cursor.fetchall()]
    responsible=members[0] if len(members)==1 else None
    from services.lead_journey_service import ensure_action
    names={'yandex_business':'Яндекс Бизнес','yandex_maps':'Яндекс Карты','2gis':'2ГИС'}
    description=f"Добавьте услугу «{service['name']}», стоимость {service['price']} {service['currency']}, на площадки: "+', '.join(names.get(p,p) for p in platforms)+'. После фактического обновления отметьте задачу выполненной.'
    task=ensure_action(cursor,journey_id=None,business_id=business_id,user_id=responsible,lead_id=None,flow_type='maps',
        entity_type='service',entity_id=service['id'],action_type='complete_map_task',due_at=datetime.now(timezone.utc),
        payload={'task_title':'Обновить услугу на картах: '+service['name'],'task_reason':description,'platforms':platforms,'service_id':service['id']})
    if not responsible:
        return task['id'],'Задача обновления остальных карт создана. Единственный ответственный администратор не настроен; назначьте управляющего в команде.'
    if os.getenv('JOURNEY_NOTIFICATIONS_ENABLED','').lower() not in {'1','true','yes','on'}:
        return task['id'],'Задача обновления остальных карт назначена администратору. Уведомления задач отключены; задача доступна в LocalOS.'
    return task['id'],'Задача обновления остальных карт назначена администратору. Уведомление будет отправлено, если он включил уведомления о задачах в Telegram.'


def create(cursor,business_id,user_id,message,request_key,args):
    authorize_actor(cursor,user_id,business_id)
    if re.match(r'\s*(?:если|например|как\b|можно ли|не\b)',message,re.I) or re.search(r'\bне\s+(?:добав|созда|завед)',message,re.I):
        return result('Для добавления услуги дайте явную команду с названием и ценой.','clarification_required')
    name=(args.get('name') or '').strip()
    if not name or len(name)>200 or normalize(name) not in normalize(message):
        return result('Уточните точное название новой услуги.','clarification_required')
    try:
        price=Decimal(str(args.get('price')).replace(',','.'))
        if not price.is_finite() or price<0 or price>1000000000 or price!=price.quantize(Decimal('.01')):
            raise ValueError('price')
    except (InvalidOperation,ValueError):
        return result('Уточните стоимость услуги числом, не больше двух знаков после запятой.','clarification_required')
    cursor.execute('SELECT to_jsonb(b) data FROM businesses b WHERE id=%s',(business_id,))
    business=_row(cursor,cursor.fetchone()).get('data') or {}
    currency=(args.get('currency') or business.get('currency') or '').upper()
    if currency not in {'RUB','EUR','USD','KZT','BYN','GBP','GEL','AMD','AED','UZS','KGS','TRY'}:
        return result('Уточните валюту стоимости услуги.','clarification_required')
    aliases={'RUB':r'руб|₽','EUR':r'евро|€','USD':r'доллар|\$','KZT':r'тенге','BYN':r'белорусск.*руб',
             'GBP':r'фунт|£','GEL':r'лари','AMD':r'драм','AED':r'дирхам','UZS':r'сум','KGS':r'сом','TRY':r'лир'}
    if currency!=(business.get('currency') or '').upper() and not re.search(r'\b'+currency+r'\b|'+aliases[currency],message,re.I):
        return result('Уточните валюту: она не указана в команде или настройках бизнеса.','clarification_required')
    description=(args.get('description') or '').strip()
    category=(args.get('category') or '').strip()
    if any(value and (len(value)>1000 or normalize(value) not in normalize(message)) for value in (description,category)):
        return result('Описание и категория должны содержать только продиктованные сведения.','clarification_required')
    cursor.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',('create-service:'+business_id,))
    cursor.execute('SELECT * FROM operator_service_distribution WHERE business_id=%s AND user_id=%s AND request_key=%s',(business_id,user_id,request_key))
    existing=_row(cursor,cursor.fetchone())
    if existing:
        return result('Эта услуга уже сохранена.',distribution_id=existing['id'],service_id=existing['service_id'])
    cursor.execute('SELECT id,name FROM userservices WHERE business_id=%s AND COALESCE(is_active,TRUE)=TRUE',(business_id,))
    similar=[_row(cursor,row) for row in cursor.fetchall()]
    similar=[row for row in similar if SequenceMatcher(None,normalize(row['name']),normalize(name)).ratio()>=.82]
    if similar and not (args.get('create_separate') is True and re.search(r'отдельн|ещ[её] одну|новую.*несмотря',message,re.I)):
        return result('Уже есть похожая услуга: '+', '.join(row['name'] for row in similar[:5])+'. Добавить отдельную новую или изменить существующую?','clarification_required',similar=similar[:5])
    service={'id':str(uuid.uuid4()),'name':name,'price':str(price),'currency':currency,'description':description}
    cursor.execute('''INSERT INTO userservices(id,user_id,business_id,name,price,currency,description,category,source,is_active,created_at)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'localos',TRUE,NOW())''',(service['id'],user_id,business_id,name,price,currency,description,category))
    distribution_id=str(uuid.uuid4())
    cursor.execute('INSERT INTO operator_service_distribution(id,business_id,user_id,service_id,request_key) VALUES (%s,%s,%s,%s,%s)',
        (distribution_id,business_id,user_id,service['id'],request_key))
    task_id,task_text=manual_task(cursor,business_id,service)
    cursor.execute('UPDATE operator_service_distribution SET manual_task_id=%s WHERE id=%s',(task_id,distribution_id))
    saved_text=f'В LocalOS добавлена услуга «{name}»: {price} {currency}. {task_text}'
    google=prepare_google(cursor,business_id,user_id,{'distribution_id':distribution_id})
    if google.get('status')=='approval_required':
        return {**google,'chat_response':saved_text+'\n\n'+google['chat_response'],'service_id':service['id'],'distribution_id':distribution_id,'manual_task_id':task_id}
    return result(saved_text+'\nGoogle: '+google['chat_response'],service_id=service['id'],distribution_id=distribution_id,
                  manual_task_id=task_id,google_status=google.get('google_status','blocked'))


def distribution(cursor,business_id,ident):
    cursor.execute('''SELECT d.*,s.name,s.price,s.currency,s.description,s.is_active FROM operator_service_distribution d
        JOIN userservices s ON s.id=d.service_id AND s.business_id=d.business_id WHERE d.id=%s AND d.business_id=%s FOR UPDATE OF d,s''',(ident,business_id))
    row=_row(cursor,cursor.fetchone())
    if not row or not row.get('is_active'):
        raise ValueError('Услуга недоступна в выбранном бизнесе.')
    return row


def service_version(row):
    return version({key:str(row.get(key) or '') for key in ('service_id','name','price','currency','description')})


def prepare_google(cursor,business_id,user_id,args):
    authorize_actor(cursor,user_id,business_id)
    row=distribution(cursor,business_id,args.get('distribution_id'))
    if row['google_status']=='completed':
        return result('Google уже обновлён.',google_status='completed')
    try:
        client,account_id=load_google(cursor,business_id,args.get('account_id'))
        preview=client.preview(row)
    except Exception:
        text=str(sys.exception()) if isinstance(sys.exception(),ValueError) else 'Не удалось проверить доступ к Google. Услуга в LocalOS сохранена; подключите Google или повторите позже.'
        cursor.execute("UPDATE operator_service_distribution SET google_status='blocked',google_error=%s WHERE id=%s",(text,row['id']))
        return result(text,'blocked',google_status='blocked')
    preview.update(account_id=account_id,service_version=service_version(row))
    cursor.execute("UPDATE operator_service_distribution SET google_status='approval_required',google_preview=%s::jsonb,google_error=NULL WHERE id=%s",(json.dumps(preview),row['id']))
    return result(f"Добавить в Google «{preview.get('title')}» услугу «{row['name']}» за {row['price']} {row['currency']}? Существующие услуги будут сохранены.",
        'approval_required',capability='services.google.add',approval={'status':'pending','capability':'services.google.add','summary':f"{row['name']}: {row['price']} {row['currency']} → Google {preview.get('title')}",'envelope':{'distribution_id':row['id'],'preview':preview}})


def apply_google(cursor,business_id,user_id,envelope):
    authorize_actor(cursor,user_id,business_id)
    row=distribution(cursor,business_id,envelope.get('distribution_id'))
    if row['google_status']=='completed':
        return result('Google уже обновлён.',google_status='completed')
    preview=envelope.get('preview') or {}
    if preview!=row['google_preview'] or preview.get('service_version')!=service_version(row):
        return result('Услуга или подтверждение изменились. Подготовьте новое подтверждение.','blocked')
    try:
        client,_=load_google(cursor,business_id,preview.get('account_id'))
        evidence=client.apply(preview)
    except Exception:
        text=str(sys.exception()) if isinstance(sys.exception(),ValueError) else 'Google не подтвердил обновление. Услуга в LocalOS сохранена. Повторите подтверждение для проверки результата.'
        cursor.execute("UPDATE operator_service_distribution SET google_status='needs_attention',google_error=%s WHERE id=%s",(text,row['id']))
        return result(text,'blocked',google_status='needs_attention')
    cursor.execute("UPDATE operator_service_distribution SET google_status='completed',google_error=NULL,updated_at=NOW() WHERE id=%s",(row['id'],))
    return result('Услуга сохранена в Google, результат проверен через API. Публичная карточка может обновиться позже.',
        google_status='completed',external_writes_performed=not evidence['already_present'])


def update_manual_task(cursor,business_id,user_id,message,args):
    authorize_actor(cursor,user_id,business_id)
    row=distribution(cursor,business_id,args.get('distribution_id'))
    task_id=row.get('manual_task_id')
    if not task_id:
        return result('Для этой услуги нет задачи по ручному обновлению карт.','blocked')
    cursor.execute('SELECT * FROM journey_actions WHERE id=%s AND business_id=%s FOR UPDATE',(task_id,business_id))
    task=_row(cursor,cursor.fetchone())
    if args.get('command')=='assign':
        if not re.search(r'назнач|ответствен|поручи|передай',message,re.I):
            return result('Укажите, кому назначить задачу.','clarification_required')
        cursor.execute("SELECT m.user_id FROM business_members m JOIN users u ON u.id=m.user_id WHERE m.business_id=%s AND m.user_id=%s AND m.status='active' AND m.role IN ('admin','manager') AND u.is_active=TRUE",(business_id,args.get('user_id')))
        if not cursor.fetchone():
            return result('Выберите действующего управляющего этого бизнеса.','blocked')
        if task.get('status') in {'completed','cancelled','superseded'}:
            return result('Задача уже завершена.','blocked')
        cursor.execute('UPDATE journey_actions SET user_id=%s,version=version+1,updated_at=NOW() WHERE id=%s',(args['user_id'],task_id))
        return result('Ответственный за обновление услуги назначен. Задача доступна в LocalOS; Telegram-уведомление зависит от настроек задач.')
    if args.get('command')!='complete' or re.search(r'\bне\s+(?:выполн|обнов|готов|добав)',message,re.I) or not re.search(r'выполнено|выполнил|обновил|готово|добавил.*карт',message,re.I):
        return result('Подтвердите, что услуга действительно обновлена на всех площадках из задачи.','clarification_required')
    if task.get('status')=='completed':
        return result('Задача уже отмечена выполненной.')
    from services.lead_journey_service import execute_command
    execute_command(cursor,action_id=task_id,business_id=business_id,user_id=user_id,command='complete',expected_version=task['version'],
        idempotency_key='operator-service-complete:'+row['id'],surface='system',payload={'note':message,'verification_status':'user_reported'})
    return result('Обновление остальных карт отмечено выполненным со слов пользователя. Автоматической проверки этих площадок не было.')


def existing_price(cursor,business_id,user_id,message,args):
    authorize_actor(cursor,user_id,business_id)
    if not re.search(r'измен|обнов|существующ',message,re.I):
        return result('Подтвердите, что нужно изменить существующую услугу.','clarification_required')
    cursor.execute('SELECT id,name,price,currency FROM userservices WHERE id=%s AND business_id=%s AND COALESCE(is_active,TRUE)=TRUE',(args.get('service_id'),business_id))
    service=_row(cursor,cursor.fetchone())
    try:
        price=Decimal(args.get('price') or '')
        if not price.is_finite() or price<0 or price>1000000000 or price!=price.quantize(Decimal('.01')):
            raise ValueError('price')
    except (ValueError,InvalidOperation):
        return result('Уточните новую цену.','clarification_required')
    if not service:
        return result('Услуга не найдена в выбранном бизнесе.','blocked')
    envelope={'existing_service':service,'new_price':str(price)}
    return result(f"Изменить цену существующей услуги «{service['name']}» с {service['price']} на {price} {service.get('currency') or ''}? Новая услуга не будет создана. Это изменение только в LocalOS.",
        'approval_required',capability='services.existing_price',approval={'status':'pending','capability':'services.existing_price','envelope':envelope})


def apply_existing_price(cursor,business_id,user_id,envelope):
    authorize_actor(cursor,user_id,business_id)
    before=envelope.get('existing_service') or {}
    cursor.execute('SELECT id,name,price,currency FROM userservices WHERE id=%s AND business_id=%s AND COALESCE(is_active,TRUE)=TRUE FOR UPDATE',(before.get('id'),business_id))
    current=_row(cursor,cursor.fetchone())
    if not current or version({k:str(v) for k,v in current.items()})!=version({k:str(v) for k,v in before.items()}):
        return result('Услуга изменилась после подтверждения. Подготовьте новое изменение.','blocked')
    cursor.execute('UPDATE userservices SET price=%s WHERE id=%s AND business_id=%s',(envelope['new_price'],current['id'],business_id))
    return result(f"Цена услуги «{current['name']}» в LocalOS изменена на {envelope['new_price']} {current.get('currency') or ''}. Новая услуга не создана. Карты этим действием не обновлялись.")


def tools(cursor,business_id,user_id,message,request_key):
    def invoke(handler,args):
        try:
            return handler(args)
        except (ValueError,PermissionError):
            return result(str(sys.exception()),'blocked')
    entries=[
        {'name':'services.existing_price','capability':'services.existing_price','description':'После обнаружения похожей услуги пользователь выбрал изменить существующую. Подготовь отдельное подтверждение цены, service_id из creation_context. Меняет только LocalOS, не создаёт новую услугу и не обновляет Google.',
         'input_schema':{'type':'object','required':['service_id','price'],'properties':{'service_id':{'type':'string'},'price':{'type':'string'}}},
         'risk_class':'write_internal','approval_required':True,'deterministic_preparation_response':True,'prepare_approval':lambda a:existing_price(cursor,business_id,user_id,message,a)},
        {'name':'services.manual_task','capability':'services.create','description':'Назначить существующую задачу обновления услуги управляющему или отметить её выполненной по явному сообщению пользователя. ID задачи/управляющего бери из creation_context. Не отмечай выполненным по просьбе выполнить работу.',
         'input_schema':{'type':'object','required':['distribution_id','command'],'properties':{'distribution_id':{'type':'string'},'command':{'type':'string','enum':['assign','complete']},'user_id':{'type':'string'}}},
         'risk_class':'write_internal_draft','deterministic_response':True,'execute':lambda a:update_manual_task(cursor,business_id,user_id,message,a)},
        {'name':'services.creation_context','capability':'services.read','description':'Прочитай существующие услуги, валюту бизнеса и статусы добавленных услуг. ID бери только из этого результата. Пользователю называй названия, не ID.',
         'input_schema':{'type':'object','properties':{}},'risk_class':'read_only','execute':lambda a:context(cursor,business_id,user_id,a)},
        {'name':'services.create','capability':'services.create','description':'Создать одну новую услугу по явной команде. Название, описание и категория только из сообщения. Цена из продиктованной суммы; не выдумывай валюту — используй настройки бизнеса или уточни. При похожем названии сначала уточнение, create_separate только после явной просьбы создать отдельную. Не использовать для изменения существующей услуги. Google отдельно через services.google.add.',
         'input_schema':{'type':'object','required':['name','price'],'properties':{'name':{'type':'string','maxLength':200},'price':{'type':'string'},'currency':{'type':'string'},'description':{'type':'string'},'category':{'type':'string'},'create_separate':{'type':'boolean'}}},
         'risk_class':'write_internal_draft','deterministic_response':True,'execute':lambda a:create(cursor,business_id,user_id,message,request_key,a)},
        {'name':'services.google.add','capability':'services.google.add','description':'Подготовить подтверждение добавления сохранённой услуги в Google. distribution_id возьми из creation_context. Не выполняет внешнюю запись до отдельного подтверждения.',
         'input_schema':{'type':'object','required':['distribution_id'],'properties':{'distribution_id':{'type':'string'},'account_id':{'type':'string'}}},
         'risk_class':'external_write','approval_required':True,'deterministic_preparation_response':True,'prepare_approval':lambda a:prepare_google(cursor,business_id,user_id,a)}]
    for entry in entries:
        for key in ('execute','prepare_approval'):
            if key in entry:
                handler=entry[key]
                entry[key]=lambda a,handler=handler:invoke(handler,a)
    return entries
