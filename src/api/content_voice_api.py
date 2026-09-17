from __future__ import annotations

import sys

from flask import Blueprint, jsonify, request

from auth_system import verify_session
from core.auth_context import AuthContext
from core.api_errors import internal_error_response
from services.content_voice_service import (
    add_content_voice_example,
    delete_content_voice_example,
    get_content_voice,
    update_content_voice,
)


content_voice_bp = Blueprint("content_voice", __name__, url_prefix="/api/content-voice")


def _require_auth():
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None, (jsonify({"success": False, "error": "Требуется авторизация"}), 401)
    user_data = verify_session(auth_header.split(" ", 1)[1])
    if not user_data:
        return None, (jsonify({"success": False, "error": "Недействительный токен"}), 401)
    return user_data, None


@content_voice_bp.route("", methods=["GET", "PATCH"])
def content_voice_profile():
    user_data, error_response = _require_auth()
    if error_response:
        return error_response
    data = request.get_json(silent=True) or {} if request.method == "PATCH" else {}
    business_id = str(request.args.get("business_id") or data.get("business_id") or "").strip()
    if not business_id:
        return jsonify({"success": False, "error": "business_id обязателен"}), 400
    try:
        auth = AuthContext.from_session(user_data)
        profile = update_content_voice(auth, business_id, data) if request.method == "PATCH" else get_content_voice(auth, business_id)
        return jsonify({"success": True, "profile": profile})
    except PermissionError:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 403
    except ValueError:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 400
    except Exception:
        return internal_error_response("Не удалось обработать настройки стиля")


@content_voice_bp.route("/examples", methods=["POST"])
def content_voice_example_create():
    user_data, error_response = _require_auth()
    if error_response:
        return error_response
    data = request.get_json(silent=True) or {}
    business_id = str(data.get("business_id") or "").strip()
    if not business_id:
        return jsonify({"success": False, "error": "business_id обязателен"}), 400
    try:
        example = add_content_voice_example(
            AuthContext.from_session(user_data),
            business_id,
            str(data.get("text") or ""),
            platform=str(data.get("platform") or ""),
            origin=str(data.get("origin") or "manual"),
            quality_status=str(data.get("quality_status") or "reference"),
        )
        return jsonify({"success": True, "example": example}), 201
    except PermissionError:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 403
    except ValueError:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 400
    except Exception:
        return internal_error_response("Не удалось обработать настройки стиля")


@content_voice_bp.route("/examples/<example_id>", methods=["DELETE"])
def content_voice_example_delete(example_id: str):
    user_data, error_response = _require_auth()
    if error_response:
        return error_response
    try:
        delete_content_voice_example(AuthContext.from_session(user_data), example_id)
        return jsonify({"success": True})
    except PermissionError:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 403
    except ValueError:
        return jsonify({"success": False, "error": str(sys.exc_info()[1])}), 404
    except Exception:
        return internal_error_response("Не удалось обработать настройки стиля")


@content_voice_bp.route('/rules', methods=['GET', 'POST', 'PATCH'])
def content_rules():
    user, error = _require_auth()
    if error:
        return error
    from database_manager import DatabaseManager
    from services import content_rules
    from services.content_voice_service import _verify_access
    data=request.get_json(silent=True) or {}
    business_id=str(request.args.get('business_id') or data.get('business_id') or '')
    db=DatabaseManager()
    try:
        cursor=db.conn.cursor()
        auth=_verify_access(cursor,AuthContext.from_session(user),business_id)
        if request.method=='GET':
            rules=content_rules.load(cursor,business_id).get('content_rules',[])
            ids=list({r.get('author_id') for r in rules if r.get('author_id')})
            cursor.execute('SELECT id,name FROM users WHERE id=ANY(%s)',(ids,))
            names={row['id']:row['name'] for row in cursor.fetchall()}
            rules=[{**rule,'author_name':names.get(rule.get('author_id')) or 'Пользователь'} for rule in rules]
            return jsonify({'rules':rules,'can_manage':content_rules.can_manage(cursor,auth.user_id,business_id)})
        rule=content_rules.change(cursor,business_id=business_id,user_id=auth.user_id,
            request_id=str(data.get('request_id') or ''),text=str(data.get('text') or ''),
            rule_id=data.get('rule_id'),expected_version=data.get('expected_version'),
            status=data.get('status','active'),starts_at=data.get('starts_at'),ends_at=data.get('ends_at'))
        db.conn.commit()
        return jsonify({'rule':rule})
    except content_rules.RuleConflict:
        return jsonify({'error':str(sys.exception())}),409
    except PermissionError:
        return jsonify({'error':str(sys.exception())}),403
    except ValueError:
        return jsonify({'error':str(sys.exception())}),400
    except Exception:
        return internal_error_response('Не удалось сохранить правило')
    finally:
        db.close()


@content_voice_bp.route('/rules/<rule_id>/history', methods=['GET'])
def content_rule_history(rule_id):
    user,error=_require_auth()
    if error:
        return error
    from database_manager import DatabaseManager
    from services.content_voice_service import _verify_access
    from services.operator_conversations import _row
    db=DatabaseManager()
    try:
        cursor=db.conn.cursor();business_id=request.args.get('business_id','')
        _verify_access(cursor,AuthContext.from_session(user),business_id)
        cursor.execute('SELECT snapshot,created_at FROM content_rule_history WHERE business_id=%s AND rule_id=%s ORDER BY created_at DESC',(business_id,rule_id))
        return jsonify({'history':[_row(cursor,row) for row in cursor.fetchall()]})
    except PermissionError:
        return jsonify({'error':'Нет доступа к правилам бизнеса'}),403
    finally:
        db.close()
