"""Shared profile defaults; voice changes use Operator approvals."""
import uuid
from flask import jsonify, request
from core.auth_helpers import require_auth_from_request, verify_business_access
from database_manager import DatabaseManager
from services import business_input_settings


def register_input_settings_routes(bp):
    @bp.route('/input-settings', methods=['GET', 'PATCH'])
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
            if request.method == 'PATCH':
                payload = request.get_json(silent=True) or {}
                if not isinstance(payload, dict):
                    return jsonify({'error': 'Неверные настройки'}), 400
                data = business_input_settings.save_profile_settings(cursor, business_id, user.get('user_id') or user.get('id'), payload, str(payload.get('request_id') or uuid.uuid4()))
                response = jsonify({**data, 'can_edit': True})
                db.conn.commit()
                return response
            data = business_input_settings.resolve(cursor, business_id)
            try:
                business_input_settings.authorize_write(cursor, business_id, user.get('user_id') or user.get('id'))
                data['can_edit'] = True
            except PermissionError:
                data['can_edit'] = False
            return jsonify(data)
        except PermissionError:
            return jsonify({'error': 'Менять профиль может владелец бизнеса'}), 403
        except ValueError:
            import sys
            return jsonify({'error': str(sys.exception())}), 409
        finally:
            db.rollback_and_close()
