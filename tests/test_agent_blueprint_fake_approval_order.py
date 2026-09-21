"""Keep the approval cursor double aligned with the runner's actual SQL."""

import ast
from datetime import datetime, timedelta, timezone
from pathlib import Path
import unittest

from tests.agent_blueprint_fakes import FakeCursor


RUNNER_SOURCE = Path(__file__).resolve().parents[1] / "src/services/agent_blueprint_runner.py"


def _runner_sql(method_name, prefix):
    tree = ast.parse(RUNNER_SOURCE.read_text())
    runner = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "AgentBlueprintRunner")
    method = next(node for node in runner.body if isinstance(node, ast.FunctionDef) and node.name == method_name)
    matches = [
        node.value
        for node in ast.walk(method)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and " ".join(node.value.split()).lower().startswith(prefix)
    ]
    assert len(matches) == 1
    return matches[0]


class FakeApprovalOrderTests(unittest.TestCase):
    def setUp(self):
        self.cursor = FakeCursor()
        self.now = datetime(2026, 9, 21, 8, 0, tzinfo=timezone.utc)
        self.query = _runner_sql("_approved_draft_snapshot", "select * from agent_approvals")
        self.assertIn("order by decided_at desc, id desc limit 1", " ".join(self.query.split()).lower())

    def approval(self, approval_id, decided_at, **overrides):
        row = {
            "id": approval_id,
            "run_id": "run-1",
            "approval_type": "drafts",
            "status": "approved",
            "decided_at": decided_at,
            **overrides,
        }
        self.cursor.tables["agent_approvals"][approval_id] = row
        return row

    def selected(self, run_id="run-1"):
        self.cursor.execute(self.query, (run_id,))
        return self.cursor.fetchone()

    def test_decision_time_wins_over_insertion_order_and_id(self):
        latest = self.approval("approval-1", self.now)
        self.approval("approval-9", self.now - timedelta(minutes=1))
        self.assertIs(self.selected(), latest)

    def test_equal_decision_times_use_descending_id(self):
        highest_id = self.approval("approval-9", self.now)
        self.approval("approval-1", self.now)
        self.assertIs(self.selected(), highest_id)

    def test_filters_run_type_and_status_before_ordering(self):
        expected = self.approval("approval-1", self.now)
        self.approval("foreign-run", None, run_id="run-2")
        self.approval("different-type", None, approval_type="shortlist")
        self.approval("still-pending", None, status="pending")
        self.approval("rejected", None, status="rejected")
        self.assertIs(self.selected(), expected)

    def test_no_match_clears_previous_result(self):
        expected = self.approval("approval-1", self.now)
        self.assertIs(self.selected(), expected)
        self.assertIsNone(self.selected("missing-run"))

    def test_null_decision_time_keeps_postgres_desc_nulls_first(self):
        legacy = self.approval("approval-1", None)
        self.approval("approval-9", self.now)
        self.assertIs(self.selected(), legacy)

    def test_missing_legacy_time_is_null_and_equal_nulls_use_id(self):
        legacy = self.approval("approval-9", None)
        legacy.pop("decided_at")
        self.approval("approval-1", None)
        self.assertIs(self.selected(), legacy)

    def test_approval_update_records_time_used_by_selection(self):
        approved = self.approval("approval-1", None, status="pending")
        self.approval("approval-9", self.now - timedelta(days=1))
        query = _runner_sql("approve", "update agent_approvals")
        self.assertIn("decided_at = now()", " ".join(query.split()).lower())
        before = datetime.now(timezone.utc)
        self.cursor.execute(query, ("owner-1", "reviewed", approved["id"], "run-1"))
        after = datetime.now(timezone.utc)
        self.assertIsInstance(approved.get("decided_at"), datetime)
        self.assertEqual(approved["decided_at"].utcoffset(), timedelta(0))
        self.assertLessEqual(before, approved["decided_at"])
        self.assertLessEqual(approved["decided_at"], after)
        self.assertEqual(approved["status"], "approved")
        self.assertEqual(approved["decided_by_user_id"], "owner-1")
        self.assertEqual(approved["decision_reason"], "reviewed")
        self.assertIs(self.selected(), approved)

    def test_approval_update_does_not_touch_foreign_or_missing_row(self):
        pending = self.approval("approval-1", None, status="pending")
        original = pending.copy()
        query = _runner_sql("approve", "update agent_approvals")
        for approval_id, run_id in [("approval-1", "run-2"), ("missing", "run-1")]:
            with self.subTest(approval_id=approval_id, run_id=run_id):
                self.cursor.execute(query, ("owner-1", "reviewed", approval_id, run_id))
                self.assertEqual(pending, original)
