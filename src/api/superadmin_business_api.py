import secrets
import sys
import traceback
import uuid
from datetime import datetime

from flask import Blueprint, jsonify, request

from auth_system import get_user_by_id, set_password, verify_session
from core import email_delivery
from database_manager import DatabaseManager


superadmin_business_bp = Blueprint("superadmin_business_api", __name__)


def _auth_token_from_request():
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None
    return auth_header.split(" ")[1]


def _require_superadmin(db=None):
    token = _auth_token_from_request()
    if not token:
        if db is not None:
            db.close()
        return None, (jsonify({"error": "Требуется авторизация"}), 401)

    user_data = verify_session(token)
    if not user_data:
        if db is not None:
            db.close()
        return None, (jsonify({"error": "Недействительный токен"}), 401)

    active_db = db or DatabaseManager()
    if not active_db.is_superadmin(user_data["user_id"]):
        active_db.close()
        return None, (jsonify({"error": "Недостаточно прав"}), 403)

    return user_data, None


@superadmin_business_bp.route("/api/superadmin/businesses", methods=["GET"])
def get_all_businesses():
    """Получить все бизнесы (только для суперадмина)."""
    try:
        db = DatabaseManager()
        _, error_response = _require_superadmin(db)
        if error_response:
            return error_response

        businesses = db.get_all_businesses()
        db.close()

        return jsonify({"success": True, "businesses": businesses})

    except Exception:
        exc = sys.exc_info()[1]
        print(f"❌ Ошибка получения бизнесов: {exc}")
        return jsonify({"error": str(exc)}), 500


