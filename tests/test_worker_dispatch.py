import worker


def test_special_queue_dispatch_uses_registered_handler(monkeypatch):
    calls = []

    def handle(queue_dict):
        calls.append(queue_dict["id"])

    monkeypatch.setattr(worker, "_special_queue_handlers", lambda: {"reviews_delta": handle})

    handled = worker._dispatch_special_queue_task(
        {"id": "task-1", "task_type": "reviews_delta"}
    )

    assert handled is True
    assert calls == ["task-1"]


def test_special_queue_dispatch_leaves_parse_card_for_main_executor(monkeypatch):
    monkeypatch.setattr(worker, "_special_queue_handlers", lambda: {})

    handled = worker._dispatch_special_queue_task(
        {"id": "task-2", "task_type": "parse_card"}
    )

    assert handled is False


def test_unimplemented_google_sync_is_settled_as_error(monkeypatch):
    errors = []
    monkeypatch.setattr(worker, "_special_queue_handlers", lambda: {})
    monkeypatch.setattr(
        worker,
        "_handle_worker_error",
        lambda task_id, message: errors.append((task_id, message)),
    )

    handled = worker._dispatch_special_queue_task(
        {"id": "task-3", "task_type": "sync_google_business"}
    )

    assert handled is True
    assert errors == [
        ("task-3", "Тип задачи sync_google_business пока не реализован")
    ]


def test_process_queue_runs_claim_prepare_dispatch_execute_pipeline(monkeypatch):
    task = {"id": "task-4", "task_type": "parse_card"}
    stages = []

    monkeypatch.setattr(worker, "_claim_next_queue_task", lambda: task)
    monkeypatch.setattr(
        worker,
        "_prepare_queue_task",
        lambda claimed: (stages.append(("prepare", claimed["id"])) or (True, {"title": "ready"})),
    )
    monkeypatch.setattr(
        worker,
        "_dispatch_special_queue_task",
        lambda prepared: stages.append(("dispatch", prepared["id"])) or False,
    )
    monkeypatch.setattr(
        worker,
        "_execute_map_card_task",
        lambda prepared, card: stages.append(("execute", prepared["id"], card["title"])),
    )

    worker.process_queue()

    assert stages == [
        ("prepare", "task-4"),
        ("dispatch", "task-4"),
        ("execute", "task-4", "ready"),
    ]


def test_process_queue_stops_when_prepare_settles_retry(monkeypatch):
    task = {"id": "task-5", "task_type": "parse_card"}
    executed = []

    monkeypatch.setattr(worker, "_claim_next_queue_task", lambda: task)
    monkeypatch.setattr(worker, "_prepare_queue_task", lambda claimed: (False, None))
    monkeypatch.setattr(
        worker,
        "_dispatch_special_queue_task",
        lambda prepared: executed.append("dispatch") or False,
    )
    monkeypatch.setattr(
        worker,
        "_execute_map_card_task",
        lambda prepared, card: executed.append("execute"),
    )

    worker.process_queue()

    assert executed == []
