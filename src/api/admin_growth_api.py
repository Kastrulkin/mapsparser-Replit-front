from flask import Blueprint, jsonify, request
from database_manager import DatabaseManager
from auth_system import verify_session
import uuid
import json

admin_growth_bp = Blueprint('admin_growth_api', __name__)

def check_superadmin():
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return None
    
    token = auth_header.split(' ')[1]
    user_data = verify_session(token)
    if not user_data:
        return None
        
    db = DatabaseManager()
    is_super = db.is_superadmin(user_data['user_id'])
    db.close()
    
    return user_data if is_super else None

# ===== BUSINESS TYPES =====

@admin_growth_bp.route('/api/admin/business-types', methods=['GET'])
def get_business_types():
    """Get all business types"""
    # Assuming any authenticated user can read types, or restrict to admin/superadmin?
    # Logic: Frontend editor needs this list. Let's start with loose auth, maybe check admin later if strict.
    # GrowthPlanEditor uses this, so it likely needs admin rights.
    user = check_superadmin()
    if not user:
        return jsonify({"error": "Forbidden"}), 403
        
    try:
        db = DatabaseManager()
        cursor = db.conn.cursor()
        
        cursor.execute("SELECT * FROM BusinessTypes ORDER BY created_at DESC")
        rows = cursor.fetchall()
        
        types = []
        for row in rows:
            types.append({
                "id": row['id'],
                "type_key": row['type_key'],
                "label": row['label'],
                "description": row['description'],
                "is_active": bool(row['is_active'])
            })
            
        return jsonify({"success": True, "types": types})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()

@admin_growth_bp.route('/api/admin/business-types', methods=['POST'])
def create_business_type():
    """Create a new business type"""
    user = check_superadmin()
    if not user:
        return jsonify({"error": "Forbidden"}), 403
        
    try:
        data = request.json
        type_key = data.get('type_key')
        label = data.get('label')
        
        if not type_key or not label:
            return jsonify({"error": "Missing required fields"}), 400
            
        db = DatabaseManager()
        cursor = db.conn.cursor()
        
        type_id = str(uuid.uuid4())
        cursor.execute("""
            INSERT INTO BusinessTypes (id, type_key, label, description)
            VALUES (?, ?, ?, ?)
        """, (type_id, type_key, label, data.get('description', '')))
        
        db.conn.commit()
        return jsonify({"success": True, "id": type_id})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()

@admin_growth_bp.route('/api/admin/business-types/<type_id>', methods=['DELETE'])
def delete_business_type(type_id):
    """Delete a business type"""
    user = check_superadmin()
    if not user:
        return jsonify({"error": "Forbidden"}), 403
        
    try:
        db = DatabaseManager()
        cursor = db.conn.cursor()
        
        cursor.execute("DELETE FROM BusinessTypes WHERE id = ?", (type_id,))
        db.conn.commit()
        
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()

# ===== GROWTH STAGES =====

@admin_growth_bp.route('/api/admin/growth-stages/<type_id>', methods=['GET'])
def get_growth_stages(type_id):
    """Get stages for a business type"""
    user = check_superadmin()
    if not user:
        return jsonify({"error": "Forbidden"}), 403
        
    try:
        db = DatabaseManager()
        cursor = db.conn.cursor()
        
        cursor.execute("""
            SELECT * FROM GrowthStages 
            WHERE business_type_id = ? 
            ORDER BY stage_number ASC
        """, (type_id,))
        
        rows = cursor.fetchall()
        stages = []
        for row in rows:
            # Parse tasks from JSON string -> List
            tasks = []
            if row['tasks']:
                try:
                    tasks_raw = json.loads(row['tasks'])
                    # Compatibility: if stored as strings
                    if isinstance(tasks_raw, list):
                        # Convert simple strings to objects with ids/numbers if needed by frontend
                        # Frontend expects: { number: number, text: string }
                        for idx, t_text in enumerate(tasks_raw):
                            tasks.append({"number": idx + 1, "text": t_text})
                except:
                    pass
            
            stages.append({
                "id": row['id'],
                "stage_number": row['stage_number'],
                "title": row['title'],
                "description": row['description'],
                "goal": row['goal'],
                "expected_result": row['expected_result'],
                "duration": row['duration'],
                "is_permanent": bool(row['is_permanent']),
                "tasks": tasks
            })
            
        return jsonify({"success": True, "stages": stages})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()

@admin_growth_bp.route('/api/admin/growth-stages', methods=['POST'])
def create_growth_stage():
    """Create a new growth stage"""
    user = check_superadmin()
    if not user:
        return jsonify({"error": "Forbidden"}), 403
        
    try:
        data = request.json
        business_type_id = data.get('business_type_id')
        stage_number = data.get('stage_number')
        title = data.get('title')
        
        if not business_type_id or not title:
            return jsonify({"error": "Missing required fields"}), 400
            
        db = DatabaseManager()
        cursor = db.conn.cursor()
        
        stage_id = str(uuid.uuid4())
        tasks_json = json.dumps(data.get('tasks', [])) # Store as list of strings
        
        cursor.execute("""
            INSERT INTO GrowthStages (
                id, business_type_id, stage_number, title, description, 
                goal, expected_result, duration, is_permanent, tasks
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            stage_id, business_type_id, stage_number, title, 
            data.get('description', ''), data.get('goal', ''), 
            data.get('expected_result', ''), data.get('duration', ''), 
            1 if data.get('is_permanent') else 0, tasks_json
        ))
        
        db.conn.commit()
        return jsonify({"success": True, "id": stage_id})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()

@admin_growth_bp.route('/api/admin/growth-stages/<stage_id>', methods=['PUT'])
def update_growth_stage(stage_id):
    """Update a growth stage"""
    user = check_superadmin()
    if not user:
        return jsonify({"error": "Forbidden"}), 403
        
    try:
        data = request.json
        db = DatabaseManager()
        cursor = db.conn.cursor()
        
        tasks_json = json.dumps(data.get('tasks', []))
        
        cursor.execute("""
            UPDATE GrowthStages
            SET stage_number = ?, title = ?, description = ?, 
                goal = ?, expected_result = ?, duration = ?, 
                is_permanent = ?, tasks = ?
            WHERE id = ?
        """, (
            data.get('stage_number'), data.get('title'), 
            data.get('description', ''), data.get('goal', ''), 
            data.get('expected_result', ''), data.get('duration', ''), 
            1 if data.get('is_permanent') else 0, tasks_json,
            stage_id
        ))
        
        db.conn.commit()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()
        
@admin_growth_bp.route('/api/admin/growth-stages/<stage_id>', methods=['DELETE'])
def delete_growth_stage(stage_id):
    """Delete a growth stage"""
    user = check_superadmin()
    if not user:
        return jsonify({"error": "Forbidden"}), 403
        
    try:
        db = DatabaseManager()
        cursor = db.conn.cursor()
        
        cursor.execute("DELETE FROM GrowthStages WHERE id = ?", (stage_id,))
        db.conn.commit()
        
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()
