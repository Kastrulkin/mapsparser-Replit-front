from flask import Flask, make_response
from core.security_headers import register_security_headers


def test_control_iframe_headers_and_ordinary_page_remain_usable():
    app = Flask(__name__)
    register_security_headers(app)
    @app.get('/<path:path>')
    def page(path):
        return 'ok'
    client = app.test_client()
    for path, parent in [('/max/control', 'https://max.ru'), ('/telegram/control', 'https://web.telegram.org')]:
        response = client.get(path)
        assert response.status_code == 200
        assert 'X-Frame-Options' not in response.headers
        assert parent in response.headers['Content-Security-Policy']
        assert response.headers['X-Content-Type-Options'] == 'nosniff'
    response = client.get('/dashboard/today')
    assert response.status_code == 200 and response.headers['X-Frame-Options'] == 'SAMEORIGIN'
    assert 'microphone=(self)' in response.headers['Permissions-Policy']


def test_no_referrer_from_sensitive_endpoint_is_preserved():
    app = Flask(__name__)
    register_security_headers(app)
    @app.get('/private')
    def private():
        response = make_response('ok')
        response.headers['Referrer-Policy'] = 'no-referrer'
        return response
    assert app.test_client().get('/private').headers['Referrer-Policy'] == 'no-referrer'


def test_max_route_is_registered_as_private_spa_entry():
    from core.public_page_html import is_known_spa_route, should_noindex_spa_route
    assert is_known_spa_route('/max/control', {})
    assert is_known_spa_route('/telegram/control', {})
    assert should_noindex_spa_route('/max/control?screen=today')
    assert not is_known_spa_route('/max/unknown', {})
