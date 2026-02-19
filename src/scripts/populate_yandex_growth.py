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
            },
            {
                "number": 7,
                "title": "Автоматизация процессов",
                "description": "Внедрение CRM и базовая автоматизация клиентских коммуникаций",
                "goal": "Централизовать клиентскую базу",
                "result": "80% заполненность базы",
                "duration": "1-2 недели",
                "tasks": [
                    {
                        "text": "Выбрать и внедрить CRM (YCLIENTS, Rubitime и др.)",
                        "check_logic": "manual_check",
                        "reward_value": 50
                    },
                    {
                        "text": "Мигрировать базу клиентов в CRM",
                        "check_logic": "manual_check",
                        "reward_value": 40
                    },
                    {
                        "text": "Настроить авто-напоминания за 24 часа",
                        "check_logic": "manual_check",
                        "reward_value": 30
                    }
                ]
            },
            {
                "number": 7,
                "title": "Автоматизация коммуникаций и боты",
                "description": "Запуск чат-ботов, голосовых роботов, рассылок.",
                "goal": "Снизить no-show до 10-15%",
                "result": "Освобождение времени администратора",
                "duration": "2-3 недели",
                "tasks": [
                    {
                        "text": "Подключить BeautyBot.pro или аналог",
                        "check_logic": "manual_check",
                        "reward_value": 50
                    },
                    {
                        "text": "Создать сценарии для чат-бота",
                        "check_logic": "manual_check",
                        "reward_value": 40
                    },
                    {
                        "text": "Интегрировать бота с CRM",
                        "check_logic": "manual_check",
                        "reward_value": 40
                    }
                ]
            },
            {
                "number": 9,
                "title": "Оптимизация монетизации",
                "description": "Анализ услуг и переработка прайс-листа.",
                "goal": "Увеличить средний чек на 15%",
                "result": "Выявлены прибыльные услуги",
                "duration": "2-3 недели",
                "tasks": [
                    {
                        "text": "Проанализировать маржинальность услуг",
                        "check_logic": "manual_check",
                        "reward_value": 30
                    },
                    {
                        "text": "Выявить топ-3 маржинальных услуги",
                        "check_logic": "manual_check",
                        "reward_value": 20
                    },
                    {
                        "text": "Снять или переориентировать убыточные услуги",
                        "check_logic": "manual_check",
                        "reward_value": 30
                    }
                ]
            },
            {
                "number": 10,
                "title": "Апсейл и кросс-селл",
                "description": "Матрица доп. продаж и обучение персонала.",
                "goal": "Увеличить средний чек на 20%",
                "result": "Рост выручки",
                "duration": "2-3 недели",
                "tasks": [
                    {
                        "text": "Разработать матрицу кросс-селла",
                        "check_logic": "manual_check",
                        "reward_value": 40
                    },
                    {
                        "text": "Создать 3-5 комбо-пакетов услуг",
                        "check_logic": "manual_check",
                        "reward_value": 30
                    },
                    {
                        "text": "Внедрить подсказки для админа в CRM",
                        "check_logic": "manual_check",
                        "reward_value": 30
                    }
                ]
            },
            {
                "number": 11,
                "title": "Локальные партнерства",
                "description": "Сеть взаимовыгодных партнерств.",
                "goal": "10-15 новых клиентов/мес от партнеров",
                "result": "3-5 активных партнеров",
                "duration": "3-4 недели",
                "tasks": [
                    {
                        "text": "Составить карту соседей (фитнес, кофейни)",
                        "check_logic": "manual_check",
                        "reward_value": 20
                    },
                    {
                        "text": "Провести встречи с 5 партнерами",
                        "check_logic": "manual_check",
                        "reward_value": 50
                    },
                    {
                        "text": "Запустить совместную кросс-акцию",
                        "check_logic": "manual_check",
                        "reward_value": 50
                    }
                ]
            },
            {
                "number": 12,
                "title": "Уличный маркетинг",
                "description": "Креативные листовки и локальный buzz.",
                "goal": "Привести 15-25 клиентов с улицы",
                "result": "Узнаваемость бренда",
                "duration": "2-3 недели",
                "tasks": [
                    {
                        "text": "Разработать креативную листовку",
                        "check_logic": "manual_check",
                        "reward_value": 30
                    },
                    {
                        "text": "Напечатать тираж (500-1000 шт)",
                        "check_logic": "manual_check",
                        "reward_value": 20
                    },
                    {
                        "text": "Организовать раздачу в целевых точках",
                        "check_logic": "manual_check",
                        "reward_value": 40
                    }
                ]
            },
            {
                "number": 13,
                "title": "Продажа товаров (FMCG)",
                "description": "Косметика и домашний уход.",
                "goal": "Добавить 10% к выручке",
                "result": "Рост среднего чека",
                "duration": "2-3 недели",
                "tasks": [
                    {
                        "text": "Выбрать поставщика косметики",
                        "check_logic": "manual_check",
                        "reward_value": 30
                    },
                    {
                        "text": "Оформить витрину товаров в салоне",
                        "check_logic": "manual_check",
                        "reward_value": 30
                    },
                    {
                        "text": "Обучить мастеров продажам",
                        "check_logic": "manual_check",
                        "reward_value": 40
                    }
                ]
            },
            {
                "number": 14,
                "title": "Соцсети и контент",
                "description": "Органический трафик и сообщество.",
                "goal": "Рост подписчиков и вовлеченности",
                "result": "Активное комьюнити",
                "duration": "4-6 недель",
                "tasks": [
                    {
                        "text": "Создать контент-план на 30 дней",
                        "check_logic": "manual_check",
                        "reward_value": 40
                    },
                    {
                        "text": "Снять видео-визитку салона/мастеров",
                        "check_logic": "manual_check",
                        "reward_value": 50
                    },
                    {
                        "text": "Провести конкурс или розыгрыш",
                        "check_logic": "manual_check",
                        "reward_value": 30
                    }
                ]
            },
            {
                "number": 15,
                "title": "Управление репутацией",
                "description": "Работа с отзывами на всех площадках.",
                "goal": "Рейтинг 4.8+ везде",
                "result": "Доверие новых клиентов",
                "duration": "1-2 недели",
                "tasks": [
                    {
                        "text": "Зарегистрироваться на 2ГИС, Google, Zoon",
                        "check_logic": "manual_check",
                        "reward_value": 30
                    },
                    {
                        "text": "Настроить мониторинг отзывов",
                        "check_logic": "manual_check",
                        "reward_value": 20
                    },
                    {
                        "text": "Проработать старые негативные отзывы",
                        "check_logic": "manual_check",
                        "reward_value": 40
                    }
                ]
            },
            {
                "number": 16,
                "title": "Лояльность и Retention",
                "description": "Удержание клиентов и LTV.",
                "goal": "Повторные визиты 60%+",
                "result": "Стабильная база",
                "duration": "2-3 недели",
                "tasks": [
                    {
                        "text": "Разработать программу лояльности",
                        "check_logic": "manual_check",
                        "reward_value": 50
                    },
                    {
                        "text": "Запустить реферальную программу",
                        "check_logic": "manual_check",
                        "reward_value": 40
                    },
                    {
                        "text": "Сегментировать базу (VIP, Потерянные)",
                        "check_logic": "manual_check",
                        "reward_value": 30
                    }
                ]
            },
            {
                "number": 17,
                "title": "Email и SMS маркетинг",
                "description": "Рассылки и возвращение клиентов.",
                "goal": "Возврат 10-15% спящих клиентов",
                "result": "Дополнительные записи",
                "duration": "2-3 недели",
                "tasks": [
                    {
                        "text": "Собрать согласия на рассылку",
                        "check_logic": "manual_check",
                        "reward_value": 20
                    },
                    {
                        "text": "Подготовить цепочку писем/сообщений",
                        "check_logic": "manual_check",
                        "reward_value": 40
                    },
                    {
                        "text": "Провести реактивацию спящей базы",
                        "check_logic": "manual_check",
                        "reward_value": 50
                    }
                ]
            },
            {
                "number": 18,
                "title": "Корпоративные услуги",
                "description": "Работа с компаниями и B2B.",
                "goal": "2-3 корпоративных клиента",
                "result": "Оптовые заказы",
                "duration": "3-4 недели",
                "tasks": [
                    {
                        "text": "Подготовить КП для компаний",
                        "check_logic": "manual_check",
                        "reward_value": 30
                    },
                    {
                        "text": "Собрать базу HR-контактов района",
                        "check_logic": "manual_check",
                        "reward_value": 30
                    },
                    {
                        "text": "Заключить первый корпоративный договор",
                        "check_logic": "manual_check",
                        "reward_value": 60
                    }
                ]
            },
            {
                "number": 19,
                "title": "SEO и Блог",
                "description": "Органический поиск в Google/Yandex.",
                "goal": "Трафик из поиска",
                "result": "Бесплатные лиды",
                "duration": "4-8 недель",
                "tasks": [
                    {
                        "text": "Собрать семантическое ядро",
                        "check_logic": "manual_check",
                        "reward_value": 30
                    },
                    {
                        "text": "Оптимизировать заголовки на сайте",
                        "check_logic": "manual_check",
                        "reward_value": 30
                    },
                    {
                        "text": "Написать 3 статьи в блог",
                        "check_logic": "manual_check",
                        "reward_value": 40
                    }
                ]
            },
            {
                "number": 20,
                "title": "Анализ и оптимизация",
                "description": "Постоянное улучшение показателей.",
                "goal": "Рост выручки ежемесячно",
                "result": "Эффективный бизнес",
                "duration": "Постоянно",
                "tasks": [
                    {
                        "text": "Внедрить еженедельные отчеты",
                        "check_logic": "manual_check",
                        "reward_value": 20
                    },
                    {
                        "text": "Проводить планерки с командой",
                        "check_logic": "manual_check",
                        "reward_value": 20
                    },
                    {
                        "text": "Тестировать 1 гипотезу в неделю",
                        "check_logic": "manual_check",
                        "reward_value": 30
                    }
                ]
            }
        ]
        
        # Clear old stages
        # Clear UserStageProgress (to avoid FK error)
        cursor.execute("""
            DELETE FROM UserStageProgress WHERE stage_id IN (
                SELECT id FROM GrowthStages WHERE business_type_id = %s
            )
        """, (business_type_id,))
        
        # First delete tasks linked to stages of this business type (to avoid FK error)
        cursor.execute("""
            DELETE FROM GrowthTasks 
            WHERE stage_id IN (
                SELECT id FROM GrowthStages WHERE business_type_id = %s
            )
        """, (business_type_id,))
        
        cursor.execute("DELETE FROM GrowthStages WHERE business_type_id = %s", (business_type_id,))
        print(f"🗑️ Cleared old stages and tasks for type: {business_type_id}")
        
        # Insert new stages
        for stage in stages_data:
            stage_id = f"stage_{business_type_id}_{stage['number']}"
            cursor.execute("""
                INSERT INTO GrowthStages (id, business_type_id, stage_number, title, description, goal, expected_result, duration, is_permanent)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 0)
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
                    VALUES (%s, %s, %s, %s, %s, %s, 'time_saved', %s, %s)
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
