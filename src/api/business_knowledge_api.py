"""Business knowledge forms; read and internal save do not require an Operator plan."""
import json
import uuid
from flask import Blueprint, jsonify, request, send_file
from core.auth_helpers import require_auth_from_request
from database_manager import DatabaseManager
from services import business_knowledge
from services.business_permissions import load_actor

business_knowledge_bp=Blueprint('business_knowledge',__name__)


@business_knowledge_bp.errorhandler(413)
def oversized(_error):
    return jsonify({'error':'Файл превышает 10 МБ. Разделите документ.'}),413


def dispatch(handler):
    session=require_auth_from_request()
    if not session:return jsonify({'error':'Требуется авторизация.'}),401
    data=request.get_json(silent=True) or {} if request.is_json else request.form.to_dict()
    if not isinstance(data,dict):return jsonify({'error':'Некорректный запрос.'}),400
    scope_type=request.args.get('scope_type') or data.get('scope_type')
    scope_id=request.args.get('scope_id') or data.get('scope_id')
    db=DatabaseManager()
    try:
        cursor=db.conn.cursor()
        user=load_actor(cursor,session.get('user_id') or session.get('id'))
        user.update({key:session[key] for key in ('session_kind','scope_business_id') if key in session})
        result=handler(cursor,scope_type,scope_id,user,data)
        if request.method!='GET':db.conn.commit()
        response=jsonify(result) if isinstance(result,dict) else result
        response.headers['Cache-Control']='private, no-store'
        return response
    except PermissionError:
        import sys
        db.conn.rollback();return jsonify({'error':str(sys.exception())}),403
    except LookupError:
        import sys
        db.conn.rollback();return jsonify({'error':str(sys.exception())}),404
    except business_knowledge.Conflict:
        import sys
        db.conn.rollback();return jsonify({'error':str(sys.exception()),'refresh_required':True}),409
    except (ValueError,TypeError):
        import sys
        db.conn.rollback();return jsonify({'error':str(sys.exception())}),400
    finally:db.close()


@business_knowledge_bp.route('/api/business-knowledge',methods=['GET','POST'])
def knowledge():
    return dispatch(lambda c,t,s,u,d:business_knowledge.read(c,t,s,u) if request.method=='GET' else business_knowledge.mutate(c,t,s,u,d))


@business_knowledge_bp.get('/api/business-knowledge/templates')
def templates():
    def handle(cursor,kind,scope,user,data):
        actor=business_knowledge.access(cursor,kind,scope,user)
        from services.business_knowledge_templates import fields
        cursor.execute("SELECT type_key,label FROM businesstypes WHERE COALESCE(LOWER(is_active::text),'1') IN ('1','true','t') ORDER BY label")
        from services.operator_conversations import _row
        types=[_row(cursor,row) for row in cursor.fetchall()]
        saved=actor['target'].get('business_type')
        if saved and not any(item['type_key']==saved for item in types):types.append({'type_key':saved,'label':{'hotel':'Отель','guest_house':'Гостевой дом'}.get(saved,saved)})
        return {'items':[{**item,'fields':fields(item['type_key'])} for item in types]}
    return dispatch(handle)


@business_knowledge_bp.get('/api/business-knowledge/<record_id>/history')
def history(record_id):
    return dispatch(lambda c,t,s,u,d:business_knowledge.history(c,t,s,u,record_id))


@business_knowledge_bp.post('/api/business-knowledge/documents')
def upload():
    if request.content_length and request.content_length>10*1024*1024+65536:
        from werkzeug.exceptions import RequestEntityTooLarge
        raise RequestEntityTooLarge()
    def handle(cursor,kind,scope,user,data):
        file=request.files.get('file')
        if not file:raise ValueError('Выберите документ.')
        if data.get('version'):data['version']=int(data['version'])
        return business_knowledge.upload(cursor,kind,scope,user,file.stream.read(10*1024*1024+1),file.filename or '',data)
    return dispatch(handle)


