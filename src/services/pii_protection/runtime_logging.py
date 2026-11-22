"""Gunicorn logging that never formats request paths, arguments or tracebacks."""

from gunicorn.glogging import Logger


class SafeGunicornLogger(Logger):
    def access(self, *args, **kwargs):
        pass

    def info(self, *args, **kwargs):
        self.error_log.info('PII_RUNTIME_SERVER_EVENT')

    def warning(self, *args, **kwargs):
        self.error_log.warning('PII_RUNTIME_SERVER_WARNING')

    def error(self, *args, **kwargs):
        self.error_log.error('PII_RUNTIME_SERVER_ERROR')

    def critical(self, *args, **kwargs):
        self.error_log.critical('PII_RUNTIME_SERVER_CRITICAL')

    def exception(self, *args, **kwargs):
        self.error_log.error('PII_RUNTIME_SERVER_ERROR')

    def debug(self, *args, **kwargs):
        pass
