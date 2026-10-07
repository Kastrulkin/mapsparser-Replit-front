from flask import Blueprint, jsonify, request

from subscription_manager import get_capability_access

admin_prospecting_bp = Blueprint("admin_prospecting", __name__)


@admin_prospecting_bp.before_request
def require_paid_partnership_actions():
    if not request.path.startswith('/api/partnership/') or '/public/' in request.path:
        return None
    if request.method == 'GET':
        return None
    payload = request.get_json(silent=True) or {}
    business_id = str(payload.get('business_id') or request.args.get('business_id') or '').strip()
    if not business_id:
        return None
    access = get_capability_access(business_id, 'partnerships')
    if access.get('allowed'):
        return None
    return jsonify({'success': False, 'error': 'payment_required', **access, 'return_to': request.full_path.rstrip('?')}), 402
