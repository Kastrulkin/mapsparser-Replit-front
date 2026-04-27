import hashlib
import hmac

from crypto_pay_client import crypto_pay_webhook_secret, verify_crypto_pay_signature


def test_crypto_pay_webhook_secret_falls_back_to_token_hash(monkeypatch) -> None:
    monkeypatch.delenv("CRYPTO_PAY_WEBHOOK_SECRET", raising=False)
    monkeypatch.setenv("CRYPTO_PAY_API_TOKEN", "test-token")
    secret = crypto_pay_webhook_secret()
    assert len(secret) == 32


def test_verify_crypto_pay_signature_uses_token_based_hmac(monkeypatch) -> None:
    monkeypatch.setenv("CRYPTO_PAY_API_TOKEN", "test-token")
    raw_body = b'{"update_type":"invoice_paid"}'
    signing_key = hashlib.sha256(b"test-token").digest()
    signature = hmac.new(signing_key, raw_body, hashlib.sha256).hexdigest()
    assert verify_crypto_pay_signature(raw_body, signature) is True
