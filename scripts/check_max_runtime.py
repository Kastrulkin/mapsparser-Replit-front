#!/usr/bin/env python3
"""Read-only MAX environment check after deployment; never prints credentials."""
import hashlib
import json
import subprocess
import sys

KEYS = ('MAX_ENABLED', 'MAX_BOT_TOKEN', 'MAX_WEBHOOK_SECRET', 'MAX_BOT_USERNAME', 'MAX_PUBLISH_ENABLED', 'MAX_PUBLISH_CHAT_IDS')
SERVICES = ('app', 'worker', 'operator-worker')


def fingerprint(values):
    return {key: hashlib.sha256(str(values.get(key) or '').encode()).hexdigest() for key in KEYS}


def mismatches(expected, actual):
    return [key for key in KEYS if fingerprint(expected)[key] != actual.get(key)]


def run():
    try:
        configured = json.loads(subprocess.run(['docker', 'compose', 'config', '--format', 'json'], check=True, capture_output=True, text=True).stdout)
        failed = False
        for service in SERVICES:
            expected = configured['services'][service].get('environment') or {}
            code = 'import os,json,hashlib; keys=' + repr(KEYS) + '; print(json.dumps({k:hashlib.sha256(os.getenv(k, "").encode()).hexdigest() for k in keys}))'
            observed = json.loads(subprocess.run(['docker', 'compose', 'exec', '-T', service, 'python', '-c', code], check=True, capture_output=True, text=True).stdout)
            keys = mismatches(expected, observed)
            if keys:
                failed = True
                print(service + ': configuration not applied: ' + ', '.join(keys))
            else:
                print(service + ': MAX configuration matches')
        return 1 if failed else 0
    except (subprocess.CalledProcessError, KeyError, ValueError):
        print('Runtime check unavailable; check Compose and service availability. No credentials were printed.', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(run())