@business_knowledge_bp.get('/api/business-knowledge/<record_id>/download')
def download(record_id):
    def handle(cursor,kind,scope,user,data):
        version=request.args.get('version')
        path,name=business_knowledge.download(cursor,kind,scope,user,record_id,int(version) if version else None)
        response=send_file(path,as_attachment=True,download_name=name,conditional=False,max_age=0)
        response.headers['Cache-Control']='private, no-store'
        return response
    return dispatch(handle)


def prepare_change(cursor,scope_type,scope_id,user,data,channel='web'):
    """Reuse durable Operator approval; do not save knowledge until explicit confirmation."""
    from services.operator_conversations import get_or_create_operator_conversation,create_pending_operator_action
    actor=business_knowledge.access(cursor,scope_type,scope_id,user)
    if not actor['can_edit']:raise PermissionError('Изменение подтверждает владелец или назначенный редактор.')
    if data.get('operation') not in {'value','rule','document'}:raise ValueError('Через поручение меняются значения, правила и документы.')
    if not actor['anchor_id']:raise ValueError('Добавьте точку сети перед подготовкой подтверждения.')
    if not data.get('request_id'):raise ValueError('Нужен идентификатор запроса.')
    previous=business_knowledge.record(cursor,data['id']) if data.get('id') else None
    if previous and (previous['scope_type']!=scope_type or previous['scope_id']!=scope_id or not business_knowledge._visible(previous,actor)):
        raise PermissionError('Запись недоступна.')
    if data.get('source_entry_id'):
        if scope_type!='business':raise ValueError('Наблюдение относится к конкретной точке.')
        observation=business_knowledge.journal_source(cursor,actor,data['source_entry_id'])
        if observation.get('is_voided'):raise ValueError('Наблюдение отменено. Подготовьте изменение из актуального источника.')
        data={**data,'payload':{**(data.get('payload') or {}),'source_entry_id':observation['id'],'source_entry_version':observation['version'],'source':'Рабочий журнал: '+observation['id']}}
    # Validate exactly the same command without persisting a draft copy or its receipt.
    cursor.execute('SAVEPOINT knowledge_preview')
    try:checked=business_knowledge.mutate(cursor,scope_type,scope_id,user,data)
    finally:
        cursor.execute('ROLLBACK TO SAVEPOINT knowledge_preview')
        cursor.execute('RELEASE SAVEPOINT knowledge_preview')
    conversation=get_or_create_operator_conversation(cursor,business_id=actor['anchor_id'],user_id=user['user_id'],channel=channel,transport_key='business-knowledge')
    action=create_pending_operator_action(cursor,conversation_id=conversation['id'],business_id=actor['anchor_id'],user_id=user['user_id'],capability='business.knowledge',
        envelope={'scope_type':scope_type,'scope_id':scope_id,'change':data},request_key=data['request_id'])
    cursor.execute("UPDATE operatoractions SET expires_at=COALESCE(expires_at,NOW()+INTERVAL '30 minutes') WHERE id=%s",(action['id'],))
    return {'status':'approval_required','approval':{'action_id':action['id'],'status':'pending','business_id':actor['anchor_id']},
            'preview':{'before':business_knowledge._public(previous) if previous else None,'after':checked.get('record',{}).get('payload_json')},
            'chat_response':'Проверьте новые сведения. Они сохранятся после подтверждения.', 'external_writes_performed':False}


@business_knowledge_bp.post('/api/business-knowledge/preview')
def preview():
    return dispatch(lambda c,t,s,u,d:prepare_change(c,t,s,u,d))


@business_knowledge_bp.post('/api/business-knowledge/proposals')
def proposal():
    def handle(cursor,kind,scope,user,data):
        if kind!='business':raise ValueError('Предложение относится к конкретному бизнесу.')
        business_knowledge.access(cursor,kind,scope,user)
        text=str(data.get('text') or '').strip()
        entry=business_knowledge.propose(cursor,scope,user,text,data.get('record_id'),data.get('request_id'))
        return {'entry_id':entry['id'],'message':'Предложение сохранено в рабочем журнале. Постоянные сведения не изменены.'}
    return dispatch(handle)
