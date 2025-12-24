#!/usr/bin/env python3
"""
Миграция для создания таблиц постов (новостей) и фотографий из внешних источников.

Таблицы:
- ExternalBusinessPosts   — новости/посты из внешних источников
- ExternalBusinessPhotos  — фотографии из внешних источников
"""

import sys
import os
import sqlite3

# Добавляем путь к src для импорта модулей
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from safe_db_utils import safe_migrate, get_db_path


def migrate_external_posts_photos(cursor: sqlite3.Cursor) -> None:
    """Создать таблицы для постов и фотографий, если их ещё нет."""
    print("🔄 Создание таблиц ExternalBusinessPosts / Photos ...")

    # 1. Посты/новости организаций
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS ExternalBusinessPosts (
            id TEXT PRIMARY KEY,
            business_id TEXT NOT NULL,
            account_id TEXT,                   -- ExternalBusinessAccounts.id
            source TEXT NOT NULL,              -- 'yandex_business', 'google_business', '2gis'
            external_post_id TEXT,             -- ID поста во внешней системе
            title TEXT,
            text TEXT,
            published_at TIMESTAMP,
            image_url TEXT,
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
        CREATE INDEX IF NOT EXISTS idx_ext_posts_business
        ON ExternalBusinessPosts(business_id)
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_ext_posts_source
        ON ExternalBusinessPosts(source)
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_ext_posts_published_at
        ON ExternalBusinessPosts(published_at)
        """
    )

    # 2. Фотографии организаций
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS ExternalBusinessPhotos (
            id TEXT PRIMARY KEY,
            business_id TEXT NOT NULL,
            account_id TEXT,                   -- ExternalBusinessAccounts.id
            source TEXT NOT NULL,              -- 'yandex_business', 'google_business', '2gis'
            external_photo_id TEXT,            -- ID фото во внешней системе
            url TEXT,
            thumbnail_url TEXT,
            uploaded_at TIMESTAMP,
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
        CREATE INDEX IF NOT EXISTS idx_ext_photos_business
        ON ExternalBusinessPhotos(business_id)
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_ext_photos_source
        ON ExternalBusinessPhotos(source)
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_ext_photos_uploaded_at
        ON ExternalBusinessPhotos(uploaded_at)
        """
    )

    print("✅ Таблицы ExternalBusinessPosts / Photos созданы (если их не было)")


def main() -> None:
    print("=" * 60)
    print("🚀 Миграция: таблицы постов и фотографий из внешних источников")
    print("=" * 60)

    db_path = get_db_path()
    print(f"📁 Используем базу данных: {db_path}")

    ok = safe_migrate(
        migrate_external_posts_photos,
        "Создание таблиц ExternalBusinessPosts / Photos",
    )
    if not ok:
        print("❌ Миграция не выполнена, база откатена к бэкапу")
        sys.exit(1)

    print("✅ Миграция постов и фотографий завершена успешно")


if __name__ == "__main__":
    main()

