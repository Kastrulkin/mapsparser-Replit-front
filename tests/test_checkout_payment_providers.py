from types import SimpleNamespace

import main
from src import crypto_pay_client, stripe_integration, yookassa_integration


def test_normalize_checkout_provider_maps_russia_to_yookassa() -> None:
    assert yookassa_integration._normalize_checkout_provider("russia") == "yookassa"
    assert yookassa_integration._normalize_checkout_provider("yookassa") == "yookassa"
    assert yookassa_integration._normalize_checkout_provider("stripe") == "stripe"


def test_resolve_checkout_amount_and_currency_uses_usd_for_stripe(monkeypatch) -> None:
    monkeypatch.setattr(
        stripe_integration,
        "_normalize_checkout_tariff_for_stripe",
        lambda tariff_id: "professional",
    )

    amount, currency = yookassa_integration._resolve_checkout_amount_and_currency("stripe", "pro_monthly")

    assert str(amount) == "55"
    assert currency == "USD"


def test_create_crypto_invoice_for_checkout_session_stores_checkout_session(monkeypatch) -> None:
    created = {}
    updated = {}

    class _FakeClient:
        def configured(self) -> bool:
            return True

        def create_invoice(self, payload):
            created["payload"] = payload
            return {"invoice_id": "inv-1", "status": "active", "bot_invoice_url": "https://t.me/invoice/1"}

    monkeypatch.setattr(crypto_pay_client, "CryptoPayClient", _FakeClient)
    monkeypatch.setattr(
        crypto_pay_client,
        "create_checkout_session",
        lambda **kwargs: {"id": "checkout-1", **kwargs},
    )
    monkeypatch.setattr(
        crypto_pay_client,
        "mark_checkout_created",
        lambda session_id, **kwargs: updated.update({"session_id": session_id, **kwargs}) or {"id": session_id},
    )

    invoice = crypto_pay_client.create_crypto_invoice_for_checkout_session(
        tariff_id="starter",
        source="telegram_guest_checkout",
        telegram_id="123",
        telegram_name="Demo User",
        audit_public_url="https://localos.pro/capri",
    )

    assert invoice["checkout_session_id"] == "checkout-1"
    assert created["payload"]["fiat"] == "RUB"
    assert updated["session_id"] == "checkout-1"
    assert updated["provider_invoice_id"] == "inv-1"


def test_create_stripe_checkout_for_checkout_session_uses_checkout_metadata(monkeypatch) -> None:
    created = {}
    marked = {}

    monkeypatch.setattr(stripe_integration, "STRIPE_SECRET_KEY", "sk_test")
    monkeypatch.setattr(
        stripe_integration,
        "load_checkout_session",
        lambda session_id: {
            "id": session_id,
            "tariff_id": "pro_monthly",
            "entry_point": "pricing_page",
            "email": "owner@example.com",
        },
    )
    monkeypatch.setattr(
        stripe_integration,
        "mark_checkout_created",
        lambda session_id, **kwargs: marked.update({"session_id": session_id, **kwargs}) or {"id": session_id},
    )

    class _FakeStripeSessionApi:
        @staticmethod
        def create(**kwargs):
            created.update(kwargs)
            return SimpleNamespace(
                id="cs_test_1",
                url="https://stripe.test/checkout",
                status="open",
                payment_status="unpaid",
            )

    fake_stripe = SimpleNamespace(checkout=SimpleNamespace(Session=_FakeStripeSessionApi))
    monkeypatch.setattr(stripe_integration, "stripe", fake_stripe)

    result = stripe_integration.create_stripe_checkout_for_checkout_session("checkout-42")

    assert result["checkout_id"] == "cs_test_1"
    assert created["metadata"]["checkout_session_id"] == "checkout-42"
    assert created["customer_email"] == "owner@example.com"
    assert marked["provider_invoice_id"] == "cs_test_1"


