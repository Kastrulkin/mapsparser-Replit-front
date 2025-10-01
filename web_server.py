
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
import sqlite3

def get_db_connection():
    """Получить соединение с SQLite базой данных"""
    conn = sqlite3.connect("reports.db")
    conn.row_factory = sqlite3.Row
    return conn

class AutoRefreshHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory='.', **kwargs)
    
    def end_headers(self):
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        super().end_headers()
    
    def do_GET(self):
        print(f"DEBUG: GET request to: {self.path}")
        
        # API endpoint для скачивания отчёта
        if self.path.startswith('/api/download-report/'):
            print(f"DEBUG: Routing to download handler")
            self.handle_download_report()
            return
        
        # API endpoint для получения содержимого отчёта
        if self.path.startswith('/api/report-content/'):
            print(f"DEBUG: Routing to content handler")
            self.handle_report_content()
            return
        
        # Новый endpoint для просмотра отчёта в браузере
        # Поддерживаем оба пути: старый '/view-report/' и новый '/api/view-report/'
        if self.path.startswith('/view-report/') or self.path.startswith('/api/view-report/'):
            print(f"DEBUG: Routing to view report handler")
            self.handle_view_report()
            return
            
        if self.path == '/':
            self.path = '/index.html'
        return super().do_GET()
    
    def do_OPTIONS(self):
        """Handle CORS preflight requests"""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    
    def handle_download_report(self):
        """Handle report download"""
        try:
            print(f"DEBUG: Starting download report handler")
            print(f"DEBUG: Full path: {self.path}")
            # Extract report ID from URL
            report_id = self.path.split('/')[-1]
            print(f"DEBUG: Extracted report ID: {report_id}")
            # Normalize incoming id and prepare alternative forms
            normalized_id = report_id.replace('_', '-')
            underscored_id = report_id.replace('-', '_')
            print(f"DEBUG: Normalized report ID: {normalized_id}")
            print(f"DEBUG: Underscored report ID: {underscored_id}")
            
            # Get report information from database
            print(f"DEBUG: Checking Supabase initialization")
            if not supabase:
                print(f"DEBUG: Supabase not initialized!")
                self.send_error(500, "Supabase not initialized")
                return
            
            print(f"DEBUG: Supabase initialized, querying database")
            # Fetch original card by either ID variant
            result = (
                supabase
                .table("Cards")
                .select("id, url, report_path, title, status, created_at")
                .in_("id", [normalized_id, underscored_id])
                .execute()
            )
            print(f"DEBUG: Database query result: {result}")
            
            if not result.data:
                print(f"DEBUG: No data found in database for IDs: {normalized_id} | {underscored_id}")
                self.send_error(404, "Report not found")
                return
            
            print(f"DEBUG: Found data in database: {result.data}")

            report_data = result.data[0]
            report_path = report_data.get('report_path')
            title = report_data.get('title', 'report')
            print(f"DEBUG: Report data: {report_data}")
            print(f"DEBUG: Report path from DB: {report_path}")
            print(f"DEBUG: Title from DB: {title}")
            print(f"DEBUG: Report path is None: {report_path is None}")
            print(f"DEBUG: Report path is empty: {report_path == ''}")

            # Backend fallback: if current card has no file yet, try latest completed by same URL
            if (not report_path) and report_data.get('url'):
                print("DEBUG: Current report has no report_path. Trying fallback by URL...")
                fb = (
                    supabase
                    .table("Cards")
                    .select("id, report_path, title, created_at")
                    .eq("url", report_data.get('url'))
                    .order("created_at", desc=True)
                    .limit(1)
                    .execute()
                )
                print(f"DEBUG: Fallback query result: {fb}")
                if fb.data and fb.data[0].get('report_path'):
                    report_path = fb.data[0]['report_path']
                    title = fb.data[0].get('title', title)
                    print(f"DEBUG: Using fallback report_path: {report_path}")
                else:
                    print("DEBUG: Fallback not found or has no report_path")

            if not report_path or not os.path.exists(report_path):
                print(f"DEBUG: Report file not found: {report_path}")
                self.send_error(404, "Report file not found")
                return
            
            print(f"DEBUG: File exists, size: {os.path.getsize(report_path)} bytes")
            print(f"DEBUG: File permissions: {oct(os.stat(report_path).st_mode)[-3:]}")
            
            # Отправляем файл
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            # Используем безопасное имя файла без русских символов
            safe_title = title.encode('ascii', 'ignore').decode('ascii') if title else 'report'
            self.send_header('Content-Disposition', f'attachment; filename="seo_report_{safe_title}.html"')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
            self.send_header('Access-Control-Allow-Headers', 'Content-Type, Accept')
            self.end_headers()
            
            try:
                print(f"DEBUG: Trying to read file with UTF-8 encoding")
                with open(report_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    print(f"DEBUG: File read successfully, content length: {len(content)}")
                    print(f"DEBUG: First 200 chars: {repr(content[:200])}")
                    self.wfile.write(content.encode('utf-8'))
                    print(f"DEBUG: Content sent successfully")
            except UnicodeDecodeError as e:
                print(f"DEBUG: UTF-8 failed, trying cp1251: {e}")
                # Если UTF-8 не работает, попробуем cp1251
                with open(report_path, 'r', encoding='cp1251') as f:
                    content = f.read()
                    print(f"DEBUG: File read with cp1251, content length: {len(content)}")
                    self.wfile.write(content.encode('utf-8'))
                    print(f"DEBUG: Content sent successfully with cp1251")
            except Exception as e:
                print(f"DEBUG: All encoding methods failed: {e}")
                # Если всё не работает, отправляем пустой файл
                self.wfile.write(b'<html><body><h1>Error loading report</h1></body></html>')
                
        except Exception as e:
            print(f"Error downloading report: {e}")
            self.send_error(500, "Server error occurred")
    
    def handle_report_content(self):
        """Handle getting report content for viewing"""
        try:
            # Extract report ID from URL
            report_id = self.path.split('/')[-1]
            print(f"DEBUG: Requesting report content for ID: {report_id}")
            
            # Get report information from database
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT report_path FROM Cards WHERE id = ?", (report_id,))
            result = cursor.fetchone()
            conn.close()
            
            if not result:
                print(f"DEBUG: Report not found for ID: {report_id}")
                self.send_error(404, "Report not found")
                return
                
            report_path = result['report_path']
            print(f"DEBUG: Report path: {report_path}")
            
            if not report_path or not os.path.exists(report_path):
                print(f"DEBUG: Report file not found: {report_path}")
                self.send_error(404, "Report file not found")
                return
            
            print(f"DEBUG: File exists, size: {os.path.getsize(report_path)} bytes")
            print(f"DEBUG: File permissions: {oct(os.stat(report_path).st_mode)[-3:]}")
            
            # Send file content
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
            self.send_header('Access-Control-Allow-Headers', 'Content-Type, Accept')
            self.end_headers()
            
            try:
                with open(report_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    self.wfile.write(content.encode('utf-8'))
            except UnicodeDecodeError:
                # Если UTF-8 не работает, попробуем cp1251
                with open(report_path, 'r', encoding='cp1251') as f:
                    content = f.read()
                    self.wfile.write(content.encode('utf-8'))
            except Exception as e:
                # Если всё не работает, отправляем пустой файл
                self.wfile.write(b'<html><body><h1>Error loading report</h1></body></html>')
                
        except Exception as e:
            print(f"Error getting report content: {e}")
            self.send_error(500, "Server error occurred")

    def handle_view_report(self):
        """Handle viewing report in browser"""
        try:
            print(f"DEBUG: Starting view report handler")
            print(f"DEBUG: Full path: {self.path}")
            # Extract report ID from URL
            report_id = self.path.split('/')[-1]
            print(f"DEBUG: Extracted report ID: {report_id}")
            # Normalize incoming id and prepare alternative forms
            normalized_id = report_id.replace('_', '-')
            underscored_id = report_id.replace('-', '_')
            print(f"DEBUG: Normalized report ID: {normalized_id}")
            print(f"DEBUG: Underscored report ID: {underscored_id}")
            
            # Get report information from database
            if not supabase:
                print(f"DEBUG: Supabase not initialized!")
                self.send_error(500, "Supabase not initialized")
                return
                
            print(f"DEBUG: Querying database for report")
            result = (
                supabase
                .table("Cards")
                .select("id, url, report_path, title, status, created_at")
                .in_("id", [normalized_id, underscored_id])
                .execute()
            )
            print(f"DEBUG: Database query result: {result}")
            
            if not result.data:
                print(f"DEBUG: No data found in database for IDs: {normalized_id} | {underscored_id}")
                self.send_error(404, "Report not found")
                return
                
            report_data = result.data[0]
            report_path = report_data.get('report_path')
            title = report_data.get('title', 'report')
            print(f"DEBUG: Report path from DB: {report_path}")
            print(f"DEBUG: Title from DB: {title}")

            # Backend fallback: if current card has no file yet, try latest completed by same URL
            if (not report_path) and report_data.get('url'):
                print("DEBUG: Current report has no report_path. Trying fallback by URL...")
                fb = (
                    supabase
                    .table("Cards")
                    .select("id, report_path, title, created_at")
                    .eq("url", report_data.get('url'))
                    .order("created_at", desc=True)
                    .limit(1)
                    .execute()
                )
                print(f"DEBUG: Fallback query result: {fb}")
                if fb.data and fb.data[0].get('report_path'):
                    report_path = fb.data[0]['report_path']
                    title = fb.data[0].get('title', title)
                    print(f"DEBUG: Using fallback report_path: {report_path}")
                else:
                    print("DEBUG: Fallback not found or has no report_path")

            if not report_path or not os.path.exists(report_path):
                print(f"DEBUG: Report file not found: {report_path}")
                self.send_error(404, "Report file not found")
                return
            
            print(f"DEBUG: File exists, size: {os.path.getsize(report_path)} bytes")
            
            # Send file content for viewing in browser
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
            self.send_header('Access-Control-Allow-Headers', 'Content-Type, Accept')
            self.end_headers()
            
            try:
                print(f"DEBUG: Reading file for viewing")
                with open(report_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    print(f"DEBUG: File read successfully, content length: {len(content)}")
                    self.wfile.write(content.encode('utf-8'))
                    print(f"DEBUG: Content sent successfully for viewing")
            except UnicodeDecodeError as e:
                print(f"DEBUG: UTF-8 failed, trying cp1251: {e}")
                with open(report_path, 'r', encoding='cp1251') as f:
                    content = f.read()
                    print(f"DEBUG: File read with cp1251, content length: {len(content)}")
                    self.wfile.write(content.encode('utf-8'))
                    print(f"DEBUG: Content sent successfully with cp1251")
            except Exception as e:
                print(f"DEBUG: All encoding methods failed: {e}")
                self.wfile.write(b'<html><body><h1>Error loading report</h1></body></html>')
                
        except Exception as e:
            print(f"Error viewing report: {e}")
            self.send_error(500, "Server error occurred")

def watch_files():
    """Monitor changes in data folder"""
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
                    print(f"Updated file: {file_path.name}")
                    last_modified[str(file_path)] = current_mtime
        except Exception as e:
            pass
        
        time.sleep(1)

def create_index_html():
    """Creates main page with list of reports"""
    data_dir = Path('data')
    reports = list(data_dir.glob('*.html')) if data_dir.exists() else []
    
    html_content = f"""
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SEO Analyzer Yandex Maps</title>
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
    <h1>SEO Analyzer Yandex Maps</h1>
    <div class="report-list">
        <h2>Reports</h2>
        {
            ''.join([
                f'<div class="report-item"><a href="data/{report.name}" target="_blank">{report.stem.replace("report_", "")}</a></div>'
                for report in reports
            ]) if reports else '<div class="no-reports">Reports not created yet</div>'
        }
    </div>
    <div class="refresh-info">
        Page automatically refreshes every 5 seconds
    </div>
</body>
</html>
"""
    
    with open('index.html', 'w', encoding='utf-8') as f:
        f.write(html_content)

def update_index_periodically():
    """Periodically updates main page"""
    while True:
        create_index_html()
        time.sleep(5)

if __name__ == "__main__":
    PORT = 8001
    
    # Create initial main page
    create_index_html()
    
    # Start file monitoring in separate thread
    file_watcher = threading.Thread(target=watch_files, daemon=True)
    file_watcher.start()
    
    # Start index page updates in separate thread
    index_updater = threading.Thread(target=update_index_periodically, daemon=True)
    index_updater.start()
    
    # Start web server
    with socketserver.TCPServer(("0.0.0.0", PORT), AutoRefreshHandler) as httpd:
        print(f"Server running at http://0.0.0.0:{PORT}")
        print("Files will be automatically updated!")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nServer stopped")
