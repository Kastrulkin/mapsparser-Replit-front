"""Read protected local configuration without exposing its values in failures."""

import json
import os
import stat

from services.pii_protection.gateway import PIIProtectionError


CLIENT_CONFIG = '/run/secrets/localos-pii-client.json'
SERVER_CONFIG = '/run/secrets/localos-pii-runtime.json'


def read_secret_json(path):
    descriptor = None
    try:
        if not isinstance(path, str) or not os.path.isabs(path):
            raise ValueError()
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_mode & 0o077 or metadata.st_size > 65536:
            raise ValueError()
        data = os.read(descriptor, 65537)
        if len(data) > 65536:
            raise ValueError()
        value = json.loads(data)
        if not isinstance(value, dict) or value.get('version') != 1:
            raise ValueError()
        return value
    except Exception:
        raise PIIProtectionError('PII_RUNTIME_CONFIGURATION_REQUIRED') from None
    finally:
        if descriptor is not None:
            os.close(descriptor)
