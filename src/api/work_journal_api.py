"""Work journal HTTP adapter; the same application services back chat."""
import sys
import uuid
from flask import Blueprint, jsonify, request
from auth_system import verify_session
from core.auth_helpers import session_allows_business
from database_manager import DatabaseManager
from services import work_journal, work_recommendations, operator_work_journal, work_review
from services.operator_conversations import _row

work_journal_bp=Blueprint('work_journal_api',__name__)


def actor():
    header=request.headers.get('Authorization','')
    user=verify_session(header[7:]) if header.startswith('Bearer ') else None
    if not user:raise PermissionError('Требуется авторизация.')
    return user


def dispatch(handler):
    db=DatabaseManager()
    try:
        session=actor();data=request.get_json(silent=True) or {};business=request.args.get('business_id') or data.get('business_id')
        if not business:raise ValueError('Выберите бизнес.')
        if not session_allows_business(session,business):raise PermissionError('Нет доступа к бизнесу в этой сессии.')
        user=session.get('user_id') or session.get('id')
        value=handler(db.conn.cursor(),business,user,data)
        response=jsonify(value)
        if request.method!='GET':db.conn.commit()
        return response
    except PermissionError:
        db.conn.rollback();return jsonify({'error':str(sys.exception())}),403
    except ValueError:
        db.conn.rollback();return jsonify({'error':str(sys.exception())}),409
    except Exception:
        db.conn.rollback()
        raise
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
        response['review_enabled']=work_review.enabled(business)
        response['can_review']=response['review_enabled'] and work_review.can_review(cursor,business,user)
        if response['can_review']:
            cursor.execute("SELECT m.user_id,m.role,COALESCE(to_jsonb(u)->>'name',to_jsonb(u)->>'email',m.user_id) name FROM business_members m JOIN users u ON u.id=m.user_id WHERE m.business_id=%s AND m.status='active'",(business,))
            response['members']=[_row(cursor,row) for row in cursor.fetchall()]
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


@work_journal_bp.route('/api/work-journal/review',methods=['GET'])
def review_inbox():
    return dispatch(lambda c,b,u,d:{'items':work_review.list_inbox(c,b,u,request.args.get('status','new') or None,request.args.get('category') or None)})


@work_journal_bp.route('/api/work-journal/<entry_id>/decision',methods=['POST'])
def review_decision(entry_id):
    return dispatch(lambda c,b,u,d:{'entry':work_review.decision(c,b,u,entry_id,d)})


@work_journal_bp.route('/api/work-journal/<entry_id>/actions',methods=['GET','POST'])
def review_actions(entry_id):
    return dispatch(lambda c,b,u,d:({'action':work_review.create_action(c,b,u,entry_id,d)} if request.method=='POST' else {'items':work_review.links(c,b,u,entry_id)}))


@work_journal_bp.route('/api/work-journal/<entry_id>/actions/complete',methods=['POST'])
def complete_review_action(entry_id):
    return dispatch(lambda c,b,u,d:{'action':work_review.complete_action(c,b,u,entry_id,d)})


@work_journal_bp.route('/api/work-journal/digest-settings',methods=['GET','POST'])
def review_digest_settings():
    return dispatch(lambda c,b,u,d:work_review.digest_settings(c,b,u,d if request.method=='POST' else None))
