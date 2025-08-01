#!/usr/bin/env python3
"""
Тест официального Hugging Face MCP клиента
"""

import os
import subprocess
import json
import sys
from dotenv import load_dotenv

load_dotenv()

def test_mcp_client():
    """Тестируем официальный MCP клиент"""
    hf_token = os.getenv('HUGGINGFACE_API_TOKEN')
    if not hf_token:
        print("❌ HUGGINGFACE_API_TOKEN не найден")
        return False
    
    print("🔍 Тестируем официальный Hugging Face MCP клиент")
    print("=" * 60)
    
    try:
        # Проверяем доступность пакета
        print("📦 Проверяем доступность @huggingface/mcp-client...")
        result = subprocess.run(
            ["npx", "-y", "@huggingface/mcp-client", "--help"],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            print("✅ MCP клиент доступен!")
            print(f"📄 Помощь: {result.stdout[:200]}...")
        else:
            print(f"❌ Ошибка: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print("⏰ Таймаут при проверке MCP клиента")
        return False
    except Exception as e:
        print(f"❌ Исключение: {e}")
        return False
    
    # Тестируем поиск моделей через MCP
    try:
        print("\n🔍 Тестируем поиск моделей через MCP...")
        
        # Создаем MCP запрос для поиска моделей
        mcp_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "search_models",
                "arguments": {
                    "query": "russian text generation",
                    "limit": 5
                }
            }
        }
        
        # Отправляем запрос через npx
        process = subprocess.Popen(
            ["npx", "-y", "@huggingface/mcp-client"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env={"HUGGINGFACE_API_TOKEN": hf_token}
        )
        
        try:
            stdout, stderr = process.communicate(
                input=json.dumps(mcp_request) + "\n",
                timeout=30
            )
            
            if process.returncode == 0:
                print("✅ MCP запрос выполнен!")
                print(f"📄 Ответ: {stdout[:500]}...")
                
                # Парсим ответ
                try:
                    response = json.loads(stdout)
                    if "result" in response:
                        models = response["result"].get("content", [])
                        print(f"📊 Найдено моделей: {len(models)}")
                        for i, model in enumerate(models[:3], 1):
                            print(f"  {i}. {model.get('id', 'N/A')}")
                    else:
                        print("⚠️ Неожиданный формат ответа")
                        
                except json.JSONDecodeError:
                    print("⚠️ Не удалось распарсить JSON ответ")
                    
            else:
                print(f"❌ Ошибка MCP: {stderr}")
                
        except subprocess.TimeoutExpired:
            process.kill()
            print("⏰ Таймаут при выполнении MCP запроса")
            
    except Exception as e:
        print(f"❌ Ошибка при тестировании MCP: {e}")
        return False
    
    return True

def test_mcp_tools():
    """Тестируем доступные инструменты MCP"""
    print("\n🔧 Тестируем доступные инструменты MCP...")
    
    try:
        # Запрос списка инструментов
        tools_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/list",
            "params": {}
        }
        
        process = subprocess.Popen(
            ["npx", "-y", "@huggingface/mcp-client"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env={"HUGGINGFACE_API_TOKEN": os.getenv('HUGGINGFACE_API_TOKEN')}
        )
        
        stdout, stderr = process.communicate(
            input=json.dumps(tools_request) + "\n",
            timeout=30
        )
        
        if process.returncode == 0:
            print("✅ Список инструментов получен!")
            print(f"📄 Инструменты: {stdout[:300]}...")
        else:
            print(f"❌ Ошибка: {stderr}")
            
    except Exception as e:
        print(f"❌ Ошибка при получении инструментов: {e}")

if __name__ == "__main__":
    success = test_mcp_client()
    test_mcp_tools()
    
    if success:
        print(f"\n🎉 MCP клиент работает!")
    else:
        print(f"\n💥 MCP клиент не работает.") 