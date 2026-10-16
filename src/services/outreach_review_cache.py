"""Short-lived shared results; never an authorization or a dispatch decision."""
from datetime import datetime
from zoneinfo import ZoneInfo
from functools import lru_cache
import hashlib
import json
import os

CACHE_VERSION = 'sales-review-cache-v1'
CACHE_TTL_SECONDS = 3600


def review_cache_key(*, stage, prompt, provenance, business_id, user_id, model_config, code_digest, now=None):
    day = (now or datetime.now(ZoneInfo('Europe/Moscow'))).astimezone(ZoneInfo('Europe/Moscow')).date().isoformat()
    content = {'version': CACHE_VERSION, 'stage': stage, 'day': day, 'prompt': prompt,
               'provenance': provenance, 'business_id': business_id, 'user_id': user_id,
               'model_config': model_config, 'code_digest': code_digest}
    digest = hashlib.sha256(json.dumps(content, ensure_ascii=False, sort_keys=True, default=str, separators=(',', ':')).encode()).hexdigest()
    return 'localos:outreach:review:' + digest


@lru_cache(maxsize=2)
def _client(url):
    import redis
    return redis.Redis.from_url(url, socket_connect_timeout=.2, socket_timeout=.2, decode_responses=True)


def _backend():
    if os.getenv('OUTREACH_REVIEW_CACHE_ENABLED', 'true').lower() not in {'true', '1', 'yes'}:
        return None
    url = os.getenv('OUTREACH_REVIEW_CACHE_REDIS_URL') or os.getenv('RATE_LIMIT_STORAGE_URI') or os.getenv('WEB_TRACKING_METRICS_REDIS_URL', '')
    return _client(url) if url.startswith(('redis://', 'rediss://')) else None


def get_review(key):
    if not key:
        return None
    try:
        backend = _backend()
        raw = backend.get(key) if backend is not None else None
        result = json.loads(raw) if raw else None
        return result if isinstance(result, dict) else None
    except Exception:
        # A cache outage must cause a normal budgeted check, never approval.
        return None


def save_review(key, result):
    if not key:
        return
    try:
        backend = _backend()
        if backend is not None:
            backend.setex(key, CACHE_TTL_SECONDS, json.dumps(result, ensure_ascii=False))
    except Exception:
        pass


def model_configuration(routed):
    from dataclasses import asdict
    from gigachat_config import get_gigachat_config
    from services.llm.registry import get_task_definition, model_for_definition
    tasks = ('outreach_public_copy', 'outreach_language_review') if routed else ('outreach_personalization',)
    return {task: {'definition': asdict(get_task_definition(task)),
                   'model': model_for_definition(get_task_definition(task)),
                   'gigachat': get_gigachat_config().get_model_config(task_type=task)}
            for task in tasks}
