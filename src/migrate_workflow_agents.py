#!/usr/bin/env python3
"""
Миграция для обновления структуры агентов на workflow формат
"""
from safe_db_utils import safe_migrate, get_db_connection
import sqlite3
import json

def migrate_workflow_agents(cursor):
    """Миграция для обновления структуры агентов"""
    
    print("🔄 Обновление структуры таблицы AIAgents для workflow...")
    
    # Добавляем новые поля для workflow структуры
    new_fields = [
        ('workflow', 'TEXT'),  # Workflow структура (YAML текст со стейтами, scenarios, tools)
        ('task', 'TEXT'),  # Задачи агента (markdown)
        ('identity', 'TEXT'),  # Личность агента
        ('speech_style', 'TEXT'),  # Стиль речи
    ]
    
    for field_name, field_type in new_fields:
        try:
            cursor.execute(f'ALTER TABLE AIAgents ADD COLUMN {field_name} {field_type}')
            print(f"  ✅ Добавлено поле: {field_name}")
        except sqlite3.OperationalError as e:
            if 'duplicate column' in str(e).lower():
                print(f"  ℹ️  Поле {field_name} уже существует")
            else:
                print(f"  ⚠️  Ошибка при добавлении {field_name}: {e}")
    
    # Обновляем существующих агентов, конвертируя старую структуру в новую
    print("\n🔄 Конвертация существующих агентов в workflow формат...")
    
    cursor.execute("SELECT id, name, type, states_json FROM AIAgents")
    agents = cursor.fetchall()
    
    for agent_id, name, agent_type, old_states_json in agents:
        if not old_states_json:
            continue
        
        try:
            old_states = json.loads(old_states_json)
            workflow_states = []
            
            for state_key, state_data in old_states.items():
                # Конвертируем старый формат в новый workflow формат
                workflow_state = {
                    'name': state_key,
                    'kind': 'StateConfig',
                    'process_name': f'{name}Process',
                    'init_state': state_key == 'greeting' or state_key == list(old_states.keys())[0],
                    'description': state_data.get('description', ''),
                    'state_scenarios': []
                }
                
                # Конвертируем next_states в state_scenarios
                next_states = state_data.get('next_states', [])
                for next_state in next_states:
                    scenario = {
                        'next_state': next_state,
                        'transition_name': f'{state_key}To{next_state}',
                        'description': f'Переход из {state_key} в {next_state}'
                    }
                    workflow_state['state_scenarios'].append(scenario)
                
                # Добавляем промпт как часть description, если есть
                if state_data.get('prompt'):
                    workflow_state['description'] += f"\n\n{state_data.get('prompt')}"
                
                # Добавляем базовые инструменты
                workflow_state['available_tools'] = {
                    'SingleStatefulOutboundAgent': ['ForwardSpeech']
                }
                
                workflow_states.append(workflow_state)
            
            # Сохраняем workflow структуру
            cursor.execute("""
                UPDATE AIAgents 
                SET workflow = ?
                WHERE id = ?
            """, (json.dumps(workflow_states, ensure_ascii=False, indent=2), agent_id))
            
            print(f"  ✅ Конвертирован агент: {name}")
            
        except Exception as e:
            print(f"  ⚠️  Ошибка конвертации агента {name}: {e}")
    
    print("\n✅ Миграция workflow структуры завершена")

def main():
    """Главная функция миграции"""
    print("=" * 60)
    print("🚀 Миграция: Обновление структуры агентов на workflow")
    print("=" * 60)
    
    success = safe_migrate(
        migrate_workflow_agents,
        "Обновление структуры агентов на workflow формат"
    )
    
    if success:
        print("\n✅ Миграция завершена успешно!")
    else:
        print("\n❌ Миграция завершена с ошибками!")
        return 1
    
    return 0

if __name__ == '__main__':
    exit(main())

