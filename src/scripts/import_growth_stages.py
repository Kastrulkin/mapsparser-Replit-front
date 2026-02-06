import json
import os
import sys

# Добавляем src в путь, чтобы импортировать модули
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from safe_db_utils import safe_migrate

def import_growth_stages(cursor):
    """Импорт этапов роста из JSON файла"""
    
    config_path = os.path.join(os.path.dirname(__file__), '../config/growth_stages.json')
    if not os.path.exists(config_path):
        print(f"❌ Файл конфигурации не найден: {config_path}")
        return

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        print(f"📦 Загружено {len(data['business_types'])} типов бизнеса из JSON")
        
        # Очищаем старые этапы и задачи (каскадное удаление должно бы работать, но для надежности)
        cursor.execute("DELETE FROM GrowthTasks")
        cursor.execute("DELETE FROM GrowthStages")
        print("🧹 Очищены старые данные этапов")

        for bt in data['business_types']:
            type_key = bt['type_key']
            
            # Находим ID типа бизнеса
            cursor.execute("SELECT id FROM BusinessTypes WHERE type_key = ?", (type_key,))
            row = cursor.fetchone()
            
            if not row:
                # Если типа нет - создаем
                bt_id = f"bt_{type_key}"
                print(f"➕ Создание типа бизнеса: {bt['label']} ({bt_id})")
                cursor.execute("""
                    INSERT INTO BusinessTypes (id, type_key, label, description)
                    VALUES (?, ?, ?, ?)
                """, (bt_id, type_key, bt['label'], bt.get('description', '')))
            else:
                bt_id = row[0]
                
            # Добавляем этапы
            for stage in bt.get('stages', []):
                stage_id = f"{bt_id}_s{stage['stage_number']}"
                
                cursor.execute("""
                    INSERT INTO GrowthStages (id, business_type_id, stage_number, title, description, goal, expected_result, duration)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    stage_id, 
                    bt_id, 
                    stage['stage_number'], 
                    stage['title'], 
                    stage['description'],
                    stage['goal'],
                    stage['expected_result'],
                    stage['duration']
                ))
                
                # Добавляем задачи
                for task in stage.get('tasks', []):
                    task_id = f"{stage_id}_t{task['task_number']}"
                    cursor.execute("""
                        INSERT INTO GrowthTasks (id, stage_id, task_number, task_text)
                        VALUES (?, ?, ?, ?)
                    """, (task_id, stage_id, task['task_number'], task['text']))
                    
        print("✅ Импорт успешно завершен")
        
    except json.JSONDecodeError as e:
        print(f"❌ Ошибка парсинга JSON: {e}")
    except Exception as e:
        print(f"❌ Ошибка импорта: {e}")
        raise e

if __name__ == "__main__":
    safe_migrate(import_growth_stages, "Import Growth Stages from JSON")
