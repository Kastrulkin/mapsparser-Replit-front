#!/usr/bin/env python3
"""
Миграция для интеграции ChatGPT + Stripe + тарифы
Расширяет таблицу Businesses и создаёт новые таблицы
"""
from safe_db_utils import safe_migrate, get_db_connection
import sqlite3

def migrate_chatgpt_integration(cursor):
    """Миграция для ChatGPT интеграции"""
    
    print("🔄 Расширение таблицы Businesses...")
    
    # Добавляем новые поля в Businesses (если их ещё нет)
    new_fields = [
        ('city', 'TEXT'),
        ('country', 'TEXT DEFAULT "US"'),
        ('latitude', 'REAL'),
        ('longitude', 'REAL'),
        ('timezone', 'TEXT'),
        ('working_hours_json', 'TEXT'),
        ('chatgpt_enabled', 'INTEGER DEFAULT 0'),
        ('chatgpt_api_key', 'TEXT'),
        ('telegram_bot_connected', 'INTEGER DEFAULT 0'),
        ('telegram_username', 'TEXT'),
        ('whatsapp_phone', 'TEXT'),
        ('whatsapp_verified', 'INTEGER DEFAULT 0'),
        ('stripe_customer_id', 'TEXT'),
        ('stripe_subscription_id', 'TEXT'),
        ('subscription_tier', 'TEXT DEFAULT "trial"'),
        ('subscription_status', 'TEXT DEFAULT "active"'),
        ('trial_ends_at', 'TIMESTAMP'),
        ('subscription_ends_at', 'TIMESTAMP'),
        ('moderation_status', 'TEXT DEFAULT "pending"'),
        ('moderation_notes', 'TEXT')
    ]
    
    for field_name, field_type in new_fields:
        try:
            cursor.execute(f'ALTER TABLE Businesses ADD COLUMN {field_name} {field_type}')
            print(f"  ✅ Добавлено поле: {field_name}")
        except sqlite3.OperationalError as e:
            if 'duplicate column' in str(e).lower():
                print(f"  ℹ️  Поле {field_name} уже существует")
            else:
                print(f"  ⚠️  Ошибка при добавлении {field_name}: {e}")
    
    print("\n🔄 Создание таблицы Bookings...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS Bookings (
            id TEXT PRIMARY KEY,
            business_id TEXT NOT NULL,
            client_name TEXT NOT NULL,
            client_phone TEXT NOT NULL,
            client_email TEXT,
            service_id TEXT,
            service_name TEXT,
            booking_time TIMESTAMP NOT NULL,
            booking_time_local TEXT,
            source TEXT DEFAULT 'chatgpt',
            status TEXT DEFAULT 'pending',
            notes TEXT,
            notification_sent INTEGER DEFAULT 0,
            notification_channel TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (business_id) REFERENCES Businesses(id) ON DELETE CASCADE,
            FOREIGN KEY (service_id) REFERENCES UserServices(id) ON DELETE SET NULL
        )
    """)
    print("  ✅ Таблица Bookings создана/проверена")
    
    # Создаём индексы для Bookings
    try:
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_bookings_business_id ON Bookings(business_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_bookings_status ON Bookings(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_bookings_booking_time ON Bookings(booking_time)")
        print("  ✅ Индексы для Bookings созданы")
    except Exception as e:
        print(f"  ⚠️  Ошибка создания индексов: {e}")
    
    print("\n🔄 Создание таблицы StripePayments...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS StripePayments (
            id TEXT PRIMARY KEY,
            business_id TEXT NOT NULL,
            stripe_payment_intent_id TEXT UNIQUE,
            stripe_invoice_id TEXT,
            amount INTEGER NOT NULL,
            currency TEXT DEFAULT 'usd',
            status TEXT,
            subscription_tier TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (business_id) REFERENCES Businesses(id) ON DELETE CASCADE
        )
    """)
    print("  ✅ Таблица StripePayments создана/проверена")
    
    # Создаём индексы для StripePayments
    try:
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_stripe_payments_business_id ON StripePayments(business_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_stripe_payments_status ON StripePayments(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_stripe_payments_payment_intent ON StripePayments(stripe_payment_intent_id)")
        print("  ✅ Индексы для StripePayments созданы")
    except Exception as e:
        print(f"  ⚠️  Ошибка создания индексов: {e}")
    
    print("\n🔄 Создание таблицы CRMIntegrations...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS CRMIntegrations (
            id TEXT PRIMARY KEY,
            business_id TEXT NOT NULL,
            crm_type TEXT NOT NULL,
            api_key TEXT,
            api_url TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (business_id) REFERENCES Businesses(id) ON DELETE CASCADE
        )
    """)
    print("  ✅ Таблица CRMIntegrations создана/проверена")
    
    # Создаём индексы для CRMIntegrations
    try:
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_crm_integrations_business_id ON CRMIntegrations(business_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_crm_integrations_crm_type ON CRMIntegrations(crm_type)")
        print("  ✅ Индексы для CRMIntegrations созданы")
    except Exception as e:
        print(f"  ⚠️  Ошибка создания индексов: {e}")
    
    print("\n✅ Миграция ChatGPT интеграции завершена!")

def main():
    """Запуск миграции"""
    print("=" * 60)
    print("🚀 Миграция: ChatGPT интеграция + Stripe + тарифы")
    print("=" * 60)
    print()
    
    safe_migrate(
        migrate_chatgpt_integration,
        "Расширение Businesses и создание таблиц для ChatGPT интеграции"
    )
    
    print()
    print("=" * 60)
    print("✅ Миграция успешно завершена!")
    print("=" * 60)

if __name__ == "__main__":
    main()

