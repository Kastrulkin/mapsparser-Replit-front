"""Partnership lead lifecycle routes."""
from __future__ import annotations
import sys

from flask import Blueprint

from services import partnership_leads_service as service
from flask import jsonify, request, current_app
from api.content_plans_api import _require_auth
from database_manager import DatabaseManager
from services.telegram_control_scope import resolve_control_scope
from services.partnership_results import read_results, save_agreement, result_counts
from core.auth_helpers import verify_business_access

partnership_leads_bp = Blueprint("partnership_leads_api", __name__)


@partnership_leads_bp.route('/api/partnership/results', methods=['GET'])
@partnership_leads_bp.route('/api/partnership/results/<workstream_id>', methods=['POST'])
def partnership_results(workstream_id=None):
    user, error = _require_auth()
    if error:
        return error
    payload = (request.get_json(silent=True) or {}) if request.method == 'POST' else request.args
    if not hasattr(payload, 'get') or payload.get('scope_type', 'business') not in {'business', 'network'}:
        return jsonify(error='Недоступный контекст'), 403
    if not payload.get('scope_id') and not payload.get('business_id'):
        return jsonify(error='Выберите бизнес или сеть'), 400
    db = DatabaseManager()
    try:
        cursor = db.conn.cursor()
        scope = resolve_control_scope(cursor, user_id=str(user['user_id']), requested_kind=str(payload.get('scope_type') or 'business'), requested_id=payload.get('scope_id') or payload.get('business_id'))
        if not scope or scope.get('kind') not in {'business', 'network'}:
            return jsonify(error='Выберите доступный бизнес или сеть'), 403
        ids = scope.get('business_ids') or []
        for business_id in ids:
            allowed, _ = verify_business_access(cursor, business_id, user)
            if not allowed:
                return jsonify(error='Нет доступа к точке'), 403
            access_error = service._partnership_write_access(business_id, user)
            if access_error:
                return access_error
        if workstream_id:
            data = save_agreement(cursor, workstream_id, ids, str(payload.get('command') or ''), payload, str(user['user_id']))
            db.conn.commit()
            current_app.logger.info('partnership_agreement_action workstream_id=%s command=%s revision=%s', workstream_id, payload.get('command'), data.get('revision'))
            return jsonify(success=True, agreement=data)
        items = read_results(cursor, ids)
        cursor.execute('SELECT id, name FROM businesses WHERE id=ANY(%s) ORDER BY name, id', (list(ids),))
        locations = [dict(row) if hasattr(row, 'keys') else {'id': row[0], 'name': row[1]} for row in cursor.fetchall()]
        return jsonify(success=True, scope=scope, items=items, locations=locations, counts=result_counts(items))
    except PermissionError:
        db.conn.rollback()
        return jsonify(error='Партнёр недоступен'), 403
    except ValueError:
        db.conn.rollback()
        return jsonify(error=str(sys.exc_info()[1])), 409
    finally:
        db.close()

@partnership_leads_bp.route('/api/partnership/leads', methods=['GET'])
def partnership_list_leads():
    return service.partnership_list_leads()

@partnership_leads_bp.route('/api/partnership/leads/<string:lead_id>', methods=['PATCH'])
def partnership_update_lead(lead_id):
    return service.partnership_update_lead(lead_id)


@partnership_leads_bp.route('/api/partnership/leads/<string:lead_id>/shortlist', methods=['POST'])
def partnership_catalog_shortlist(lead_id):
    return service.partnership_catalog_shortlist(lead_id)

@partnership_leads_bp.route('/api/partnership/leads/<string:lead_id>/manual-contact', methods=['POST'])
def partnership_mark_lead_manual_contact(lead_id):
    return service.partnership_mark_lead_manual_contact(lead_id)

@partnership_leads_bp.route('/api/partnership/leads/bulk-update', methods=['POST'])
def partnership_bulk_update_leads():
    return service.partnership_bulk_update_leads()

