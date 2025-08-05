#!/usr/bin/env python3
import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

supabase_url = os.getenv('SUPABASE_URL')
supabase_key = os.getenv('SUPABASE_KEY')
supabase = create_client(supabase_url, supabase_key)

try:
    # Проверяем очередь обработки
    result = supabase.table('ParseQueue').select('*').execute()
    print('Записи в очереди ParseQueue:')
    for record in result.data:
        print(f"ID: {record.get('id')}, URL: {record.get('url')}, Status: {record.get('status')}, User: {record.get('user_id')}")
    
    if not result.data:
        print("Очередь пуста")
        
except Exception as e:
    print(f"Ошибка: {e}") 