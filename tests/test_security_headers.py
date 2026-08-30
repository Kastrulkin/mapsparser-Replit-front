import pytest

import main


@pytest.mark.parametrize(
    ("header_name", "expected_value"),
    (
        ("X-Content-Type-Options", "nosniff"),
        ("Referrer-Policy", "strict-origin-when-cross-origin"),
    ),
)
def test_spa_response_sets_exact_security_header(header_name, expected_value):
    response = main.app.test_client().get("/")

    assert response.status_code == 200
    assert response.headers.get(header_name) == expected_value


@pytest.mark.parametrize(
    "header_name",
    (
        "Content-Security-Policy-Report-Only",
        "Permissions-Policy",
    ),
)
def test_spa_response_sets_nonempty_security_header(header_name):
    response = main.app.test_client().get("/")

    assert response.status_code == 200
    assert response.headers.get(header_name)


def test_spa_response_prevents_cross_origin_framing():
    response = main.app.test_client().get("/")

    assert response.status_code == 200
    assert response.headers.get("X-Frame-Options") in {"DENY", "SAMEORIGIN"}


def test_spa_csp_allows_the_configured_yandex_metrika_frame():
    response = main.app.test_client().get("/")

    assert response.status_code == 200
    policy = response.headers.get("Content-Security-Policy-Report-Only") or ""
    frame_sources = next(
        (directive for directive in policy.split(";") if directive.strip().startswith("frame-src ")),
        "",
    )
    assert "https://mc.yandex.ru" in frame_sources
