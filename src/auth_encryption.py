#!/usr/bin/env python3
"""
Утилиты для безопасного шифрования/расшифровки auth_data для внешних источников
(Яндекс.Бизнес, Google Business, 2ГИС).

Использует Fernet (symmetric encryption) из библиотеки cryptography.
Если библиотека не установлена, использует base64 (только для dev, небезопасно).
"""

import os
import base64
from typing import Optional

# Пытаемся импортировать cryptography
try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    CRYPTOGRAPHY_AVAILABLE = True
except ImportError:
    CRYPTOGRAPHY_AVAILABLE = False
    print("⚠️ Модуль cryptography не установлен. Используется base64 (небезопасно для продакшена).")
    print("   Для продакшена установите: pip install cryptography")


def _get_encryption_key() -> bytes:
    """
    Получить ключ шифрования из переменной окружения или сгенерировать его.
    
    Для продакшена обязательно установите EXTERNAL_AUTH_SECRET_KEY в .env
    """
    secret_key = os.getenv("EXTERNAL_AUTH_SECRET_KEY", "").strip()
    
    if not secret_key:
        # Для dev: генерируем ключ из фиксированной строки (НЕБЕЗОПАСНО для продакшена!)
        print("⚠️ EXTERNAL_AUTH_SECRET_KEY не установлен. Используется dev-ключ (небезопасно).")
        secret_key = "dev_secret_key_change_in_production"
    
    if CRYPTOGRAPHY_AVAILABLE:
        # Используем PBKDF2 для генерации ключа из секрета
        salt = b"local_external_auth_salt"  # В продакшене лучше использовать случайную соль
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(secret_key.encode()))
        return key
    else:
        # Fallback: просто base64 encode секрета (небезопасно!)
        return base64.urlsafe_b64encode(secret_key.encode()[:32].ljust(32, b'0'))


def encrypt_auth_data(plain_text: str) -> str:
    """
    Зашифровать auth_data (cookie, token и т.д.) для хранения в БД.
    
    Args:
        plain_text: Исходный текст (JSON строка с cookies/token)
    
    Returns:
        Зашифрованная строка (base64)
    """
    if not plain_text:
        return ""
    
    try:
        if CRYPTOGRAPHY_AVAILABLE:
            key = _get_encryption_key()
            fernet = Fernet(key)
            encrypted = fernet.encrypt(plain_text.encode())
            return base64.urlsafe_b64encode(encrypted).decode()
        else:
            # Fallback: просто base64 (небезопасно!)
            return base64.b64encode(plain_text.encode()).decode()
    except Exception as e:
        print(f"❌ Ошибка шифрования auth_data: {e}")
        raise


def decrypt_auth_data(encrypted_text: str) -> Optional[str]:
    """
    Расшифровать auth_data из БД.
    
    Args:
        encrypted_text: Зашифрованная строка из БД
    
    Returns:
        Расшифрованный текст или None при ошибке
    """
    if not encrypted_text:
        return None
    
    try:
        if CRYPTOGRAPHY_AVAILABLE:
            key = _get_encryption_key()
            fernet = Fernet(key)
            encrypted_bytes = base64.urlsafe_b64decode(encrypted_text.encode())
            decrypted = fernet.decrypt(encrypted_bytes)
            return decrypted.decode()
        else:
            # Fallback: просто base64 decode
            return base64.b64decode(encrypted_text.encode()).decode()
    except base64.binascii.Error as e:
        print(f"❌ Ошибка base64 декодирования: {e}")
        print(f"   Возможно, данные не зашифрованы или в другом формате")
        return None
    except Exception as e:
        print(f"❌ Ошибка расшифровки auth_data: {type(e).__name__}: {e}")
        import traceback
        if os.getenv("DEBUG_AUTH_DECRYPT", "0") == "1":
            traceback.print_exc()
        return None

