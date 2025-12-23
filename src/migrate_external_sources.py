#!/usr/bin/env python3
"""
Миграция для создания единых таблиц подключения внешних источников
(Яндекс.Бизнес, Google Business Profile, 2ГИС) и нормализованных
отзывов/статистики.

Таблицы:
- ExternalBusinessAccounts  — подключение аккаунта внешнего источника к бизнесу
- ExternalBusinessReviews   — нормализованные отзывы из всех источников
- ExternalBusinessStats     — агрегированная статистика по датам
"""

import sys
import sqlite3
from safe_db_utils import safe_migrate, get_db_path


def migrate_external_sources(cursor: sqlite3.Cursor) -> None:
    """Создать таблицы для внешних источников, если их ещё нет."""
    print("🔄 Создание таблиц ExternalBusiness* ...")

    # 1. Аккаунты внешних источников (Яндекс.Бизнес, Google, 2ГИС и т.д.)
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS ExternalBusinessAccounts (
            id TEXT PRIMARY KEY,
            business_id TEXT NOT NULL,
            source TEXT NOT NULL,              -- 'yandex_business', 'google_business', '2gis'
            external_id TEXT,                  -- ID аккаунта/организации во внешней системе
            display_name TEXT,                 -- Человекочитаемое имя (как в кабинете)
            auth_data_encrypted TEXT,          -- Зашифрованные cookie / refresh_token / API-key
            is_active INTEGER DEFAULT 1,
            last_sync_at TIMESTAMP,
            last_error TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (business_id) REFERENCES Businesses(id) ON DELETE CASCADE
        )
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_external_accounts_business
        ON ExternalBusinessAccounts(business_id)
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_external_accounts_source
        ON ExternalBusinessAccounts(source)
        """
    )

    # 2. Нормализованные отзывы из всех источников
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS ExternalBusinessReviews (
            id TEXT PRIMARY KEY,
            business_id TEXT NOT NULL,
            account_id TEXT,                   -- ExternalBusinessAccounts.id
            source TEXT NOT NULL,              -- 'yandex_business', 'google_business', '2gis', 'yandex_maps'
            external_review_id TEXT,           -- ID отзыва во внешней системе
            rating INTEGER,                    -- 1-5
            author_name TEXT,
            author_profile_url TEXT,
            text TEXT,
            response_text TEXT,
            response_at TIMESTAMP,
            published_at TIMESTAMP,
            lang TEXT,
            raw_payload TEXT,                  -- исходный JSON от внешнего сервиса
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (business_id) REFERENCES Businesses(id) ON DELETE CASCADE,
            FOREIGN KEY (account_id) REFERENCES ExternalBusinessAccounts(id) ON DELETE SET NULL
        )
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_ext_reviews_business
        ON ExternalBusinessReviews(business_id)
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_ext_reviews_source
        ON ExternalBusinessReviews(source)
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_ext_reviews_published_at
        ON ExternalBusinessReviews(published_at)
        """
    )

    # 3. Агрегированная статистика (показы, клики, действия, рейтинг, кол-во отзывов)
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS ExternalBusinessStats (
            id TEXT PRIMARY KEY,
            business_id TEXT NOT NULL,
            account_id TEXT,
            source TEXT NOT NULL,              -- 'yandex_business', 'google_business', '2gis'
            date TEXT NOT NULL,                -- YYYY-MM-DD
            views_total INTEGER,
            clicks_total INTEGER,
            actions_total INTEGER,
            rating REAL,
            reviews_total INTEGER,
            raw_payload TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (business_id) REFERENCES Businesses(id) ON DELETE CASCADE,
            FOREIGN KEY (account_id) REFERENCES ExternalBusinessAccounts(id) ON DELETE SET NULL
        )
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_ext_stats_business_date
        ON ExternalBusinessStats(business_id, date)
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_ext_stats_source
        ON ExternalBusinessStats(source)
        """
    )

    print("✅ Таблицы ExternalBusinessAccounts / Reviews / Stats созданы (если их не было)")


def main() -> None:
    print("=" * 60)
    print("🚀 Миграция: таблицы внешних источников (Яндекс.Бизнес, Google, 2ГИС)")
    print("=" * 60)

    db_path = get_db_path()
    print(f"📁 Используем базу данных: {db_path}")

    ok = safe_migrate(
        migrate_external_sources,
        "Создание таблиц ExternalBusinessAccounts / Reviews / Stats",
    )
    if not ok:
        print("❌ Миграция не выполнена, база откатена к бэкапу")
        sys.exit(1)

    print("✅ Миграция внешних источников завершена успешно")


if __name__ == "__main__":
    main()


