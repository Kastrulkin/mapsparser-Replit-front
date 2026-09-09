"""Render only configuration: no local secrets, services or outbound messages."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
PACING = {
    "OUTREACH_DISPATCH_BATCH_SIZE": "2",
    "OUTREACH_DISPATCH_INTERVAL_SEC": "60",
    "OUTREACH_REPLY_SYNC_INTERVAL_SEC": "60",
}


class OutreachDispatchComposeTest(unittest.TestCase):
    def render(self, *, overrides=None, split_workers=False):
        docker = shutil.which("docker")
        if not docker:
            self.skipTest("Docker Compose CLI required; no daemon needed")
        env = {"PATH": os.environ.get("PATH", ""), "HOME": os.environ.get("HOME", "")}
        env.update(overrides or {})
        args = [docker, "compose", "--env-file", "/dev/null", "-f", "docker-compose.yml"]
        if split_workers:
            args.extend(["-f", "docker-compose.workers.yml"])
        args.extend(["config", "--no-env-resolution", "--format", "json"])
        result = subprocess.run(args, cwd=ROOT, env=env, text=True,
                                capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0, "Compose rendering failed; full config omitted")
        return json.loads(result.stdout)["services"]

    def test_default_worker_uses_short_batches_and_explicit_reply_cadence(self):
        services = self.render()
        worker = services["worker"]["environment"]
        self.assertEqual({key: worker.get(key) for key in PACING}, PACING)
        self.assertEqual(worker["OUTREACH_DISPATCH_ENABLED"], "false")
        self.assertEqual(worker["OUTREACH_DISPATCH_BUSINESS_IDS"], "")
        self.assertTrue(set(PACING).isdisjoint(services["app"]["environment"]))

    def test_explicit_deployment_overrides_remain_supported(self):
        overrides = dict(zip(PACING, ("1", "90", "30")))
        worker = self.render(overrides=overrides)["worker"]["environment"]
        self.assertEqual({key: worker.get(key) for key in PACING}, overrides)

    def test_optional_dispatcher_inherits_safe_pacing(self):
        services = self.render(split_workers=True)
        worker = services["worker-dispatcher"]["environment"]
        self.assertEqual({key: worker.get(key) for key in PACING}, PACING)
        self.assertEqual(worker["WORKER_ROLE"], "dispatcher")
        self.assertEqual(services["worker"]["environment"]["WORKER_ROLE"], "parser")


if __name__ == "__main__":
    unittest.main()
