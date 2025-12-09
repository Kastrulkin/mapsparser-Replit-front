#!/usr/bin/env python3
"""
Безопасная миграция: добавление business_type и полей для Яндекс-статистики.

А также создание таблицы для исторических рядов по данным Яндекс.Карт.
"""

from safe_db_utils import safe_migrate


def add_business_type_and_yandex_fields(cursor):
    """Добавить business_type и yandex_* в Businesses и создать YandexBusinessStats"""
    # Определяем текущие колонки в Businesses
    cursor.execute("PRAGMA table_info(Businesses)")
    columns = [row[1] for row in cursor.fetchall()]

    # business_type: тип бизнеса внутри бьюти-вертикали
    if "business_type" not in columns:
        print("➕ Добавляю поле business_type в Businesses...")
        cursor.execute(
            """
            ALTER TABLE Businesses
            ADD COLUMN business_type TEXT DEFAULT 'beauty_salon'
            """
        )
        print("✅ Поле business_type добавлено с значением по умолчанию 'beauty_salon'")
    else:
        print("ℹ️  Поле business_type уже существует в Businesses")

    # yandex_org_id: идентификатор организации в Яндекс.Картах
    if "yandex_org_id" not in columns:
        print("➕ Добавляю поле yandex_org_id в Businesses...")
        cursor.execute(
            """
            ALTER TABLE Businesses
            ADD COLUMN yandex_org_id TEXT
            """
        )
        print("✅ Поле yandex_org_id добавлено")
    else:
        print("ℹ️  Поле yandex_org_id уже существует в Businesses")

    # yandex_url: ссылка на карточку в Яндекс.Картах
    if "yandex_url" not in columns:
        print("➕ Добавляю поле yandex_url в Businesses...")
        cursor.execute(
            """
            ALTER TABLE Businesses
            ADD COLUMN yandex_url TEXT
            """
        )
        print("✅ Поле yandex_url добавлено")
    else:
        print("ℹ️  Поле yandex_url уже существует в Businesses")

    # Дополнительные "снимочные" поля (опционально, как кеш последних значений)
    snapshot_fields = {
        "yandex_rating": "FLOAT",
        "yandex_reviews_total": "INTEGER",
        "yandex_reviews_30d": "INTEGER",
        "yandex_last_sync": "TIMESTAMP",
    }

    for field_name, field_type in snapshot_fields.items():
        if field_name not in columns:
            print(f"➕ Добавляю поле {field_name} в Businesses...")
            cursor.execute(
                f"""
                ALTER TABLE Businesses
                ADD COLUMN {field_name} {field_type}
                """
            )
            print(f"✅ Поле {field_name} добавлено")
        else:
            print(f"ℹ️  Поле {field_name} уже существует в Businesses")

    # Таблица с историческими рядами по Яндекс-данным
    print("🔍 Проверяю наличие таблицы YandexBusinessStats...")
    cursor.execute(
        """
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='YandexBusinessStats'
        """
    )
    if not cursor.fetchone():
        print("📝 Создаю таблицу YandexBusinessStats...")
        cursor.execute(
            """
            CREATE TABLE YandexBusinessStats (
                id TEXT PRIMARY KEY,
                business_id TEXT NOT NULL,
                date DATE NOT NULL,
                rating FLOAT,
                reviews_total INTEGER,
                reviews_30d INTEGER,
                fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (business_id) REFERENCES Businesses (id) ON DELETE CASCADE
            )
            """
        )
        # Индексы для быстрых выборок по бизнесу и дате
        try:
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_yandex_stats_business_id ON YandexBusinessStats(business_id)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_yandex_stats_business_date ON YandexBusinessStats(business_id, date)"
            )
            print("✅ Таблица YandexBusinessStats создана с индексами")
        except Exception as e:
            print(f"⚠️ Не удалось создать индексы для YandexBusinessStats: {e}")
    else:
        print("ℹ️ Таблица YandexBusinessStats уже существует")


if __name__ == "__main__":
    print("🔄 Начинаю миграцию: business_type и Яндекс-поля в Businesses + YandexBusinessStats")
    success = safe_migrate(
        add_business_type_and_yandex_fields,
        "Добавление business_type, yandex_* и таблицы YandexBusinessStats",
    )

    if success:
        print("✅ Миграция завершена успешно!")
    else:
        print("❌ Миграция не удалась. Проверьте логи выше.")


