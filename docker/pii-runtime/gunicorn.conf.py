"""One model worker; bounded connections and a quiet, fixed-code logger."""

import ssl

bind = '0.0.0.0:8765'
workers = 1
worker_class = 'gthread'
threads = 8
worker_connections = 64
backlog = 32
preload_app = False
max_requests = 0
timeout = 20
graceful_timeout = 10
keepalive = 5
limit_request_line = 1024
limit_request_fields = 12
limit_request_field_size = 2048
certfile = '/run/secrets/pii-server.crt'
keyfile = '/run/secrets/pii-server.key'
logger_class = 'services.pii_protection.runtime_logging.SafeGunicornLogger'
accesslog = None
errorlog = '-'
loglevel = 'info'


def ssl_context(conf, default_ssl_context_factory):
    context = default_ssl_context_factory()
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    return context
