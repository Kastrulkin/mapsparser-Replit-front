#!/usr/bin/env python3
"""
Тестовый скрипт для проверки API
"""
import requests
import json

def test_api():
    base_url = "http://localhost:8000"
    
    print("🧪 Тестируем API...")
    
    # Тест health check
    print("\n1. Health check:")
    try:
        response = requests.get(f"{base_url}/health")
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.json()}")
    except Exception as e:
        print(f"   Error: {e}")
    
    # Тест регистрации
    print("\n2. Регистрация:")
    try:
        response = requests.post(f"{base_url}/api/auth/register", 
                               json={"email":"test@example.com","password":"test123","name":"Test User"})
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.text[:200]}")
    except Exception as e:
        print(f"   Error: {e}")
    
    # Тест входа
    print("\n3. Вход:")
    try:
        response = requests.post(f"{base_url}/api/auth/login", 
                               json={"email":"test@example.com","password":"test123"})
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.text[:200]}")
    except Exception as e:
        print(f"   Error: {e}")

if __name__ == "__main__":
    test_api()
