"""Bounded process-local admission at the single authoritative recognition worker."""

import hashlib
import hmac
import math
import threading
import time

from services.pii_protection.gateway import PIIProtectionError


class AdmissionLimiter:
    def __init__(self, config, clock=time.monotonic):
        values = [config.get(key, default) for key, default in (
            ('protect_rps', 10), ('protect_burst', 4),
            ('business_protect_rps', 4), ('business_protect_burst', 4))]
        if any(isinstance(value, bool) or not isinstance(value, (int, float))
               or not math.isfinite(value) or value <= 0 for value in values):
            raise PIIProtectionError('PII_RUNTIME_CONFIGURATION_REQUIRED')
        self.rate, self.burst, self.business_rate, self.business_burst = values
        if (not 0.1 <= self.rate <= 100 or not 1 <= self.burst <= 50
                or not 0.1 <= self.business_rate <= self.rate or not 1 <= self.business_burst <= self.burst):
            raise PIIProtectionError('PII_RUNTIME_CONFIGURATION_REQUIRED')
        self.clock = clock
        self.key = config['bearer_token'].encode()
        self.lock = threading.Lock()
        self.global_bucket = [self.burst, clock()]
        self.businesses = {}
        self.denied = 0

    def _refill(self, bucket, rate, burst, now):
        bucket[0] = min(burst, bucket[0] + max(0, now - bucket[1]) * rate)
        bucket[1] = now

    def admit(self, business_id):
        key = hmac.new(self.key, business_id.encode(), hashlib.sha256).digest()
        now = self.clock()
        with self.lock:
            self._refill(self.global_bucket, self.rate, self.burst, now)
            if key not in self.businesses:
                if len(self.businesses) >= 1024:
                    self.businesses = {k: v for k, v in self.businesses.items() if now - v[1] < 60}
                if len(self.businesses) >= 1024:
                    self.denied += 1
                    return False
                self.businesses[key] = [self.business_burst, now]
            bucket = self.businesses[key]
            self._refill(bucket, self.business_rate, self.business_burst, now)
            if self.global_bucket[0] < 1 or bucket[0] < 1:
                self.denied += 1
                return False
            self.global_bucket[0] -= 1
            bucket[0] -= 1
            return True

    def status(self):
        with self.lock:
            return {'protect_rps': self.rate, 'protect_burst': self.burst,
                    'business_protect_rps': self.business_rate, 'business_protect_burst': self.business_burst,
                    'rate_limited': self.denied}
