"""Tenant-scoped, read-only team directory for the business profile."""
from flask import jsonify, request
from core.auth_helpers import require_auth_from_request, verify_business_access
from database_manager import DatabaseManager
from services.business_member_directory import list_business_members


def register_member_directory_routes(bp):
    @bp.route('/business-members', methods=['GET'])
    def business_members():
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
            return jsonify({'business_id': business_id, 'members': list_business_members(cursor, business_id)})
        finally:
            db.rollback_and_close()
