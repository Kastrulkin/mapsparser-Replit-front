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
import json
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
                
                # Согласно документации GigaChat: нужно закодировать Client ID:Client Secret в base64
                # и передать в заголовке Authorization как Basic Auth
                auth_string = f"{client_id}:{client_secret}"
                auth_bytes = auth_string.encode('utf-8')
                auth_base64 = base64.b64encode(auth_bytes).decode('utf-8')
                
                headers = {
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Accept": "application/json",
                    "RqUID": rquid,
                    "Authorization": f"Basic {auth_base64}"
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
    
    def _post_with_retry(self, url: str, headers: Dict[str, str], json_body: Dict[str, Any], max_retries: int = 3, timeout: int = 60) -> Dict[str, Any]:
        """POST запрос с retry и ротацией ключей"""
        last_error = None
        
        for attempt in range(max_retries):
            try:
                response = requests.post(url, json=json_body, headers=headers, timeout=timeout, verify=self.verify_tls)
                
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
            
            response = requests.post(url, headers=headers, files=files, data=data, verify=False, timeout=120)
            
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

    def analyze_screenshot(self, image_base64: str, prompt: str, task_type: str = None,
                          business_id: str = None, user_id: str = None) -> str:
        """Анализ скриншота карточки
        
        Args:
            image_base64: Base64 изображения
            prompt: Текст промпта
            task_type: Тип задачи для выбора модели (service_optimization, review_reply, 
                      news_generation, ai_agent_marketing, ai_agent_booking, ai_agent_booking_complex)
        """
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
            
            model_config = self.config.get_model_config(task_type=task_type)
            # Для анализа скриншотов увеличиваем max_tokens до максимума (4000)
            # чтобы избежать обрезания JSON при большом количестве услуг
            max_tokens_for_screenshot = min(model_config.get("max_tokens", 4000), 4000)
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
                    "max_tokens": max_tokens_for_screenshot,
                    "frequency_penalty": model_config.get("frequency_penalty", 0),
                    "presence_penalty": model_config.get("presence_penalty", 0)
                }
            }
            
            # Для анализа скриншотов увеличиваем таймаут до 180 секунд (3 минуты)
            result = self._post_with_retry(url, headers, data, max_retries=3, timeout=180)
            print(f"🚨 DEBUG: Полный ответ от GigaChat: {result}")
            
            # Извлекаем usage из ответа
            usage_info = {}
            if "usage" in result:
                usage_info = {
                    "prompt_tokens": result["usage"].get("prompt_tokens", 0),
                    "completion_tokens": result["usage"].get("completion_tokens", 0),
                    "total_tokens": result["usage"].get("total_tokens", 0)
                }
            elif "alternatives" in result and len(result["alternatives"]) > 0:
                if "usage" in result["alternatives"][0]:
                    usage_info = {
                        "prompt_tokens": result["alternatives"][0]["usage"].get("prompt_tokens", 0),
                        "completion_tokens": result["alternatives"][0]["usage"].get("completion_tokens", 0),
                        "total_tokens": result["alternatives"][0]["usage"].get("total_tokens", 0)
                    }
            
            # Сохраняем использование токенов в БД
            if usage_info and (business_id or user_id):
                self._save_token_usage(
                    business_id=business_id,
                    user_id=user_id,
                    task_type=task_type or "service_optimization",
                    model=model_config["model"],
                    usage_info=usage_info,
                    endpoint="chat/completions"
                )
            
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
    
    def analyze_text(self, prompt: str, task_type: str = None, functions: List[Dict] = None, 
                     business_id: str = None, user_id: str = None) -> Tuple[str, Dict[str, Any]]:
        """Анализ текста с поддержкой Function Calling
        
        Args:
            prompt: Текст промпта
            task_type: Тип задачи для выбора модели (service_optimization, review_reply, 
                      news_generation, ai_agent_marketing, ai_agent_booking, ai_agent_booking_complex)
            functions: Список функций для Function Calling (опционально)
            business_id: ID бизнеса для сохранения статистики токенов (опционально)
            user_id: ID пользователя для сохранения статистики токенов (опционально)
        
        Returns:
            Tuple[str, Dict]: (content, usage_info) - содержимое ответа и информация об использовании токенов
        """
        try:
            token = self.get_access_token()
            
            url = f"{self.base_url}/chat/completions"
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
            
            model_config = self.config.get_model_config(task_type=task_type)
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
            
            # Добавляем функции для Function Calling, если они указаны
            if functions:
                data["functions"] = functions
                data["parameters"]["function_call"] = "auto"
            
            result = self._post_with_retry(url, headers, data, max_retries=3)
            
            # Извлекаем usage из ответа
            usage_info = {}
            if "usage" in result:
                usage_info = {
                    "prompt_tokens": result["usage"].get("prompt_tokens", 0),
                    "completion_tokens": result["usage"].get("completion_tokens", 0),
                    "total_tokens": result["usage"].get("total_tokens", 0)
                }
            elif "alternatives" in result and len(result["alternatives"]) > 0:
                if "usage" in result["alternatives"][0]:
                    usage_info = {
                        "prompt_tokens": result["alternatives"][0]["usage"].get("prompt_tokens", 0),
                        "completion_tokens": result["alternatives"][0]["usage"].get("completion_tokens", 0),
                        "total_tokens": result["alternatives"][0]["usage"].get("total_tokens", 0)
                    }
            
            # Сохраняем использование токенов в БД
            if usage_info and (business_id or user_id):
                self._save_token_usage(
                    business_id=business_id,
                    user_id=user_id,
                    task_type=task_type or "unknown",
                    model=model_config["model"],
                    usage_info=usage_info,
                    endpoint="chat/completions"
                )
            
            # Извлекаем содержимое ответа
            if "alternatives" in result:
                message = result["alternatives"][0]["message"]
                content = message.get("content", "")
                
                # Проверяем, есть ли вызов функции
                if "function_call" in message:
                    function_call = message["function_call"]
                    # Возвращаем информацию о вызове функции
                    return json.dumps({
                        "function_call": {
                            "name": function_call.get("name"),
                            "arguments": function_call.get("arguments", {})
                        }
                    }), usage_info
            elif "choices" in result:
                message = result["choices"][0]["message"]
                content = message.get("content", "")
                
                # Проверяем, есть ли вызов функции
                if "function_call" in message:
                    function_call = message["function_call"]
                    return json.dumps({
                        "function_call": {
                            "name": function_call.get("name"),
                            "arguments": function_call.get("arguments", {})
                        }
                    }), usage_info
            else:
                raise Exception("Неизвестная структура ответа от GigaChat")
            
            # Очищаем JSON от лишних символов (для обратной совместимости)
            import re
            cleaned_content = re.sub(r'}[^}]*$', '}', content) if content else ""
            
            return cleaned_content, usage_info
            
        except Exception as e:
            print(f"❌ Ошибка анализа текста: {e}")
            raise
    
    def _save_token_usage(self, business_id: str = None, user_id: str = None, 
                         task_type: str = "unknown", model: str = "unknown",
                         usage_info: Dict[str, Any] = None, endpoint: str = "unknown"):
        """Сохранить информацию об использовании токенов в БД"""
        try:
            import uuid
            from database_manager import DatabaseManager
            
            db = DatabaseManager()
            cursor = db.conn.cursor()
            
            # Проверяем, существует ли таблица (PostgreSQL: to_regclass)
            cursor.execute("SELECT to_regclass('public.tokenusage')")
            reg = cursor.fetchone()
            if not reg or reg[0] is None:
                db.close()
                return  # Таблица еще не создана
            
            usage_id = str(uuid.uuid4())
            cursor.execute("""
                INSERT INTO TokenUsage 
                (id, business_id, user_id, task_type, model, prompt_tokens, completion_tokens, total_tokens, endpoint)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                usage_id,
                business_id,
                user_id,
                task_type,
                model,
                usage_info.get("prompt_tokens", 0),
                usage_info.get("completion_tokens", 0),
                usage_info.get("total_tokens", 0),
                endpoint
            ))
            
            db.conn.commit()
            db.close()
            
        except Exception as e:
            print(f"⚠️ Ошибка сохранения использования токенов: {e}")
            # Не прерываем выполнение, если не удалось сохранить статистику
    
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
            print(f"⚠️ Позиция ошибки: {e.pos}, длина текста: {len(response_text)}")
            
            # Попробуем исправить обрезанный JSON
            try:
                # Если JSON обрезан, попробуем найти последний валидный элемент массива services
                if '"services"' in response_text and '[' in response_text:
                    # Находим начало массива services
                    services_start = response_text.find('"services"')
                    if services_start != -1:
                        array_start = response_text.find('[', services_start)
                        if array_start != -1:
                            # Пытаемся найти последний валидный объект в массиве
                            # Ищем все закрывающие скобки объектов }
                            brace_count = 0
                            last_valid_brace = -1
                            in_string = False
                            escape_next = False
                            
                            for i in range(array_start, len(response_text)):
                                char = response_text[i]
                                if escape_next:
                                    escape_next = False
                                    continue
                                if char == '\\':
                                    escape_next = True
                                    continue
                                if char == '"' and not escape_next:
                                    in_string = not in_string
                                    continue
                                if not in_string:
                                    if char == '{':
                                        brace_count += 1
                                    elif char == '}':
                                        brace_count -= 1
                                        if brace_count == 0:
                                            last_valid_brace = i
                            
                            if last_valid_brace != -1:
                                # Обрезаем до последнего валидного объекта
                                # Находим начало JSON объекта
                                json_start = response_text.find('{')
                                if json_start != -1:
                                    # Берем от начала до последнего валидного объекта
                                    fixed_json = response_text[json_start:last_valid_brace + 1]
                                    # Закрываем массив services и объект
                                    fixed_json += ']}'
                                    
                                    print(f"🔧 Попытка восстановить обрезанный JSON")
                                    print(f"🔧 Длина восстановленного JSON: {len(fixed_json)}")
                                    parsed = json.loads(fixed_json)
                                    services_count = len(parsed.get('services', []))
                                    print(f"✅ JSON успешно восстановлен, услуг: {services_count}")
                                    return parsed
            except Exception as fix_error:
                print(f"⚠️ Не удалось восстановить JSON: {fix_error}")
                import traceback
                traceback.print_exc()
            
            # Попробуем более простой способ - найти все валидные объекты в массиве
            try:
                import re
                # Ищем все объекты вида {"original_name": ..., "optimized_name": ...}
                # Используем регулярное выражение для поиска валидных JSON объектов
                services_pattern = r'\{"original_name"[^}]*"category"[^}]*\}'
                matches = re.findall(services_pattern, response_text)
                
                if matches:
                    # Собираем валидные объекты в массив
                    valid_services = []
                    for match in matches:
                        try:
                            service_obj = json.loads(match)
                            valid_services.append(service_obj)
                        except:
                            continue
                    
                    if valid_services:
                        print(f"🔧 Найдено {len(valid_services)} валидных услуг через regex")
                        return {
                            "services": valid_services,
                            "general_recommendations": []
                        }
            except Exception as regex_error:
                print(f"⚠️ Regex восстановление не удалось: {regex_error}")
            
            # Попробуем стандартную очистку
            try:
                cleaned = response_text.strip()
                if cleaned.startswith('```json'):
                    cleaned = cleaned[7:]
                if cleaned.endswith('```'):
                    cleaned = cleaned[:-3]
                cleaned = cleaned.strip()
                
                return json.loads(cleaned)
            except:
                # Последняя попытка - вернуть то, что удалось распарсить
                return {
                    "error": "Не удалось распарсить JSON. Возможно, ответ был обрезан из-за большого количества услуг. Попробуйте разбить на несколько скриншотов.",
                    "raw_response": response_text[:1000],
                    "note": f"Длина ответа: {len(response_text)} символов, возможно достигнут лимит токенов"
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

# Функции-хелперы для обратной совместимости
def analyze_text_with_gigachat(prompt: str, task_type: str = None, 
                               business_id: str = None, user_id: str = None) -> str:
    """
    Упрощенная функция для анализа текста (обратная совместимость)
    Возвращает только строку, без информации об использовании токенов
    
    Args:
        prompt: Текст промпта
        task_type: Тип задачи для выбора модели
        business_id: ID бизнеса для отслеживания токенов (опционально)
        user_id: ID пользователя для отслеживания токенов (опционально)
    """
    client = get_gigachat_client()
    content, _ = client.analyze_text(
        prompt, 
        task_type=task_type,
        business_id=business_id,
        user_id=user_id
    )
    return content

def analyze_screenshot_with_gigachat(image_base64: str, prompt: str, task_type: str = None,
                                     business_id: str = None, user_id: str = None) -> str:
    """
    Упрощенная функция для анализа скриншота (обратная совместимость)
    Возвращает только строку, без информации об использовании токенов
    
    Args:
        image_base64: Base64 изображения
        prompt: Текст промпта
        task_type: Тип задачи для выбора модели
        business_id: ID бизнеса для отслеживания токенов (опционально)
        user_id: ID пользователя для отслеживания токенов (опционально)
    """
    client = get_gigachat_client()
    return client.analyze_screenshot(
        image_base64, 
        prompt, 
        task_type=task_type,
        business_id=business_id,
        user_id=user_id
    )

