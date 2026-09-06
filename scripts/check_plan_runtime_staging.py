#!/usr/bin/env python3
"""Exercise retired schema helpers on the real isolated staging migration chain."""
import json
import os
import uuid

import psycopg2


def main():
    if os.getenv("APP_ENV") != "staging" or os.getenv("POSTGRES_DB") != "localos_staging":
        raise RuntimeError("Only isolated localos_staging is supported")
    from database_manager import get_db_connection
    from api.prospecting.access_schema import _ensure_manual_crm_tables, _ensure_sales_room_tables
    from api.prospecting.audit_routes import _ensure_partnership_artifacts_table_from_cursor
    from core.action_ledger import ensure_ledger_tables
    from core.action_orchestrator import ActionOrchestrator
    from core.industry_pattern_recalibration import ensure_industry_pattern_tables
    from api.wordstat_api import _ensure_excluded_table, _ensure_custom_table, _ensure_negative_table
    from services.agent_capability_handlers import (
        _ensure_communication_request_table, _ensure_service_optimization_request_table,
        _ensure_review_reply_draft_table, _ensure_sheet_operation_request_table,
    )
    connection = get_db_connection()
    cursor = connection.cursor()
    role = "localos_plan_dml_proof_" + uuid.uuid4().hex
    cursor.execute(f'CREATE ROLE "{role}" NOLOGIN')
    cursor.execute(f'GRANT USAGE ON SCHEMA public TO "{role}"')
    cursor.execute(f'GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA public TO "{role}"')
    connection.commit()
    try:
        cursor.execute(f'SET ROLE "{role}"')
        for query in ("CREATE TABLE forbidden_plan_ddl(id INT)", "ALTER TABLE prospectingleads ADD COLUMN forbidden_plan INT", "DROP TABLE prospectingleads"):
            cursor.execute("SAVEPOINT permission_probe")
            try:
                cursor.execute(query)
            except psycopg2.errors.InsufficientPrivilege:
                cursor.execute("ROLLBACK TO SAVEPOINT permission_probe")
            else:
                raise AssertionError("DML proof role unexpectedly has DDL authority")
        cursor.execute("SAVEPOINT caller_work")
        _ensure_manual_crm_tables(connection)
        _ensure_sales_room_tables(connection)
        _ensure_partnership_artifacts_table_from_cursor(cursor)
        ensure_ledger_tables(cursor)
        checker = ActionOrchestrator({})
        checker.ensure_tables(cursor)
        ensure_industry_pattern_tables(connection)
        for helper in (_ensure_excluded_table, _ensure_custom_table, _ensure_negative_table,
                       _ensure_communication_request_table, _ensure_service_optimization_request_table,
                       _ensure_review_reply_draft_table, _ensure_sheet_operation_request_table):
            helper(cursor)
        cursor.execute("ROLLBACK TO SAVEPOINT caller_work")
        cursor.execute("SELECT version_num FROM alembic_version")
        row = cursor.fetchone()
        revision = row.get("version_num") if hasattr(row, "get") else row[0]
        print(json.dumps({"status": "passed", "revision": revision, "ddl_denied": ["CREATE", "ALTER", "DROP"],
                          "runtime_helpers": 13, "caller_savepoint_preserved": True}))
    finally:
        connection.rollback()
        cursor.execute("RESET ROLE")
        cursor.execute(f'DROP OWNED BY "{role}"')
        cursor.execute(f'DROP ROLE "{role}"')
        connection.commit()
        connection.close()


if __name__ == "__main__":
    main()