@partnership_leads_bp.route('/api/partnership/leads/<string:lead_id>', methods=['DELETE'])
def partnership_delete_lead(lead_id):
    return service.partnership_delete_lead(lead_id)

@partnership_leads_bp.route('/api/partnership/leads/bulk-delete', methods=['POST'])
def partnership_bulk_delete_leads():
    return service.partnership_bulk_delete_leads()

@partnership_leads_bp.route('/api/partnership/leads/<string:lead_id>/prepare-room', methods=['POST'])
def partnership_prepare_sales_room(lead_id):
    return service.partnership_prepare_sales_room(lead_id)

@partnership_leads_bp.route('/api/admin/prospecting/lead/<string:lead_id>/status', methods=['POST'])
def update_lead_status(lead_id):
    return service.update_lead_status(lead_id)

@partnership_leads_bp.route('/api/admin/prospecting/lead/<string:lead_id>/manual-contact', methods=['POST'])
def mark_lead_manual_contact(lead_id):
    return service.mark_lead_manual_contact(lead_id)

@partnership_leads_bp.route('/api/admin/prospecting/lead/<string:lead_id>/comment', methods=['POST'])
def add_lead_comment(lead_id):
    return service.add_lead_comment(lead_id)

@partnership_leads_bp.route('/api/admin/prospecting/lead/<string:lead_id>/timeline', methods=['GET'])
def get_lead_timeline(lead_id):
    return service.get_lead_timeline(lead_id)

@partnership_leads_bp.route('/api/admin/prospecting/lead/<string:lead_id>/shortlist', methods=['POST'])
def review_lead_shortlist(lead_id):
    return service.review_lead_shortlist(lead_id)

@partnership_leads_bp.route('/api/admin/prospecting/lead/<string:lead_id>/select', methods=['POST'])
def select_lead_for_outreach(lead_id):
    return service.select_lead_for_outreach(lead_id)

@partnership_leads_bp.route('/api/admin/prospecting/lead/<string:lead_id>/channel', methods=['POST'])
def select_outreach_channel(lead_id):
    return service.select_outreach_channel(lead_id)

@partnership_leads_bp.route('/api/admin/prospecting/lead/<string:lead_id>/contacts', methods=['POST'])
def update_lead_contacts(lead_id):
    return service.update_lead_contacts(lead_id)

@partnership_leads_bp.route('/api/admin/prospecting/lead/<string:lead_id>/language', methods=['POST'])
def update_lead_language(lead_id):
    return service.update_lead_language(lead_id)

@partnership_leads_bp.route('/api/admin/prospecting/lead/<string:lead_id>', methods=['DELETE'])
def delete_lead(lead_id):
    return service.delete_lead(lead_id)

@partnership_leads_bp.route('/api/admin/prospecting/lead/<string:lead_id>/workstreams', methods=['POST'])
def create_lead_workstream(lead_id):
    return service.create_lead_workstream(lead_id)


