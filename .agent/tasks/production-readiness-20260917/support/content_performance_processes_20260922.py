"""Birth-pinned process ownership for the bounded performance driver.

The reviewed driver does not daemonize; it does create new-session children.
Remember observed descendants so a parent's exit does not lose their identity.
Never rediscover ownership by command substring or signal a reused PID.
"""

from __future__ import annotations

class OwnedProcesses:
    def __init__(self, process, backend=None):
        if backend is None:
            import psutil

            backend = psutil
        self.backend = backend
        self.process = process
        self.owned = {}
        self.retired = set()
        self.root = None
        try:
            root = backend.Process(process.pid)
            self.root = (root.pid, root.create_time())
            self.owned[self.root] = root
        except backend.NoSuchProcess:
            if process.poll() is None:
                raise RuntimeError("driver identity vanished before it could be pinned")

    def live(self, key):
        if key in self.retired:
            return False
        process = self.owned[key]
        try:
            # A fresh Process is essential: create_time on the stored object
            # may be cached even after the numeric PID has been reused.
            if self.backend.Process(key[0]).create_time() != key[1] or not process.is_running():
                self.retired.add(key)
                return False
            if process.status() == self.backend.STATUS_ZOMBIE:
                self.retired.add(key)
                return False
            return True
        except self.backend.NoSuchProcess:
            self.retired.add(key)
            return False

    def observe(self):
        # Retained children can themselves spawn children after the root exits.
        for key in list(self.owned):
            if not self.live(key):
                continue
            try:
                descendants = self.owned[key].children(recursive=True)
            except self.backend.NoSuchProcess:
                continue
            for child in descendants:
                try:
                    identity = (child.pid, child.create_time())
                    self.owned.setdefault(identity, child)
                except self.backend.NoSuchProcess:
                    continue

    def remaining(self):
        return [key for key in self.owned if self.live(key)]

    def cleanup(self):
        failures = []
        try:
            self.observe()
        except self.backend.Error:
            failures.append("final_observation_failed")
        signalled = []
        for operation, wait_seconds in (("terminate", 5), ("kill", 5)):
            candidates = []
            for key in reversed(list(self.owned)):
                try:
                    if self.live(key):
                        process = self.owned[key]
                        getattr(process, operation)()
                        candidates.append(process)
                        signalled.append({"pid": key[0], "created": key[1], "signal": operation})
                except self.backend.NoSuchProcess:
                    continue
                except self.backend.Error:
                    failures.append(operation + "_failed")
            if candidates:
                self.backend.wait_procs(candidates, timeout=wait_seconds)
        try:
            remaining = [{"pid": key[0], "created": key[1]} for key in self.remaining()]
        except self.backend.Error:
            failures.append("remaining_process_check_failed")
            remaining = None
        return {
            "status": "clean" if not failures and remaining == [] else "cleanup_failed",
            "observed": [{"pid": key[0], "created": key[1]} for key in self.owned],
            "signalled": signalled,
            "remaining": remaining,
            "errors": failures,
        }
