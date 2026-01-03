#!/usr/bin/env python3
"""
Миграция для создания таблицы AIAgents - шаблоны агентов, настраиваемые администратором
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from safe_db_utils import safe_migrate, get_db_connection
import sqlite3
import json

def migrate_ai_agents_table(cursor):
    """Миграция для создания таблицы AIAgents"""
    
    print("🔄 Создание таблицы AIAgents...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS AIAgents (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            type TEXT NOT NULL,
            description TEXT,
            personality TEXT,
            states_json TEXT,
            restrictions_json TEXT,
            variables_json TEXT,
            is_active INTEGER DEFAULT 1,
            created_by TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    print("  ✅ Таблица AIAgents создана/проверена")
    
    # Создаём индексы
    try:
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ai_agents_type ON AIAgents(type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ai_agents_active ON AIAgents(is_active)")
        print("  ✅ Индексы для AIAgents созданы")
    except Exception as e:
        print(f"  ⚠️  Ошибка создания индексов: {e}")
    
    # Добавляем поле agent_id в Businesses для связи с агентом
    print("\n🔄 Добавление поля agent_id в Businesses...")
    try:
        cursor.execute('ALTER TABLE Businesses ADD COLUMN ai_agent_id TEXT')
        print("  ✅ Добавлено поле: ai_agent_id")
    except sqlite3.OperationalError as e:
        if 'duplicate column' in str(e).lower():
            print("  ℹ️  Поле ai_agent_id уже существует")
        else:
            print(f"  ⚠️  Ошибка при добавлении ai_agent_id: {e}")
    
    # Создаём два дефолтных агента
    print("\n🔄 Создание дефолтных агентов...")
    
    # Агент 1: Маркетинговый
    marketing_agent_id = 'marketing_agent_default'
    marketing_states = {
        'greeting': {
            'name': 'Приветствие',
            'description': 'Приветствие и предложение акции',
            'prompt': 'Поприветствуй клиента и предложи актуальную акцию',
            'next_states': ['offer_details', 'goodbye']
        },
        'offer_details': {
            'name': 'Детали акции',
            'description': 'Рассказ о деталях акции',
            'prompt': 'Расскажи подробнее об акции, ответь на вопросы',
            'next_states': ['booking', 'goodbye']
        },
        'booking': {
            'name': 'Запись',
            'description': 'Запись клиента на услугу по акции',
            'prompt': 'Помоги клиенту записаться на услугу',
            'next_states': ['confirmation', 'goodbye']
        },
        'confirmation': {
            'name': 'Подтверждение',
            'description': 'Подтверждение записи',
            'prompt': 'Подтверди детали записи',
            'next_states': ['goodbye']
        },
        'goodbye': {
            'name': 'Завершение',
            'description': 'Завершение разговора',
            'prompt': 'Попрощайся с клиентом',
            'next_states': []
        }
    }
    
    marketing_restrictions = {
        'text': 'Не предлагай скидки больше 50%. Всегда уточняй предпочтения клиента перед записью.'
    }
    
    marketing_variables = {
        'salon_name': 'Название салона',
        'current_promotion': 'Текущая акция',
        'promotion_discount': 'Размер скидки',
        'promotion_valid_until': 'Акция действует до'
    }
    
    cursor.execute("""
        INSERT OR REPLACE INTO AIAgents 
        (id, name, type, description, personality, states_json, restrictions_json, variables_json, is_active)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
    """, (
        marketing_agent_id,
        'Маркетинговый агент',
        'marketing',
        'Агент для отправки информации об акциях и реанимации клиентов',
        'Дружелюбный, активный, заинтересованный в продажах. Использует эмодзи для привлечения внимания.',
        json.dumps(marketing_states, ensure_ascii=False),
        json.dumps(marketing_restrictions, ensure_ascii=False),
        json.dumps(marketing_variables, ensure_ascii=False)
    ))
    print("  ✅ Создан маркетинговый агент")
    
    # Агент 2: Для записи
    booking_agent_id = 'booking_agent_default'
    booking_states = {
        'greeting': {
            'name': 'Приветствие',
            'description': 'Приветствие и предложение помощи',
            'prompt': 'Поприветствуй клиента и предложи помощь с записью',
            'next_states': ['service_inquiry', 'availability_check']
        },
        'service_inquiry': {
            'name': 'Вопрос об услуге',
            'description': 'Клиент спрашивает об услугах',
            'prompt': 'Расскажи об услугах, ответь на вопросы',
            'next_states': ['availability_check', 'pricing', 'goodbye']
        },
        'availability_check': {
            'name': 'Проверка свободного времени',
            'description': 'Проверка доступного времени для записи',
            'prompt': 'Уточни предпочтения по времени и проверь доступность',
            'next_states': ['booking', 'service_inquiry']
        },
        'pricing': {
            'name': 'Уточнение цен',
            'description': 'Клиент спрашивает о ценах',
            'prompt': 'Расскажи о ценах на услуги',
            'next_states': ['booking', 'service_inquiry', 'goodbye']
        },
        'booking': {
            'name': 'Запись',
            'description': 'Создание записи',
            'prompt': 'Помоги клиенту записаться, уточни все детали',
            'next_states': ['confirmation']
        },
        'confirmation': {
            'name': 'Подтверждение',
            'description': 'Подтверждение записи',
            'prompt': 'Подтверди детали записи и поблагодари',
            'next_states': ['goodbye']
        },
        'goodbye': {
            'name': 'Завершение',
            'description': 'Завершение разговора',
            'prompt': 'Попрощайся с клиентом',
            'next_states': []
        }
    }
    
    booking_restrictions = {
        'text': 'Не записывай клиента без подтверждения всех деталей. Всегда уточняй имя, телефон и предпочтения по времени.'
    }
    
    booking_variables = {
        'salon_name': 'Название салона',
        'available_times': 'Доступное время',
        'service_duration': 'Длительность услуги',
        'master_name': 'Имя мастера'
    }
    
    cursor.execute("""
        INSERT OR REPLACE INTO AIAgents 
        (id, name, type, description, personality, states_json, restrictions_json, variables_json, is_active)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
    """, (
        booking_agent_id,
        'Агент для записи',
        'booking',
        'Агент для ответов на вопросы и записи на свободное время',
        'Профессиональный, вежливый, внимательный к деталям. Помогает клиенту выбрать удобное время.',
        json.dumps(booking_states, ensure_ascii=False),
        json.dumps(booking_restrictions, ensure_ascii=False),
        json.dumps(booking_variables, ensure_ascii=False)
    ))
    print("  ✅ Создан агент для записи")
    
    # Добавляем поле для выбора типа агента в Businesses
    print("\n🔄 Добавление поля ai_agent_type в Businesses...")
    try:
        cursor.execute('ALTER TABLE Businesses ADD COLUMN ai_agent_type TEXT DEFAULT "booking"')
        print("  ✅ Добавлено поле: ai_agent_type")
    except sqlite3.OperationalError as e:
        if 'duplicate column' in str(e).lower():
            print("  ℹ️  Поле ai_agent_type уже существует")
        else:
            print(f"  ⚠️  Ошибка при добавлении ai_agent_type: {e}")

def main():
    """Главная функция миграции"""
    print("=" * 60)
    print("🚀 Миграция: Создание таблицы AIAgents")
    print("=" * 60)
    
    success = safe_migrate(
        migrate_ai_agents_table,
        "Создание таблицы AIAgents и дефолтных агентов"
    )
    
    if success:
        print("\n✅ Миграция завершена успешно!")
    else:
        print("\n❌ Миграция завершена с ошибками!")
        return 1
    
    return 0

if __name__ == '__main__':
    exit(main())

