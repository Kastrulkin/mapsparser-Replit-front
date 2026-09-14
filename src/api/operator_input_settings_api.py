"""Read saved defaults; changes use the existing Operator approval flow."""
from flask import jsonify, request
from core.auth_helpers import require_auth_from_request, verify_business_access
from database_manager import DatabaseManager
from services import business_input_settings


def register_input_settings_routes(bp):
    @bp.route('/input-settings', methods=['GET'])
    def operator_input_settings():
        user = require_auth_from_request()
        if not user:
            return jsonify({'error': 'Требуется авторизация'}), 401
        business_id = request.args.get('business_id')
        if not business_id:
            return jsonify({'error': 'Выберите бизнес'}), 400
        db = DatabaseManager()
        try:
            cursor = db.conn.cursor()
            allowed, _ = verify_business_access(cursor, business_id, user)
            if not allowed:
                return jsonify({'error': 'Нет доступа к бизнесу'}), 403
            data = business_input_settings.resolve(cursor, business_id)
            try:
                business_input_settings.authorize_write(cursor, business_id, user.get('user_id') or user.get('id'))
                data['can_edit'] = True
            except PermissionError:
                data['can_edit'] = False
            return jsonify(data)
        finally:
            db.rollback_and_close()
