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
        self.oauth_url = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
        self.credentials_pool: List[Tuple[str, str]] = []
        self.current_index = 0
        self.access_token = None
        self.token_expires_at = 0
        self.last_auth_error = None
        
        # Загружаем конфигурацию GigaChat
        self.config = get_gigachat_config()
        
        # Настройка проверки сертификатов TLS
        # Можно указать путь к кастомному CA через GIGACHAT_CA_BUNDLE или REQUESTS_CA_BUNDLE
        ca_bundle = os.getenv("GIGACHAT_CA_BUNDLE") or os.getenv("REQUESTS_CA_BUNDLE")
        if ca_bundle and os.path.exists(ca_bundle):
            self.verify_tls = ca_bundle  # verify принимает путь к файлу CA
            print(f"🔐 Используется пользовательский CA bundle: {ca_bundle}")
        elif os.getenv("GIGACHAT_SSL_VERIFY", "true").lower() == "false":
            # Отключаем проверку SSL если явно указано
            self.verify_tls = False
            print("⚠️ SSL проверка отключена для GigaChat")
        else:
            # По умолчанию используем системные сертификаты
            self.verify_tls = True
        
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
                url = self.oauth_url
                data = {"scope": "GIGACHAT_API_PERS"}
                
                # Генерируем уникальный RqUID для каждого запроса
                import uuid
                rquid = str(uuid.uuid4())
                
                # Правильный формат Basic авторизации: base64(client_id:client_secret)
                credentials = f"{client_id}:{client_secret}"
                encoded_credentials = base64.b64encode(credentials.encode()).decode()
                
                headers = {
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Accept": "application/json",
                    "RqUID": rquid,
                    "Authorization": f"Basic {encoded_credentials}"
                }
                
                response = requests.post(
                    url, 
                    data=data, 
                    headers=headers, 
                    timeout=30,
                    verify=self.verify_tls
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
                response = requests.post(url, json=json_body, headers=headers, timeout=60, verify=self.verify_tls)
                
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
    
    def upload_file_simple(self, file_data: bytes, filename: str) -> str:
        """Простая загрузка файла в GigaChat"""
        try:
            token = self.get_access_token()
            
            url = f"{self.base_url}/files"
            headers = {
                "Authorization": f"Bearer {token}"
            }
            
            # ИСПРАВЛЕНИЕ: Правильный формат multipart/form-data
            files = {'file': (filename, file_data, 'image/png')}
            data = {'purpose': 'general'}
            
            response = requests.post(url, headers=headers, files=files, data=data, verify=False, timeout=60)
            
            if response.status_code == 200:
                result = response.json()
                print(f"DEBUG: Ответ от /files: {result}")
                return result.get('id')
            else:
                print(f"DEBUG: Ошибка загрузки: {response.status_code}")
                print(f"DEBUG: Тело ответа: {response.text}")
                raise Exception(f"Ошибка загрузки: {response.status_code} - {response.text}")
                
        except Exception as e:
            print(f"DEBUG: Исключение в upload_file_simple: {str(e)}")
            raise Exception(f"Ошибка загрузки файла: {str(e)}")

    def analyze_screenshot(self, image_base64: str, prompt: str) -> str:
        """Анализ скриншота карточки"""
        try:
            print(f"🚨 DEBUG: Начинаем анализ скриншота")
            print(f"🚨 DEBUG: Размер base64: {len(image_base64)} символов")
            
            # Загружаем файл в GigaChat
            import base64
            file_data = base64.b64decode(image_base64)
            file_id = self.upload_file_simple(file_data, "screenshot.png")
            print(f"🚨 DEBUG: Файл загружен, file_id: {file_id}")
            
            # Получаем токен
            token = self.get_access_token()
            
            # Формируем запрос к GigaChat
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
                        "content": prompt,
                        "attachments": [file_id]
                    }
                ],
                "parameters": {
                    "temperature": model_config.get("temperature", 0.1),
                    "max_tokens": model_config.get("max_tokens", 2000),
                    "frequency_penalty": model_config.get("frequency_penalty", 0),
                    "presence_penalty": model_config.get("presence_penalty", 0)
                }
            }
            
            result = self._post_with_retry(url, headers, data, max_retries=3)
            print(f"🚨 DEBUG: Полный ответ от GigaChat: {result}")
            
            # Исправляем согласно документации GigaChat
            if "alternatives" in result:
                content = result["alternatives"][0]["message"]["content"]
                print(f"🚨 DEBUG: Используем структуру 'alternatives'")
            elif "choices" in result:
                content = result["choices"][0]["message"]["content"]
                print(f"🚨 DEBUG: Используем структуру 'choices' (старая)")
            else:
                raise Exception("Неизвестная структура ответа от GigaChat")
            
            print(f"🚨 DEBUG: Извлеченный контент: {content}")
            
            # Очищаем JSON от лишних символов
            import re
            import json
            
            # Находим последнюю закрывающую скобку }
            last_brace = content.rfind('}')
            if last_brace != -1:
                cleaned_content = content[:last_brace + 1]
            else:
                cleaned_content = content
            
            print(f"🚨 DEBUG: Оригинальный ответ: {content[:200]}...")
            print(f"🚨 DEBUG: Очищенный ответ: {cleaned_content[:200]}...")
            print(f"🚨 DEBUG: Проблемный участок (позиция 830-840): {content[830:840]}")
            print(f"🚨 DEBUG: Длина оригинального: {len(content)}, очищенного: {len(cleaned_content)}")
            
            # Проверяем, что JSON валидный
            try:
                json.loads(cleaned_content)
                print(f"✅ JSON валидный после очистки")
            except json.JSONDecodeError as e:
                print(f"❌ JSON все еще невалидный: {e}")
                # Попробуем более агрессивную очистку
                cleaned_content = re.sub(r'}[^}]*$', '}', content)
                print(f"🚨 DEBUG: Агрессивная очистка: {cleaned_content[:200]}...")
            
            return cleaned_content
            
        except Exception as e:
            print(f"🚨 DEBUG: Исключение в analyze_screenshot: {str(e)}")
            raise Exception(f"Ошибка анализа скриншота: {str(e)}")
    
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
                "parameters": {
                    "temperature": model_config["temperature"],
                    "max_tokens": model_config["max_tokens"],
                    "top_p": model_config.get("top_p", 1),
                    "frequency_penalty": model_config.get("frequency_penalty", 0),
                    "presence_penalty": model_config.get("presence_penalty", 0)
                }
            }
            
            result = self._post_with_retry(url, headers, data, max_retries=3)
            
            # Исправляем согласно документации GigaChat
            if "alternatives" in result:
                content = result["alternatives"][0]["message"]["content"]
            elif "choices" in result:
                content = result["choices"][0]["message"]["content"]
            else:
                raise Exception("Неизвестная структура ответа от GigaChat")
            
            # Очищаем JSON от лишних символов
            import re
            # Убираем все символы после последней закрывающей скобки }
            cleaned_content = re.sub(r'}[^}]*$', '}', content)
            print(f"🚨 DEBUG: Оригинальный ответ: {content[:100]}...")
            print(f"🚨 DEBUG: Очищенный ответ: {cleaned_content[:100]}...")
            
            return cleaned_content
            
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
