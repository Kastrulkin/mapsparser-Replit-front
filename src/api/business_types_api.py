import sys
import traceback

from flask import Blueprint, jsonify, request

from auth_system import verify_session
from database_manager import DatabaseManager


business_types_bp = Blueprint("business_types_api", __name__)


def _row_to_dict(cursor, row):
    if row is None:
        return None
    if hasattr(row, "keys"):
        return {key: row[key] for key in row.keys()}
    columns = [description[0] for description in cursor.description]
    return dict(zip(columns, row))


@business_types_bp.route("/api/business-types", methods=["GET"])
def get_business_types_public():
    """Получить все активные типы бизнеса (для всех пользователей)"""
    try:
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return jsonify({"error": "Требуется авторизация"}), 401

        token = auth_header.split(" ")[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401

        db = DatabaseManager()
        cursor = db.conn.cursor()
        cursor.execute(
            """
            SELECT type_key, label
            FROM businesstypes
            WHERE COALESCE(LOWER(is_active::text), '1') IN ('1', 'true', 't')
            ORDER BY label
            """
        )
        rows = cursor.fetchall()

        types = []
        for row in rows:
            row_data = _row_to_dict(cursor, row) if row else {}
            types.append(
                {
                    "type_key": row_data.get("type_key"),
                    "label": row_data.get("label"),
                }
            )

        db.close()
        return jsonify({"types": types})

    except Exception:
        error = sys.exc_info()[1]
        print(f"❌ Ошибка получения типов бизнеса: {error}")
        traceback.print_exc()
        return jsonify({"error": str(error)}), 500
