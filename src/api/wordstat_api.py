from flask import Blueprint, jsonify, request
import sqlite3
import subprocess
import os
import sys
from datetime import datetime
import re
import uuid

# Adjust path to import modules from src/
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database_manager import get_db_connection
from auth_system import verify_session
from core.helpers import get_business_owner_id

wordstat_bp = Blueprint('wordstat_api', __name__, url_prefix='/api/wordstat')

STOP_WORDS = {
    "и", "в", "на", "с", "по", "для", "или", "от", "до", "под", "при", "за", "к", "из", "о",
    "the", "and", "for", "with", "from", "to", "of",
    "услуга", "услуги", "салон", "beauty", "service", "services",
}

BUSINESS_TYPE_HINTS = {
    "beauty_salon": ["салон красоты", "косметология", "маникюр", "педикюр", "парикмахерская"],
    "barbershop": ["барбершоп", "мужская стрижка", "борода", "бритье"],
    "nail_studio": ["маникюр", "педикюр", "ногти", "гель лак"],
    "spa": ["спа", "массаж", "релакс", "уход за телом"],
    "massage": ["массаж", "релакс", "лечебный массаж"],
    "cosmetology": ["косметология", "чистка лица", "пилинг", "уход за лицом"],
    "brows_lashes": ["брови", "ресницы", "ламинирование ресниц"],
}


def _extract_terms(text: str):
    words = re.findall(r"[a-zA-Zа-яА-ЯёЁ0-9]+", (text or "").lower())
    result = []
    for w in words:
        if len(w) < 3 or w in STOP_WORDS or w.isdigit():
            continue
        result.append(w)
    return result


def _score_keyword(keyword_text: str, terms):
    text = (keyword_text or "").lower()
    score = 0
    for t in terms:
        if t in text:
            score += 2 if len(t) >= 6 else 1
    return score


def _require_auth():
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return None, (jsonify({'success': False, 'error': 'Требуется авторизация'}), 401)
    user_data = verify_session(auth_header.split(' ', 1)[1])
    if not user_data:
        return None, (jsonify({'success': False, 'error': 'Недействительный токен'}), 401)
    return user_data, None


def _ensure_business_access(cursor, user_data, business_id: str):
    owner_id = get_business_owner_id(cursor, business_id, include_active_check=True)
    is_superadmin = bool(user_data.get('is_superadmin'))
    current_user_id = user_data.get('user_id') or user_data.get('id')
    if not owner_id:
        return (jsonify({'success': False, 'error': 'Бизнес не найден'}), 404)
    if owner_id != current_user_id and not is_superadmin:
        return (jsonify({'success': False, 'error': 'Нет доступа к бизнесу'}), 403)
    return None


