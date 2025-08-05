#!/usr/bin/env python3
import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

supabase_url = os.getenv('SUPABASE_URL')
supabase_key = os.getenv('SUPABASE_KEY')
supabase = create_client(supabase_url, supabase_key)

def update_user_data(user_id, name, phone, yandex_url):
    print(f"=== Обновление данных пользователя {user_id} ===")
    
    try:
        result = supabase.table('Users').update({
            'name': name,
            'phone': phone,
            'yandex_url': yandex_url
        }).eq('id', user_id).execute()
        
        if result.data:
            print("Данные успешно обновлены!")
            user = result.data[0]
            print(f"ID: {user.get('id')}")
            print(f"Email: {user.get('email')}")
            print(f"Имя: {user.get('name')}")
            print(f"Телефон: {user.get('phone')}")
            print(f"Yandex URL: {user.get('yandex_url')}")
        else:
            print("Ошибка: данные не обновлены")
            
    except Exception as e:
        print(f"Ошибка при обновлении данных: {e}")

def update_all_users():
    print("=== Обновление данных для всех пользователей ===")
    
    # Данные для обновления (замените на реальные)
    users_data = [
        {
            'id': '450eaa4e-5186-42e5-b749-0c939baa40bf',
            'name': 'Павел Демьянов',
            'phone': '+7 (999) 123-45-67',
            'yandex_url': 'https://yandex.ru/maps/org/feniks_anny/1196644682/'
        },
        {
            'id': '863b8703-842d-49b6-9754-adbec8b20e01',
            'name': 'Александр Демьянов',
            'phone': '+7 (999) 234-56-78',
            'yandex_url': 'https://yandex.ru/maps/org/test_business/123456789/'
        },
        {
            'id': '9751a818-be4c-4e34-8ba2-5dadf1d97129',
            'name': 'Демьянов',
            'phone': '+7 (999) 345-67-89',
            'yandex_url': 'https://yandex.ru/maps/org/another_business/987654321/'
        }
    ]
    
    for user_data in users_data:
        update_user_data(
            user_data['id'],
            user_data['name'],
            user_data['phone'],
            user_data['yandex_url']
        )
        print("-" * 50)

if __name__ == "__main__":
    # Обновляем данные для всех пользователей
    update_all_users() 