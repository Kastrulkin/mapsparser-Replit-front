"""Pure ownership controls. Fake process objects; no processes are signalled."""

import unittest
from types import SimpleNamespace

from content_performance_processes_20260922 import OwnedProcesses


class Missing(Exception):
    pass


class Denied(Exception):
    pass


class FakeProcess:
    def __init__(self, pid, born):
        self.pid = pid
        self.born = born
        self.alive = True
        self.descendants = []
        self.signals = []
        self.deny_observation = False

    def create_time(self):
        return self.born

    def is_running(self):
        return self.alive

    def status(self):
        return "running"

    def children(self, recursive):
        if self.deny_observation:
            raise Denied()
        return self.descendants

    def terminate(self):
        self.signals.append("terminate")
        self.alive = False

    def kill(self):
        self.signals.append("kill")
        self.alive = False


class FakeBackend:
    Error = (Missing, Denied)
    NoSuchProcess = Missing
    STATUS_ZOMBIE = "zombie"

    def __init__(self, processes):
        self.processes = {process.pid: process for process in processes}

    def Process(self, pid):
        if pid not in self.processes:
            raise Missing()
        return self.processes[pid]

    def wait_procs(self, processes, timeout):
        return [process for process in processes if not process.alive], [process for process in processes if process.alive]


class ProcessOwnership(unittest.TestCase):
    def setUp(self):
        self.root = FakeProcess(10, 1.0)
        self.child = FakeProcess(20, 2.0)
        self.root.descendants = [self.child]
        self.backend = FakeBackend([self.root, self.child])
        self.handle = SimpleNamespace(pid=10, poll=lambda: None)

    def test_reparented_child_is_retained_after_root_exit(self):
        registry = OwnedProcesses(self.handle, self.backend)
        registry.observe()
        self.root.alive = False
        result = registry.cleanup()
        self.assertEqual(result["status"], "clean")
        self.assertEqual(self.child.signals, ["terminate"])
        self.assertEqual(self.root.signals, [])

    def test_reused_pid_is_never_signalled(self):
        registry = OwnedProcesses(self.handle, self.backend)
        registry.observe()
        replacement = FakeProcess(20, 200.0)
        self.backend.processes[20] = replacement
        self.root.alive = False
        result = registry.cleanup()
        self.assertEqual(result["status"], "clean")
        self.assertEqual(self.child.signals, [])
        self.assertEqual(replacement.signals, [])

    def test_unrelated_process_is_not_discovered_or_signalled(self):
        outsider = FakeProcess(30, 3.0)
        self.backend.processes[30] = outsider
        registry = OwnedProcesses(self.handle, self.backend)
        registry.observe()
        result = registry.cleanup()
        self.assertEqual(result["remaining"], [])
        self.assertEqual(outsider.signals, [])
        self.assertTrue(outsider.alive)

    def test_observation_denial_is_not_a_cleanup_pass(self):
        registry = OwnedProcesses(self.handle, self.backend)
        self.root.deny_observation = True
        result = registry.cleanup()
        self.assertEqual(result["status"], "cleanup_failed")
        self.assertIn("final_observation_failed", result["errors"])

    def test_new_descendant_of_retained_child_is_owned(self):
        registry = OwnedProcesses(self.handle, self.backend)
        registry.observe()
        self.root.alive = False
        grandchild = FakeProcess(40, 4.0)
        self.backend.processes[40] = grandchild
        self.child.descendants = [grandchild]
        result = registry.cleanup()
        self.assertEqual(result["status"], "clean")
        self.assertEqual(grandchild.signals, ["terminate"])


if __name__ == "__main__":
    unittest.main()
