#!/usr/bin/env python3
"""
Script to populate Growth Stages and Tasks for Yandex Maps Strategy.
"""
import sys
import os
import uuid

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.safe_db_utils import get_db_connection

def populate():
    print("🔄 Populating Yandex Growth Stages...")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # 0. Find or create 'general' business type or allow linking to 'beauty_salon'
        # For now, let's link to 'beauty_salon' as primary target of user
        cursor.execute("SELECT id FROM BusinessTypes WHERE type_key = 'beauty_salon'")
        row = cursor.fetchone()
        if not row:
            print("❌ 'beauty_salon' business type not found. Run init_database_schema.py first.")
            return
        
        business_type_id = row[0]
        
        # Clear existing stages for this type to avoid duplicates (optional, or update?)
        # For safety/clean state, let's delete existing stages for this type if they are the old ones
        # Use transaction
        
        # Define Stages content
        stages_data = [
            {
                "number": 1,
                "title": "Рейтинг и первые оценки",
                "description": "Формирование стартового рейтинга.",
                "goal": "Получить 5+ отзывов",
                "result": "Появление рейтинга в карточке (снимается заглушка 4.3)",
                "duration": "1-2 недели",
                "tasks": [
                    {
                        "text": "Набрать первые 3-5 оценок",
                        "tooltip": "У новой организации рейтинг не отображается, пока не наберётся несколько оценок.",
                        "check_logic": "reviews_count_5",
                        "reward_value": 30
                    },
                    {
                        "text": "Подтвердить карточку (синяя галочка)",
                        "tooltip": "Заполненность профиля минимум на 90% + не менее 3 фото.",
                        "check_logic": "profile_verified",
                        "reward_value": 60
                    }
                ]
            },
            {
                "number": 2,
                "title": "Базовое оформление",
                "description": "Технические требования для доверия алгоритмов.",
                "goal": "Заполнить карточку на 90%+",
                "result": "Синяя галочка, рост доверия",
                "duration": "1 день",
                "tasks": [
                    {
                        "text": "Заполнить контакты и график работы",
                        "tooltip": "Телефон, сайт, мессенджеры, график, сезонные исключения.",
                        "check_logic": "profile_contacts_full",
                        "reward_value": 15
                    },
                    {
                        "text": "Загрузить минимум 3 качественных фото",
                        "tooltip": "Фасад, интерьер, вход. Без стоков.",
                        "check_logic": "photos_count_3",
                        "reward_value": 20
                    },
                    {
                        "text": "Добавить товары и услуги",
                        "tooltip": "Подробные карточки с ценами повышают конверсию.",
                        "check_logic": "services_added",
                        "reward_value": 45
                    }
                ]
            },
            {
                "number": 3,
                "title": "Гигиена отзывов",
                "description": "Правила модерации и безопасности.",
                "goal": "Пройти модерацию без удалений",
                "result": "Отзывы не удаляются алгоритмами",
                "duration": "Постоянно",
                "tasks": [
                    {
                        "text": "Обеспечить отзывы от первого лица",
                        "tooltip": "Без 'подруга сказала'. Реальный визит.",
                        "check_logic": "manual_check",
                        "reward_value": 0
                    },
                    {
                        "text": "Исключить рекламу и ссылки в отзывах",
                        "tooltip": "Запрещены промокоды и ссылки в тексте отзыва.",
                        "check_logic": "manual_check",
                        "reward_value": 0
                    }
                ]
            },
            {
                "number": 4,
                "title": "Операционная работа",
                "description": "Системный сбор отзывов.",
                "goal": "Поток 5-10 отзывов в месяц",
                "result": "Устойчивый рост рейтинга",
                "duration": "Ежемесячно",
                "tasks": [
                    {
                        "text": "Разместить QR-код в зоне кассы",
                        "tooltip": "Ведущий прямо на форму отзыва.",
                        "check_logic": "manual_check",
                        "reward_value": 30
                    },
                    {
                        "text": "Внедрить скрипт просьбы об отзыве",
                        "tooltip": "Мягкая просьба администратора или мастера.",
                        "check_logic": "manual_check",
                        "reward_value": 60
                    },
                    {
                        "text": "Отвечать на ВСЕ отзывы (позитив и негатив)",
                        "tooltip": "В течение 24 часов.",
                        "check_logic": "reply_rate_100",
                        "reward_value": 15
                    }
                ]
            },
            {
                "number": 5,
                "title": "Знак «Хорошее место»",
                "description": "Высшая лига Яндекс Карт.",
                "goal": "Рейтинг 4.5+ и знак",
                "result": "x2-x3 переходов из карт",
                "duration": "3-6 месяцев",
                "tasks": [
                    {
                        "text": "Достичь рейтинга 4.5+",
                        "tooltip": "При наличии 5+ отзывов.",
                        "check_logic": "rating_4_5",
                        "reward_value": 120
                    },
                    {
                        "text": "Набрать 15+ отзывов",
                        "tooltip": "Минимальный порог для доверия и знака.",
                        "check_logic": "reviews_count_15",
                        "reward_value": 60
                    }
                ]
            }
        ]
        
        # Clear old stages
        cursor.execute("DELETE FROM GrowthStages WHERE business_type_id = ?", (business_type_id,))
        print(f"🗑️ Cleared old stages for type: {business_type_id}")
        
        # Insert new stages
        for stage in stages_data:
            stage_id = f"stage_{business_type_id}_{stage['number']}"
            cursor.execute("""
                INSERT INTO GrowthStages (id, business_type_id, stage_number, title, description, goal, expected_result, duration, is_permanent)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)
            """, (
                stage_id,
                business_type_id,
                stage['number'],
                stage['title'],
                stage['description'],
                stage['goal'],
                stage['result'],
                stage['duration']
            ))
            
            # Insert tasks
            for i, task in enumerate(stage['tasks'], 1):
                task_id = f"task_{stage_id}_{i}"
                cursor.execute("""
                    INSERT INTO GrowthTasks (id, stage_id, task_number, task_text, check_logic, reward_value, reward_type, tooltip, is_auto_verifiable)
                    VALUES (?, ?, ?, ?, ?, ?, 'time_saved', ?, ?)
                """, (
                    task_id,
                    stage_id,
                    i,
                    task['text'],
                    task['check_logic'],
                    task['reward_value'],
                    task['tooltip'],
                    1 if task.get('check_logic') != 'manual_check' else 0
                ))
                
        conn.commit()
        print("✅ Population completed successfully")
        
    except Exception as e:
        print(f"❌ Population failed: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    populate()
