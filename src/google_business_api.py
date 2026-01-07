#!/usr/bin/env python3
"""
Клиент для работы с Google Business Profile API
"""
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.errors import HttpError
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

class GoogleBusinessAPI:
    def __init__(self, credentials: Credentials):
        self.service = build('mybusinessaccountmanagement', 'v1', credentials=credentials)
        self.locations_service = build('mybusiness', 'v4', credentials=credentials)
        self.accounts_service = self.service.accounts()
    
    def _handle_api_error(self, operation: str, error: HttpError) -> None:
        """Обработка ошибок API (helper метод)"""
        print(f"❌ Ошибка {operation}: {error}")
    
    def list_accounts(self) -> List[Dict[str, Any]]:
        """Получить список аккаунтов"""
        try:
            response = self.accounts_service.list().execute()
            return response.get('accounts', [])
        except HttpError as e:
            self._handle_api_error("получения аккаунтов", e)
            return []
    
    def list_locations(self, account_name: str) -> List[Dict[str, Any]]:
        """Получить список локаций для аккаунта"""
        try:
            response = self.locations_service.accounts().locations().list(
                parent=account_name
            ).execute()
            return response.get('locations', [])
        except HttpError as e:
            self._handle_api_error("получения локаций", e)
            return []
    
    def get_location(self, location_name: str) -> Optional[Dict[str, Any]]:
        """Получить информацию о локации"""
        try:
            return self.locations_service.accounts().locations().get(
                name=location_name
            ).execute()
        except HttpError as e:
            self._handle_api_error("получения локации", e)
            return None
    
    def list_reviews(self, location_name: str, page_size: int = 50) -> List[Dict[str, Any]]:
        """Получить отзывы для локации"""
        try:
            response = self.locations_service.accounts().locations().reviews().list(
                parent=location_name,
                pageSize=page_size
            ).execute()
            return response.get('reviews', [])
        except HttpError as e:
            self._handle_api_error("получения отзывов", e)
            return []
    
    def update_review_reply(self, location_name: str, review_id: str, reply_text: str) -> bool:
        """Опубликовать ответ на отзыв"""
        try:
            self.locations_service.accounts().locations().reviews().updateReply(
                name=f"{location_name}/reviews/{review_id}",
                body={
                    'reply': {
                        'comment': reply_text
                    }
                }
            ).execute()
            return True
        except HttpError as e:
            self._handle_api_error("публикации ответа", e)
            return False
    
    def list_local_posts(self, location_name: str) -> List[Dict[str, Any]]:
        """Получить посты/публикации для локации"""
        try:
            response = self.locations_service.accounts().locations().localPosts().list(
                parent=location_name
            ).execute()
            return response.get('localPosts', [])
        except HttpError as e:
            self._handle_api_error("получения постов", e)
            return []
    
    def create_local_post(self, location_name: str, post_data: Dict[str, Any]) -> Optional[str]:
        """Создать пост/публикацию"""
        try:
            response = self.locations_service.accounts().locations().localPosts().create(
                parent=location_name,
                body=post_data
            ).execute()
            return response.get('name')
        except HttpError as e:
            self._handle_api_error("создания поста", e)
            return None
    
    def get_insights(self, location_name: str, start_date: str, end_date: str) -> Dict[str, Any]:
        """Получить статистику (insights) для локации"""
        # Метрики для запроса статистики
        METRICS = [
            'QUERIES_DIRECT', 'QUERIES_INDIRECT', 'VIEWS_MAPS', 'VIEWS_SEARCH',
            'ACTIONS_WEBSITE', 'ACTIONS_PHONE', 'ACTIONS_DRIVING_DIRECTIONS',
            'PHOTOS_VIEWS_MERCHANT', 'PHOTOS_VIEWS_CUSTOMERS',
            'PHOTOS_COUNT_MERCHANT', 'PHOTOS_COUNT_CUSTOMERS'
        ]
        
        try:
            response = self.locations_service.accounts().locations().reportInsights(
                name=location_name,
                body={
                    'locationNames': [location_name],
                    'basicRequest': {
                        'metricRequests': [
                            {'metric': metric, 'options': ['AGGREGATED_DAILY']}
                            for metric in METRICS
                        ],
                        'timeRange': {
                            'startTime': start_date,
                            'endTime': end_date
                        }
                    }
                }
            ).execute()
            return response
        except HttpError as e:
            self._handle_api_error("получения статистики", e)
            return {}

