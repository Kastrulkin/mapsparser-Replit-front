"""Pure validation controls; no network or database operations."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


PATH = Path(__file__).with_name("content_performance_sitecustomize_20260922.py")
SPEC = importlib.util.spec_from_file_location("performance_guard_contract", PATH)
GUARD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GUARD)


class GuardContract(unittest.TestCase):
    def setUp(self):
        self.context = {
            "host": "127.0.0.1", "port": 35429,
            "role": "readiness_perf_owner", "base_database": "readiness_perf_control",
        }
        self.parameters = {
            "host": "127.0.0.1", "port": "35429", "user": "readiness_perf_owner",
            "dbname": "localos_readiness_measure_" + "a" * 32,
        }

    def test_accepts_only_exact_context(self):
        self.assertEqual(GUARD.validate_context(self.context), self.context)
        for key, value in (("host", "localhost"), ("port", True), ("port", 5432), ("role", "postgres")):
            candidate = dict(self.context)
            candidate[key] = value
            with self.assertRaises(PermissionError):
                GUARD.validate_context(candidate)

    def test_rejects_unknown_context(self):
        with self.assertRaises(PermissionError):
            GUARD.validate_context(dict(self.context, extra="value"))

    def test_allows_only_owned_names_and_control_catalog(self):
        for name in (self.parameters["dbname"], "postgres", "readiness_perf_control"):
            GUARD.validate_parameters(dict(self.parameters, dbname=name), self.context)
        for name in ("production", "localos_readiness_measure_test", "localos_readiness_measure_" + "a" * 31):
            with self.assertRaises(PermissionError):
                GUARD.validate_parameters(dict(self.parameters, dbname=name), self.context)

    def test_rejects_every_identity_override(self):
        for key, value in (("host", "localhost"), ("port", "35418"), ("user", "postgres")):
            with self.assertRaises(PermissionError):
                GUARD.validate_parameters(dict(self.parameters, **{key: value}), self.context)

    def test_rejects_libpq_alternate_configuration(self):
        for key in ("hostaddr", "service", "options", "password", "sslcert", "sslrootcert"):
            with self.assertRaises(PermissionError):
                GUARD.validate_parameters(dict(self.parameters, **{key: "unexpected"}), self.context)

    def child(self, code, *, context=None, extra_environment=None):
        directory = tempfile.TemporaryDirectory(prefix="localos-perf-guard-check-", dir="/private/tmp")
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        shutil.copyfile(PATH, root / "sitecustomize.py")
        (root / "context.json").write_text(json.dumps(context or self.context), encoding="utf-8")
        environment = {
            "PATH": "/usr/bin:/bin", "HOME": str(root), "PYTHONPATH": str(root),
            "PYTHONDONTWRITEBYTECODE": "1", "PYTHON_DOTENV_DISABLED": "1",
        }
        environment.update(extra_environment or {})
        return subprocess.run(
            [sys.executable, "-B", "-c", code], env=environment,
            cwd=root, capture_output=True, text=True, timeout=10, check=False,
        )

    def test_startup_installs_guard_first(self):
        child = self.child("import psycopg2; assert psycopg2.connect.__module__ == 'sitecustomize'")
        self.assertEqual(child.returncode, 0, child.stderr)

    def test_invalid_context_aborts_startup(self):
        child = self.child("raise RuntimeError('must not execute')", context=dict(self.context, port=5432))
        self.assertEqual(child.returncode, 78)
        self.assertNotIn("must not execute", child.stderr)

    def test_inherited_libpq_environment_aborts_startup(self):
        child = self.child("raise RuntimeError('must not execute')", extra_environment={"PGHOST": "127.0.0.1"})
        self.assertEqual(child.returncode, 78)
        self.assertNotIn("must not execute", child.stderr)

    def test_installed_socket_hook_rejects_off_port_before_connect(self):
        child = self.child(
            "import socket\n"
            "try:\n"
            "    socket.socket().connect(('127.0.0.1', 1))\n"
            "except PermissionError:\n"
            "    pass\n"
            "else:\n"
            "    raise AssertionError('connection was admitted')\n"
        )
        self.assertEqual(child.returncode, 0, child.stderr)

    def test_installed_database_wrapper_rejects_merged_identity(self):
        child = self.child(
            "import psycopg2\n"
            "try:\n"
            "    psycopg2.connect('postgresql://readiness_perf_owner@127.0.0.1:35429/postgres', port=1)\n"
            "except PermissionError:\n"
            "    pass\n"
            "else:\n"
            "    raise AssertionError('connection was admitted')\n"
        )
        self.assertEqual(child.returncode, 0, child.stderr)

    def test_libpq_override_added_after_startup_is_rejected(self):
        child = self.child(
            "import os, psycopg2\n"
            "os.environ['PGHOSTADDR'] = '127.0.0.1'\n"
            "try:\n"
            "    psycopg2.connect('postgresql://readiness_perf_owner@127.0.0.1:35429/postgres')\n"
            "except PermissionError:\n"
            "    pass\n"
            "else:\n"
            "    raise AssertionError('override was admitted')\n"
        )
        self.assertEqual(child.returncode, 0, child.stderr)


if __name__ == "__main__":
    unittest.main()