def test_yookassa_checkout_falls_back_to_onetime_when_recurring_not_allowed(monkeypatch) -> None:
    calls = []
    marked = {}

    monkeypatch.setattr(
        yookassa_integration,
        "load_checkout_session",
        lambda session_id: {
            "id": session_id,
            "tariff_id": "starter_monthly",
            "entry_point": "registered_paywall",
            "business_id": "biz-1",
        },
    )
    monkeypatch.setattr(
        yookassa_integration,
        "mark_checkout_created",
        lambda session_id, **kwargs: marked.update({"session_id": session_id, **kwargs}) or {"id": session_id},
    )

    class _FakeYooKassaClient:
        def configured(self) -> bool:
            return True

        def create_payment(self, *, payload, idempotency_key):
            calls.append({"payload": payload, "idempotency_key": idempotency_key})
            if len(calls) == 1:
                raise RuntimeError("YooKassa API 403: {'type': 'error', 'code': 'forbidden', 'description': \"This store can't make recurring payments.\"}")
            return {
                "id": "pay-onetime",
                "status": "pending",
                "confirmation": {"confirmation_url": "https://yookassa.test/pay"},
            }

    monkeypatch.setattr(yookassa_integration, "YooKassaClient", _FakeYooKassaClient)

    result = yookassa_integration.create_yookassa_payment_for_checkout_session("checkout-1")

    assert len(calls) == 2
    assert calls[0]["payload"]["save_payment_method"] is True
    assert "save_payment_method" not in calls[1]["payload"]
    assert calls[1]["payload"]["metadata"]["autopay_unavailable_reason"] == "yookassa_recurring_not_enabled"
    assert result["payment_id"] == "pay-onetime"
    assert result["confirmation_url"] == "https://yookassa.test/pay"
    assert result["autopay_requested"] is False
    assert marked["provider_invoice_id"] == "pay-onetime"


def test_subscription_public_payload_exposes_autopay_flags() -> None:
    payload = yookassa_integration._subscription_public_payload(
        {
            "id": "sub-1",
            "tariff_id": "starter_monthly",
            "pending_tariff_id": None,
            "status": "active",
            "period_start": None,
            "next_billing_date": None,
            "retry_count": 0,
            "next_retry_at": None,
            "last_payment_id": "pay-1",
            "business_id": "biz-1",
            "payment_method_id": "pm-1",
        }
    )

    assert payload["autopay_enabled"] is True
    assert payload["payment_method_linked"] is True
    assert payload["payment_method_summary"] is None


def test_blocked_subscription_with_saved_card_does_not_show_autopay_enabled() -> None:
    payload = yookassa_integration._subscription_public_payload(
        {
            "id": "sub-1",
            "tariff_id": "starter_monthly",
            "pending_tariff_id": None,
            "status": "blocked",
            "period_start": None,
            "next_billing_date": "2026-04-05T15:38:45+00:00",
            "retry_count": 2,
            "next_retry_at": "2026-03-07T21:06:33+00:00",
            "last_payment_id": "pay-1",
            "business_id": "biz-1",
            "payment_method_id": "pm-1",
        }
    )

    assert payload["payment_method_linked"] is True
    assert payload["autopay_enabled"] is False


def test_subscription_renewal_state_reports_missing_payment_method() -> None:
    renewal_state = yookassa_integration._subscription_renewal_state(
        {
            "status": "active",
            "payment_method_id": None,
            "next_billing_date": "2026-07-10T12:00:00+00:00",
            "next_retry_at": None,
        }
    )

    assert renewal_state["state"] == "needs_payment_method"
    assert renewal_state["reason"] == "missing_payment_method_id"


def test_subscription_renewal_state_reports_retry_pending() -> None:
    renewal_state = yookassa_integration._subscription_renewal_state(
        {
            "status": "blocked",
            "payment_method_id": "pm-1",
            "next_billing_date": None,
            "next_retry_at": "2026-07-11T09:30:00+00:00",
        }
    )

    assert renewal_state["state"] == "retry_pending"
    assert renewal_state["reason"] == "retry_scheduled"


def test_billing_routes_expose_payment_method_unlink() -> None:
    actual = {rule.rule: rule.endpoint for rule in main.app.url_map.iter_rules()}
    assert actual.get("/api/billing/payment-method/unlink") == "billing.billing_payment_method_unlink"