def _ensure_excluded_table(cursor):
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS wordstatkeywordsexcluded (
            id TEXT PRIMARY KEY,
            business_id TEXT NOT NULL,
            keyword TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (business_id, keyword)
        )
        """
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_wordstat_excluded_business ON wordstatkeywordsexcluded(business_id)"
    )


def _ensure_custom_table(cursor):
    # Avoid race errors on first concurrent requests that try to initialize the same table.
    cursor.execute(
        """
        DO $$
        BEGIN
            CREATE TABLE wordstatkeywordscustom (
                id TEXT PRIMARY KEY,
                business_id TEXT NOT NULL,
                keyword TEXT NOT NULL,
                views INTEGER DEFAULT 0,
                category TEXT DEFAULT 'custom',
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (business_id, keyword)
            );
        EXCEPTION
            WHEN duplicate_table OR unique_violation THEN
                NULL;
        END
        $$;
        """
    )
    cursor.execute(
        """
        DO $$
        BEGIN
            CREATE INDEX idx_wordstat_custom_business ON wordstatkeywordscustom(business_id);
        EXCEPTION
            WHEN duplicate_table OR duplicate_object THEN
                NULL;
        END
        $$;
        """
    )

@wordstat_bp.route('/keywords', methods=['GET'])
def get_keywords():
    """Get popular keywords filtered by business context (services/type/city)."""
    user_data, auth_error = _require_auth()
    if auth_error:
        return auth_error

    business_id = (request.args.get('business_id') or '').strip()
    use_city = (request.args.get('use_city') or '').strip().lower() in ('1', 'true', 'yes')

    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        cursor.execute(
            """
            SELECT to_regclass('public.wordstatkeywords') AS t
            """
        )
        reg_row = cursor.fetchone() or {}
        table_exists = (reg_row.get('t') if isinstance(reg_row, dict) else None)
        if not table_exists:
            return jsonify({
                'success': True,
                'count': 0,
                'items': [],
                'grouped': {}
            })

        terms = []
        city = None

        if business_id:
            access_error = _ensure_business_access(cursor, user_data, business_id)
            if access_error:
                return access_error

            cursor.execute(
                "SELECT business_type, city FROM businesses WHERE id = %s",
                (business_id,)
            )
            b_row = cursor.fetchone() or {}
            business_type = (b_row.get('business_type') if isinstance(b_row, dict) else None) or ''
            city = (b_row.get('city') if isinstance(b_row, dict) else None) or ''

            # Берем услуги последнего снапшота парсинга (или активные как fallback)
            cursor.execute(
                """
                WITH latest_ts AS (
                    SELECT MAX(updated_at) AS ts
                    FROM userservices
                    WHERE business_id = %s
                      AND source IN ('yandex_maps', 'yandex_business')
                      AND (is_active IS TRUE OR is_active IS NULL)
                )
                SELECT name, description
                FROM userservices
                WHERE business_id = %s
                  AND (is_active IS TRUE OR is_active IS NULL)
                  AND (
                      updated_at = (SELECT ts FROM latest_ts)
                      OR source IS NULL
                  )
                """,
                (business_id, business_id),
            )
            for row in cursor.fetchall() or []:
                r = row if isinstance(row, dict) else {}
                terms.extend(_extract_terms((r.get('name') or '')))
                terms.extend(_extract_terms((r.get('description') or '')))

            for hint in BUSINESS_TYPE_HINTS.get(str(business_type), []):
                terms.extend(_extract_terms(hint))

        # Get top keywords from Wordstat pool
        cursor.execute("""
            SELECT keyword, views, category, updated_at 
            FROM wordstatkeywords
            ORDER BY views DESC
            LIMIT 5000
        """)
        
        rows = cursor.fetchall() or []
        keywords = [dict(row) if not isinstance(row, dict) else row for row in rows]

        excluded_keywords = set()
        if business_id:
            _ensure_excluded_table(cursor)
            cursor.execute(
                "SELECT keyword FROM wordstatkeywordsexcluded WHERE business_id = %s",
                (business_id,),
            )
            for row in cursor.fetchall() or []:
                if isinstance(row, dict):
                    kw = (row.get('keyword') or '').strip().lower()
                elif isinstance(row, tuple):
                    kw = (row[0] or '').strip().lower()
                else:
                    kw = ''
                if kw:
                    excluded_keywords.add(kw)

        if excluded_keywords:
            keywords = [k for k in keywords if (k.get('keyword') or '').strip().lower() not in excluded_keywords]

        if business_id:
            _ensure_custom_table(cursor)
            cursor.execute(
                """
                SELECT keyword, views, category, updated_at
                FROM wordstatkeywordscustom
                WHERE business_id = %s
                ORDER BY views DESC, updated_at DESC
                """,
                (business_id,),
            )
            custom_rows = cursor.fetchall() or []
            custom_items = [dict(row) if not isinstance(row, dict) else row for row in custom_rows]
            if excluded_keywords:
                custom_items = [k for k in custom_items if (k.get('keyword') or '').strip().lower() not in excluded_keywords]

            existing = {(k.get('keyword') or '').strip().lower() for k in keywords}
            for item in custom_items:
                kw = (item.get('keyword') or '').strip().lower()
                if kw and kw not in existing:
                    keywords.append(item)
                    existing.add(kw)

        # Контекстный отбор по услугам/типу бизнеса
        if terms:
            uniq_terms = list(dict.fromkeys(terms))[:80]
            filtered = []
            for k in keywords:
                score = _score_keyword(k.get('keyword') or '', uniq_terms)
                if score > 0:
                    k['match_score'] = score
                    filtered.append(k)
            filtered.sort(key=lambda x: (int(x.get('views') or 0), x.get('match_score', 0)), reverse=True)
            keywords = filtered[:600]
        else:
            keywords = keywords[:600]
        keywords.sort(key=lambda x: int(x.get('views') or 0), reverse=True)

        if use_city and city:
            city_clean = str(city).strip()
            for k in keywords:
                kw = (k.get('keyword') or '').strip()
                if city_clean and city_clean.lower() not in kw.lower():
                    k['keyword_with_city'] = f"{kw} {city_clean}"
                else:
                    k['keyword_with_city'] = kw
        
        # Group by category
        by_category = {}
        for k in keywords:
            cat = k['category'] or 'other'
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(k)
            
        return jsonify({
            'success': True,
            'count': len(keywords),
            'items': keywords,
            'grouped': by_category
        })
        
    except Exception as e:
        print(f"Error fetching wordstat keywords: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        conn.close()


@wordstat_bp.route('/search', methods=['GET'])
def search_keywords():
    user_data, auth_error = _require_auth()
    if auth_error:
        return auth_error

    business_id = (request.args.get('business_id') or '').strip()
    query = (request.args.get('q') or '').strip()
    try:
        limit = int(request.args.get('limit') or 10)
    except Exception:
        limit = 10
    limit = min(max(limit, 1), 50)

    if not business_id:
        return jsonify({'success': False, 'error': 'Не указан business_id'}), 400
    if len(query) < 2:
        return jsonify({'success': True, 'count': 0, 'items': []})

    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        access_error = _ensure_business_access(cursor, user_data, business_id)
        if access_error:
            return access_error

        _ensure_excluded_table(cursor)
        _ensure_custom_table(cursor)

        cursor.execute(
            "SELECT keyword FROM wordstatkeywordsexcluded WHERE business_id = %s",
            (business_id,),
        )
        excluded = {
            ((r.get('keyword') if isinstance(r, dict) else r[0]) or '').strip().lower()
            for r in (cursor.fetchall() or [])
        }

        cursor.execute(
            """
            SELECT keyword, views, category, updated_at
            FROM wordstatkeywordscustom
            WHERE business_id = %s
            """,
            (business_id,),
        )
        custom_existing = {
            ((r.get('keyword') if isinstance(r, dict) else r[0]) or '').strip().lower()
            for r in (cursor.fetchall() or [])
        }

        like_q = f"%{query.lower()}%"
        cursor.execute(
            """
            SELECT keyword, views, category, updated_at
            FROM wordstatkeywords
            WHERE LOWER(keyword) LIKE %s
            ORDER BY views DESC
            LIMIT 200
            """,
            (like_q,),
        )
        rows = cursor.fetchall() or []
        items = []
        for row in rows:
            item = dict(row) if not isinstance(row, dict) else row
            kw = (item.get('keyword') or '').strip().lower()
            if not kw:
                continue
            if kw in excluded or kw in custom_existing:
                continue
            items.append(item)
            if len(items) >= limit:
                break

        return jsonify({'success': True, 'count': len(items), 'items': items})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        conn.close()

@wordstat_bp.route('/update', methods=['POST'])
def trigger_update():
    """Trigger the background update script"""
    try:
        user_data, auth_error = _require_auth()
        if auth_error:
            return auth_error

        payload = request.get_json(silent=True) or {}
        business_id = (payload.get('business_id') or request.args.get('business_id') or '').strip()
        if business_id:
            conn = get_db_connection()
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            try:
                access_error = _ensure_business_access(cursor, user_data, business_id)
                if access_error:
                    return access_error
            finally:
                conn.close()

            return jsonify({
                'success': True,
                'message': 'Данные обновлены для текущего бизнеса'
            })

        script_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'update_wordstat_data.py')
        oauth_token = os.getenv('YANDEX_WORDSTAT_OAUTH_TOKEN', '').strip()
        if not oauth_token:
            return jsonify({
                'success': False,
                'error': 'YANDEX_WORDSTAT_OAUTH_TOKEN не задан в окружении контейнера app'
            }), 400
        
        # Run in background (nohup) or wait? 
        # Since it can take time, normally background. But user might want feedback.
        # Let's run it synchronously for now if it's not too long, or use check_update_needed logic.
        # Actually, let's run it as a subprocess.
        
        # Check if auth token is set
        # We can't easily check env vars passed to subprocess unless we pass them.
        # Assuming environment is set up.
        
        # Using subprocess to run the script
        process = subprocess.Popen(
            ['python3', script_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Wait for a bit (timeout) to see if it crashes immediately, otherwise return accepted.
        try:
            stdout, stderr = process.communicate(timeout=2)
            if process.returncode != 0:
                 details = (stderr or stdout or '').strip()
                 if not details:
                     details = 'unknown error (stdout/stderr empty)'
                 return jsonify({'success': False, 'error': f"Script failed: {details}"}), 500
        except subprocess.TimeoutExpired:
            # Running in background
            pass
            
        return jsonify({
            'success': True, 
            'message': 'Update started manually. Check back in a few minutes.'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@wordstat_bp.route('/keywords', methods=['DELETE'])
def exclude_keyword():
    user_data, auth_error = _require_auth()
    if auth_error:
        return auth_error

    payload = request.get_json(silent=True) or {}
    business_id = (payload.get('business_id') or '').strip()
    keyword = (payload.get('keyword') or '').strip()

    if not business_id:
        return jsonify({'success': False, 'error': 'Не указан business_id'}), 400
    if not keyword:
        return jsonify({'success': False, 'error': 'Не указан keyword'}), 400

    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        access_error = _ensure_business_access(cursor, user_data, business_id)
        if access_error:
            return access_error

        _ensure_excluded_table(cursor)
        cursor.execute(
            """
            INSERT INTO wordstatkeywordsexcluded (id, business_id, keyword, created_at)
            VALUES (%s, %s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (business_id, keyword) DO NOTHING
            """,
            (str(uuid.uuid4()), business_id, keyword),
        )
        conn.commit()

        return jsonify({
            'success': True,
            'message': 'Ключевой запрос удалён и исключён из оптимизации'
        })
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        conn.close()


@wordstat_bp.route('/keywords/custom', methods=['POST'])
def add_custom_keyword():
    user_data, auth_error = _require_auth()
    if auth_error:
        return auth_error

    payload = request.get_json(silent=True) or {}
    business_id = (payload.get('business_id') or '').strip()
    keyword = (payload.get('keyword') or '').strip()
    category = (payload.get('category') or 'custom').strip() or 'custom'
    try:
        views = int(payload.get('views') or 0)
    except Exception:
        views = 0

    if not business_id:
        return jsonify({'success': False, 'error': 'Не указан business_id'}), 400
    if not keyword:
        return jsonify({'success': False, 'error': 'Не указан keyword'}), 400

    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        access_error = _ensure_business_access(cursor, user_data, business_id)
        if access_error:
            return access_error

        _ensure_custom_table(cursor)
        cursor.execute(
            """
            INSERT INTO wordstatkeywordscustom (id, business_id, keyword, views, category, updated_at, created_at)
            VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT (business_id, keyword)
            DO UPDATE SET
                views = EXCLUDED.views,
                category = COALESCE(NULLIF(EXCLUDED.category, ''), wordstatkeywordscustom.category),
                updated_at = CURRENT_TIMESTAMP
            """,
            (str(uuid.uuid4()), business_id, keyword, views, category),
        )
        conn.commit()
        return jsonify({'success': True, 'message': 'Ключевой запрос добавлен'})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        conn.close()

@wordstat_bp.route('/metadata', methods=['GET'])
def get_metadata():
    """Get metadata about last update"""
    try:
        prompts_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'prompts')
        metadata_path = os.path.join(prompts_dir, 'wordstat_metadata.json')
        
        if os.path.exists(metadata_path):
            with open(metadata_path, 'r', encoding='utf-8') as f:
                import json
                data = json.load(f)
                return jsonify({'success': True, 'metadata': data})
        else:
            return jsonify({'success': False, 'error': 'No metadata found'}), 404
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
