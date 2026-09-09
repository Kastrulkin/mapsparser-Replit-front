from __future__ import annotations

import ast
from pathlib import Path

import worker


def test_card_automation_is_cooperatively_capped_with_outreach(monkeypatch):
    monkeypatch.setenv("WORKER_ROLE", "all")
    monkeypatch.setenv("OUTREACH_DISPATCH_ENABLED", "true")
    monkeypatch.setenv("CARD_AUTOMATION_BATCH_SIZE", "20")

    assert worker._card_automation_batch_size() == 1


def test_card_automation_keeps_standalone_default_and_configured_lower(monkeypatch):
    monkeypatch.setenv("WORKER_ROLE", "all")
    monkeypatch.delenv("OUTREACH_DISPATCH_ENABLED", raising=False)
    monkeypatch.delenv("CARD_AUTOMATION_BATCH_SIZE", raising=False)

    assert worker._card_automation_batch_size() == 20

    monkeypatch.setenv("CARD_AUTOMATION_BATCH_SIZE", "7")
    assert worker._card_automation_batch_size() == 7


def test_card_automation_cap_only_applies_to_dispatcher_role(monkeypatch):
    monkeypatch.setenv("WORKER_ROLE", "parser")
    monkeypatch.setenv("OUTREACH_DISPATCH_ENABLED", "true")
    monkeypatch.setenv("CARD_AUTOMATION_BATCH_SIZE", "20")

    assert worker._card_automation_batch_size() == 20


def test_outreach_due_check_precedes_card_automation_in_dispatcher_loop():
    source = Path(worker.__file__).read_text(encoding="utf-8")
    module = ast.parse(source)
    main_guard = next(
        node
        for node in module.body
        if isinstance(node, ast.If)
        and isinstance(node.test, ast.Compare)
        and isinstance(node.test.left, ast.Name)
        and node.test.left.id == "__name__"
    )
    loop = next(node for node in main_guard.body if isinstance(node, ast.While))
    loop_try = next(node for node in loop.body if isinstance(node, ast.Try))
    dispatcher_guard = next(
        node
        for node in loop_try.body
        if isinstance(node, ast.If)
        and isinstance(node.test, ast.Call)
        and isinstance(node.test.func, ast.Name)
        and node.test.func.id == "_worker_role_enabled"
        and node.test.args
        and isinstance(node.test.args[0], ast.Constant)
        and node.test.args[0].value == "dispatcher"
    )
    calls = [
        node.value.func.id
        for node in dispatcher_guard.body
        if isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Name)
    ]

    assert calls.index("_dispatch_outreach_queue_if_due") < calls.index(
        "_run_card_automation_if_due"
    )
