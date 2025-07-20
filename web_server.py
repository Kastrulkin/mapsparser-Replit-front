
#!/usr/bin/env python3
"""
Веб-сервер с автоматическим обновлением файлов
"""
import http.server
import socketserver
import os
import threading
import time
from pathlib import Path

class AutoRefreshHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory='.', **kwargs)
    
    def end_headers(self):
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')
        super().end_headers()
    
    def do_GET(self):
        if self.path == '/':
            self.path = '/index.html'
        return super().do_GET()

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
