from __future__ import annotations

import os
from typing import Any
from urllib.parse import quote, urlparse


def media_storage_backend() -> str:
    backend = str(os.environ.get("MEDIA_STORAGE_BACKEND") or "local").strip().lower()
    if backend in {"s3", "yandex_object_storage", "object_storage"}:
        return "s3"
    return "local"


def media_upload_root() -> str:
    upload_dir = os.environ.get(
        "MEDIA_UPLOAD_DIR",
        os.path.join(os.environ.get("DEBUG_DIR", "debug_data"), "media_uploads"),
    )
    return os.path.abspath(upload_dir)


def build_media_object_key(*, business_id: str, asset_id: str, variant: str, extension: str) -> str:
    clean_variant = str(variant or "original").strip().strip("/") or "original"
    clean_extension = str(extension or "").strip().lstrip(".").lower()
    stored_name = f"{asset_id}.{clean_extension}" if clean_extension else str(asset_id)
    return f"businesses/{business_id}/media/{clean_variant}/{stored_name}"


def store_media_file(
    *,
    business_id: str,
    asset_id: str,
    variant: str,
    extension: str,
    content: bytes,
    original_name: str,
    mime_type: str,
) -> dict[str, Any]:
    if media_storage_backend() == "s3":
        return _store_media_file_s3(
            business_id=business_id,
            asset_id=asset_id,
            variant=variant,
            extension=extension,
            content=content,
            original_name=original_name,
            mime_type=mime_type,
        )
    return _store_media_file_local(
        business_id=business_id,
        asset_id=asset_id,
        variant=variant,
        extension=extension,
        content=content,
        mime_type=mime_type,
    )


def load_media_file(storage_path: str) -> bytes | None:
    clean_path = str(storage_path or "").strip()
    if not clean_path:
        return None
    if clean_path.startswith("s3://"):
        return _load_media_file_s3(clean_path)
    return _load_media_file_local(clean_path)


def _store_media_file_local(
    *,
    business_id: str,
    asset_id: str,
    variant: str,
    extension: str,
    content: bytes,
    mime_type: str,
) -> dict[str, Any]:
    relative_key = build_media_object_key(
        business_id=business_id,
        asset_id=asset_id,
        variant=variant,
        extension=extension,
    )
    storage_path = os.path.join(media_upload_root(), relative_key)
    os.makedirs(os.path.dirname(storage_path), exist_ok=True)
    file_handle = open(storage_path, "wb")
    try:
        file_handle.write(content)
    finally:
        file_handle.close()
    return {
        "backend": "local",
        "storage_key": relative_key,
        "storage_path": storage_path,
        "mime_type": mime_type or "application/octet-stream",
        "size_bytes": len(content),
    }


def _load_media_file_local(storage_path: str) -> bytes | None:
    absolute_path = os.path.abspath(storage_path)
    upload_root = media_upload_root()
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


def _store_media_file_s3(
    *,
    business_id: str,
    asset_id: str,
    variant: str,
    extension: str,
    content: bytes,
    original_name: str,
    mime_type: str,
) -> dict[str, Any]:
    bucket = _required_env("MEDIA_S3_BUCKET")
    prefix = str(os.environ.get("MEDIA_S3_PREFIX") or "localos-media").strip().strip("/")
    relative_key = build_media_object_key(
        business_id=business_id,
        asset_id=asset_id,
        variant=variant,
        extension=extension,
    )
    key = "/".join(part for part in [prefix, relative_key] if part)
    client = _s3_client()
    client.put_object(
        Bucket=bucket,
        Key=key,
        Body=content,
        ContentType=mime_type or "application/octet-stream",
        Metadata={"original-name": _metadata_safe_value(original_name)},
    )
    return {
        "backend": "s3",
        "storage_key": key,
        "storage_path": f"s3://{bucket}/{key}",
        "public_url": _public_s3_url(bucket=bucket, key=key),
        "mime_type": mime_type or "application/octet-stream",
        "size_bytes": len(content),
    }


def _load_media_file_s3(storage_path: str) -> bytes | None:
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
        raise RuntimeError("boto3 is required for MEDIA_STORAGE_BACKEND=s3")

    endpoint_url = os.environ.get("MEDIA_S3_ENDPOINT_URL") or "https://storage.yandexcloud.net"
    region_name = os.environ.get("MEDIA_S3_REGION") or None
    access_key = os.environ.get("MEDIA_S3_ACCESS_KEY_ID") or os.environ.get("AWS_ACCESS_KEY_ID")
    secret_key = os.environ.get("MEDIA_S3_SECRET_ACCESS_KEY") or os.environ.get("AWS_SECRET_ACCESS_KEY")
    if not access_key or not secret_key:
        raise RuntimeError("MEDIA_S3_ACCESS_KEY_ID and MEDIA_S3_SECRET_ACCESS_KEY are required")
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
    base_url = str(os.environ.get("MEDIA_S3_PUBLIC_BASE_URL") or "").strip().rstrip("/")
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
