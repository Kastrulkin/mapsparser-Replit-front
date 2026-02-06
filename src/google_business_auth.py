#!/usr/bin/env python3
"""
OAuth 2.0 аутентификация для Google Business Profile API
"""
import os
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
from typing import Dict, Any

class GoogleBusinessAuth:
    def __init__(self):
        self.client_id = os.getenv('GOOGLE_CLIENT_ID')
        self.client_secret = os.getenv('GOOGLE_CLIENT_SECRET')
        self.redirect_uri = os.getenv('GOOGLE_REDIRECT_URI', 'http://localhost:8000/api/google/oauth/callback')
        self.scopes = [
            'https://www.googleapis.com/auth/business.manage',
            'https://www.googleapis.com/auth/businessprofileperformance'
        ]
    
    def _create_flow(self) -> Flow:
        """Создать Flow для OAuth (helper метод)"""
        if not self.client_id or not self.client_secret:
            raise ValueError("GOOGLE_CLIENT_ID и GOOGLE_CLIENT_SECRET должны быть установлены")
        
        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [self.redirect_uri]
                }
            },
            scopes=self.scopes
        )
        flow.redirect_uri = self.redirect_uri
        return flow
    
    def get_authorization_url(self, state: str) -> str:
        """Получить URL для авторизации"""
        flow = self._create_flow()
        authorization_url, _ = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            state=state,
            prompt='consent'  # Принудительно запрашиваем refresh token
        )
        return authorization_url
    
    def get_credentials_from_code(self, code: str) -> Credentials:
        """Получить credentials из authorization code"""
        flow = self._create_flow()
        flow.fetch_token(code=code)
        return flow.credentials
    
    def refresh_credentials(self, credentials: Credentials) -> Credentials:
        """Обновить credentials, если они истекли"""
        if credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        return credentials
    
    def credentials_to_dict(self, credentials: Credentials) -> Dict[str, Any]:
        """Преобразовать credentials в словарь для сохранения"""
        return {
            'token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'token_uri': credentials.token_uri,
            'client_id': credentials.client_id,
            'client_secret': credentials.client_secret,
            'scopes': credentials.scopes
        }
    
    def dict_to_credentials(self, creds_dict: Dict[str, Any]) -> Credentials:
        """Восстановить credentials из словаря"""
        return Credentials.from_authorized_user_info(creds_dict, scopes=self.scopes)

