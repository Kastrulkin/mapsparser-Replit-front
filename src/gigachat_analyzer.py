#!/usr/bin/env python3
"""
Анализатор с использованием GigaChat API
"""
import requests
import json
import os
from typing import Dict, Any, List, Tuple
import time
import random

class GigaChatAnalyzer:
    def __init__(self, client_id: str = None, client_secret: str = None):
        """Поддержка одиночного ключа и пула ключей с ротацией.

        Пул можно задать переменной окружения GIGACHAT_KEYS в формате:
        "id1:secret1;id2:secret2;id3:secret3"
        """
        # Загружаем пул ключей из окружения, если переданы неявно
        keys_env = os.getenv("GIGACHAT_KEYS", "").strip()
        self.credentials_pool: List[Tuple[str, str]] = []
        if keys_env:
            try:
                for pair in keys_env.split(";"):
                    pair = pair.strip()
                    if not pair:
                        continue
                    cid, csec = pair.split(":", 1)
                    self.credentials_pool.append((cid.strip(), csec.strip()))
            except Exception:
                # Игнорируем форматные ошибки и fallback к одиночному ключу
                self.credentials_pool = []

        if client_id and client_secret:
            self.credentials_pool.insert(0, (client_id, client_secret))

        # Если ничего не нашли в пуле — пробуем старые переменные окружения
        if not self.credentials_pool:
            env_id = os.getenv('GIGACHAT_CLIENT_ID')
            env_secret = os.getenv('GIGACHAT_CLIENT_SECRET')
            if env_id and env_secret:
                self.credentials_pool = [(env_id, env_secret)]

        self.current_index = 0
        self.base_url = "https://gigachat.devices.sberbank.ru/api/v1"
        ca_bundle = os.getenv("GIGACHAT_CA_BUNDLE") or os.getenv("REQUESTS_CA_BUNDLE")
        if ca_bundle and os.path.exists(ca_bundle):
            self.verify_tls = ca_bundle
        elif os.getenv("GIGACHAT_SSL_VERIFY", "true").lower() == "false":
            self.verify_tls = False
        else:
            self.verify_tls = True
        self.access_token = None
        self.token_expires_at = 0
        self.last_auth_error = None
    
    def _rotate_credentials(self) -> None:
        if not self.credentials_pool:
            return
        self.current_index = (self.current_index + 1) % len(self.credentials_pool)
        # Инвалидируем текущий токен при смене ключа
        self.access_token = None
        self.token_expires_at = 0

    def _get_current_credentials(self) -> Tuple[str, str]:
        if not self.credentials_pool:
            raise RuntimeError("GigaChat credentials are not configured")
        return self.credentials_pool[self.current_index]

    def get_access_token(self) -> str:
        """Получить токен доступа с ротацией ключей и retry."""
        if self.access_token and time.time() < self.token_expires_at:
            return self.access_token

        last_error = None
        attempts = min(3, max(1, len(self.credentials_pool) or 1))
        for attempt in range(attempts):
            client_id, client_secret = self._get_current_credentials()
            url = f"{self.base_url}/oauth"
            data = {"scope": "GIGACHAT_API_PERS"}
            
            # Согласно документации GigaChat: нужно закодировать Client ID:Client Secret в base64
            import base64
            auth_string = f"{client_id}:{client_secret}"
            auth_bytes = auth_string.encode('utf-8')
            auth_base64 = base64.b64encode(auth_bytes).decode('utf-8')
            
            headers = {
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
                "Authorization": f"Basic {auth_base64}"
            }
            try:
                response = requests.post(url, data=data, headers=headers, timeout=30, verify=self.verify_tls)
                if response.status_code in (401, 403):
                    # Неверный/просроченный ключ — пробуем следующий
                    last_error = RuntimeError(f"Auth failed for key index {self.current_index}: {response.status_code}")
                    self._rotate_credentials()
                    continue
                response.raise_for_status()
                token_data = response.json()
                self.access_token = token_data["access_token"]
                # Токен действует 30 минут, обновляем за 5 минут до истечения
                self.token_expires_at = time.time() + (25 * 60)
                print("✅ GigaChat токен получен успешно")
                return self.access_token
            except Exception as e:
                last_error = e
                # Экспоненциальная задержка с джиттером
                time.sleep(0.5 * (2 ** attempt) + random.random() * 0.25)
                # Попробуем другой ключ
                self._rotate_credentials()

        raise RuntimeError(f"Не удалось получить токен GigaChat: {last_error}")
    
    def analyze_business_data(self, card_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Анализирует данные бизнеса с помощью GigaChat
        """
        try:
            # Получаем токен
            token = self.get_access_token()
            
            # Подготавливаем данные для анализа
            analysis_text = self.prepare_data_for_analysis(card_data)
            
            # Формируем промпт для анализа
            prompt = self.create_analysis_prompt(analysis_text, card_data)
            
            # Отправляем запрос к GigaChat
            analysis_result = self.send_analysis_request(prompt, token)
            
            # Парсим результат
            parsed_result = self.parse_analysis_result(analysis_result)
            
            return {
                'analysis': parsed_result,
                'recommendations': parsed_result.get('recommendations', []),
                'score': parsed_result.get('score', 50)
            }
            
        except Exception as e:
            print(f"❌ Ошибка анализа GigaChat: {e}")
            # Возвращаем простой анализ в случае ошибки
            return self.fallback_analysis(card_data)
    
    def prepare_data_for_analysis(self, card_data: Dict[str, Any]) -> str:
        """Подготавливает данные для анализа"""
        text_parts = []
        
        # Основная информация
        if card_data.get('title'):
            text_parts.append(f"Название: {card_data['title']}")
        
        if card_data.get('address'):
            text_parts.append(f"Адрес: {card_data['address']}")
        
        if card_data.get('phone'):
            text_parts.append(f"Телефон: {card_data['phone']}")
        
        if card_data.get('site'):
            text_parts.append(f"Сайт: {card_data['site']}")
        
        if card_data.get('rating'):
            text_parts.append(f"Рейтинг: {card_data['rating']}")
        
        if card_data.get('reviews_count'):
            text_parts.append(f"Количество отзывов: {card_data['reviews_count']}")
        
        if card_data.get('hours'):
            text_parts.append(f"Часы работы: {card_data['hours']}")
        
        # Описание
        if card_data.get('overview'):
            overview = card_data['overview']
            if isinstance(overview, dict) and 'description' in overview:
                text_parts.append(f"Описание: {overview['description']}")
            elif isinstance(overview, str):
                text_parts.append(f"Описание: {overview}")
        
        # Категории
        if card_data.get('categories'):
            categories = card_data['categories']
            if isinstance(categories, list):
                text_parts.append(f"Категории: {', '.join(categories)}")
            elif isinstance(categories, str):
                text_parts.append(f"Категории: {categories}")
        
        # Отзывы (первые 5)
        if card_data.get('reviews') and card_data['reviews'].get('items'):
            reviews = card_data['reviews']['items'][:5]  # Берем первые 5 отзывов
            review_texts = []
            for review in reviews:
                if review.get('text'):
                    review_texts.append(f"Отзыв: {review['text']}")
            if review_texts:
                text_parts.append("Отзывы клиентов:\n" + "\n".join(review_texts))
        
        return "\n".join(text_parts)
    
    def create_analysis_prompt(self, analysis_text: str, card_data: Dict[str, Any]) -> str:
        """Создает промпт для анализа"""
        business_name = card_data.get('title', 'Бизнес')
        
        prompt = f"""
Ты - эксперт по SEO и анализу бизнеса. Проанализируй данные карточки бизнеса "{business_name}" и дай подробную оценку.

Данные для анализа:
{analysis_text}

Пожалуйста, проведи анализ и ответь в следующем JSON формате:
{{
    "score": <число от 0 до 100>,
    "analysis_text": "<подробный анализ на русском языке>",
    "strengths": ["<сильные стороны 1>", "<сильные стороны 2>", ...],
    "weaknesses": ["<слабые стороны 1>", "<слабые стороны 2>", ...],
    "recommendations": ["<рекомендация 1>", "<рекомендация 2>", ...],
    "seo_opportunities": ["<возможность для SEO 1>", "<возможность для SEO 2>", ...]
}}

Критерии оценки:
- Полнота информации (название, адрес, телефон, сайт, часы работы)
- Качество отзывов и рейтинг
- Наличие фотографий и описания
- SEO-оптимизация
- Удобство для клиентов

Дай честную и конструктивную оценку с конкретными рекомендациями по улучшению.
"""
        return prompt
    
    def _post_with_retry(self, url: str, headers: Dict[str, str], json_body: Dict[str, Any], max_retries: int = 3) -> Dict[str, Any]:
        last_error = None
        for attempt in range(max_retries):
            try:
                response = requests.post(url, json=json_body, headers=headers, timeout=60)
                # Если лимиты/авторизация — пробуем ротацию ключа и повтор
                if response.status_code in (401, 403, 429, 503):
                    last_error = RuntimeError(f"HTTP {response.status_code}")
                    # Сменим ключ и обновим токен
                    self._rotate_credentials()
                    self.get_access_token()
                else:
                    response.raise_for_status()
                    return response.json()
            except Exception as e:
                last_error = e
            # Бэк-офф с джиттером
            time.sleep(0.75 * (2 ** attempt) + random.random() * 0.3)
        raise RuntimeError(f"Запрос к GigaChat не удался после повторов: {last_error}")

    def send_analysis_request(self, prompt: str, token: str) -> str:
        """Отправляет запрос к GigaChat с ретраями и ротацией ключей."""
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        data = {
            "model": "GigaChat:latest",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7,
            "max_tokens": 2000
        }
        result = self._post_with_retry(url, headers, data, max_retries=3)
        return result['choices'][0]['message']['content']
    
    def parse_analysis_result(self, analysis_text: str) -> Dict[str, Any]:
        """Парсит результат анализа"""
        try:
            # Ищем JSON в ответе
            start_idx = analysis_text.find('{')
            end_idx = analysis_text.rfind('}') + 1
            
            if start_idx != -1 and end_idx != -1:
                json_str = analysis_text[start_idx:end_idx]
                result = json.loads(json_str)
                
                # Валидируем результат
                if 'score' in result and 'analysis_text' in result:
                    return result
            
            # Если JSON не найден, создаем базовый результат
            return self.create_fallback_result(analysis_text)
            
        except Exception as e:
            print(f"❌ Ошибка парсинга результата: {e}")
            return self.create_fallback_result(analysis_text)
    
    def create_fallback_result(self, analysis_text: str) -> Dict[str, Any]:
        """Создает базовый результат при ошибке парсинга"""
        return {
            "score": 50,
            "analysis_text": analysis_text[:500] + "..." if len(analysis_text) > 500 else analysis_text,
            "strengths": ["Анализ выполнен"],
            "weaknesses": ["Требуется дополнительная информация"],
            "recommendations": ["Обратитесь к специалисту для детального анализа"],
            "seo_opportunities": ["Оптимизируйте карточку бизнеса"]
        }
    
    def fallback_analysis(self, card_data: Dict[str, Any]) -> Dict[str, Any]:
        """Простой анализ при ошибке GigaChat"""
        score = 50
        strengths = []
        weaknesses = []
        recommendations = []
        
        # Простая логика
        if card_data.get('site'):
            strengths.append("Есть сайт")
            score += 10
        else:
            weaknesses.append("Нет сайта")
            recommendations.append("Создайте официальный сайт")
        
        if card_data.get('phone'):
            strengths.append("Есть телефон")
            score += 5
        else:
            weaknesses.append("Нет телефона")
            recommendations.append("Добавьте контактный телефон")
        
        if card_data.get('rating'):
            try:
                rating = float(card_data['rating'])
                if rating >= 4.5:
                    strengths.append("Высокий рейтинг")
                    score += 15
                elif rating < 3.5:
                    weaknesses.append("Низкий рейтинг")
                    recommendations.append("Работайте над качеством услуг")
            except:
                pass
        
        return {
            'analysis': {
                'score': min(100, max(0, score)),
                'analysis_text': f"Простой анализ карточки {card_data.get('title', 'бизнеса')}",
                'strengths': strengths,
                'weaknesses': weaknesses,
                'recommendations': recommendations,
                'seo_opportunities': ["Оптимизируйте SEO"]
            },
            'recommendations': recommendations,
            'score': min(100, max(0, score))
        }
    
    def analyze_with_image(self, prompt: str, image_base64: str) -> str:
        """Анализ изображения с текстовым промптом"""
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
            
            data = {
                "model": "GigaChat-2-Pro",
                "messages": [
                    {
                        "role": "user",
                        "content": message_content
                    }
                ],
                "temperature": 0.1,
                "max_tokens": 4000
            }
            
            response = requests.post(url, headers=headers, json=data, timeout=60)
            response.raise_for_status()
            
            result = response.json()
            return result["choices"][0]["message"]["content"]
            
        except Exception as e:
            print(f"❌ Ошибка анализа изображения: {e}")
            raise
    
    def analyze_text(self, prompt: str) -> str:
        """Анализ текста с промптом"""
        try:
            token = self.get_access_token()
            
            url = f"{self.base_url}/chat/completions"
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
            
            data = {
                "model": "GigaChat-2-Pro",
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "temperature": 0.1,
                "max_tokens": 4000
            }
            
            response = requests.post(url, headers=headers, json=data, timeout=60, verify=self.verify_tls)
            response.raise_for_status()
            
            result = response.json()
            return result["choices"][0]["message"]["content"]
            
        except Exception as e:
            print(f"❌ Ошибка анализа текста: {e}")
            raise

def analyze_business_data(card_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Главная функция для анализа данных бизнеса
    """
    # Получаем ключи из переменных окружения
    client_id = os.getenv('GIGACHAT_CLIENT_ID')
    client_secret = os.getenv('GIGACHAT_CLIENT_SECRET')
    
    if not client_id or not client_secret:
        print("⚠️ GigaChat ключи не найдены, используем простой анализ")
        from simple_ai_analyzer import analyze_business_data as simple_analyze
        return simple_analyze(card_data)
    
    try:
        analyzer = GigaChatAnalyzer(client_id, client_secret)
        return analyzer.analyze_business_data(card_data)
    except Exception as e:
        print(f"❌ Ошибка GigaChat анализа: {e}")
        print("🔄 Переключаемся на простой анализ")
        from simple_ai_analyzer import analyze_business_data as simple_analyze
        return simple_analyze(card_data)

if __name__ == "__main__":
    # Тест анализатора
    test_data = {
        'title': 'Тестовый бизнес',
        'address': 'Тестовый адрес',
        'phone': '+7 (999) 123-45-67',
        'rating': '4.5',
        'reviews_count': '25'
    }
    
    result = analyze_business_data(test_data)
    print("Результат анализа:")
    print(json.dumps(result, ensure_ascii=False, indent=2))
