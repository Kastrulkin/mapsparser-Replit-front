#!/usr/bin/env python3
"""
GigaChat клиент с ротацией ключей и retry логикой
"""
import os
import json
import time
import random
import base64
import requests
from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime, timedelta
from gigachat_config import get_gigachat_config

class GigaChatClient:
    def __init__(self):
        """Инициализация с поддержкой ротации ключей"""
        self.base_url = "https://gigachat.devices.sberbank.ru/api/v1"
        self.credentials_pool: List[Tuple[str, str]] = []
        self.current_index = 0
        self.access_token = None
        self.token_expires_at = 0
        self.last_auth_error = None
        
        # Загружаем конфигурацию GigaChat
        self.config = get_gigachat_config()
        
        # Загружаем ключи из переменных окружения
        self._load_credentials()
    
    def _load_credentials(self):
        """Загружает ключи из переменных окружения"""
        # Формат: GIGACHAT_KEYS="id1:secret1;id2:secret2;id3:secret3"
        keys_env = os.getenv("GIGACHAT_KEYS", "").strip()
        if keys_env:
            try:
                for pair in keys_env.split(";"):
                    pair = pair.strip()
                    if not pair:
                        continue
                    cid, csec = pair.split(":", 1)
                    self.credentials_pool.append((cid.strip(), csec.strip()))
            except Exception as e:
                print(f"⚠️ Ошибка парсинга GIGACHAT_KEYS: {e}")
        
        # Fallback к старым переменным
        if not self.credentials_pool:
            env_id = os.getenv('GIGACHAT_CLIENT_ID')
            env_secret = os.getenv('GIGACHAT_CLIENT_SECRET')
            if env_id and env_secret:
                self.credentials_pool = [(env_id, env_secret)]
        
        if not self.credentials_pool:
            raise RuntimeError("GigaChat ключи не настроены. Установите GIGACHAT_KEYS или GIGACHAT_CLIENT_ID/GIGACHAT_CLIENT_SECRET")
    
    def _rotate_credentials(self):
        """Ротация к следующему ключу"""
        if not self.credentials_pool:
            return
        self.current_index = (self.current_index + 1) % len(self.credentials_pool)
        # Инвалидируем токен при смене ключа
        self.access_token = None
        self.token_expires_at = 0
        print(f"🔄 Переключение на ключ {self.current_index + 1}/{len(self.credentials_pool)}")
    
    def _get_current_credentials(self) -> Tuple[str, str]:
        """Получить текущие учетные данные"""
        if not self.credentials_pool:
            raise RuntimeError("GigaChat credentials are not configured")
        return self.credentials_pool[self.current_index]
    
    def get_access_token(self) -> str:
        """Получить токен доступа с ротацией ключей и retry"""
        if self.access_token and time.time() < self.token_expires_at:
            return self.access_token
        
        last_error = None
        attempts = min(3, max(1, len(self.credentials_pool) or 1))
        
        for attempt in range(attempts):
            try:
                client_id, client_secret = self._get_current_credentials()
                url = f"{self.base_url}/oauth"
                data = {"scope": "GIGACHAT_API_PERS"}
                headers = {
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Accept": "application/json"
                }
                
                response = requests.post(
                    url, 
                    data=data, 
                    headers=headers, 
                    auth=(client_id, client_secret), 
                    timeout=30
                )
                
                if response.status_code in (401, 403):
                    # Неверный/просроченный ключ — пробуем следующий
                    last_error = RuntimeError(f"Auth failed for key {self.current_index + 1}: {response.status_code}")
                    self._rotate_credentials()
                    continue
                
                response.raise_for_status()
                token_data = response.json()
                self.access_token = token_data["access_token"]
                # Токен действует 30 минут, обновляем за 5 минут до истечения
                self.token_expires_at = time.time() + (25 * 60)
                print(f"✅ GigaChat токен получен (ключ {self.current_index + 1})")
                return self.access_token
                
            except Exception as e:
                last_error = e
                # Экспоненциальная задержка с джиттером
                time.sleep(0.5 * (2 ** attempt) + random.random() * 0.25)
                # Попробуем другой ключ
                self._rotate_credentials()
        
        raise RuntimeError(f"Не удалось получить токен GigaChat: {last_error}")
    
    def _post_with_retry(self, url: str, headers: Dict[str, str], json_body: Dict[str, Any], max_retries: int = 3) -> Dict[str, Any]:
        """POST запрос с retry и ротацией ключей"""
        last_error = None
        
        for attempt in range(max_retries):
            try:
                response = requests.post(url, json=json_body, headers=headers, timeout=60)
                
                # Если лимиты/авторизация — пробуем ротацию ключа и повтор
                if response.status_code in (401, 403, 429, 503):
                    last_error = RuntimeError(f"HTTP {response.status_code}")
                    # Сменим ключ и обновим токен
                    self._rotate_credentials()
                    headers["Authorization"] = f"Bearer {self.get_access_token()}"
                else:
                    response.raise_for_status()
                    return response.json()
                    
            except Exception as e:
                last_error = e
            
            # Бэк-офф с джиттером
            time.sleep(0.75 * (2 ** attempt) + random.random() * 0.3)
        
        raise RuntimeError(f"Запрос к GigaChat не удался после повторов: {last_error}")
    
    def analyze_screenshot(self, image_base64: str, prompt: str) -> str:
        """Анализ скриншота карточки"""
        try:
            token = self.get_access_token()
            
            url = f"{self.base_url}/chat/completions"
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
            
            # Формируем сообщение с изображением
            message_content = [
                {
                    "type": "text",
                    "text": prompt
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{image_base64}"
                    }
                }
            ]
            
            model_config = self.config.get_model_config()
            data = {
                "model": model_config["model"],
                "messages": [
                    {
                        "role": "user",
                        "content": message_content
                    }
                ],
                "temperature": model_config["temperature"],
                "max_tokens": model_config["max_tokens"]
            }
            
            result = self._post_with_retry(url, headers, data, max_retries=3)
            return result["choices"][0]["message"]["content"]
            
        except Exception as e:
            print(f"❌ Ошибка анализа скриншота: {e}")
            raise
    
    def analyze_text(self, prompt: str) -> str:
        """Анализ текста"""
        try:
            token = self.get_access_token()
            
            url = f"{self.base_url}/chat/completions"
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
            
            model_config = self.config.get_model_config()
            data = {
                "model": model_config["model"],
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "temperature": model_config["temperature"],
                "max_tokens": model_config["max_tokens"]
            }
            
            result = self._post_with_retry(url, headers, data, max_retries=3)
            return result["choices"][0]["message"]["content"]
            
        except Exception as e:
            print(f"❌ Ошибка анализа текста: {e}")
            raise
    
    def parse_json_response(self, response_text: str) -> Dict[str, Any]:
        """Парсинг JSON ответа с автокоррекцией"""
        try:
            # Ищем JSON в ответе
            start_idx = response_text.find('{')
            end_idx = response_text.rfind('}') + 1
            
            if start_idx != -1 and end_idx != -1:
                json_str = response_text[start_idx:end_idx]
                return json.loads(json_str)
            else:
                # Если JSON не найден, создаем базовый ответ
                return {
                    "error": "Не удалось найти JSON в ответе",
                    "raw_response": response_text[:500]
                }
                
        except json.JSONDecodeError as e:
            print(f"⚠️ Ошибка парсинга JSON: {e}")
            # Попробуем исправить JSON
            try:
                # Убираем лишние символы и пробуем снова
                cleaned = response_text.strip()
                if cleaned.startswith('```json'):
                    cleaned = cleaned[7:]
                if cleaned.endswith('```'):
                    cleaned = cleaned[:-3]
                cleaned = cleaned.strip()
                
                return json.loads(cleaned)
            except:
                return {
                    "error": "Не удалось распарсить JSON",
                    "raw_response": response_text[:500]
                }
        except Exception as e:
            return {
                "error": f"Ошибка обработки ответа: {str(e)}",
                "raw_response": response_text[:500]
            }

# Глобальный экземпляр клиента
_gigachat_client = None

def get_gigachat_client() -> GigaChatClient:
    """Получить глобальный экземпляр GigaChat клиента"""
    global _gigachat_client
    if _gigachat_client is None:
        _gigachat_client = GigaChatClient()
    return _gigachat_client

def analyze_screenshot_with_gigachat(image_base64: str, prompt: str) -> Dict[str, Any]:
    """Анализ скриншота через GigaChat"""
    try:
        client = get_gigachat_client()
        response = client.analyze_screenshot(image_base64, prompt)
        return client.parse_json_response(response)
    except Exception as e:
        return {
            "error": f"Ошибка анализа скриншота: {str(e)}",
            "fallback": True
        }

def analyze_text_with_gigachat(prompt: str) -> Dict[str, Any]:
    """Анализ текста через GigaChat"""
    try:
        client = get_gigachat_client()
        response = client.analyze_text(prompt)
        return client.parse_json_response(response)
    except Exception as e:
        return {
            "error": f"Ошибка анализа текста: {str(e)}",
            "fallback": True
        }
