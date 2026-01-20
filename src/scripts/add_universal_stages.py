#!/usr/bin/env python3
"""
Add universal Yandex Maps stages (1-6) to ALL business types.
These stages are applicable to any business on Yandex Maps.
"""
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.safe_db_utils import get_db_connection

def add_universal_stages():
    """Add stages 1-6 (Yandex Maps path to 5 stars) to all business types."""
    
    print("🚀 Adding universal Yandex Maps stages to all business types...")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Universal stages 1-6 (Yandex Maps strategy)
        universal_stages = [
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
                        "tooltip": "Мягкая просьба администратора или сотрудника.",
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
            },
            {
                "number": 6,
                "title": "Путь к 5.0 звёздам",
                "description": "Совершенство качества обслуживания для идеального рейтинга.",
                "goal": "Достичь рейтинга 5.0 на Яндекс Картах",
                "result": "Максимальное доверие и конверсия",
                "duration": "6-12 месяцев",
                "tasks": [
                    {
                        "text": "Достичь 30+ пятизвёздочных отзывов",
                        "tooltip": "Соотношение 5★ должно быть не менее 85-90% от общего числа отзывов.",
                        "check_logic": "reviews_5star_30",
                        "reward_value": 150
                    },
                    {
                        "text": "Ответить на 100% отзывов за последние 3 месяца",
                        "tooltip": "Включая все оценки без текста - благодарность обязательна.",
                        "check_logic": "reply_rate_100_3months",
                        "reward_value": 80
                    },
                    {
                        "text": "Обновлять фото каждые 2 недели",
                        "tooltip": "Свежий контент: новые работы, обновления интерьера, сезонные акции.",
                        "check_logic": "photos_updated_2weeks",
                        "reward_value": 60
                    },
                    {
                        "text": "Публиковать новости и посты 2 раза в месяц",
                        "tooltip": "Акции, события, достижения - активность повышает доверие алгоритмов.",
                        "check_logic": "posts_2per_month",
                        "reward_value": 50
                    },
                    {
                        "text": "Поддерживать заполненность профиля 100%",
                        "tooltip": "Все контакты, услуги, графики актуальны и подробны.",
                        "check_logic": "profile_completeness_100",
                        "reward_value": 40
                    },
                    {
                        "text": "Удержать рейтинг 4.9+ минимум 3 месяца",
                        "tooltip": "Стабильность качества - ключ к 5.0. Один провал может откинуть назад.",
                        "check_logic": "rating_4_9_stable_3months",
                        "reward_value": 100
                    }
                ]
            }
        ]
        
        # Get all business types from init_database_schema.py or database
        # For now, we'll get them from database if table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='BusinessTypes'")
        if not cursor.fetchone():
            print("⚠️ BusinessTypes table doesn't exist yet. Run init_database_schema.py first.")
            return
        
        cursor.execute("SELECT id, type_key, label FROM BusinessTypes")
        business_types = cursor.fetchall()
        
        if not business_types:
            print("⚠️ No business types found in database.")
            return
        
        print(f"📋 Found {len(business_types)} business types")
        
        for bt in business_types:
            bt_id, bt_key, bt_name = bt
            print(f"\n🔄 Processing: {bt_name} ({bt_key})")
            
            # Check if stages already exist for this type
            cursor.execute("""
                SELECT COUNT(*) FROM GrowthStages 
                WHERE business_type_id = ? AND stage_number BETWEEN 1 AND 6
            """, (bt_id,))
            
            existing_count = cursor.fetchone()[0]
            
            if existing_count > 0:
                print(f"   ⏭️ Skipping - already has {existing_count} universal stages")
                continue
            
            # Insert universal stages for this business type
            for stage in universal_stages:
                stage_id = f"stage_{bt_id}_{stage['number']}"
                
                cursor.execute("""
                    INSERT OR REPLACE INTO GrowthStages 
                    (id, business_type_id, stage_number, title, description, goal, expected_result, duration, is_permanent)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)
                """, (
                    stage_id,
                    bt_id,
                    stage['number'],
                    stage['title'],
                    stage['description'],
                    stage['goal'],
                    stage['result'],
                    stage['duration']
                ))
                
                # Insert tasks for this stage
                for i, task in enumerate(stage['tasks'], 1):
                    task_id = f"task_{stage_id}_{i}"
                    cursor.execute("""
                        INSERT OR REPLACE INTO GrowthTasks 
                        (id, stage_id, task_number, task_text, check_logic, reward_value, reward_type, tooltip, is_auto_verifiable)
                        VALUES (?, ?, ?, ?, ?, ?, 'time_saved', ?, ?)
                    """, (
                        task_id,
                        stage_id,
                        i,
                        task['text'],
                        task['check_logic'],
                        task['reward_value'],
                        task.get('tooltip'),
                        1 if task.get('check_logic') != 'manual_check' else 0
                    ))
            
            print(f"   ✅ Added 6 universal stages")
        
        conn.commit()
        print("\n✅ Successfully added universal stages to all business types!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    add_universal_stages()
