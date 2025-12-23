#!/usr/bin/env python3
"""
Скрипт для форматирования cookies из DevTools в строку для вставки.

Использование:
    python format_cookies.py
    Затем вставьте cookies построчно (ключ=значение) и нажмите Enter дважды для завершения.
"""

def format_cookies():
    """Форматирует cookies из ввода в строку для вставки."""
    print("=" * 60)
    print("Форматирование cookies для Яндекс.Бизнес")
    print("=" * 60)
    print("\nВставьте cookies построчно в формате:")
    print("  ключ=значение")
    print("Или скопируйте всю таблицу из DevTools.")
    print("\nДля завершения ввода нажмите Enter дважды.\n")
    
    cookies = []
    lines = []
    
    # Читаем все строки
    while True:
        try:
            line = input().strip()
            if not line:
                if lines:
                    break
                continue
            lines.append(line)
        except EOFError:
            break
    
    # Парсим строки
    for line in lines:
        # Пропускаем заголовки таблицы
        if line.startswith("Name") or line.startswith("Value") or "---" in line:
            continue
        
        # Если строка содержит табуляцию или несколько пробелов (формат таблицы)
        parts = line.split('\t')
        if len(parts) < 2:
            parts = line.split('  ')
            parts = [p.strip() for p in parts if p.strip()]
        
        # Пытаемся найти ключ и значение
        if '=' in line:
            # Формат: ключ=значение
            if '=' in line:
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip()
                if key and value:
                    cookies.append(f"{key}={value}")
        elif len(parts) >= 2:
            # Формат таблицы: ключ значение ...
            key = parts[0].strip()
            value = parts[1].strip()
            if key and value and key != "Name" and value != "Value":
                cookies.append(f"{key}={value}")
    
    if not cookies:
        print("\n❌ Не удалось распарсить cookies. Попробуйте вставить в формате:")
        print("   ключ1=значение1")
        print("   ключ2=значение2")
        return
    
    # Формируем итоговую строку
    cookies_string = "; ".join(cookies)
    
    print("\n" + "=" * 60)
    print("✅ Сформированная строка cookies:")
    print("=" * 60)
    print(cookies_string)
    print("=" * 60)
    print(f"\nДлина: {len(cookies_string)} символов")
    print(f"Количество cookies: {len(cookies)}")
    print("\nСкопируйте эту строку и вставьте в форму!")


if __name__ == "__main__":
    format_cookies()

