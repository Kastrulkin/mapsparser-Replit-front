from flask import Blueprint, jsonify, request
import sqlite3
import subprocess
import os
import sys
from datetime import datetime
import re

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

@wordstat_bp.route('/keywords', methods=['GET'])
def get_keywords():
    """Get popular keywords filtered by business context (services/type/city)."""
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return jsonify({'success': False, 'error': 'Требуется авторизация'}), 401
    user_data = verify_session(auth_header.split(' ', 1)[1])
    if not user_data:
        return jsonify({'success': False, 'error': 'Недействительный токен'}), 401

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
            owner_id = get_business_owner_id(cursor, business_id, include_active_check=True)
            is_superadmin = bool(user_data.get('is_superadmin'))
            current_user_id = user_data.get('user_id') or user_data.get('id')
            if not owner_id:
                return jsonify({'success': False, 'error': 'Бизнес не найден'}), 404
            if owner_id != current_user_id and not is_superadmin:
                return jsonify({'success': False, 'error': 'Нет доступа к бизнесу'}), 403

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

        # Контекстный отбор по услугам/типу бизнеса
        if terms:
            uniq_terms = list(dict.fromkeys(terms))[:80]
            filtered = []
            for k in keywords:
                score = _score_keyword(k.get('keyword') or '', uniq_terms)
                if score > 0:
                    k['match_score'] = score
                    filtered.append(k)
            filtered.sort(key=lambda x: (x.get('match_score', 0), int(x.get('views') or 0)), reverse=True)
            keywords = filtered[:600]
        else:
            keywords = keywords[:600]

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

@wordstat_bp.route('/update', methods=['POST'])
def trigger_update():
    """Trigger the background update script"""
    try:
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
