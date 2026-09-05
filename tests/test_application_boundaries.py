import ast
from pathlib import Path

from core.unit_of_work import UnitOfWork


class FakeDatabase:
    def __init__(self):
        self.conn = self
        self.commits = 0
        self.rollbacks = 0
    def commit(self):
        self.commits += 1
    def rollback_and_close(self):
        self.rollbacks += 1


def test_new_unit_of_work_requires_explicit_success_commit():
    unit = UnitOfWork(FakeDatabase)
    with unit:
        pass
    assert unit.database.commits == 0
    assert unit.database.rollbacks == 1
    committed = UnitOfWork(FakeDatabase)
    with committed:
        committed.commit()
    assert committed.database.commits == 1


def test_new_application_modules_do_not_depend_on_http_or_main():
    root = Path(__file__).parents[1] / "src"
    for path in (root/"core/auth_context.py",root/"services/today_preferences_service.py",root/"services/today_workspace.py",root/"services/compiled_script_runtime.py"):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            modules = [alias.name for alias in node.names] if isinstance(node,ast.Import) else [node.module or ""] if isinstance(node,ast.ImportFrom) else []
            assert not any(module.split('.')[0] in {"main","flask","api"} for module in modules), str(path)
