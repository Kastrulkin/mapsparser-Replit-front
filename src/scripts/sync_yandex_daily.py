#!/usr/bin/env python3
"""
Ежедневная синхронизация данных Яндекс.Карт.

Запуск локально:
    cd /path/to/project
    source venv/bin/activate
    python src/scripts/sync_yandex_daily.py

Для сервера можно повесить на cron / systemd timer.
"""

from datetime import datetime

from yandex_sync_service import YandexSyncService
from database_manager import DatabaseManager


def main() -> None:
    print(f"[{datetime.utcnow().isoformat()}] 🔄 Старт ежедневной синхронизации Яндекс")

    service = YandexSyncService()
    db = DatabaseManager()
    cursor = db.conn.cursor()

    try:
        # Получаем все активные сети
        cursor.execute("SELECT id, name FROM Networks")
        networks = cursor.fetchall()

        total_synced = 0
        for network_id, name in networks:
            print(f"\n🕸  Синхронизирую сеть: {name} ({network_id})")
            synced = service.sync_network(network_id)
            total_synced += synced
            print(f"   ➜ Обновлено бизнесов: {synced}")

        print(
            f"\n[{datetime.utcnow().isoformat()}] ✅ Синхронизация завершена, всего обновлено бизнесов: {total_synced}"
        )
    except Exception as e:
        print(f"[{datetime.utcnow().isoformat()}] ❌ Ошибка при выполнении синхронизации: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    main()


