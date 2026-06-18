from __future__ import annotations

import os
from typing import Any
from urllib.parse import quote, urlparse


def sales_room_storage_backend() -> str:
    backend = str(os.environ.get("SALES_ROOM_STORAGE_BACKEND") or "local").strip().lower()
    if backend in {"s3", "yandex_object_storage", "object_storage"}:
        return "s3"
    return "local"


def sales_room_upload_root() -> str:
    upload_dir = os.environ.get(
        "SALES_ROOM_UPLOAD_DIR",
        os.path.join(os.environ.get("DEBUG_DIR", "debug_data"), "sales_room_uploads"),
    )
    return os.path.abspath(upload_dir)


def store_sales_room_file(
    *,
    room_id: str,
    file_id: str,
    extension: str,
    content: bytes,
    original_name: str,
    mime_type: str,
) -> dict[str, Any]:
    if sales_room_storage_backend() == "s3":
        return _store_sales_room_file_s3(
            room_id=room_id,
            file_id=file_id,
            extension=extension,
            content=content,
            original_name=original_name,
            mime_type=mime_type,
        )
    return _store_sales_room_file_local(
        room_id=room_id,
        file_id=file_id,
        extension=extension,
        content=content,
    )


def load_sales_room_file(storage_path: str) -> bytes | None:
    clean_path = str(storage_path or "").strip()
    if not clean_path:
        return None
    if clean_path.startswith("s3://"):
        return _load_sales_room_file_s3(clean_path)
    return _load_sales_room_file_local(clean_path)


def _store_sales_room_file_local(*, room_id: str, file_id: str, extension: str, content: bytes) -> dict[str, Any]:
    storage_dir = os.path.join(sales_room_upload_root(), str(room_id))
    os.makedirs(storage_dir, exist_ok=True)
    stored_name = f"{file_id}.{extension}" if extension else file_id
    storage_path = os.path.join(storage_dir, stored_name)
    file_handle = open(storage_path, "wb")
    try:
        file_handle.write(content)
    finally:
        file_handle.close()
    return {
        "backend": "local",
        "storage_path": storage_path,
    }


def _load_sales_room_file_local(storage_path: str) -> bytes | None:
    absolute_path = os.path.abspath(storage_path)
    upload_root = sales_room_upload_root()
    try:
        if os.path.commonpath([upload_root, absolute_path]) != upload_root:
            return None
    except ValueError:
        return None
    if not os.path.exists(absolute_path) or not os.path.isfile(absolute_path):
        return None
    file_handle = open(absolute_path, "rb")
    try:
        return file_handle.read()
    finally:
        file_handle.close()


def _store_sales_room_file_s3(
    *,
    room_id: str,
    file_id: str,
    extension: str,
    content: bytes,
    original_name: str,
    mime_type: str,
) -> dict[str, Any]:
    bucket = _required_env("SALES_ROOM_S3_BUCKET")
    prefix = str(os.environ.get("SALES_ROOM_S3_PREFIX") or "sales-room-files").strip().strip("/")
    stored_name = f"{file_id}.{extension}" if extension else file_id
    key_parts = [part for part in [prefix, str(room_id), stored_name] if part]
    key = "/".join(key_parts)
    client = _s3_client()
    put_kwargs: dict[str, Any] = {
        "Bucket": bucket,
        "Key": key,
        "Body": content,
        "ContentType": mime_type or "application/octet-stream",
        "Metadata": {
            "original-name": _metadata_safe_value(original_name),
        },
    }
    client.put_object(**put_kwargs)
    return {
        "backend": "s3",
        "storage_path": f"s3://{bucket}/{key}",
        "public_url": _public_s3_url(bucket=bucket, key=key),
    }


def _load_sales_room_file_s3(storage_path: str) -> bytes | None:
    parsed = urlparse(storage_path)
    bucket = parsed.netloc
    key = parsed.path.lstrip("/")
    if not bucket or not key:
        return None
    client = _s3_client()
    response = client.get_object(Bucket=bucket, Key=key)
    body = response.get("Body")
    if body is None:
        return None
    return body.read()


def _s3_client() -> Any:
    try:
        import boto3
    except ImportError:
        raise RuntimeError("boto3 is required for SALES_ROOM_STORAGE_BACKEND=s3")

    endpoint_url = os.environ.get("SALES_ROOM_S3_ENDPOINT_URL") or "https://storage.yandexcloud.net"
    region_name = os.environ.get("SALES_ROOM_S3_REGION") or "ru-central1"
    access_key = os.environ.get("SALES_ROOM_S3_ACCESS_KEY_ID") or os.environ.get("AWS_ACCESS_KEY_ID")
    secret_key = os.environ.get("SALES_ROOM_S3_SECRET_ACCESS_KEY") or os.environ.get("AWS_SECRET_ACCESS_KEY")
    if not access_key or not secret_key:
        raise RuntimeError("SALES_ROOM_S3_ACCESS_KEY_ID and SALES_ROOM_S3_SECRET_ACCESS_KEY are required")
    return boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        region_name=region_name,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
    )


def _required_env(name: str) -> str:
    value = str(os.environ.get(name) or "").strip()
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


def _public_s3_url(*, bucket: str, key: str) -> str:
    base_url = str(os.environ.get("SALES_ROOM_S3_PUBLIC_BASE_URL") or "").strip().rstrip("/")
    if not base_url:
        return ""
    encoded_key = "/".join(quote(part) for part in key.split("/"))
    return f"{base_url}/{encoded_key}"


def _metadata_safe_value(value: str) -> str:
    clean = str(value or "").strip()
    try:
        clean.encode("ascii")
        return clean[:240]
    except UnicodeEncodeError:
        return quote(clean[:180])
