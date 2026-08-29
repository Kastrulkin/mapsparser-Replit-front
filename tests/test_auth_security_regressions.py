import pytest


@pytest.mark.parametrize(
    "lookup_result",
    [
        {"error": "Пользователь с таким email не найден"},
        {"error": "Email уже подтвержден"},
    ],
)
def test_resend_verification_does_not_disclose_account_state(monkeypatch, lookup_result):
    import main

    monkeypatch.setattr(main, "rotate_verification_token", lambda _email: lookup_result)

    response = main.app.test_client().post(
        "/api/auth/resend-verification",
        json={"email": "person@example.com"},
    )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["success"] is True
    assert payload["message"] == (
        "Если аккаунт существует и email ещё не подтверждён, "
        "мы отправили новое письмо."
    )
    serialized = str(payload).lower()
    assert "не найден" not in serialized
    assert "уже подтвержден" not in serialized


def test_verify_email_does_not_expose_internal_exception(monkeypatch):
    import main

    sentinel = "postgresql://internal-user:internal-password@db/private"

    def fail_verification(_token):
        raise RuntimeError(sentinel)

    monkeypatch.setattr(main, "verify_email_token", fail_verification)

    response = main.app.test_client().post(
        "/api/auth/verify-email",
        json={"token": "invalid-test-token"},
    )

    payload = response.get_json()
    assert response.status_code == 500
    assert sentinel not in str(payload)
    assert payload["error"] == "Не удалось подтвердить email"
