
#!/usr/bin/env python3
"""
Веб-сервер с автоматическим обновлением файлов и API для отчётов
"""
import http.server
import socketserver
import os
import threading
import time
import json
import urllib.parse
from pathlib import Path
from supabase import create_client, Client
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Инициализация Supabase
def init_supabase():
    url = os.getenv('SUPABASE_URL')
    key = os.getenv('SUPABASE_KEY')
    if not url or not key:
        print("ERROR: SUPABASE_URL или SUPABASE_KEY не найдены!")
        return None
    return create_client(url, key)

supabase: Client = init_supabase()

class AutoRefreshHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory='.', **kwargs)
    
    def end_headers(self):
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')
        super().end_headers()
    
    def do_GET(self):
        # API endpoint для скачивания отчёта
        if self.path.startswith('/api/download-report/'):
            self.handle_download_report()
            return
        
        # API endpoint для получения содержимого отчёта
        if self.path.startswith('/api/report-content/'):
            self.handle_report_content()
            return
            
        if self.path == '/':
            self.path = '/index.html'
        return super().do_GET()
    
    def handle_download_report(self):
        """Обработка скачивания отчёта"""
        try:
            # Извлекаем ID отчёта из URL
            report_id = self.path.split('/')[-1]
            
            # Получаем информацию об отчёте из базы данных
            if not supabase:
                self.send_error(500, "Supabase не инициализирован")
                return
                
            result = supabase.table("Cards").select("report_path, title").eq("id", report_id).execute()
            
            if not result.data:
                self.send_error(404, "Отчёт не найден")
                return
                
            report_data = result.data[0]
            report_path = report_data.get('report_path')
            title = report_data.get('title', 'report')
            
            if not report_path or not os.path.exists(report_path):
                self.send_error(404, "Файл отчёта не найден")
                return
            
            # Отправляем файл
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Disposition', f'attachment; filename="seo_report_{title}.html"')
            self.end_headers()
            
            with open(report_path, 'rb') as f:
                self.wfile.write(f.read())
                
        except Exception as e:
            print(f"Ошибка при скачивании отчёта: {e}")
            self.send_error(500, f"Ошибка сервера: {str(e)}")
    
    def handle_report_content(self):
        """Обработка получения содержимого отчёта для просмотра"""
        try:
            # Извлекаем ID отчёта из URL
            report_id = self.path.split('/')[-1]
            
            # Получаем информацию об отчёте из базы данных
            if not supabase:
                self.send_error(500, "Supabase не инициализирован")
                return
                
            result = supabase.table("Cards").select("report_path").eq("id", report_id).execute()
            
            if not result.data:
                self.send_error(404, "Отчёт не найден")
                return
                
            report_data = result.data[0]
            report_path = report_data.get('report_path')
            
            if not report_path or not os.path.exists(report_path):
                self.send_error(404, "Файл отчёта не найден")
                return
            
            # Отправляем содержимое файла
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            with open(report_path, 'rb') as f:
                self.wfile.write(f.read())
                
        except Exception as e:
            print(f"Ошибка при получении содержимого отчёта: {e}")
            self.send_error(500, f"Ошибка сервера: {str(e)}")

def watch_files():
    """Мониторинг изменений в папке data"""
    data_dir = Path('data')
    if not data_dir.exists():
        data_dir.mkdir(exist_ok=True)
    
    last_modified = {}
    
    while True:
        try:
            for file_path in data_dir.glob('*.html'):
                current_mtime = file_path.stat().st_mtime
                if str(file_path) not in last_modified:
                    last_modified[str(file_path)] = current_mtime
                elif current_mtime > last_modified[str(file_path)]:
                    print(f"Обновлен файл: {file_path.name}")
                    last_modified[str(file_path)] = current_mtime
        except Exception as e:
            pass
        
        time.sleep(1)

def create_index_html():
    """Создает главную страницу со списком отчетов"""
    data_dir = Path('data')
    reports = list(data_dir.glob('*.html')) if data_dir.exists() else []
    
    html_content = f"""
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SEO Анализатор Яндекс.Карт</title>
    <meta http-equiv="refresh" content="5">
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; background: #f9f9f9; }}
        h1 {{ color: #2d3a4a; }}
        .report-list {{ background: #fff; padding: 20px; border-radius: 8px; }}
        .report-item {{ margin: 10px 0; padding: 10px; border: 1px solid #e0e0e0; border-radius: 4px; }}
        .report-item a {{ text-decoration: none; color: #1976d2; font-weight: bold; }}
        .report-item a:hover {{ text-decoration: underline; }}
        .no-reports {{ color: #666; font-style: italic; }}
        .refresh-info {{ color: #666; font-size: 0.9em; margin-top: 20px; }}
    </style>
</head>
<body>
    <h1>SEO Анализатор Яндекс.Карт</h1>
    <div class="report-list">
        <h2>Отчеты</h2>
        {
            ''.join([
                f'<div class="report-item"><a href="data/{report.name}" target="_blank">{report.stem.replace("report_", "")}</a></div>'
                for report in reports
            ]) if reports else '<div class="no-reports">Отчеты еще не созданы</div>'
        }
    </div>
    <div class="refresh-info">
        Страница автоматически обновляется каждые 5 секунд
    </div>
</body>
</html>
"""
    
    with open('index.html', 'w', encoding='utf-8') as f:
        f.write(html_content)

def update_index_periodically():
    """Периодически обновляет главную страницу"""
    while True:
        create_index_html()
        time.sleep(5)

if __name__ == "__main__":
    PORT = 8000
    
    # Создаем начальную главную страницу
    create_index_html()
    
    # Запускаем мониторинг файлов в отдельном потоке
    file_watcher = threading.Thread(target=watch_files, daemon=True)
    file_watcher.start()
    
    # Запускаем обновление индексной страницы в отдельном потоке
    index_updater = threading.Thread(target=update_index_periodically, daemon=True)
    index_updater.start()
    
    # Запускаем веб-сервер
    with socketserver.TCPServer(("0.0.0.0", PORT), AutoRefreshHandler) as httpd:
        print(f"Сервер запущен на http://0.0.0.0:{PORT}")
        print("Файлы будут автоматически обновляться!")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nСервер остановлен")
