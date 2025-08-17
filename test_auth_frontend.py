#!/usr/bin/env python3
import os
import requests
from dotenv import load_dotenv

# Загружаем .env файл
load_dotenv()

# Читаем переменные окружения
url = os.getenv('SUPABASE_URL')
anon_key = os.getenv('SUPABASE_ANON_KEY')  # Анонимный ключ для фронтенда

if not url or not anon_key:
    print("Ошибка: SUPABASE_URL или SUPABASE_ANON_KEY не найдены в .env файле")
    exit(1)

print("Тестируем авторизацию через фронтенд API...")

# URL для авторизации
auth_url = f"{url}/auth/v1/user"

headers = {
    'apikey': anon_key,
    'Authorization': f'Bearer {anon_key}',
    'Content-Type': 'application/json'
}

try:
    # Пробуем получить текущего пользователя
    response = requests.get(auth_url, headers=headers)
    print(f"Статус ответа: {response.status_code}")
    print(f"Ответ: {response.text}")
    
except Exception as e:
    print(f"Ошибка: {e}")
