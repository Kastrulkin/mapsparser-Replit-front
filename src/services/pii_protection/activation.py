"""Operator-scoped activation; deployment configuration is never request input."""

import os
from contextvars import ContextVar


CONFIG_FILE = '/run/secrets/localos-pii-activation.json'
DEPLOYMENT_REQUIRED_FILE = os.path.join(os.path.dirname(__file__), '.activation-required')
OPERATOR_REQUEST = ContextVar('pii_operator_request', default=False)


def configuration():
    from services.pii_protection.gateway import PIIProtectionError
    from services.pii_protection.runtime_config import read_secret_json
    path = os.getenv('PII_ACTIVATION_CONFIG_FILE', CONFIG_FILE)
    required = (os.getenv('PII_ACTIVATION_REQUIRED', '').lower() in {'true', '1', 'yes'}
                or os.path.lexists(path + '.required')
                or (OPERATOR_REQUEST.get() and os.path.lexists(DEPLOYMENT_REQUIRED_FILE)))
    if os.path.lexists(path) or required:
        value = read_secret_json(path)
        if (set(value) != {'version', 'enabled', 'scope', 'mode'} or not isinstance(value['enabled'], bool)
                or value['scope'] != 'operator_text' or value['mode'] not in {'enforce', 'blocked'}):
            raise PIIProtectionError('PII_ACTIVATION_CONFIGURATION_INVALID')
        return value
    scope = os.getenv('PII_PROTECTION_SCOPE', 'all')
    if scope not in {'all', 'operator_text'}:
        raise PIIProtectionError('PII_ACTIVATION_CONFIGURATION_INVALID')
    return {'version': 1, 'enabled': os.getenv('PII_PROTECTION_ENABLED', 'false').lower() in {'true', '1', 'yes', 'on'},
            'scope': scope, 'mode': 'enforce'}


def active():
    settings = configuration()
    return settings['enabled'] and (settings['scope'] == 'all' or OPERATOR_REQUEST.get())


def enter_operator_request():
    # The trusted shared handler owns this boundary, independently of channel JSON.
    token = OPERATOR_REQUEST.set(True)
    try:
        configuration()
    except Exception:
        OPERATOR_REQUEST.reset(token)
        raise
    return token


def exit_operator_request(token):
    OPERATOR_REQUEST.reset(token)
