#!/usr/bin/env python3
import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

supabase_url = os.getenv('SUPABASE_URL')
supabase_key = os.getenv('SUPABASE_KEY')
supabase = create_client(supabase_url, supabase_key)

try:
    # Получаем детальную информацию об отчёте "У Жени"
    result = supabase.table('Cards').select('*').eq('id', 'ac33c28e-f0b8-4d10-89da-b52bed600d14').execute()
    
    if result.data:
        card = result.data[0]
        print('Детали отчёта "У Жени":')
        for key, value in card.items():
            print(f"{key}: {value}")
    else:
        print("Отчёт не найден")
        
except Exception as e:
    print(f"Ошибка: {e}") 