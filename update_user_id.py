#!/usr/bin/env python3
import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

supabase_url = os.getenv('SUPABASE_URL')
supabase_key = os.getenv('SUPABASE_KEY')
supabase = create_client(supabase_url, supabase_key)

def update_user_id():
    print("=== Обновление ID пользователя ===")
    
    # Старый ID (в таблице Users)
    old_id = "450eaa4e-5186-42e5-b749-0c939baa40bf"
    # Новый ID (из Auth)
    new_id = "db12ed3e-4c96-4d66-91e6-b1dab012ce30"
    email = "demyanovap@yandex.ru"
    
    try:
        # Проверяем, существует ли пользователь со старым ID
        check_old = supabase.table('Users').select('*').eq('id', old_id).execute()
        
        if not check_old.data:
            print(f"❌ Пользователь с ID {old_id} не найден")
            return
        
        old_user = check_old.data[0]
        print(f"✅ Найден пользователь со старым ID:")
        print(f"Старый ID: {old_id}")
        print(f"Email: {old_user.get('email')}")
        print(f"Имя: {old_user.get('name')}")
        print(f"Yandex URL: {old_user.get('yandex_url')}")
        
        # Проверяем, не существует ли уже пользователь с новым ID
        check_new = supabase.table('Users').select('*').eq('id', new_id).execute()
        
        if check_new.data:
            print(f"⚠️  Пользователь с ID {new_id} уже существует")
            print("Удаляем дублирующую запись...")
            delete_result = supabase.table('Users').delete().eq('id', new_id).execute()
            if delete_result.data:
                print("✅ Дублирующая запись удалена")
        
        # Обновляем ID пользователя
        print(f"Обновляем ID с {old_id} на {new_id}...")
        
        # Сначала создаём запись с новым ID
        new_user_data = {
            'id': new_id,
            'email': old_user.get('email'),
            'name': old_user.get('name'),
            'phone': old_user.get('phone'),
            'yandex_url': old_user.get('yandex_url'),
            'created_at': old_user.get('created_at')
        }
        
        insert_result = supabase.table('Users').insert(new_user_data).execute()
        
        if insert_result.data:
            print("✅ Запись с новым ID создана")
            
            # Удаляем старую запись
            delete_old = supabase.table('Users').delete().eq('id', old_id).execute()
            if delete_old.data:
                print("✅ Старая запись удалена")
            
            # Проверяем результат
            verify_result = supabase.table('Users').select('*').eq('id', new_id).execute()
            if verify_result.data:
                user = verify_result.data[0]
                print(f"\n✅ Пользователь успешно обновлен:")
                print(f"ID: {user.get('id')}")
                print(f"Email: {user.get('email')}")
                print(f"Имя: {user.get('name')}")
                print(f"Телефон: {user.get('phone')}")
                print(f"Yandex URL: {user.get('yandex_url')}")
        else:
            print("❌ Ошибка при создании записи с новым ID")
            
    except Exception as e:
        print(f"❌ Ошибка: {e}")

def verify_final_state():
    print("\n=== Проверка финального состояния ===")
    try:
        # Проверяем пользователя с новым ID
        auth_id = "db12ed3e-4c96-4d66-91e6-b1dab012ce30"
        result = supabase.table('Users').select('*').eq('id', auth_id).execute()
        
        if result.data:
            user = result.data[0]
            print("✅ Пользователь найден с правильным ID:")
            print(f"ID: {user.get('id')}")
            print(f"Email: {user.get('email')}")
            print(f"Имя: {user.get('name')}")
            print(f"Телефон: {user.get('phone')}")
            print(f"Yandex URL: {user.get('yandex_url')}")
            
            # Проверяем отчёты
            reports_result = supabase.table('Cards').select('*').eq('user_id', auth_id).execute()
            if reports_result.data:
                print(f"\n✅ Найдено отчётов: {len(reports_result.data)}")
                for report in reports_result.data:
                    print(f"  - {report.get('title')} ({report.get('url')})")
            else:
                print("\n❌ Отчётов не найдено")
        else:
            print("❌ Пользователь с правильным ID не найден")
    except Exception as e:
        print(f"❌ Ошибка при проверке: {e}")

if __name__ == "__main__":
    update_user_id()
    verify_final_state() 