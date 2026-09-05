"""Small explicit transaction boundary for new runtime code.

Legacy ``DatabaseManager.close`` commits for compatibility. New code should use
this helper when it needs an unambiguous commit/rollback boundary.
"""

from __future__ import annotations

from typing import Any

from database_manager import DatabaseManager


class UnitOfWork:
    """Own one database transaction and never commit it after an exception."""

    def __init__(self, database_factory=DatabaseManager) -> None:
        self.database = database_factory()
        self._finished = False

    @property
    def cursor(self) -> Any:
        if self._finished:
            raise RuntimeError("unit of work is already finished")
        return self.database.conn.cursor()

    def commit(self) -> None:
        if self._finished:
            raise RuntimeError("unit of work is already finished")
        self.database.conn.commit()
        self._finished = True

    def rollback(self) -> None:
        if self._finished:
            return
        self.database.conn.rollback()
        self._finished = True

    def __enter__(self) -> "UnitOfWork":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> bool:
        # A successful block still needs an explicit commit. This also discards
        # accidental writes through a retained cursor after a prior commit.
        self.database.rollback_and_close()
        self._finished = True
        return False
