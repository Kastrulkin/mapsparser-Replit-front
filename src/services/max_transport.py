"""Bounded MAX Bot API transport. Never retry an uncertain external write."""
from __future__ import annotations

import os
import requests
from services.max_tls import max_ca_file


class MaxTransportError(RuntimeError):
    def __init__(self, code, *, uncertain=False):
        super().__init__(code)
        self.code = code
        self.uncertain = uncertain


class MaxTransport:
    base_url = "https://platform-api2.max.ru"

    def __init__(self, token=None, *, session=None):
        self.token = token or os.getenv("MAX_BOT_TOKEN", "")
        self.session = session or requests.Session()
        self.session.verify = max_ca_file()

    def call(self, method, path, *, params=None, body=None):
        if not self.token:
            raise MaxTransportError("max_not_configured")
        try:
            response = self.session.request(method, self.base_url + path,
                headers={"Authorization": self.token}, params=params, json=body,
                timeout=(5, 20), allow_redirects=False, verify=self.session.verify)
        except requests.RequestException:
            raise MaxTransportError("max_connection_failed", uncertain=method != "GET") from None
        if not 200 <= response.status_code < 300:
            raise MaxTransportError("max_api_rejected", uncertain=(response.status_code >= 500 or response.status_code in {408, 409}) and method != "GET")
        try:
            result = response.json()
        except ValueError:
            raise MaxTransportError("max_invalid_response", uncertain=method != "GET") from None
        if not isinstance(result, dict):
            raise MaxTransportError("max_invalid_response", uncertain=method != "GET")
        if result.get("success") is False or result.get("code") and result.get("message") and not isinstance(result.get("message"), dict):
            raise MaxTransportError("max_api_rejected")
        return result

    def send(self, user_id, text, *, attachments=None, format=None):
        result = self.call("POST", "/messages", params={"user_id": str(user_id)},
                           body={"text": text, "attachments": attachments or [], **({"format": format} if format else {})})
        if not ((result.get('message') or {}).get('body') or {}).get('mid'):
            raise MaxTransportError('max_message_unconfirmed', uncertain=True)
        return result

    def edit(self, message_id, text, *, attachments=None, format=None):
        result = self.call('PUT', '/messages', params={'message_id': message_id},
            body={'text': text, 'attachments': attachments or [], **({'format': format} if format else {})})
        if result.get('success') is not True:
            raise MaxTransportError('max_edit_unconfirmed', uncertain=True)
        return {'message': {'body': {'mid': message_id}}}
