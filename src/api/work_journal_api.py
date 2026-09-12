"""Work journal HTTP adapter; the same application services back chat."""
import sys
import uuid
from flask import Blueprint, jsonify, request
from auth_system import verify_session
from database_manager import DatabaseManager
from services import work_journal, work_recommendations, operator_work_journal
from services.operator_conversations import _row

work_journal_bp=Blueprint('work_journal_api',__name__)


def actor():
    header=request.headers.get('Authorization','')
    user=verify_session(header[7:]) if header.startswith('Bearer ') else None
    if not user:raise PermissionError('Требуется авторизация.')
    return user.get('user_id') or user.get('id')


def dispatch(handler):
    db=DatabaseManager()
    try:
        user=actor();data=request.get_json(silent=True) or {};business=request.args.get('business_id') or data.get('business_id')
        if not business:raise ValueError('Выберите бизнес.')
        value=handler(db.conn.cursor(),business,user,data)
        if request.method!='GET':db.conn.commit()
        return jsonify(value)
    except PermissionError:
        db.conn.rollback();return jsonify({'error':str(sys.exception())}),403
    except ValueError:
        db.conn.rollback();return jsonify({'error':str(sys.exception())}),409
    finally:db.close()


@work_journal_bp.route('/api/work-journal',methods=['GET','POST'])
def journal():
    def handle(cursor,business,user,data):
        if request.method=='POST':
            text=data.get('text') or ''
            row=work_journal.save_note(cursor,business,user,'web',None,data.get('request_id'),text,{**data,'quote':text})
            return {'status':'completed','entry':row}
        if not work_journal.installed(cursor):
            from services.operator_audio import authorize_actor
            authorize_actor(cursor,user,business)
            return {'enabled':False,'items':[]}
        current=work_journal.scope(cursor,business,user)
        rows=work_journal.list_entries(cursor,business,user,request.args.get('query',''),request.args.get('date'))
        for row in rows:row['can_edit']=current['role']=='owner' or row['user_id']==user
        response={'enabled':work_journal.enabled(business),'items':rows,'role':current['role'],'policy':work_recommendations.policy(cursor,business)}
        if current['role']=='owner':
            cursor.execute("SELECT id,kind,before_json,after_json,created_at FROM business_work_history WHERE business_id=%s AND kind<>'note' ORDER BY created_at DESC LIMIT 30",(business,))
            response['policy_history']=[_row(cursor,r) for r in cursor.fetchall()]
        return response
    return dispatch(handle)


@work_journal_bp.route('/api/work-journal/<entry_id>',methods=['PATCH'])
def edit(entry_id):
    return dispatch(lambda c,b,u,d:{'status':'completed','entry':work_journal.save_note(c,b,u,'web',None,d.get('request_id'),d.get('text') or '',{**d,'id':entry_id,'quote':d.get('text') or ''})})


@work_journal_bp.route('/api/work-journal/<entry_id>/history',methods=['GET'])
def history(entry_id):
    return dispatch(lambda c,b,u,d:{'items':work_journal.history(c,b,u,entry_id)})


@work_journal_bp.route('/api/work-journal/recommendations',methods=['POST'])
def recommendations():
    return dispatch(lambda c,b,u,d:work_recommendations.recommend(c,b,u,d))


def create_policy_preview(cursor,business,user,data,channel='web'):
    from services.operator_chat_service import process_chat
    def router(c,**kwargs):
        return operator_work_journal.prepare_approval(c,business,user,channel,kwargs['message'],data),{}
    return process_chat(cursor,business_id=business,user_id=user,channel=channel,message=data.get('message') or 'Подготовь изменение правил рекомендаций',
        payload={'request_id':data.get('request_id') or str(uuid.uuid4()),'work_change_hash':work_journal.digest({k:v for k,v in data.items() if k!='request_id'})},router=router)


@work_journal_bp.route('/api/work-journal/policy/preview',methods=['POST'])
def preview():
    return dispatch(lambda c,b,u,d:create_policy_preview(c,b,u,d))
