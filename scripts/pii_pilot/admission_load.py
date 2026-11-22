"""Opt-in synthetic admission load; private RPC only, no application/provider calls."""

import argparse
import concurrent.futures
import json
import math
import time
import uuid
from pathlib import Path

from services.pii_protection.gateway import PIIProtectionError, Scope
from services.pii_protection.remote import RemoteProtectionService
from services.pii_protection.runtime_config import CLIENT_CONFIG


def phase(client, name, offered_rps, businesses, seconds):
    text = 'Full name: Mira Exampleton; email: synthetic-load@example.invalid'
    epoch = uuid.uuid4().hex
    def execute(number):
        started = time.monotonic()
        scope = Scope('synthetic-load-' + epoch + '-' + str(number % businesses),
                      'synthetic-diagnostic', 'synthetic-' + uuid.uuid4().hex)
        try:
            result = client.protect(text, scope)
            assert 'synthetic-load@example.invalid' not in result.text
            assert result.restore_text(result.text) == text
            return None, time.monotonic() - started
        except PIIProtectionError:
            import sys
            return str(sys.exc_info()[1]), time.monotonic() - started
    started = time.monotonic()
    futures = []
    pool = concurrent.futures.ThreadPoolExecutor(max_workers=8)
    try:
        for number in range(round(offered_rps * seconds)):
            time.sleep(max(0, started + number / offered_rps - time.monotonic()))
            futures.append(pool.submit(execute, number))
        results = [future.result() for future in futures]
    finally:
        pool.shutdown(wait=True)
    elapsed = time.monotonic() - started
    errors = {}
    latencies = []
    for code, latency in results:
        if code:
            errors[code] = errors.get(code, 0) + 1
        else:
            latencies.append(latency * 1000)
    latencies.sort()
    return {'phase': name, 'offered_rps': offered_rps, 'businesses': businesses,
            'duration_seconds': round(elapsed, 3), 'attempts': len(results), 'successes': len(latencies),
            'errors': errors, 'p95_ms': round(latencies[min(len(latencies) - 1, math.ceil(len(latencies) * .95) - 1)], 3) if latencies else None}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    parser.add_argument('--nominal-seconds', type=int, default=30)
    parser.add_argument('--overload-seconds', type=int, default=20)
    args = parser.parse_args()
    if not 10 <= args.nominal_seconds <= 120 or not 10 <= args.overload_seconds <= 120:
        raise RuntimeError('SYNTHETIC_DURATION_INVALID')
    client = RemoteProtectionService.from_file(CLIENT_CONFIG)
    before = client._call('/v1/status', {})
    if not before.get('synthetic_only') or before.get('protect_rps') != 10 or before.get('business_protect_rps') != 4:
        raise RuntimeError('SYNTHETIC_LIMIT_PROFILE_REQUIRED')
    results = [phase(client, 'nominal', 8, 4, args.nominal_seconds),
               phase(client, 'global_overload', 20, 4, args.overload_seconds),
               phase(client, 'business_overload', 12, 1, args.overload_seconds)]
    after = client._call('/v1/status', {})
    report = {'status': 'measured', 'synthetic_only': True, 'external_llm_calls': 0,
              'model_pid': after['model_pid'], 'phases': results,
              'limits': {key: after[key] for key in ['protect_rps', 'protect_burst', 'business_protect_rps', 'business_protect_burst']}}
    Path(args.output).write_text(json.dumps(report, indent=2) + '\n')
    assert before['model_pid'] == after['model_pid']
    assert not results[0]['errors'] and results[0]['successes'] == results[0]['attempts']
    for result, rate, burst in [(results[1], before['protect_rps'], before['protect_burst']),
                                (results[2], before['business_protect_rps'], before['business_protect_burst'])]:
        assert set(result['errors']) <= {'PII_RUNTIME_RATE_LIMITED', 'PII_RUNTIME_BUSY'}
        assert result['errors'].get('PII_RUNTIME_RATE_LIMITED', 0) > 0
        assert result['successes'] <= math.ceil(rate * result['duration_seconds']) + burst
    report['status'] = 'passed'
    Path(args.output).write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
