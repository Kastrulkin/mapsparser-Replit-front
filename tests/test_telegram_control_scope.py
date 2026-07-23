import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

from services.operator_scope_summary import format_scope_summary_for_telegram
from services.telegram_control_scope import resolve_control_scope, toggle_favorite_control_scope
from services.telegram_webapp_auth import validate_telegram_webapp_init_data


class ScopeCursor:
    def __init__(self, *, actor, networks=None, businesses=None, locations=None):
        self.actor = actor
        self.networks = networks or []
        self.businesses = businesses or []
        self.locations = locations or {}
        self.rows = []

    def execute(self, query, params=()):
        normalized = " ".join(query.lower().split())
        if "from users" in normalized:
            self.rows = [self.actor] if self.actor else []
        elif "from networks n" in normalized:
            self.rows = self.networks
        elif "select distinct" in normalized and "from businesses b" in normalized:
            self.rows = self.businesses
        elif "count(*) as cnt from businesses" in normalized:
            self.rows = [{"cnt": len(self.businesses)}]
        elif "to_regclass" in normalized:
            self.rows = [{"table_ref": None}]
        elif "select id from businesses" in normalized and "network_id =" in normalized:
            network_id = str(params[0])
            self.rows = [{"id": item} for item in self.locations.get(network_id, [])]
        elif "select id from businesses where id" in normalized:
            requested_id = str(params[0])
            self.rows = [{"id": requested_id}] if any(str(item.get("id")) == requested_id for item in self.businesses) else []
        elif "from businesses b" in normalized and "where b.id" in normalized:
            requested_id = str(params[0])
            self.rows = [item for item in self.businesses if str(item.get("id")) == requested_id]
        else:
            raise AssertionError(f"Unexpected query: {normalized}")

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return list(self.rows)


def test_single_business_owner_gets_business_without_switcher():
    cursor = ScopeCursor(
        actor={"id": "owner-1", "name": "Owner", "is_superadmin": False},
        businesses=[{"id": "biz-1", "name": "One", "address": "", "network_id": None}],
    )

    scope = resolve_control_scope(cursor, user_id="owner-1")

    assert scope["kind"] == "business"
    assert scope["id"] == "biz-1"
    assert scope["can_switch"] is False


def test_network_owner_opens_network_and_can_drill_into_locations():
    cursor = ScopeCursor(
        actor={"id": "owner-2", "name": "Owner", "is_superadmin": False},
        networks=[{"id": "net-1", "name": "Chain", "locations_count": 2}],
        businesses=[
            {"id": "biz-1", "name": "First", "address": "A", "network_id": "net-1", "network_name": "Chain"},
            {"id": "biz-2", "name": "Second", "address": "B", "network_id": "net-1", "network_name": "Chain"},
        ],
        locations={"net-1": ["biz-1", "biz-2"]},
    )

    scope = resolve_control_scope(cursor, user_id="owner-2")

    assert scope["kind"] == "network"
    assert scope["business_ids"] == ["biz-1", "biz-2"]
    assert scope["can_switch"] is True


def test_superadmin_opens_platform_by_default():
    cursor = ScopeCursor(
        actor={"id": "admin", "name": "Admin", "is_superadmin": True},
        networks=[{"id": "net-1", "name": "Chain", "locations_count": 1}],
        businesses=[{"id": "biz-1", "name": "One", "address": "", "network_id": "net-1"}],
    )

    scope = resolve_control_scope(cursor, user_id="admin")

    assert scope["kind"] == "platform"
    assert scope["id"] is None
    assert scope["name"] == "Вся платформа"


def test_telegram_webapp_signature_and_age_are_verified():
    token = "123456:test-token"
    values = {
        "auth_date": str(int(time.time())),
        "query_id": "query-1",
        "user": json.dumps({"id": 123, "first_name": "Alex"}, separators=(",", ":")),
    }
    check_string = "\n".join(f"{key}={values[key]}" for key in sorted(values))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    values["hash"] = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()

    verified = validate_telegram_webapp_init_data(urlencode(values), bot_token=token)

    assert verified["telegram_id"] == "123"
    tampered = urlencode({**values, "query_id": "other"})
    assert validate_telegram_webapp_init_data(tampered, bot_token=token) is None


def test_telegram_summary_names_source_and_freshness_without_technical_stats():
    summary = {
        "scope": {"kind": "business", "name": "Весёлая расчёска"},
        "attention_items": [{"title": "Отзывы без ответа", "count": 50}],
        "metrics": [
            {
                "key": "provider_reviews_total",
                "label": "Отзывов на карте",
                "value": 296,
                "source": "cards.latest",
                "source_label": "Карты",
                "updated_at": "2026-07-23T09:15:00+00:00",
            }
        ],
    }

    rendered = format_scope_summary_for_telegram(summary)

    assert "LocalOS · Весёлая расчёска" in rendered
    assert "Отзывов на карте: 296" in rendered
    assert "23.07 09:15 · Карты" in rendered
    assert "API hits" not in rendered
    assert "User-Agent" not in rendered


def test_current_scope_can_be_added_to_favorites():
    class FavoriteCursor:
        def __init__(self):
            self.rows = []
            self.updated = False

        def execute(self, query, params=()):
            normalized = " ".join(query.lower().split())
            if "to_regclass" in normalized:
                self.rows = [{"table_ref": "telegramcontrolpreferences"}]
            elif "select * from telegramcontrolpreferences" in normalized:
                self.rows = [{
                    "scope_type": "business",
                    "scope_id": "biz-1",
                    "recent_scopes_json": [],
                    "favorite_scopes_json": [],
                    "last_business_by_network_json": {},
                    "notification_preferences_json": {},
                }]
            elif normalized.startswith("insert into telegramcontrolpreferences"):
                self.rows = []
            elif normalized.startswith("update telegramcontrolpreferences"):
                self.updated = True
                self.rows = []
            else:
                raise AssertionError(f"Unexpected query: {normalized}")

        def fetchone(self):
            return self.rows[0] if self.rows else None

    cursor = FavoriteCursor()

    favorite = toggle_favorite_control_scope(
        cursor,
        user_id="owner-1",
        telegram_id="123",
        scope={"kind": "business", "id": "biz-1", "name": "One"},
    )

    assert favorite is True
    assert cursor.updated is True
