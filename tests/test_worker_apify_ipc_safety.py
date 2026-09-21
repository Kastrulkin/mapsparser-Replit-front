"""AST-isolated retention checks for the worker's Apify subprocess IPC."""

from __future__ import annotations

import ast
import builtins
import copy
import json
import multiprocessing
import os
from pathlib import Path
import queue
import sys
import tempfile
import types
import unittest


WORKER_SOURCE = Path(__file__).parents[1] / "src" / "worker.py"
MARKER = "synthetic-private-apify-ipc-marker"


def _source_text() -> str:
    if "--source-stdin" in sys.argv:
        sys.argv.remove("--source-stdin")
        return sys.stdin.read()
    return WORKER_SOURCE.read_text(encoding="utf-8")


SOURCE_TEXT = _source_text()


def _functions():
    tree = ast.parse(SOURCE_TEXT, filename=str(WORKER_SOURCE))
    names = {
        "_parse_card_via_apify_subprocess_entry",
        "_parse_card_via_apify_with_timeout",
    }
    selected = [copy.deepcopy(node) for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
    if {node.name for node in selected} != names:
        raise AssertionError("expected both current Apify IPC functions")
    module = ast.Module(
        body=[ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0), *selected],
        type_ignores=[],
    )
    return ast.fix_missing_locations(module)


class _TrackedFile:
    def __init__(self, handle, path: str, writes: list[tuple[Path, int, str]]):
        self._handle = handle
        self._path = Path(path)
        self._writes = writes

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        self._handle.close()
        if self._path.exists():
            self._writes.append((self._path, self._path.stat().st_mode & 0o777, self._path.read_text(encoding="utf-8")))
        return False

    def __getattr__(self, name):
        return getattr(self._handle, name)


class _Queue:
    def __init__(self):
        self.items = []
        self.closed = False
        self.joined = False

    def put(self, value):
        self.items.append(value)

    def empty(self):
        return not self.items

    def get(self, *_args, **_kwargs):
        if not self.items:
            raise queue.Empty
        return self.items.pop(0)

    def close(self):
        self.closed = True

    def join_thread(self):
        self.joined = True


class _Process:
    def __init__(
        self,
        target,
        args,
        *,
        run_child: bool,
        alive: bool,
        start_error=None,
        ignore_terminate=False,
        ignore_kill=False,
    ):
        self._target = target
        self._args = args
        self._run_child = run_child
        self._alive = alive
        self._start_error = start_error
        self._ignore_terminate = ignore_terminate
        self._ignore_kill = ignore_kill
        self.events = []
        self.closed = False

    def start(self):
        self.events.append(("start", None))
        if self._start_error is not None:
            raise self._start_error
        if self._run_child:
            self._target(*self._args)

    def join(self, *args, **kwargs):
        timeout = kwargs.get("timeout")
        if args:
            timeout = args[0]
        self.events.append(("join", timeout))
        return None

    def is_alive(self):
        return self._alive

    def terminate(self):
        self.events.append(("terminate", None))
        if not self._ignore_terminate:
            self._alive = False

    def kill(self):
        self.events.append(("kill", None))
        if not self._ignore_kill:
            self._alive = False

    def close(self):
        self.events.append(("close", None))
        self.closed = True