def test_yookassa_checkout_webhook_attaches_saved_payment_method(monkeypatch) -> None:
    calls = {}

    class _FakeYooKassaClient:
        def configured(self) -> bool:
            return True

        def get_payment(self, payment_id):
            calls["get_payment"] = payment_id
            return {
                "id": payment_id,
                "status": "succeeded",
                "metadata": {"checkout_session_id": "checkout-1"},
                "payment_method": {"id": "pm-saved-1", "saved": True},
            }

    class _FakeCursor:
        rowcount = 1

        def __init__(self):
            self.update_params = None

        def execute(self, query, params=None):
            if "UPDATE subscriptions" in query:
                self.update_params = params
                calls["update_params"] = params

        def fetchone(self):
            return {
                "id": "sub-1",
                "payment_method_id": "pm-saved-1",
                "next_billing_date": "2026-08-06T12:00:00+00:00",
            }

    class _FakeConn:
        def __init__(self):
            self.cursor_obj = _FakeCursor()

        def cursor(self):
            return self.cursor_obj

        def commit(self):
            calls["committed"] = True

        def rollback(self):
            calls["rolled_back"] = True

    class _FakeDb:
        def __init__(self):
            self.conn = _FakeConn()

        def close(self):
            calls["closed"] = True

    monkeypatch.setattr(yookassa_integration, "YooKassaClient", _FakeYooKassaClient)
    monkeypatch.setattr(yookassa_integration, "DatabaseManager", _FakeDb)
    monkeypatch.setattr(
        yookassa_integration,
        "mark_checkout_paid",
        lambda session_id, **kwargs: calls.update({"mark_checkout_paid": (session_id, kwargs)}),
    )
    monkeypatch.setattr(
        yookassa_integration,
        "complete_checkout",
        lambda session_id: {"session_id": session_id, "subscription_id": "sub-1"},
    )

    with main.app.test_request_context(
        "/api/yookassa/webhook",
        method="POST",
        json={"event": "payment.succeeded", "object": {"id": "pay-1"}},
    ):
        response, status_code = yookassa_integration.yookassa_webhook()

    assert status_code == 200
    assert response.get_json()["ok"] is True
    assert calls["get_payment"] == "pay-1"
    assert calls["mark_checkout_paid"][0] == "checkout-1"
    assert calls["update_params"] == ("pm-saved-1", "pay-1", "sub-1")
    assert calls["committed"] is True


def test_run_due_renewals_blocks_subscription_without_payment_method(monkeypatch) -> None:
    calls = {}

    class _FakeYooKassaClient:
        def configured(self) -> bool:
            return True

        def create_payment(self, *, payload, idempotency_key):
            raise AssertionError("renewal payment must not be created without payment_method_id")

    class _FakeCursor:
        def __init__(self):
            self.rows = [
                {
                    "id": "sub-missing",
                    "user_id": "user-1",
                    "business_id": "biz-1",
                    "tariff_id": "starter_monthly",
                    "status": "active",
                    "next_billing_date": "2026-07-01T00:00:00+00:00",
                    "payment_method_id": None,
                    "retry_count": 0,
                    "next_retry_at": None,
                }
            ]
            self.last_update = None

        def execute(self, query, params=None):
            if "SELECT *" in query and "FROM subscriptions" in query:
                return
            if "UPDATE subscriptions" in query:
                self.last_update = params
                calls["subscription_blocked"] = True
                return
            if "INSERT INTO billing_attempts" in query:
                calls["attempt_params"] = params
                return
            if "information_schema.columns" in query:
                self.rows = []
                return

        def fetchall(self):
            rows = self.rows
            self.rows = []
            return rows

        def fetchone(self):
            return {
                "id": "sub-missing",
                "user_id": "user-1",
                "business_id": "biz-1",
                "tariff_id": "starter_monthly",
                "status": "blocked",
                "next_billing_date": "2026-07-01T00:00:00+00:00",
                "payment_method_id": None,
                "retry_count": 3,
                "next_retry_at": None,
            }

    class _FakeConn:
        def __init__(self):
            self.cursor_obj = _FakeCursor()

        def cursor(self):
            return self.cursor_obj

        def commit(self):
            calls["committed"] = True

        def rollback(self):
            calls["rolled_back"] = True

    class _FakeDb:
        def __init__(self):
            self.conn = _FakeConn()

        def close(self):
            calls["closed"] = True

    monkeypatch.setattr(yookassa_integration, "YooKassaClient", _FakeYooKassaClient)
    monkeypatch.setattr(yookassa_integration, "DatabaseManager", _FakeDb)

    result = yookassa_integration.run_due_renewals(batch_size=1)

    assert result["success"] is True
    assert result["processed"] == 1
    assert result["errors"] == 1
    assert result["details"][0]["error"] == "missing payment_method_id"
    assert calls["subscription_blocked"] is True
    assert calls["attempt_params"][5] == "needs_payment_method"
    assert calls["attempt_params"][10] == "missing_payment_method_id"
    assert calls["committed"] is True