@superadmin_business_bp.route("/api/superadmin/businesses", methods=["POST"])
def create_business():
    """Создать новый бизнес (только для суперадмина)."""
    try:
        db = DatabaseManager()
        _, error_response = _require_superadmin(db)
        if error_response:
            return error_response

        data = request.get_json()
        name = data.get("name")
        description = data.get("description", "")
        industry = data.get("industry", "")
        owner_id = data.get("owner_id")
        owner_email = data.get("owner_email")
        owner_name = data.get("owner_name", "")
        owner_phone = data.get("owner_phone", "")

        if not name:
            db.close()
            return jsonify({"error": "Название бизнеса обязательно"}), 400

        if owner_email and not owner_id:
            existing_user = db.get_user_by_email(owner_email)
            if existing_user:
                owner_id = existing_user["id"]
                print(f"✅ Найден существующий пользователь: {owner_email} (ID: {owner_id})")
            else:
                cursor = db.conn.cursor()
                owner_id = str(uuid.uuid4())

                try:
                    cursor.execute(
                        """
                        INSERT INTO Users (id, email, name, phone, created_at, is_active, is_verified)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            owner_id,
                            owner_email,
                            owner_name or None,
                            owner_phone or None,
                            datetime.now().isoformat(),
                            1,
                            0,
                        ),
                    )
                    db.conn.commit()
                    print(f"✅ Создан новый пользователь: {owner_email} (ID: {owner_id})")
                except Exception:
                    exc = sys.exc_info()[1]
                    db.conn.rollback()
                    db.close()
                    print(f"❌ Ошибка создания пользователя: {exc}")
                    traceback.print_exc()
                    return jsonify({"error": f"Ошибка создания пользователя: {str(exc)}"}), 400

        if not owner_id:
            db.close()
            return jsonify({"error": "Необходимо указать owner_id или owner_email для создания бизнеса"}), 400

        try:
            business_id = db.create_business(name, description, industry, owner_id)
            db.conn.commit()
            db.close()
            return jsonify({"success": True, "business_id": business_id, "owner_id": owner_id})
        except Exception:
            exc = sys.exc_info()[1]
            db.conn.rollback()
            db.close()
            print(f"❌ Ошибка создания бизнеса: {exc}")
            traceback.print_exc()
            return jsonify({"error": f"Ошибка создания бизнеса: {str(exc)}"}), 500

    except Exception:
        exc = sys.exc_info()[1]
        print(f"❌ Ошибка создания бизнеса: {exc}")
        traceback.print_exc()
        return jsonify({"error": str(exc)}), 500


@superadmin_business_bp.route("/api/superadmin/businesses/<business_id>", methods=["PUT"])
def update_business(business_id):
    """Обновить бизнес (только для суперадмина)."""
    try:
        db = DatabaseManager()
        _, error_response = _require_superadmin(db)
        if error_response:
            return error_response

        data = request.get_json()
        name = data.get("name")
        description = data.get("description")
        industry = data.get("industry")

        db.update_business(business_id, name, description, industry)
        db.close()

        return jsonify({"success": True})

    except Exception:
        exc = sys.exc_info()[1]
        print(f"❌ Ошибка обновления бизнеса: {exc}")
        return jsonify({"error": str(exc)}), 500


@superadmin_business_bp.route("/api/superadmin/businesses/<business_id>/send-credentials", methods=["POST"])
def send_business_credentials(business_id):
    """Отправить данные для входа владельцу бизнеса (только для суперадмина)."""
    try:
        db = DatabaseManager()
        _, error_response = _require_superadmin(db)
        if error_response:
            return error_response

        cursor = db.conn.cursor()
        cursor.execute(
            """
            SELECT b.*, u.email, u.name owner_name
            FROM Businesses b
            LEFT JOIN Users u ON b.owner_id = u.id
            WHERE b.id = %s
            """,
            (business_id,),
        )
        business_row = cursor.fetchone()

        if not business_row:
            db.close()
            return jsonify({"error": "Бизнес не найден"}), 404

        business = dict(business_row)
        owner_email = business.get("email")

        if not owner_email:
            db.close()
            return jsonify({"error": "У бизнеса не указан email владельца"}), 400

        owner_id = business.get("owner_id")
        if not owner_id:
            db.close()
            return jsonify({"error": "У бизнеса не указан владелец"}), 400

        owner_user = get_user_by_id(owner_id)
        if not owner_user:
            db.close()
            return jsonify({"error": "Владелец бизнеса не найден"}), 404

        temp_password = None
        if not owner_user.get("password_hash"):
            temp_password = secrets.token_urlsafe(12)
            set_password(owner_id, temp_password)
            print(f"✅ Сгенерирован временный пароль для {owner_email}")

        login_url = "https://beautybot.pro/login"
        subject = f"Данные для входа в личный кабинет {business.get('name', 'BeautyBot')}"

        if temp_password:
            body = f"""
Здравствуйте, {business.get('owner_name', '')}!

Ваш бизнес "{business.get('name', '')}" был зарегистрирован в системе BeautyBot.

Данные для входа в личный кабинет:
Email: {owner_email}
Пароль: {temp_password}

Пожалуйста, войдите в систему по ссылке: {login_url}

После первого входа рекомендуется изменить пароль в настройках профиля.

---
С уважением,
Команда BeautyBot
            """
        else:
            body = f"""
Здравствуйте, {business.get('owner_name', '')}!

Ваш бизнес "{business.get('name', '')}" зарегистрирован в системе BeautyBot.

Для входа в личный кабинет используйте ваш существующий пароль:
Email: {owner_email}

Войти в систему: {login_url}

Если вы забыли пароль, воспользуйтесь функцией восстановления пароля на странице входа.

---
С уважением,
Команда BeautyBot
            """

        email_sent = email_delivery.send_email(owner_email, subject, body)
        db.close()

        if email_sent:
            return jsonify(
                {
                    "success": True,
                    "message": f"Данные для входа отправлены на {owner_email}",
                    "password_generated": temp_password is not None,
                }
            )
        return jsonify({"error": "Не удалось отправить email"}), 500

    except Exception:
        exc = sys.exc_info()[1]
        print(f"❌ Ошибка отправки credentials: {exc}")
        traceback.print_exc()
        return jsonify({"error": str(exc)}), 500


@superadmin_business_bp.route("/api/superadmin/businesses/<business_id>", methods=["DELETE"])
def delete_business(business_id):
    """Удалить бизнес (только для суперадмина)."""
    try:
        db = DatabaseManager()
        _, error_response = _require_superadmin(db)
        if error_response:
            return error_response

        print(f"🔍 DELETE запрос для бизнеса: {business_id}")
        success = db.delete_business(business_id)
        db.close()

        if success:
            return jsonify({"success": True, "message": "Бизнес удалён навсегда"})
        return jsonify({"error": "Бизнес не найден или не удалось удалить"}), 404

    except Exception:
        exc = sys.exc_info()[1]
        print(f"❌ Ошибка удаления бизнеса: {exc}")
        traceback.print_exc()
        return jsonify({"error": str(exc)}), 500
