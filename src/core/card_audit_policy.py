from __future__ import annotations

from typing import Dict


# Canonical policy for card audit (lead + business snapshots).
# Keep this file as the single place for threshold tuning.
CARD_AUDIT_POLICY: Dict[str, Dict[str, float]] = {
    "weights": {
        "profile": 0.20,
        "reputation": 0.35,
        "services": 0.30,
        "activity": 0.15,
    },
    "health_thresholds": {
        "strong_min": 80.0,
        "growth_min": 55.0,
    },
    "rating": {
        "risk_max": 4.4,
        "target_min": 4.7,
    },
    "reviews": {
        "target_min": 30.0,
    },
    "services": {
        "minimum_visible": 5.0,
    },
    "photos": {
        "good_min": 5.0,
    },
    "activity": {
        "recent_days": 45.0,
    },
    "cadence": {
        "news_posts_per_month_min": 4.0,
        "photos_per_month_min": 8.0,
        "reviews_response_hours_max": 48.0,
    },
    "unanswered_reviews": {
        "high_severity_min": 3.0,
    },
}


def policy_value(section: str, key: str, default: float) -> float:
    section_values = CARD_AUDIT_POLICY.get(section)
    if not isinstance(section_values, dict):
        return default
    raw = section_values.get(key)
    if raw is None:
        return default
    try:
        return float(raw)
    except Exception:
        return default
