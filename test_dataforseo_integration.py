#!/usr/bin/env python3
"""
Тест интеграции DataForSEO MCP сервера
"""

import requests
import json
import os
from typing import Dict, Any

# URL DataForSEO MCP сервера на Smithery.ai
DATAFORSEO_MCP_URL = "https://server.smithery.ai/@moaiandin/mcp-dataforseo"

def call_dataforseo_mcp(tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Вызывает DataForSEO MCP сервер через HTTP
    """
    try:
        headers = {
            "Content-Type": "application/json"
        }
        
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": params
            }
        }
        
        response = requests.post(DATAFORSEO_MCP_URL, headers=headers, json=payload)
        
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Ошибка HTTP: {response.status_code}")
            return {"error": f"HTTP {response.status_code}"}
            
    except Exception as e:
        print(f"Ошибка при вызове DataForSEO MCP: {e}")
        return {"error": str(e)}

def test_serp_analysis():
    """Тест анализа SERP"""
    print("🔍 Тестируем анализ SERP...")
    
    params = {
        "keyword": "салон красоты москва",
        "language_code": "ru",
        "location_name": "Москва,Россия",
        "search_engine": "google",
        "depth": 10
    }
    
    result = call_dataforseo_mcp("serp-organic-live-advanced", params)
    print(f"Результат SERP анализа: {json.dumps(result, indent=2, ensure_ascii=False)}")

def test_keyword_volume():
    """Тест объема ключевых слов"""
    print("📊 Тестируем объем ключевых слов...")
    
    params = {
        "keywords": ["салон красоты", "парикмахерская", "маникюр"],
        "language_code": "ru",
        "location_name": "Россия"
    }
    
    result = call_dataforseo_mcp("keywords-google-ads-search-volume", params)
    print(f"Результат анализа ключевых слов: {json.dumps(result, indent=2, ensure_ascii=False)}")

def test_onpage_analysis():
    """Тест on-page анализа"""
    print("📄 Тестируем on-page анализ...")
    
    params = {
        "url": "https://beautybot.pro",
        "enable_javascript": True
    }
    
    result = call_dataforseo_mcp("instant_pages", params)
    print(f"Результат on-page анализа: {json.dumps(result, indent=2, ensure_ascii=False)}")

def main():
    """Основная функция тестирования"""
    print("🚀 Тестирование интеграции DataForSEO MCP сервера")
    print("=" * 50)
    
    # Тест 1: SERP анализ
    test_serp_analysis()
    print("\n" + "-" * 30 + "\n")
    
    # Тест 2: Объем ключевых слов
    test_keyword_volume()
    print("\n" + "-" * 30 + "\n")
    
    # Тест 3: On-page анализ
    test_onpage_analysis()
    
    print("\n✅ Тестирование завершено!")

if __name__ == "__main__":
    main() 