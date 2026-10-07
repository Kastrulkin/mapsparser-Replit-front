"""Best-effort shared ingestion counters backed by Redis minute buckets."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from functools import lru_cache
import logging
import os
import re
import time

try:
    import redis
except ImportError:  # Telemetry must not make the application unavailable.
    redis = None


logger = logging.getLogger(__name__)
LATENCY_BUCKETS_MS = (25, 50, 100, 250, 500, 1000, 2500)
METRICS_TTL_SECONDS = 48 * 60 * 60
_last_warning_at = 0.0


def _redis_url() -> str:
    configured = os.getenv("WEB_TRACKING_METRICS_REDIS_URL", "").strip()
    if configured:
        return configured
    shared = os.getenv("RATE_LIMIT_STORAGE_URI", "").strip()
    return shared if shared.startswith(("redis://", "rediss://")) else ""


@lru_cache(maxsize=2)
def _redis_client(url: str):
    if not url or redis is None:
        return None
    return redis.Redis.from_url(url, socket_connect_timeout=0.2, socket_timeout=0.2, decode_responses=True)


def _minute_key(value: datetime) -> str:
    configured = os.getenv("WEB_TRACKING_METRICS_PREFIX", "localos:web_tracking:ingestion")
    prefix = re.sub(r"[^A-Za-z0-9:_-]+", "_", configured.strip())[:120]
    return f"{prefix or 'localos:web_tracking:ingestion'}:{value.astimezone(timezone.utc):%Y%m%d%H%M}"


def _safe_outcome(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9_]+", "_", str(value or "unknown").strip().lower())
    return normalized[:64] or "unknown"


def _warn_unavailable() -> None:
    global _last_warning_at
    now = time.monotonic()
    if now - _last_warning_at >= 60:
        _last_warning_at = now
        logger.warning("web tracking shared ingestion metrics unavailable")


def record_ingestion_metrics(
    *,
    status: int,
    outcome: str,
    latency_ms: float,
    received: int = 0,
    accepted: int = 0,
    duplicates: int = 0,
    now: datetime | None = None,
    client=None,
) -> None:
    """Record one response without ever affecting the ingestion response path."""
    try:
        target = client if client is not None else _redis_client(_redis_url())
        if target is None:
            return
        timestamp = now or datetime.now(timezone.utc)
        key = _minute_key(timestamp)
        latency_bucket = next((value for value in LATENCY_BUCKETS_MS if latency_ms <= value), "inf")
        response_class = f"responses_{max(0, min(9, int(status) // 100))}xx"
        increments = {
            "requests": 1,
            "events_received": max(0, int(received or 0)),
            "accepted": max(0, int(accepted or 0)),
            "duplicates": max(0, int(duplicates or 0)),
            "rejected_requests": 1 if status >= 400 else 0,
            response_class: 1,
            f"status_{int(status)}": 1,
            f"outcome_{_safe_outcome(outcome)}": 1,
            f"latency_le_{latency_bucket}": 1,
        }
        pipeline = target.pipeline(transaction=False)
        for field, amount in increments.items():
            if amount:
                pipeline.hincrby(key, field, amount)
        pipeline.expire(key, METRICS_TTL_SECONDS)
        pipeline.execute()
    except Exception:
        _warn_unavailable()


def _percentile(histogram: dict[str, int], percentile: float) -> int | None:
    total = sum(histogram.values())
    if not total:
        return None
    target = max(1, int(total * percentile + 0.999999))
    cumulative = 0
    for label in [str(value) for value in LATENCY_BUCKETS_MS] + ["inf"]:
        cumulative += histogram.get(label, 0)
        if cumulative >= target:
            return LATENCY_BUCKETS_MS[-1] + 1 if label == "inf" else int(label)
    return None


def get_ingestion_metrics(*, minutes: int = 60, now: datetime | None = None, client=None) -> dict:
    window_minutes = max(1, min(int(minutes), 180))
    empty = {
        "available": False,
        "window_minutes": window_minutes,
        "requests": 0,
        "events_received": 0,
        "accepted": 0,
        "duplicates": 0,
        "rejected_requests": 0,
        "responses_2xx": 0,
        "responses_4xx": 0,
        "responses_5xx": 0,
        "p50_ms": None,
        "p95_ms": None,
        "p99_ms": None,
    }
    try:
        target = client if client is not None else _redis_client(_redis_url())
        if target is None:
            return empty
        timestamp = (now or datetime.now(timezone.utc)).replace(second=0, microsecond=0)
        keys = [_minute_key(timestamp - timedelta(minutes=offset)) for offset in range(window_minutes)]
        pipeline = target.pipeline(transaction=False)
        for key in keys:
            pipeline.hgetall(key)
        rows = pipeline.execute()
        totals: dict[str, int] = {}
        for row in rows:
            for field, value in (row or {}).items():
                totals[field] = totals.get(field, 0) + int(value or 0)
        histogram = {
            label: totals.get(f"latency_le_{label}", 0)
            for label in [str(value) for value in LATENCY_BUCKETS_MS] + ["inf"]
        }
        return {
            **empty,
            "available": True,
            **{field: totals.get(field, 0) for field in (
                "requests",
                "events_received",
                "accepted",
                "duplicates",
                "rejected_requests",
                "responses_2xx",
                "responses_4xx",
                "responses_5xx",
            )},
            "p50_ms": _percentile(histogram, 0.50),
            "p95_ms": _percentile(histogram, 0.95),
            "p99_ms": _percentile(histogram, 0.99),
        }
    except Exception:
        _warn_unavailable()
        return empty
