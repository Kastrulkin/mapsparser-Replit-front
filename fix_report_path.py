#!/usr/bin/env python3
import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

supabase_url = os.getenv('SUPABASE_URL')
supabase_key = os.getenv('SUPABASE_KEY')
supabase = create_client(supabase_url, supabase_key)

try:
    # Получаем отчёт с неправильным путём
    result = supabase.table('Cards').select('id, title, report_path').eq('id', 'ac33c28e-f0b8-4d10-89da-b52bed600d14').execute()
    
    if result.data:
        card = result.data[0]
        print(f"Текущий путь: {card.get('report_path')}")
        
        # Проверяем, какой файл реально существует
        data_dir = "/root/mapsparser-Replit-front/data"
        if os.path.exists(data_dir):
            files = os.listdir(data_dir)
            html_files = [f for f in files if f.endswith('.html')]
            print(f"Файлы в папке data: {html_files}")
            
            if html_files:
                # Берём первый HTML файл
                correct_path = os.path.join(data_dir, html_files[0])
                print(f"Исправляем путь на: {correct_path}")
                
                # Обновляем путь в базе данных
                update_result = supabase.table('Cards').update({
                    'report_path': correct_path
                }).eq('id', 'ac33c28e-f0b8-4d10-89da-b52bed600d14').execute()
                
                print("Путь обновлён в базе данных")
            else:
                print("HTML файлы не найдены в папке data")
        else:
            print("Папка data не существует")
    else:
        print("Отчёт не найден в базе данных")
        
except Exception as e:
    print(f"Ошибка: {e}") 