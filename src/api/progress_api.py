import os

from flask import Blueprint, jsonify, request
from database_manager import DatabaseManager
from auth_system import verify_session
from progress_calculator import calculate_business_progress
from core.card_audit import build_card_audit_snapshot
from core.map_url_normalizer import normalize_map_url

progress_bp = Blueprint('progress_api', __name__)


def _row_get(row, key, index=0, default=None):
    if row is None:
        return default
    if isinstance(row, dict):
        return row.get(key, default)
    if hasattr(row, "keys"):
        try:
            return row[key]
        except Exception:
            return default
    try:
        return row[index]
    except Exception:
        return default


def _public_audit_url(slug: str) -> str:
    frontend_base = str(
        os.getenv("FRONTEND_BASE_URL")
        or os.getenv("PUBLIC_DOMAIN")
        or "https://localos.pro"
    ).strip().rstrip("/")
    return f"{frontend_base}/{str(slug or '').strip().lstrip('/')}"


def _same_business_name(left: str, right: str) -> bool:
    return str(left or "").strip().lower() == str(right or "").strip().lower()

def require_auth():
    """Проверка авторизации"""
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return None
    
    token = auth_header.split(' ')[1]
    return verify_session(token)

@progress_bp.route('/api/business/<business_id>/progress', methods=['GET'])
def get_business_progress(business_id):
    """Получить прогресс выполнения этапов роста для бизнеса"""
    try:
        user_data = require_auth()
        if not user_data:
            return jsonify({"error": "Требуется авторизация"}), 401
        
        db = DatabaseManager()
        cursor = db.conn.cursor()
        
        # Проверяем доступ к бизнесу
        cursor.execute("SELECT owner_id FROM Businesses WHERE id = %s", (business_id,))
        business = cursor.fetchone()
        
        if not business:
            db.close()
            return jsonify({"error": "Бизнес не найден"}), 404
        
        # Проверяем права доступа
        if business[0] != user_data['user_id'] and not user_data.get('is_superadmin'):
            db.close()
            return jsonify({"error": "Нет доступа к этому бизнесу"}), 403
        
        db.close()
        
        # Рассчитываем прогресс
        progress_data = calculate_business_progress(business_id)
        
        return jsonify({
            "success": True,
            "progress": progress_data
        })
        
    except Exception as e:
        print(f"❌ Ошибка получения прогресса: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@progress_bp.route('/api/business/<business_id>/card-audit', methods=['GET'])
def get_business_card_audit(business_id):
    """Получить аудит карточки бизнеса."""
    try:
        user_data = require_auth()
        if not user_data:
            return jsonify({"error": "Требуется авторизация"}), 401

        db = DatabaseManager()
        cursor = db.conn.cursor()

        cursor.execute("SELECT owner_id FROM Businesses WHERE id = %s", (business_id,))
        business = cursor.fetchone()

        if not business:
            db.close()
            return jsonify({"error": "Бизнес не найден"}), 404

        owner_id = business[0] if not hasattr(business, "keys") else business.get("owner_id")
        if owner_id != user_data['user_id'] and not user_data.get('is_superadmin'):
            db.close()
            return jsonify({"error": "Нет доступа к этому бизнесу"}), 403

        db.close()

        audit = build_card_audit_snapshot(business_id)
        return jsonify({
            "success": True,
            "audit": audit,
        })
    except Exception as e:
        print(f"❌ Ошибка получения аудита карточки: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@progress_bp.route('/api/business/<business_id>/public-audit-links', methods=['GET'])
def get_business_public_audit_links(business_id):
    """Получить релевантные public-audit ссылки для страницы прогресса."""
    try:
        user_data = require_auth()
        if not user_data:
            return jsonify({"error": "Требуется авторизация"}), 401

        db = DatabaseManager()
        cursor = db.conn.cursor()

        cursor.execute(
            """
            SELECT id, owner_id, name, network_id, business_type
            FROM businesses
            WHERE id = %s
            LIMIT 1
            """,
            (business_id,),
        )
        business = cursor.fetchone()

        if not business:
            db.close()
            return jsonify({"error": "Бизнес не найден"}), 404

        owner_id = str(_row_get(business, 'owner_id', 1, '') or '').strip()
        if owner_id != user_data['user_id'] and not user_data.get('is_superadmin'):
            db.close()
            return jsonify({"error": "Нет доступа к этому бизнесу"}), 403

        business_name = str(_row_get(business, 'name', 2, '') or '').strip()
        network_id = str(_row_get(business, 'network_id', 3, '') or '').strip()
        business_type = str(_row_get(business, 'business_type', 4, '') or '').strip().lower()
        is_network_parent = bool(network_id) and network_id == str(business_id or '').strip()
        if business_type == 'network':
            is_network_parent = True

        cursor.execute(
            """
            SELECT url
            FROM businessmaplinks
            WHERE business_id = %s
            ORDER BY created_at DESC
            """,
            (business_id,),
        )
        map_links = {
            normalize_map_url(_row_get(row, 'url', 0, ''))
            for row in (cursor.fetchall() or [])
            if str(_row_get(row, 'url', 0, '') or '').strip()
        }
        map_links.discard("")

        cursor.execute(
            """
            SELECT slug, source_url, page_json, updated_at
            FROM publicreportrequests
            WHERE status = 'completed'
            ORDER BY updated_at DESC
            LIMIT 400
            """
        )
        rows = cursor.fetchall() or []
        db.close()

        links = []
        seen_slugs = set()
        for row in rows:
            slug = str(_row_get(row, 'slug', 0, '') or '').strip()
            if not slug or slug in seen_slugs:
                continue
            page_json = _row_get(row, 'page_json', 2, {}) or {}
            if not isinstance(page_json, dict):
                continue
            audit = page_json.get("audit") if isinstance(page_json.get("audit"), dict) else {}
            audit_profile = str(audit.get("audit_profile") or "").strip().lower()
            page_name = str(page_json.get("name") or page_json.get("display_name") or "").strip()
            source_url = str(page_json.get("source_url") or _row_get(row, 'source_url', 1, '') or '').strip()
            normalized_source_url = normalize_map_url(source_url)

            if is_network_parent:
                if not audit_profile.startswith("network_"):
                    continue
                if not _same_business_name(page_name, business_name):
                    continue
                links.append(
                    {
                        "slug": slug,
                        "public_url": _public_audit_url(slug),
                        "title": page_name or business_name or "Аудит сети",
                        "kind": "network",
                        "audit_profile": audit_profile,
                        "audit_profile_label": audit.get("audit_profile_label"),
                        "updated_at": _row_get(row, 'updated_at', 3),
                    }
                )
                seen_slugs.add(slug)
                break

            matched_by_map = bool(normalized_source_url) and normalized_source_url in map_links
            matched_by_name = not map_links and _same_business_name(page_name, business_name)
            if audit_profile.startswith("network_") or not (matched_by_map or matched_by_name):
                continue

            links.append(
                {
                    "slug": slug,
                    "public_url": _public_audit_url(slug),
                    "title": page_name or business_name or "Аудит точки",
                    "kind": "business",
                    "audit_profile": audit_profile,
                    "audit_profile_label": audit.get("audit_profile_label"),
                    "updated_at": _row_get(row, 'updated_at', 3),
                }
            )
            seen_slugs.add(slug)
            break

        return jsonify({
            "success": True,
            "links": links,
            "scope": "network" if is_network_parent else "business",
        })
    except Exception as e:
        print(f"❌ Ошибка получения ссылок на public audits: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
