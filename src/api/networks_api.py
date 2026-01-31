"""
Networks API Blueprint
Endpoints for managing business networks and importing locations
"""
from flask import Blueprint, request, jsonify
from database_manager import DatabaseManager
from core.auth_helpers import require_auth_from_request
from services.yandex_xml_parser import parse_yandex_network_xml, validate_xml
import uuid
from datetime import datetime

networks_bp = Blueprint('networks_api', __name__)


def verify_network_access(cursor, network_id: str, user_data: dict) -> tuple[bool, str | None]:
    """
    Проверяет доступ пользователя к сети
    
    Returns:
        (has_access: bool, owner_id: str | None)
    """
    cursor.execute("SELECT owner_id FROM Networks WHERE id = ?", (network_id,))
    network = cursor.fetchone()
    
    if not network:
        return False, None
    
    owner_id = network[0]
    user_id = user_data.get('user_id') or user_data.get('id')
    has_access = owner_id == user_id or user_data.get('is_superadmin', False)
    
    return has_access, owner_id


@networks_bp.route('/api/networks/<network_id>/import-xml', methods=['POST'])
def import_network_xml(network_id):
    """
    Импорт точек сети из XML файла Яндекс.Бизнес
    
    Request:
        - file: XML файл (multipart/form-data)
    
    Response:
        {
            "success": true,
            "created_count": 96,
            "business_ids": ["uuid1", "uuid2", ...],
            "summary": {
                "total": 96,
                "with_coordinates": 95,
                "with_phone": 96,
                "with_email": 5
            }
        }
    """
    try:
        user_data = require_auth_from_request()
        if not user_data:
            return jsonify({"error": "Требуется авторизация"}), 401
        
        db = None
        try:
            db = DatabaseManager()
            cursor = db.conn.cursor()
            
            # Проверяем доступ к сети
            has_access, owner_id = verify_network_access(cursor, network_id, user_data)
            if not has_access:
                return jsonify({
                    "error": "Нет доступа к сети" if owner_id else "Сеть не найдена"
                }), 403 if owner_id else 404
            
            # Получаем XML из запроса
            if 'file' not in request.files:
                return jsonify({"error": "Файл не загружен"}), 400
            
            xml_file = request.files['file']
            if not xml_file.filename.endswith('.xml'):
                return jsonify({"error": "Файл должен быть в формате XML"}), 400
            
            xml_content = xml_file.read().decode('utf-8')
            
            # Валидация XML
            is_valid, message = validate_xml(xml_content)
            if not is_valid:
                return jsonify({"error": message}), 400
            
            print(f"📋 XML валидация пройдена: {message}")
            
            # Парсим XML
            companies = parse_yandex_network_xml(xml_content)
            print(f"📊 Распарсено {len(companies)} компаний из XML")
            
            # Создаем точки в БД
            created_ids = []
            stats = {
                'total': len(companies),
                'with_coordinates': 0,
                'with_phone': 0,
                'with_email': 0,
                'duplicates_skipped': 0
            }
            
            for company in companies:
                # Проверяем дубликат по yandex_org_id
                if company['yandex_org_id']:
                    cursor.execute("""
                        SELECT id FROM Businesses 
                        WHERE yandex_org_id = ? AND network_id = ?
                    """, (company['yandex_org_id'], network_id))
                    existing = cursor.fetchone()
                    
                    if existing:
                        print(f"⚠️ Пропускаем дубликат: {company['name']} (ID: {company['yandex_org_id']})")
                        stats['duplicates_skipped'] += 1
                        continue
                
                business_id = str(uuid.uuid4())
                
                # Вставляем бизнес
                cursor.execute("""
                    INSERT INTO Businesses (
                        id, name, address, latitude, longitude,
                        working_hours, phone, email,
                        yandex_org_id, yandex_last_sync,
                        network_id, owner_id, is_active,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """, (
                    business_id,
                    company['name'],
                    company['address'],
                    company['latitude'],
                    company['longitude'],
                    company['working_hours'],
                    company['phone'],
                    company['email'],
                    company['yandex_org_id'],
                    company['yandex_last_sync'],
                    network_id,
                    owner_id
                ))
                
                # Создаем ссылку на Яндекс.Карты (если есть company-id)
                if company['yandex_org_id']:
                    yandex_url = f"https://yandex.ru/maps/org/{company['yandex_org_id']}"
                    cursor.execute("""
                        INSERT INTO BusinessMapLinks (
                            id, business_id, user_id, url, map_type, created_at
                        ) VALUES (?, ?, ?, ?, 'yandex_maps', CURRENT_TIMESTAMP)
                    """, (str(uuid.uuid4()), business_id, owner_id, yandex_url))
                
                created_ids.append(business_id)
                
                # Обновляем статистику
                if company['latitude'] and company['longitude']:
                    stats['with_coordinates'] += 1
                if company['phone']:
                    stats['with_phone'] += 1
                if company['email']:
                    stats['with_email'] += 1
                
                print(f"✅ Создана точка: {company['name']} (ID: {business_id})")
            
            db.conn.commit()
            
            print(f"🎉 Импорт завершен: создано {len(created_ids)} точек")
            print(f"📊 Статистика: {stats}")
            
            return jsonify({
                "success": True,
                "created_count": len(created_ids),
                "business_ids": created_ids,
                "summary": stats
            })
        
        finally:
            if db:
                db.close()
    
    except Exception as e:
        print(f"❌ Ошибка импорта XML: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
