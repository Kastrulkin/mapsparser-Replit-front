#!/usr/bin/env python3
"""
Скрипт для очистки проекта от устаревших файлов.

ВНИМАНИЕ: Перед запуском убедитесь, что все изменения закоммичены в git!
"""

import os
import shutil
from pathlib import Path

# Файлы для удаления (безопасные - точно не используются)
FILES_TO_DELETE = [
    "format_cookies.py",  # Временный файл для тестирования
    "src/ai_analyzer.py",  # Не используется (Hugging Face API)
    "frontend/serve_spa.py",  # Не используется (main.py раздаёт SPA)
    "src/card_analyzer.py",  # Используется только в неиспользуемом user_api.py
]

# Файлы для перемещения
FILES_TO_MOVE = {
    "src/test_yandex_business_connection.py": "tests/test_yandex_business_connection.py",
}

# Файлы, требующие проверки перед удалением
FILES_TO_CHECK = [
    "src/user_api.py",  # Отдельный Flask app, проверить функционал
    "manage_gigachat.py",  # Утилита, проверить актуальность
    "src/add_to_queue.py",  # Проверить использование
]

def confirm_action(message: str) -> bool:
    """Запросить подтверждение у пользователя"""
    response = input(f"{message} (y/N): ").strip().lower()
    return response in ('y', 'yes', 'да')

def delete_file(filepath: str) -> bool:
    """Удалить файл с проверкой существования"""
    path = Path(filepath)
    if not path.exists():
        print(f"⚠️  Файл не найден: {filepath}")
        return False
    
    try:
        path.unlink()
        print(f"✅ Удалён: {filepath}")
        return True
    except Exception as e:
        print(f"❌ Ошибка при удалении {filepath}: {e}")
        return False

def move_file(src: str, dst: str) -> bool:
    """Переместить файл"""
    src_path = Path(src)
    dst_path = Path(dst)
    
    if not src_path.exists():
        print(f"⚠️  Файл не найден: {src}")
        return False
    
    # Создаём директорию назначения, если её нет
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        shutil.move(str(src_path), str(dst_path))
        print(f"✅ Перемещён: {src} → {dst}")
        return True
    except Exception as e:
        print(f"❌ Ошибка при перемещении {src}: {e}")
        return False

def main():
    """Основная функция очистки"""
    print("=" * 60)
    print("🧹 Очистка проекта от устаревших файлов")
    print("=" * 60)
    print("\n⚠️  ВНИМАНИЕ: Убедитесь, что все изменения закоммичены в git!")
    print()
    
    if not confirm_action("Продолжить очистку?"):
        print("❌ Очистка отменена")
        return
    
    deleted_count = 0
    moved_count = 0
    
    # Удаляем безопасные файлы
    print("\n📁 Удаление устаревших файлов:")
    print("-" * 60)
    for filepath in FILES_TO_DELETE:
        if delete_file(filepath):
            deleted_count += 1
    
    # Перемещаем файлы
    print("\n📦 Перемещение файлов:")
    print("-" * 60)
    for src, dst in FILES_TO_MOVE.items():
        if move_file(src, dst):
            moved_count += 1
    
    # Файлы для проверки
    print("\n⚠️  Файлы, требующие ручной проверки:")
    print("-" * 60)
    for filepath in FILES_TO_CHECK:
        path = Path(filepath)
        if path.exists():
            print(f"  - {filepath}")
            print(f"    Проверьте использование и удалите вручную, если не нужен")
    
    # Итоги
    print("\n" + "=" * 60)
    print("✅ Очистка завершена!")
    print(f"   Удалено файлов: {deleted_count}")
    print(f"   Перемещено файлов: {moved_count}")
    print("=" * 60)
    print("\n💡 Рекомендации:")
    print("   1. Проверьте изменения: git status")
    print("   2. Проверьте, что проект работает: python src/main.py")
    print("   3. Если всё ок, закоммитьте изменения: git add -A && git commit -m 'Cleanup: удалены устаревшие файлы'")

if __name__ == "__main__":
    main()

