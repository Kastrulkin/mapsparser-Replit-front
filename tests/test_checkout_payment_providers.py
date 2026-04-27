from types import SimpleNamespace

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
