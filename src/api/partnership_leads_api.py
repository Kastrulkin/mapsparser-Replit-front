"""Partnership lead lifecycle routes."""
from __future__ import annotations
import sys

from flask import Blueprint

from services import partnership_leads_service as service
from flask import jsonify, request, current_app
from api.content_plans_api import _require_auth
from database_manager import DatabaseManager
from services.telegram_control_scope import resolve_control_scope
from services.partnership_results import read_results, save_agreement
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
        confirmed = [item for item in items if (item.get('agreement_json') or {}).get('status') == 'confirmed']
        launched = [item for item in confirmed if item.get('partnership_launched_at')]
        return jsonify(success=True, scope=scope, items=items, locations=locations, counts={
            'partners': len({str(item.get('company_id') or item['id']) for item in confirmed}),
            'launched': len(launched), 'preparing': len(confirmed) - len(launched),
            'needs_decision': sum(bool(item.get('agreement_json')) and (item['agreement_json'].get('status') != 'confirmed' or item['agreement_json'].get('instruction_terms_version') != item['agreement_json'].get('terms_version')) for item in items),
        })
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
