"""Pure contracts for the content performance wrapper; no PostgreSQL/process run."""

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch


PATH = Path(__file__).with_name("content_performance_native_20260922.py")
SPEC = importlib.util.spec_from_file_location("content_performance_native_20260922", PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ContentPerformanceWrapperContracts(unittest.TestCase):
    def temporary(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        return Path(temporary.name)

    def replace(self, name, value):
        replacement = patch.object(MODULE, name, value)
        replacement.start()
        self.addCleanup(replacement.stop)

    def test_smoke_uses_zero_warmups_one_serial_and_no_load(self):
        command = MODULE.driver_command(Path("/private/tmp/localos-content-perf.contract"), 35429, True, Path("/private/tmp/localos-content-perf.contract/guard"))
        self.assertEqual(command[command.index("--warmups") + 1], "0")
        self.assertEqual(command[command.index("--serial-samples") + 1], "1")
        self.assertEqual(command[command.index("--load-samples") + 1], "0")

    def test_policy_denies_global_writes_then_allows_only_owned_root(self):
        policy = MODULE.sandbox_policy(35429, Path("/private/tmp/localos-content-perf.contract/guard"))
        self.assertIn("(deny file-write*)", policy)
        self.assertIn('/private/tmp/localos-content-perf.contract', policy)
        self.assertIn('(remote ip "localhost:35429")', policy)

    def test_protected_hashes_include_measurement_harness(self):
        root = self.temporary()
        guard = root / "sitecustomize.py"
        context = root / "context.json"
        guard.write_text("guard", encoding="utf-8")
        context.write_text("{}", encoding="utf-8")
        values = MODULE.protected_hashes(guard, context)
        self.assertIn("repository_driver", values)
        self.assertIn("repository_benchmark", values)
        self.assertIn("guard", values)
        self.assertIn("context", values)

    def test_postcheck_rejects_wrong_sample_matrix_before_database_query(self):
        root = self.temporary()
        (root / "guard").mkdir()
        guard = root / "guard/sitecustomize.py"
        guard.write_text("guard", encoding="utf-8")
        payload = {
            "executed": True,
            "valid": True,
            "invalid_reasons": [],
            "plan": {
                "refs": {"baseline": "a" * 40, "current": "b" * 40},
                "harness_sha256": MODULE.digest(MODULE.BENCHMARK),
                "driver": {"sha256": MODULE.digest(MODULE.DRIVER)},
                "guard": {"path": str(guard), "sha256": MODULE.digest(guard)},
                "limits": {"warmups_per_ref": 0, "serial_samples_per_ref": 1, "load_samples_per_ref": 0},
            },
            "runs": {"baseline": [], "current": []},
        }
        (root / "driver-output.json").write_text(json.dumps(payload), encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "nonempty unique"):
            MODULE.post_driver_database_check(root, 35429, {}, True, payload["plan"]["refs"])

    def test_identity_failure_retains_direct_postgres_handle(self):
        root = self.temporary()
        process = Mock(pid=101)
        process.poll.return_value = None
        init_runner = Mock(return_value=Mock(returncode=0, stdout="synthetic initdb", stderr=""))
        self.replace("run", init_runner)
        self.replace("postmaster_pid", Mock(return_value=101))
        self.replace("verify_postmaster", Mock())
        self.replace("psql_scalar", Mock(side_effect=RuntimeError("synthetic identity failure")))
        replacement = patch.object(MODULE.subprocess, "Popen", Mock(return_value=process))
        replacement.start()
        self.addCleanup(replacement.stop)
        caught = self.assertRaises(MODULE.ClusterInitializationError)
        with caught:
            MODULE.initialize_cluster(root, 35429, {})
        self.assertIs(caught.exception.process, process)
        self.assertEqual(caught.exception.identity["pid"], 101)
        command = init_runner.call_args.args[0]
        self.assertIn("--encoding=UTF8", command)
        self.assertIn("--locale=C", command)

    def test_pre_pidfile_failure_still_stops_owned_handle(self):
        root = self.temporary()
        process = Mock(pid=101)
        process.poll.return_value = None
        self.replace("verify_postmaster", Mock())
        record = MODULE.stop_exact_cluster(root, 101, process)
        self.assertEqual(record["status"], "stopped")
        process.send_signal.assert_called_once_with(MODULE.signal.SIGINT)

    def test_already_exited_postgres_is_never_signalled(self):
        process = Mock(pid=101, returncode=1)
        process.poll.return_value = 1
        record = MODULE.stop_exact_cluster(self.temporary(), 101, process)
        self.assertEqual(record["status"], "already_exited")
        process.send_signal.assert_not_called()


if __name__ == "__main__":
    unittest.main()
