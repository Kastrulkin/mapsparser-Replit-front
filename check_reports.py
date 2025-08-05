#!/usr/bin/env python3
import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

supabase_url = os.getenv('SUPABASE_URL')
supabase_key = os.getenv('SUPABASE_KEY')
supabase = create_client(supabase_url, supabase_key)

try:
    result = supabase.table('Cards').select('id, title, report_path').execute()
    print('Отчёты в базе:')
    for record in result.data:
        print(f"ID: {record.get('id')}, Title: {record.get('title')}, Path: {record.get('report_path')}")
    
    if not result.data:
        print("В базе нет отчётов")
        
except Exception as e:
    print(f"Ошибка: {e}") 