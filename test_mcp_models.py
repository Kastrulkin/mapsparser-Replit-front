#!/usr/bin/env python3
"""
Тестирование MCP сервера Hugging Face для поиска моделей
"""
import subprocess
import json
import os
from dotenv import load_dotenv

load_dotenv()

def test_mcp_server():
    """Тестирует MCP сервер Hugging Face"""
    
    hf_token = os.getenv('HUGGINGFACE_API_TOKEN')
    if not hf_token:
        print("❌ HUGGINGFACE_API_TOKEN не найден")
        return
    
    print("🔍 Тестирование MCP сервера Hugging Face...")
    print("=" * 60)
    
    try:
        # Запускаем MCP сервер
        cmd = [
            "npx", "-y", "huggingface-mcp-server",
            "--transport", "stdio",
            "--api-key", hf_token
        ]
        
        print(f"🚀 Запуск команды: {' '.join(cmd)}")
        
        # Запускаем процесс
        process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Отправляем MCP запрос для получения списка моделей
        mcp_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/list",
            "params": {}
        }
        
        print("📤 Отправляем запрос на получение списка инструментов...")
        request_str = json.dumps(mcp_request) + "\n"
        
        stdout, stderr = process.communicate(input=request_str, timeout=10)
        
        print(f"📥 Ответ stdout: {stdout}")
        print(f"❌ Ошибки stderr: {stderr}")
        
        if stdout:
            try:
                response = json.loads(stdout)
                print(f"✅ Получен ответ: {json.dumps(response, indent=2)}")
            except json.JSONDecodeError:
                print(f"⚠️  Не удалось распарсить JSON: {stdout}")
        
        process.terminate()
        
    except subprocess.TimeoutExpired:
        print("⏰ Таймаут выполнения команды")
        process.kill()
    except Exception as e:
        print(f"❌ Ошибка: {e}")

def test_direct_api():
    """Тестирует прямой API для сравнения"""
    
    print("\n" + "=" * 60)
    print("🔍 Сравнение с прямым API...")
    print("=" * 60)
    
    import requests
    
    hf_token = os.getenv('HUGGINGFACE_API_TOKEN')
    headers = {
        "Authorization": f"Bearer {hf_token}",
        "Content-Type": "application/json"
    }
    
    # Поиск популярных моделей для текстовой генерации
    search_queries = [
        "text-generation",
        "text2text-generation",
        "russian language"
    ]
    
    for query in search_queries:
        print(f"\n📝 Поиск: {query}")
        
        try:
            response = requests.get(
                "https://huggingface.co/api/models",
                headers=headers,
                params={
                    "search": query,
                    "sort": "downloads",
                    "direction": "-1",
                    "limit": 5
                }
            )
            
            if response.status_code == 200:
                models = response.json()
                print(f"✅ Найдено {len(models)} моделей")
                
                for i, model in enumerate(models[:3], 1):
                    print(f"   {i}. {model.get('id', 'N/A')} ({model.get('downloads', 0):,} загрузок)")
            else:
                print(f"❌ Ошибка API: {response.status_code}")
                
        except Exception as e:
            print(f"❌ Ошибка запроса: {e}")

if __name__ == "__main__":
    test_mcp_server()
    test_direct_api() 