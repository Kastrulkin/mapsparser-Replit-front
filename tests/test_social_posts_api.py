from flask import Flask

from src.api import social_posts_api


def test_social_post_write_rate_limit_allows_first_request(monkeypatch):
    social_posts_api._WRITE_RATE_BUCKETS.clear()
    monkeypatch.setenv("SOCIAL_POST_WRITE_RATE_LIMIT", "1")
    monkeypatch.setenv("SOCIAL_POST_WRITE_RATE_WINDOW_SEC", "60")

    assert social_posts_api._check_write_rate_limit("user-1", "publish") is None


def test_social_post_write_rate_limit_blocks_repeated_action(monkeypatch):
    social_posts_api._WRITE_RATE_BUCKETS.clear()
    monkeypatch.setenv("SOCIAL_POST_WRITE_RATE_LIMIT", "1")
    monkeypatch.setenv("SOCIAL_POST_WRITE_RATE_WINDOW_SEC", "60")

    assert social_posts_api._check_write_rate_limit("user-1", "publish") is None
    app = Flask(__name__)
    with app.app_context():
        error_response = social_posts_api._check_write_rate_limit("user-1", "publish")

    assert error_response is not None
    assert error_response[1] == 429
