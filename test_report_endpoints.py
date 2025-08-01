#!/usr/bin/env python3
"""
Тестовый скрипт для проверки новых эндпоинтов отчётов
"""
import requests
import json
import os
from dotenv import load_dotenv

load_dotenv()

def test_report_endpoints():
    """Тестирует новые эндпоинты отчётов"""
    
    # Базовый URL
    base_url = "https://beautybot.pro"
    
    # Получаем тестовый card_id из базы данных
    supabase_url = os.getenv('SUPABASE_URL')
    supabase_key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
    
    if not supabase_url or not supabase_key:
        print("❌ Ошибка: Не настроены переменные окружения Supabase")
        return
    
    try:
        from supabase import create_client
        supabase = create_client(supabase_url, supabase_key)
        
        # Получаем первую карточку с отчётом
        result = supabase.table("Cards").select("id, title, report_path").not_.is_("report_path", "null").limit(1).execute()
        
        if not result.data:
            print("❌ Нет карточек с отчётами для тестирования")
            return
        
        card_id = result.data[0]['id']
        title = result.data[0]['title']
        report_path = result.data[0]['report_path']
        
        print(f"✅ Найдена карточка для тестирования:")
        print(f"   ID: {card_id}")
        print(f"   Название: {title}")
        print(f"   Путь к отчёту: {report_path}")
        print()
        
        # Тест 1: Статус отчёта
        print("🔍 Тест 1: Проверка статуса отчёта")
        try:
            response = requests.get(f"{base_url}/api/reports/{card_id}/status")
            print(f"   Статус: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"   Данные: {json.dumps(data, indent=2, ensure_ascii=False)}")
                print("   ✅ Статус отчёта работает")
            else:
                print(f"   ❌ Ошибка: {response.text}")
        except Exception as e:
            print(f"   ❌ Ошибка запроса: {e}")
        print()
        
        # Тест 2: Просмотр отчёта
        print("👁️ Тест 2: Просмотр отчёта")
        try:
            response = requests.get(f"{base_url}/api/view-report/{card_id}")
            print(f"   Статус: {response.status_code}")
            print(f"   Content-Type: {response.headers.get('Content-Type')}")
            print(f"   Content-Length: {response.headers.get('Content-Length')}")
            print(f"   X-Content-Type-Options: {response.headers.get('X-Content-Type-Options')}")
            print(f"   X-Frame-Options: {response.headers.get('X-Frame-Options')}")
            
            if response.status_code == 200:
                content = response.text[:200] + "..." if len(response.text) > 200 else response.text
                print(f"   Содержимое (первые 200 символов): {content}")
                print("   ✅ Просмотр отчёта работает")
            else:
                print(f"   ❌ Ошибка: {response.text}")
        except Exception as e:
            print(f"   ❌ Ошибка запроса: {e}")
        print()
        
        # Тест 3: Скачивание отчёта
        print("📥 Тест 3: Скачивание отчёта")
        try:
            response = requests.get(f"{base_url}/api/download-report/{card_id}")
            print(f"   Статус: {response.status_code}")
            print(f"   Content-Type: {response.headers.get('Content-Type')}")
            print(f"   Content-Disposition: {response.headers.get('Content-Disposition')}")
            print(f"   Content-Length: {response.headers.get('Content-Length')}")
            print(f"   X-Content-Type-Options: {response.headers.get('X-Content-Type-Options')}")
            print(f"   X-Frame-Options: {response.headers.get('X-Frame-Options')}")
            
            if response.status_code == 200:
                # Сохраняем тестовый файл
                filename = f"test_report_{card_id}.html"
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(response.text)
                print(f"   ✅ Отчёт сохранён в {filename}")
                print("   ✅ Скачивание отчёта работает")
            else:
                print(f"   ❌ Ошибка: {response.text}")
        except Exception as e:
            print(f"   ❌ Ошибка запроса: {e}")
        print()
        
        print("🎉 Тестирование завершено!")
        
    except Exception as e:
        print(f"❌ Ошибка при тестировании: {e}")

if __name__ == "__main__":
    test_report_endpoints() 