def _namespace(
    parse,
    *,
    run_child=True,
    alive=False,
    supplied_queue=None,
    real_fork=False,
    start_error=None,
    ignore_terminate=False,
    ignore_kill=False,
):
    writes: list[tuple[Path, int, str]] = []
    private_files = []
    open_calls = []
    processes = []
    result_queue = supplied_queue or _Queue()

    def tracked_temporary_file(*args, **kwargs):
        handle = tempfile.TemporaryFile(*args, **kwargs)
        private_files.append((handle, os.fstat(handle.fileno()).st_mode & 0o777))
        return handle

    def tracked_open(path, mode="r", *args, **kwargs):
        open_calls.append((Path(path), mode))
        handle = builtins.open(path, mode, *args, **kwargs)
        if "w" in mode:
            return _TrackedFile(handle, str(path), writes)
        return handle

    def process_factory(*, target, args, daemon):
        if not daemon:
            raise AssertionError("Apify subprocess must stay daemonized")
        process = _Process(
            target,
            args,
            run_child=run_child,
            alive=alive,
            start_error=start_error,
            ignore_terminate=ignore_terminate,
            ignore_kill=ignore_kill,
        )
        processes.append(process)
        return process

    context = types.SimpleNamespace(Queue=lambda **_kwargs: result_queue, Process=process_factory)
    namespace = {
        "Any": object,
        "Dict": dict,
        "Optional": object,
        "multiprocessing": multiprocessing if real_fork else types.SimpleNamespace(get_context=lambda name: context),
        "os": os,
        "queue": queue,
        "json": json,
        "open": tracked_open,
        "tempfile": types.SimpleNamespace(TemporaryFile=tracked_temporary_file),
        "_parse_card_via_apify": parse,
        "redact_sensitive_text": lambda _value, *, limit: "redacted",
        "debug_url_summary": lambda _url: {"provider": "other", "route": "other"},
        "debug_value_shape": lambda _value: {"type": "object"},
    }
    exec(compile(_functions(), str(WORKER_SOURCE), "exec"), namespace)
    resources = types.SimpleNamespace(
        queue=result_queue,
        processes=processes,
        private_files=private_files,
        open_calls=open_calls,
    )
    return namespace, writes, resources


def _marker_writes(writes):
    return [(path, mode, content) for path, mode, content in writes if MARKER in content]


class WorkerApifyIpcSafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        def deny_external_effects(event, _args):
            if event in {"socket.connect", "subprocess.Popen", "os.system", "os.posix_spawn", "os.spawn", "sqlite3.connect"}:
                raise AssertionError(f"unexpected external effect: {event}")

        sys.addaudithook(deny_external_effects)

    def _assert_no_durable_raw_ipc(self, debug_dir: Path, writes):
        durable_contents = "\n".join(
            path.read_text(encoding="utf-8")
            for path in debug_dir.rglob("*")
            if path.is_file()
        )
        self.assertNotIn(MARKER, durable_contents)
        self.assertFalse((debug_dir / "apify_result.json").exists())
        for path, mode, _content in _marker_writes(writes):
            self.assertNotEqual(path.parent, debug_dir)
            self.assertEqual(mode & 0o077, 0)
            self.assertEqual(path.parent.stat().st_mode & 0o077, 0)

    def _assert_resources_closed(self, resources):
        self.assertTrue(resources.queue.closed)
        self.assertTrue(resources.queue.joined)
        for process in resources.processes:
            self.assertTrue(process.closed)
        for handle, _mode in resources.private_files:
            self.assertTrue(handle.closed)

    def _assert_parent_resources_closed(self, resources):
        self.assertTrue(resources.queue.closed)
        self.assertTrue(resources.queue.joined)
        for handle, _mode in resources.private_files:
            self.assertTrue(handle.closed)

    def test_success_keeps_functional_payload_without_durable_debug_ipc(self):
        payload = {
            "title": MARKER,
            "raw_payload_json": {"nested": MARKER},
            "_apify_debug": {"run_input": {"marker": MARKER}, "usage_total_usd": 0.25},
        }
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        debug_dir = Path(directory.name) / "durable-debug"
        namespace, writes, resources = _namespace(lambda *_args, **_kwargs: payload)
        result = namespace["_parse_card_via_apify_with_timeout"](
            "https://example.invalid/map", debug_bundle_dir=str(debug_dir), timeout_sec=30,
        )
        self.assertEqual(result, payload)
        self._assert_no_durable_raw_ipc(debug_dir, writes)
        self.assertTrue(resources.private_files)
        for handle, mode in resources.private_files:
            self.assertEqual(mode & 0o077, 0)
            self.assertTrue(handle.closed)
        self._assert_resources_closed(resources)

    def test_child_failure_keeps_error_code_without_durable_raw_ipc(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        debug_dir = Path(directory.name) / "durable-debug"

        def fail(*_args, **_kwargs):
            raise RuntimeError(MARKER)

        namespace, writes, resources = _namespace(fail)
        result = namespace["_parse_card_via_apify_with_timeout"](
            "https://example.invalid/map", debug_bundle_dir=str(debug_dir), timeout_sec=30,
        )
        self.assertEqual(result.get("error"), "apify_parser_subprocess_exception")
        self.assertEqual(result["message"], "redacted")
        self._assert_no_durable_raw_ipc(debug_dir, writes)
        self._assert_resources_closed(resources)

    def test_timeout_and_empty_queue_keep_error_semantics(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        debug_dir = Path(directory.name) / "durable-debug"
        timeout_namespace, timeout_writes, timeout_resources = _namespace(lambda *_args, **_kwargs: {}, run_child=False, alive=True)
        timeout_result = timeout_namespace["_parse_card_via_apify_with_timeout"](
            "https://example.invalid/map", debug_bundle_dir=str(debug_dir), timeout_sec=30,
        )
        self.assertEqual(timeout_result.get("error"), "apify_parser_subprocess_timeout")
        self._assert_no_durable_raw_ipc(debug_dir, timeout_writes)
        self._assert_resources_closed(timeout_resources)

        empty_namespace, empty_writes, empty_resources = _namespace(lambda *_args, **_kwargs: {}, run_child=False)
        empty_result = empty_namespace["_parse_card_via_apify_with_timeout"](
            "https://example.invalid/map", debug_bundle_dir=str(debug_dir), timeout_sec=30,
        )
        self.assertEqual(empty_result.get("error"), "apify_parser_subprocess_no_result")
        self._assert_no_durable_raw_ipc(debug_dir, empty_writes)
        self._assert_resources_closed(empty_resources)

    def test_large_result_without_debug_bundle_does_not_timeout_before_queue_drain(self):
        payload = {
            "title": MARKER,
            "raw_payload_json": {"body": MARKER * 20000},
            "_apify_debug": {"run_input": {"marker": MARKER}},
        }
        namespace, _writes, _resources = _namespace(
            lambda *_args, **_kwargs: payload,
            real_fork=True,
        )
        result = namespace["_parse_card_via_apify_with_timeout"](
            "https://example.invalid/map", timeout_sec=3,
        )
        self.assertEqual(result, payload)

    def test_child_queue_carries_only_a_small_readiness_marker(self):
        payload = {"title": MARKER, "raw_payload_json": {"marker": MARKER}}
        namespace, _writes, resources = _namespace(lambda *_args, **_kwargs: payload)
        transport = tempfile.TemporaryFile(mode="w+", encoding="utf-8")
        self.addCleanup(transport.close)
        namespace["_parse_card_via_apify_subprocess_entry"](
            resources.queue,
            "https://example.invalid/map",
            {},
            transport,
        )
        self.assertEqual(resources.queue.items, [{"transport_ready": True}])
        self.assertNotIn(MARKER, repr(resources.queue.items))
        transport.seek(0)
        self.assertIn(MARKER, transport.read())

    def test_start_failure_closes_transport_queue_and_process(self):
        namespace, _writes, resources = _namespace(
            lambda *_args, **_kwargs: {},
            start_error=RuntimeError("synthetic start failure"),
        )
        with self.assertRaisesRegex(RuntimeError, "synthetic start failure"):
            namespace["_parse_card_via_apify_with_timeout"](
                "https://example.invalid/map", timeout_sec=30,
            )
        self._assert_resources_closed(resources)

    def test_timeout_escalates_to_kill_when_child_ignores_terminate(self):
        namespace, _writes, resources = _namespace(
            lambda *_args, **_kwargs: {},
            run_child=False,
            alive=True,
            ignore_terminate=True,
        )
        result = namespace["_parse_card_via_apify_with_timeout"](
            "https://example.invalid/map", timeout_sec=30,
        )
        self.assertEqual(result.get("error"), "apify_parser_subprocess_timeout")
        process = resources.processes[0]
        names = [name for name, _value in process.events]
        self.assertIn("kill", names)
        self.assertLess(names.index("terminate"), names.index("kill"))
        self.assertGreater(
            [index for index, event in enumerate(process.events) if event == ("join", 5)][0],
            names.index("terminate"),
        )
        self.assertGreater(
            [index for index, event in enumerate(process.events) if event == ("join", 5)][1],
            names.index("kill"),
        )
        self._assert_resources_closed(resources)

    def test_unkillable_child_keeps_timeout_result_and_closes_parent_resources(self):
        namespace, _writes, resources = _namespace(
            lambda *_args, **_kwargs: {},
            run_child=False,
            alive=True,
            ignore_terminate=True,
            ignore_kill=True,
        )
        result = namespace["_parse_card_via_apify_with_timeout"](
            "https://example.invalid/map", timeout_sec=30,
        )
        self.assertEqual(result.get("error"), "apify_parser_subprocess_timeout")
        process = resources.processes[0]
        names = [name for name, _value in process.events]
        self.assertIn("terminate", names)
        self.assertIn("kill", names)
        self.assertTrue(process.is_alive())
        self.assertFalse(process.closed)
        self._assert_parent_resources_closed(resources)

    def test_empty_or_malformed_transport_returns_controlled_error_and_cleans_up(self):
        for queued_value in (None, {"transport_ready": False}):
            supplied_queue = _Queue()
            if queued_value is not None:
                supplied_queue.put(queued_value)
            namespace, _writes, resources = _namespace(
                lambda *_args, **_kwargs: {},
                run_child=False,
                supplied_queue=supplied_queue,
            )
            result = namespace["_parse_card_via_apify_with_timeout"](
                "https://example.invalid/map", timeout_sec=30,
            )
            expected = "apify_parser_subprocess_no_result" if queued_value is None else "apify_parser_subprocess_invalid_result"
            self.assertEqual(result.get("error"), expected)
            self._assert_resources_closed(resources)

    def test_ready_marker_with_empty_private_transport_returns_read_failure_and_cleans_up(self):
        supplied_queue = _Queue()
        supplied_queue.put({"transport_ready": True})
        namespace, _writes, resources = _namespace(
            lambda *_args, **_kwargs: {},
            run_child=False,
            supplied_queue=supplied_queue,
        )
        result = namespace["_parse_card_via_apify_with_timeout"](
            "https://example.invalid/map", timeout_sec=30,
        )
        self.assertEqual(result.get("error"), "apify_parser_subprocess_result_read_failed")
        self._assert_resources_closed(resources)

    def test_legacy_path_spoof_is_rejected_without_opening_the_path(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        spoofed_path = Path(directory.name) / "spoofed-result.json"
        spoofed_path.write_text(json.dumps({"title": MARKER}), encoding="utf-8")
        supplied_queue = _Queue()
        supplied_queue.put({"result_file_path": str(spoofed_path)})
        namespace, _writes, resources = _namespace(
            lambda *_args, **_kwargs: {},
            run_child=False,
            supplied_queue=supplied_queue,
        )
        result = namespace["_parse_card_via_apify_with_timeout"](
            "https://example.invalid/map", timeout_sec=30,
        )
        self.assertEqual(result.get("error"), "apify_parser_subprocess_result_read_failed")
        self.assertNotIn((spoofed_path, "r"), resources.open_calls)
        self._assert_resources_closed(resources)


if __name__ == "__main__":
    unittest.main()
