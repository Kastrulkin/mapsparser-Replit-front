from __future__ import annotations

from decimal import Decimal
from typing import Any


TARIFFS: dict[str, dict[str, Any]] = {
    "starter_monthly": {
        "amount": Decimal("1200.00"),
        "currency": "RUB",
        "credits": 240,
        "business_tier": "starter",
    },
    "pro_monthly": {
        "amount": Decimal("5000.00"),
        "currency": "RUB",
        "credits": 1000,
        "business_tier": "professional",
    },
    "concierge_monthly": {
        "amount": Decimal("25000.00"),
        "currency": "RUB",
        "credits": None,
        "business_tier": "concierge",
    },
}


TARIFF_ALIASES: dict[str, str] = {
    "starter": "starter_monthly",
    "professional": "pro_monthly",
    "pro": "pro_monthly",
    "concierge": "concierge_monthly",
}
