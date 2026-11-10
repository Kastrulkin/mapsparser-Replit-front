"""Customer YouGile connections; writes use existing Operator approvals."""
import functools
import sys
from flask import Blueprint, current_app, jsonify, request
from core.auth_context import AuthContext
from core.auth_helpers import require_auth_from_request
from pg_db_utils import get_db_connection
from services import yougile_tasks
from services.yougile_client import YouGileError

yougile_bp = Blueprint('yougile_api', __name__)


def endpoint(function):
    @functools.wraps(function)
    def handle(business_id):
        actor = require_auth_from_request()
        if not actor:
            return jsonify(success=False, error='Войдите в LocalOS.'), 401
        auth = AuthContext.from_session(actor)
        if auth.session_kind != 'standard' or auth.impersonating or not auth.permits_business(business_id):
            return jsonify(success=False, error='Подключение доступно в личном аккаунте LocalOS.'), 403
        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            if function.__name__ == 'status' and not yougile_tasks.enabled():
                from services.business_permissions import load_actor, require_permission
                require_permission(cursor, business_id, load_actor(cursor, auth.user_id), 'business.read')
                return jsonify(success=True, enabled=False, connected=False, configured=False)
            yougile_tasks.authorize(cursor, business_id, auth.user_id)
            result = function(cursor, business_id, auth.user_id)
            conn.commit()
            return jsonify(success=True, **result)
        except (YouGileError, PermissionError):
            error = sys.exception()
            if conn:
                conn.rollback()
            return jsonify(success=False, code=getattr(error, 'code', 'access_denied'), error=str(error)), getattr(error, 'status', 403)
        except Exception:
            error = sys.exception()
            if conn:
                conn.rollback()
            current_app.logger.error('YouGile request failed type=%s', type(error).__name__)
            return jsonify(success=False, error='Не удалось обработать подключение YouGile.'), 500
        finally:
            if conn:
                conn.close()
    return handle


def body():
    value = request.get_json(silent=True)
    if not isinstance(value, dict):
        raise YouGileError('invalid_request', 'Проверьте данные запроса.')
    return value


@yougile_bp.get('/api/business/<business_id>/yougile/status')
@endpoint
def status(cursor, business_id, user_id):
    from services.business_permissions import actor_roles, load_actor, roles_allow
    roles = actor_roles(cursor, business_id, load_actor(cursor, user_id))
    return {**yougile_tasks.status(cursor, business_id),
            'can_configure': roles_allow(roles, 'business.settings.write'),
            'can_write': roles_allow(roles, 'operations.write')}


@yougile_bp.post('/api/business/<business_id>/yougile/connection')
@endpoint
def connect(cursor, business_id, user_id):
    return yougile_tasks.connect(cursor, business_id, user_id, body().get('api_key'))


@yougile_bp.delete('/api/business/<business_id>/yougile/connection')
@endpoint
def disconnect(cursor, business_id, user_id):
    return yougile_tasks.disconnect(cursor, business_id, user_id)


@yougile_bp.get('/api/business/<business_id>/yougile/catalog')
@endpoint
def catalog(cursor, business_id, user_id):
    return yougile_tasks.catalog(cursor, business_id, user_id, request.args.get('project_id'), request.args.get('board_id'))


@yougile_bp.put('/api/business/<business_id>/yougile/selection')
@endpoint
def selection(cursor, business_id, user_id):
    return yougile_tasks.select(cursor, business_id, user_id, body())


@yougile_bp.get('/api/business/<business_id>/yougile/tasks')
@endpoint
def tasks(cursor, business_id, user_id):
    return yougile_tasks.read_tasks(cursor, business_id, user_id)


@yougile_bp.post('/api/business/<business_id>/yougile/tasks/preview')
@endpoint
def preview(cursor, business_id, user_id):
    from services.operator_yougile_tasks import preview
    from services.operator_conversations import get_or_create_operator_conversation, create_pending_operator_action
    result = preview(cursor, business_id, user_id, body())
    if result.get('status') == 'approval_required':
        conversation = get_or_create_operator_conversation(cursor, business_id=business_id, user_id=user_id, channel='web')
        action = create_pending_operator_action(cursor, conversation_id=conversation['id'], business_id=business_id,
            user_id=user_id, capability='tasks.yougile', envelope=result['approval']['envelope'])
        cursor.execute("UPDATE operatoractions SET expires_at=COALESCE(expires_at,NOW()+INTERVAL '30 minutes') WHERE id=%s", (action['id'],))
        result['approval']['action_id'] = action['id']
    return {'operator_result': result}
