#!/usr/bin/env python3
"""
Клиент для работы с Google Business Profile API
"""
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import AuthorizedSession
from google.auth.transport.requests import Request
from googleapiclient.errors import HttpError
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta


class GoogleBusinessAPIError(RuntimeError):
    """Raised when Google Business Profile API cannot return required data."""


def _http_error_message(error: HttpError) -> str:
    status = getattr(getattr(error, "resp", None), "status", None)
    reason = getattr(getattr(error, "resp", None), "reason", None)
    detail = str(error).strip()
    prefix = f"Google API {status}" if status else "Google API"
    if reason:
        prefix = f"{prefix}: {reason}"
    return f"{prefix}. {detail}" if detail else prefix


class GoogleBusinessAPI:
    def __init__(self, credentials: Credentials):
        self.credentials = credentials
        self.authed_session = AuthorizedSession(credentials)
        self.service = build('mybusinessaccountmanagement', 'v1', credentials=credentials)
        self.locations_service = None
        try:
            self.locations_service = build('mybusiness', 'v4', credentials=credentials)
        except Exception as error:
            print(f"⚠️ Legacy Google My Business v4 service недоступен: {error}")
        try:
            self.business_info_service = build('mybusinessbusinessinformation', 'v1', credentials=credentials)
        except Exception as error:
            print(f"⚠️ Google Business Information service недоступен: {error}")
            self.business_info_service = None
        self.accounts_service = self.service.accounts()

    def _gbp_v4_json(self, method: str, path: str, body: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Call GBP v4 REST endpoints when googleapiclient discovery is unavailable."""
        clean_path = path.lstrip("/")
        url = f"https://mybusiness.googleapis.com/v4/{clean_path}"
        response = self.authed_session.request(method, url, json=body)
        return self._response_json(response)

    def _performance_json(self, method: str, path: str, params: Optional[List[tuple[str, Any]]] = None) -> Dict[str, Any]:
        clean_path = path.lstrip("/")
        url = f"https://businessprofileperformance.googleapis.com/v1/{clean_path}"
        response = self.authed_session.request(method, url, params=params)
        return self._response_json(response)

    def _response_json(self, response) -> Dict[str, Any]:
        if response.status_code >= 400:
            try:
                detail = response.json()
            except Exception:
                detail = response.text
            raise GoogleBusinessAPIError(
                f"Google API {response.status_code}: {response.reason}. {detail}"
            )
        if not response.content:
            return {}
        return response.json()

    def _performance_location_name(self, location_name: str) -> str:
        if "/locations/" in location_name:
            location_id = location_name.rsplit("/locations/", 1)[-1]
            return f"locations/{location_id}"
        return location_name

    def _date_parts(self, value: str) -> Dict[str, int]:
        date_value = datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()
        return {
            "year": date_value.year,
            "month": date_value.month,
            "day": date_value.day,
        }
    
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
            raise GoogleBusinessAPIError(_http_error_message(e)) from e
    
    def list_locations(self, account_name: str) -> List[Dict[str, Any]]:
        """Получить список локаций для аккаунта"""
        business_info_error: GoogleBusinessAPIError | None = None
        try:
            if self.business_info_service:
                response = self.business_info_service.accounts().locations().list(
                    parent=account_name,
                    readMask="name,title,storefrontAddress,categories,metadata,websiteUri"
                ).execute()
                return response.get('locations', [])
        except HttpError as e:
            self._handle_api_error("получения локаций через Business Information API", e)
            business_info_error = GoogleBusinessAPIError(_http_error_message(e))
        if self.locations_service:
            try:
                response = self.locations_service.accounts().locations().list(
                    parent=account_name
                ).execute()
                return response.get('locations', [])
            except HttpError as e:
                self._handle_api_error("получения локаций", e)
                raise business_info_error or GoogleBusinessAPIError(_http_error_message(e)) from e
        if business_info_error:
            raise business_info_error
        raise GoogleBusinessAPIError("Google Business Profile locations API недоступен в текущей конфигурации.")

    def list_accessible_locations(self) -> List[Dict[str, Any]]:
        """Получить все доступные локации во всех аккаунтах пользователя."""
        locations = []
        for account in self.list_accounts():
            account_name = account.get('name')
            if not account_name:
                continue
            for location in self.list_locations(account_name):
                item = dict(location)
                item['accountName'] = account_name
                item['accountDisplayName'] = account.get('accountName') or account.get('name')
                locations.append(item)
        return locations
    
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
        reviews = []
        page_token = None
        if not self.locations_service:
            while True:
                query = f"{location_name}/reviews?pageSize={page_size}"
                if page_token:
                    query = f"{query}&pageToken={page_token}"
                response = self._gbp_v4_json("GET", query)
                reviews.extend(response.get('reviews', []))
                page_token = response.get('nextPageToken')
                if not page_token:
                    break
            return reviews
        try:
            while True:
                request = self.locations_service.accounts().locations().reviews().list(
                    parent=location_name,
                    pageSize=page_size,
                    pageToken=page_token
                )
                response = request.execute()
                reviews.extend(response.get('reviews', []))
                page_token = response.get('nextPageToken')
                if not page_token:
                    break
            return reviews
        except HttpError as e:
            self._handle_api_error("получения отзывов", e)
            return []
    
    def update_review_reply(self, location_name: str, review_id: str, reply_text: str) -> bool:
        """Опубликовать ответ на отзыв"""
        try:
            review_name = review_id if review_id.startswith("accounts/") else f"{location_name}/reviews/{review_id}"
            if not self.locations_service:
                self._gbp_v4_json("PUT", f"{review_name}/reply", {
                    'comment': reply_text
                })
                return True
            self.locations_service.accounts().locations().reviews().updateReply(
                name=review_name,
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
        if not self.locations_service:
            response = self._gbp_v4_json("GET", f"{location_name}/localPosts")
            return response.get('localPosts', [])
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
            if not self.locations_service:
                response = self._gbp_v4_json("POST", f"{location_name}/localPosts", post_data)
                return response.get('name')
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
        performance_metrics = [
            'BUSINESS_IMPRESSIONS_DESKTOP_MAPS',
            'BUSINESS_IMPRESSIONS_DESKTOP_SEARCH',
            'BUSINESS_IMPRESSIONS_MOBILE_MAPS',
            'BUSINESS_IMPRESSIONS_MOBILE_SEARCH',
            'BUSINESS_DIRECTION_REQUESTS',
            'CALL_CLICKS',
            'WEBSITE_CLICKS',
            'BUSINESS_CONVERSATIONS',
            'BUSINESS_BOOKINGS',
        ]
        start_parts = self._date_parts(start_date)
        end_parts = self._date_parts(end_date)
        params: List[tuple[str, Any]] = []
        for metric in performance_metrics:
            params.append(("dailyMetrics", metric))
        for prefix in ("start_date", "end_date"):
            parts = start_parts if prefix == "start_date" else end_parts
            for key, value in parts.items():
                params.append((f"dailyRange.{prefix}.{key}", value))
        performance_location = self._performance_location_name(location_name)
        try:
            return self._performance_json(
                "GET",
                f"{performance_location}:fetchMultiDailyMetricsTimeSeries",
                params=params,
            )
        except GoogleBusinessAPIError:
            camel_params: List[tuple[str, Any]] = []
            for metric in performance_metrics:
                camel_params.append(("dailyMetrics", metric))
            for prefix in ("startDate", "endDate"):
                parts = start_parts if prefix == "startDate" else end_parts
                for key, value in parts.items():
                    camel_params.append((f"dailyRange.{prefix}.{key}", value))
            return self._performance_json(
                "GET",
                f"{performance_location}:fetchMultiDailyMetricsTimeSeries",
                params=camel_params,
            )

    def get_legacy_insights(self, location_name: str, start_date: str, end_date: str) -> Dict[str, Any]:
        """Получить legacy insights, если discovery v4 доступен."""
        metrics = [
            'QUERIES_DIRECT', 'QUERIES_INDIRECT', 'VIEWS_MAPS', 'VIEWS_SEARCH',
            'ACTIONS_WEBSITE', 'ACTIONS_PHONE', 'ACTIONS_DRIVING_DIRECTIONS',
            'PHOTOS_VIEWS_MERCHANT', 'PHOTOS_VIEWS_CUSTOMERS',
            'PHOTOS_COUNT_MERCHANT', 'PHOTOS_COUNT_CUSTOMERS'
        ]
        
        try:
            if not self.locations_service:
                raise GoogleBusinessAPIError("Legacy Google Business Profile insights API is unavailable")
            response = self.locations_service.accounts().locations().reportInsights(
                name=location_name,
                body={
                    'locationNames': [location_name],
                    'basicRequest': {
                        'metricRequests': [
                            {'metric': metric, 'options': ['AGGREGATED_DAILY']}
                            for metric in metrics
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