@partnership_leads_bp.route('/api/partnership/continuations', methods=['GET', 'POST'])
@partnership_leads_bp.route('/api/partnership/continuations/<task_id>', methods=['GET', 'POST'])
def partnership_continuations(task_id=None):
    from flask import request, jsonify
    from psycopg2.extras import RealDictCursor
    from api.prospecting.access_schema import _require_auth, _resolve_business_for_user
    from pg_db_utils import get_db_connection
    from services.partnership_leads_service import _partnership_write_access
    from services.outreach_continuation import create_task, list_tasks, control_task, continuation_enabled, actor_can_write, prepare_new_task_approval, prepare_revision_approval, view, KIND
    from services.partnership_group_view import enrich_group

    user, error = _require_auth()
    if error:
        return error
    data = (request.get_json(silent=True) or {}) if request.method == 'POST' else request.args
    if not isinstance(data, dict) and request.method == 'POST':
        return jsonify({'error': 'invalid_payload'}), 400
    conn = get_db_connection()
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        requested = str(data.get('business_id') or '').strip()
        if not requested:
            return jsonify({'error': 'business_required'}), 400
        business_id = _resolve_business_for_user(cursor, user, requested)
        if business_id != requested:
            return jsonify({'error': 'access_denied'}), 403
        if not continuation_enabled(business_id):
            return jsonify({'enabled': False, 'items': []}) if request.method == 'GET' else (jsonify({'error': 'feature_disabled'}), 404)
        if not actor_can_write(cursor, business_id, user):
            return jsonify({'error': 'write_access_required'}), 403
        denied = _partnership_write_access(business_id, user)
        if denied:
            return denied
        user_id = str(user['user_id'])
        if request.method == 'GET' and task_id:
            cursor.execute("SELECT * FROM operator_async_jobs WHERE id=%s AND business_id=%s AND kind=%s",
                           (task_id, business_id, KIND))
            row = cursor.fetchone()
            if not row:
                return jsonify({'error': 'task_not_found'}), 404
            result = view(dict(row))
            from services.outreach_continuation import delivery_report
            result['report'].update(delivery_report(cursor, result))
            enrich_group(cursor, result, viewer_id=user_id)
        elif request.method == 'GET':
            from services.riderra_template_authorization_service import BUSINESS_ID
            result = {'enabled': True, 'supports_shortage_replenishment': business_id == BUSINESS_ID, 'items': list_tasks(cursor, business_id=business_id, user_id=user_id)}
            from services.outreach_continuation import delivery_report
            for task in result['items']:
                task['report'].update(delivery_report(cursor, task))
                enrich_group(cursor, task, viewer_id=user_id)
        elif str(data.get('operation') or '') == 'preview':
            from services.operator_conversations import (
                create_pending_operator_action, find_latest_operator_conversation,
                get_or_create_operator_conversation,
            )
            preview = (prepare_revision_approval(cursor, business_id=business_id, task_id=task_id,
                       raw=data.get('config'), request_id=str(data.get('request_id') or '')) if task_id else
                       prepare_new_task_approval(data.get('config'), business_id=business_id,
                                                request_id=str(data.get('request_id') or '')))
            if not preview.get('approval'):
                return jsonify(preview)
            conversation = find_latest_operator_conversation(cursor, business_id=business_id,
                                                              user_id=user_id, channel='web')
            if not conversation:
                conversation = get_or_create_operator_conversation(cursor, business_id=business_id,
                                                                    user_id=user_id, channel='web')
            action = create_pending_operator_action(cursor, conversation_id=str(conversation['id']),
                business_id=business_id, user_id=user_id, capability='partnerships.continue_outreach',
                envelope=preview['approval']['envelope'],
                request_key=str(data.get('request_id') or ''))
            cursor.execute("""UPDATE operatoractions SET status='rejected', updated_at=NOW()
                WHERE conversation_id=%s AND business_id=%s AND user_id=%s
                  AND capability='partnerships.continue_outreach'
                  AND status IN ('pending','pending_approval') AND id<>%s""",
                (str(conversation['id']), business_id, user_id, str(action['id'])))
            preview['approval']['action_id'] = str(action['id'])
            result = preview
        elif task_id:
            result = control_task(cursor, task_id=task_id, business_id=business_id, user_id=user_id,
                action=str(data.get('action') or ''), revision=str(data.get('revision') or ''),
                display_name=str(data.get('display_name') or ''))
            from services.outreach_continuation import delivery_report
            result['report'].update(delivery_report(cursor, result))
            enrich_group(cursor, result, viewer_id=user_id)
        else:
            result = create_task(cursor, business_id=business_id, user_id=user_id, config=data.get('config'), request_id=str(data.get('request_id') or ''))
        conn.commit()
        return jsonify(result)
    except ValueError as exc:
        conn.rollback()
        return jsonify({'error': str(exc)}), 409
    finally:
        conn.close()
