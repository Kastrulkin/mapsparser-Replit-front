#!/usr/bin/env python3
"""Run an allowlisted, single-container integration slice after review."""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
from pathlib import Path
import platform
import re
import runpy
import shutil
import signal
import subprocess
import sys
import time


SUPPORT = Path(__file__).resolve().parent
BASE = Path("/private/tmp/localos-readiness-20260921.hfLYPi")
SOURCE = BASE / "source"
NATIVE = BASE / "native"
EVIDENCE = NATIVE / "evidence"
VENV = NATIVE / "venv/bin/python"
PROFILES = {
    "card-growth-v1": {
        "target": "tests/test_card_growth_migration_pg.py::test_card_growth_schema_is_available_after_migrations",
        "count": 1,
        "prefix": "native-tc-one",
    },
    "client-info-v1": {"target": "tests/test_client_info_gate.py", "count": 8, "prefix": "native-tc-client-info"},
    "capabilities-phase1-v1": {
        "targets": [
            "tests/test_capabilities_api_phase1.py::test_capabilities_execute_returns_pending_human",
            "tests/test_capabilities_api_phase1.py::test_agent_capability_registry_is_business_scoped_and_redacted",
            "tests/test_capabilities_api_phase1.py::test_capabilities_execute_is_idempotent_for_same_key",
            "tests/test_capabilities_api_phase1.py::test_capabilities_decision_rejected_and_status_endpoint",
            "tests/test_capabilities_api_phase1.py::test_capabilities_execute_rejects_tenant_mismatch",
            "tests/test_capabilities_api_phase1.py::test_capabilities_action_auto_expires_by_ttl",
            "tests/test_capabilities_api_phase1.py::test_capabilities_actions_list_returns_items",
            "tests/test_capabilities_api_phase1.py::test_capabilities_action_billing_completed_rejected_expired",
            "tests/test_capabilities_api_phase1.py::test_openclaw_execute_requires_token",
            "tests/test_capabilities_api_phase1.py::test_openclaw_execute_pending_human_with_valid_token",
            "tests/test_capabilities_api_phase1.py::test_openclaw_capabilities_catalog_requires_token",
            "tests/test_capabilities_api_phase1.py::test_openclaw_capabilities_health_requires_token",
            "tests/test_capabilities_api_phase1.py::test_openclaw_capabilities_health_with_valid_token",
            "tests/test_capabilities_api_phase1.py::test_openclaw_callbacks_outbox_replay_requires_token",
            "tests/test_capabilities_api_phase1.py::test_openclaw_callbacks_outbox_replay_and_cleanup_with_valid_token",
            "tests/test_capabilities_api_phase1.py::test_openclaw_capabilities_health_trend_with_valid_token",
            "tests/test_capabilities_api_phase1.py::test_openclaw_billing_reconcile_requires_token",
            "tests/test_capabilities_api_phase1.py::test_openclaw_billing_reconcile_with_valid_token",
            "tests/test_capabilities_api_phase1.py::test_user_capabilities_health_trend_authorized",
            "tests/test_capabilities_api_phase1.py::test_openclaw_action_status_and_billing_with_valid_token",
            "tests/test_capabilities_api_phase1.py::test_openclaw_actions_list_with_valid_token",
            "tests/test_capabilities_api_phase1.py::test_openclaw_action_decision_rejected_with_valid_token",
            "tests/test_capabilities_api_phase1.py::test_openclaw_callbacks_dispatch_requires_token",
            "tests/test_capabilities_api_phase1.py::test_openclaw_callbacks_metrics_m2m_and_user",
            "tests/test_capabilities_api_phase1.py::test_openclaw_capabilities_catalog_with_valid_token",
            "tests/test_capabilities_api_phase1.py::test_capabilities_news_generate_completed_and_persisted",
            "tests/test_capabilities_api_phase1.py::test_capabilities_news_generate_service_guard_uses_selected_service",
            "tests/test_capabilities_api_phase1.py::test_capabilities_sales_ingest_completed_and_persisted",
            "tests/test_capabilities_api_phase1.py::test_capabilities_appointments_create_and_cancel",
            "tests/test_capabilities_api_phase1.py::test_capabilities_reminders_send_completed",
            "tests/test_capabilities_api_phase1.py::test_capabilities_action_timeline_user_and_m2m",
            "tests/test_capabilities_api_phase1.py::test_capabilities_unified_audit_timeline_user_and_m2m",
            "tests/test_capabilities_api_phase1.py::test_capabilities_unified_audit_timeline_export_user_and_m2m",
            "tests/test_capabilities_api_phase1.py::test_capabilities_unified_audit_event_bundle_user_and_m2m",
            "tests/test_capabilities_api_phase1.py::test_openclaw_action_read_requires_token_and_uses_action_tenant",
            "tests/test_capabilities_api_phase1.py::test_openclaw_actions_list_requires_token_and_allows_unfiltered_read",
            "tests/test_capabilities_api_phase1.py::test_openclaw_action_decision_requires_token_and_uses_action_tenant",
            "tests/test_capabilities_api_phase1.py::test_openclaw_callback_outbox_retry_then_sent",
            "tests/test_capabilities_api_phase1.py::test_openclaw_callback_outbox_goes_to_dlq",
            "tests/test_capabilities_api_phase1.py::test_openclaw_callbacks_outbox_requires_tenant_and_token",
            "tests/test_capabilities_api_phase1.py::test_openclaw_callbacks_recovery_history_m2m",
            "tests/test_capabilities_api_phase1.py::test_openclaw_callbacks_recovery_history_export_m2m_markdown",
            "tests/test_capabilities_api_phase1.py::test_user_callbacks_dispatch_scoped_by_tenant",
            "tests/test_capabilities_api_phase1.py::test_user_callbacks_recovery_report_returns_report",
            "tests/test_capabilities_api_phase1.py::test_user_callbacks_recovery_history_returns_recent_runs",
            "tests/test_capabilities_api_phase1.py::test_user_callbacks_recovery_history_export_markdown",
            "tests/test_capabilities_api_phase1.py::test_user_support_export_markdown",
            "tests/test_capabilities_api_phase1.py::test_openclaw_support_export_json_with_action_snapshot",
            "tests/test_capabilities_api_phase1.py::test_user_support_export_send_records_history",
            "tests/test_capabilities_api_phase1.py::test_user_support_export_send_history_export_markdown",
            "tests/test_capabilities_api_phase1.py::test_openclaw_support_export_send_history_export_json",
            "tests/test_capabilities_api_phase1.py::test_callback_dispatch_signature_and_dedupe_guard",
            "tests/test_capabilities_api_phase1.py::test_channels_status_returns_channel_list",
            "tests/test_capabilities_api_phase1.py::test_channels_test_send_telegram_uses_routing",
            "tests/test_capabilities_api_phase1.py::test_channels_route_preview_returns_fallback_chain",
            "tests/test_capabilities_api_phase1.py::test_channels_auto_test_send_uses_routing",
            "tests/test_capabilities_api_phase1.py::test_channels_status_marks_maton_ready_when_bridge_enabled",
        ],
        "count": 57,
        "exact_nodeids": True,
        "prefix": "native-tc-capabilities-phase1",
    },
    "operator-service-creation-v1": {
        "target": "tests/test_operator_service_creation.py",
        "count": 28,
        "prefix": "native-tc-operator-service-creation",
        "bootstrap_postgres": True,
    },
    "operator-voice-pg-v1": {
        "target": "tests/test_operator_voice_pg.py",
        "count": 382,
        "prefix": "native-tc-operator-voice-pg",
        "bootstrap_postgres": True,
    },
    "operator-editorial-pg-v1": {
        "targets": [
            "tests/test_operator_editorial_pg.py",
            "tests/test_operator_post_rewrite_pg.py",
            "tests/test_operator_plan_revision_pg.py",
            "tests/test_operator_followups_pg.py",
        ],
        "count": 63,
        "prefix": "native-tc-operator-editorial-pg",
        "bootstrap_postgres": True,
    },
    "callback-recovery-pg-v1": {
        "target": "tests/test_action_orchestrator_callback_recovery_pg.py",
        "count": 14,
        "prefix": "native-tc-callback-recovery-pg",
        "bootstrap_postgres": True,
    },
    "work-review-rollback-v1": {
        "targets": [
            "tests/test_work_review_migration_rollback.py::test_empty_work_review_schema_downgrades_without_cascade",
            "tests/test_work_review_migration_rollback.py::test_work_review_data_blocks_downgrade_and_remains_present[reviewer]",
            "tests/test_work_review_migration_rollback.py::test_work_review_data_blocks_downgrade_and_remains_present[link]",
            "tests/test_work_review_migration_rollback.py::test_work_review_data_blocks_downgrade_and_remains_present[settings]",
            "tests/test_work_review_migration_rollback.py::test_work_review_data_blocks_downgrade_and_remains_present[journal_fields]",
            "tests/test_work_review_migration_rollback.py::test_work_review_data_blocks_downgrade_and_remains_present[work_journal_action]",
            "tests/test_work_review_migration_rollback.py::test_concurrent_writer_cannot_commit_between_guard_and_destructive_ddl",
        ],
        "count": 7,
        "exact_nodeids": True,
        "prefix": "native-tc-work-review-rollback",
    },
    "creator-portal-rollback-v1": {
        "targets": [
            "tests/test_creator_portal_migration_rollback.py::test_empty_creator_portal_schema_downgrades_without_cascade",
            "tests/test_creator_portal_migration_rollback.py::test_creator_portal_data_blocks_downgrade_and_remains_present[relationship]",
            "tests/test_creator_portal_migration_rollback.py::test_creator_portal_data_blocks_downgrade_and_remains_present[review_field]",
            "tests/test_creator_portal_migration_rollback.py::test_concurrent_portal_writer_cannot_commit_during_downgrade",
        ],
        "count": 4,
        "exact_nodeids": True,
        "prefix": "native-tc-creator-portal-rollback",
    },
    "creator-offer-rollback-v1": {
        "targets": [
            "tests/test_creator_offer_distribution_migration_rollback.py::test_empty_offer_distribution_schema_reverses",
            "tests/test_creator_offer_distribution_migration_rollback.py::test_populated_offer_distribution_blocks_and_retains_data[business_preference]",
            "tests/test_creator_offer_distribution_migration_rollback.py::test_populated_offer_distribution_blocks_and_retains_data[offer_preference]",
            "tests/test_creator_offer_distribution_migration_rollback.py::test_populated_offer_distribution_blocks_and_retains_data[distribution_run]",
            "tests/test_creator_offer_distribution_migration_rollback.py::test_populated_offer_distribution_blocks_and_retains_data[recipient]",
            "tests/test_creator_offer_distribution_migration_rollback.py::test_mutated_campaign_columns_block_downgrade[reviewed_by]",
            "tests/test_creator_offer_distribution_migration_rollback.py::test_mutated_campaign_columns_block_downgrade[reviewed_at]",
            "tests/test_creator_offer_distribution_migration_rollback.py::test_mutated_campaign_columns_block_downgrade[distribution_locked_at]",
            "tests/test_creator_offer_distribution_migration_rollback.py::test_standalone_offer_message_blocks_downgrade_and_is_retained",
            "tests/test_creator_offer_distribution_migration_rollback.py::test_existing_collaboration_message_survives_empty_distribution_downgrade",
            "tests/test_creator_offer_distribution_migration_rollback.py::test_concurrent_writer_cannot_commit_after_data_guard_before_drop",
        ],
        "count": 11,
        "exact_nodeids": True,
        "prefix": "native-tc-creator-offer-rollback",
    },
    "author-daily-gate-pg-v1": {
        "targets": [
            "tests/test_author_daily_gate.py::test_author_gate_query_executes_on_migrated_postgres",
            "tests/test_author_daily_gate.py::test_author_gate_null_predicates_are_conservative_on_postgres",
        ],
        "count": 2,
        "exact_nodeids": True,
        "prefix": "native-tc-author-daily-gate-pg",
    },
    "knowledge-schema-pg-v1": {"target": "tests/test_knowledge_layer.py::test_knowledge_schema_applies_on_postgres", "count": 1, "exact_nodeids": True, "prefix": "native-tc-knowledge-schema-pg"},
    "outreach-pain-library-pg-v1": {
        "targets": [
            "tests/test_outreach_human_language_gate.py::test_pain_library_refresh_executes_with_real_psycopg2",
            "tests/test_outreach_human_language_gate.py::test_language_retrieval_executes_with_real_psycopg2_without_vector",
        ],
        "count": 2,
        "exact_nodeids": True,
        "prefix": "native-tc-outreach-pain-library-pg",
    },
    "riderra-template-pg-v1": {
        "targets": [
            "tests/test_riderra_template_authorization.py::test_migrated_event_allowlist_accepts_snapshot_and_rejects_unknown",
            "tests/test_riderra_template_authorization.py::test_daily_company_cap_sql_executes_atomically_on_isolated_postgres",
            "tests/test_riderra_template_authorization.py::test_dispatch_claims_author_and_noncreator_riderra_on_isolated_postgres",
        ],
        "count": 3,
        "exact_nodeids": True,
        "prefix": "native-tc-riderra-template-pg",
    },
    "sales-room-proposal-race-pg-v1": {"target": "tests/test_sales_room_proposal_version_concurrency.py::test_concurrent_first_reads_create_one_proposal_version_without_errors", "count": 1, "exact_nodeids": True, "prefix": "native-tc-sales-room-proposal-race-pg"},
    "sales-room-deadlock-pg-v1": {"target": "tests/test_sales_rooms_concurrency.py::test_concurrent_public_sales_room_reads_do_not_deadlock", "count": 1, "exact_nodeids": True, "prefix": "native-tc-sales-room-deadlock-pg"},
    "telegram-shared-audience-pg-v1": {"target": "tests/test_telegram_research.py::test_shared_audience_decision_does_not_leak_between_businesses", "count": 1, "exact_nodeids": True, "prefix": "native-tc-telegram-shared-audience-pg"},
    "web-tracking-pg-v1": {"target": "tests/test_web_tracking_postgres.py::test_postgres_migration_idempotent_ingestion_and_tenant_isolation", "count": 1, "exact_nodeids": True, "prefix": "native-tc-web-tracking-pg"},
    "worker-captcha-pg-v1": {"target": "tests/test_worker_captcha_flow.py::test_worker_schedules_automatic_captcha_retry", "count": 1, "exact_nodeids": True, "prefix": "native-tc-worker-captcha-pg"},
    "worker-expired-pg-v1": {"target": "tests/test_worker_expired_flow.py::test_worker_marks_captcha_expired_after_ttl", "count": 1, "exact_nodeids": True, "prefix": "native-tc-worker-expired-pg"},
    "worker-resume-pg-v1": {"target": "tests/test_worker_resume_flow.py::test_worker_resume_clears_captcha_fields", "count": 1, "exact_nodeids": True, "prefix": "native-tc-worker-resume-pg"},
    "finance-import-transaction-pg-v1": {"target": "tests/test_finance_import_transaction_pg.py::test_concurrent_duplicate_does_not_poison_following_finance_import_row", "count": 1, "exact_nodeids": True, "prefix": "native-tc-finance-import-transaction-pg"},
    "service-compression-race-pg-v1": {"target": "tests/test_service_compression_apply_concurrency_pg.py::test_second_compression_apply_blocks_then_returns_idempotent_result", "count": 1, "exact_nodeids": True, "prefix": "native-tc-service-compression-race-pg"},
}
ROLLBACK_PROFILE_RULES = {
    "work-review-rollback-v1": {"database_pattern": r"work_review_rollback_[0-9a-f]{32}", "child_admissions": 14, "minimum_connections": 75, "cleanup_event": "work_review_database_cleanup_checked"},
    "creator-portal-rollback-v1": {"database_pattern": r"creator_portal_rollback_[0-9a-f]{32}", "child_admissions": 8, "minimum_connections": 54, "cleanup_event": "creator_portal_database_cleanup_checked"},
    "creator-offer-rollback-v1": {"database_pattern": r"creator_offer_rollback_[0-9a-f]{32}", "child_admissions": 21, "minimum_connections": 159, "cleanup_event": "creator_offer_database_cleanup_checked"},
}
SHARED_FIXTURE_PROFILE_RULES = {
    "author-daily-gate-pg-v1": {"minimum_connections": 3, "child_admissions": 1, "budget": 32},
    "knowledge-schema-pg-v1": {"minimum_connections": 2, "child_admissions": 1, "budget": 32},
    "outreach-pain-library-pg-v1": {"minimum_connections": 4, "child_admissions": 1, "budget": 32},
    "riderra-template-pg-v1": {"minimum_connections": 3, "child_admissions": 0, "budget": 32},
    "sales-room-proposal-race-pg-v1": {"minimum_connections": 5, "child_admissions": 1, "budget": 32},
    "sales-room-deadlock-pg-v1": {"minimum_connections": 4, "child_admissions": 1, "budget": 32},
    "telegram-shared-audience-pg-v1": {"minimum_connections": 2, "child_admissions": 1, "budget": 32},
    "web-tracking-pg-v1": {"minimum_connections": 5, "child_admissions": 4, "budget": 32},
    "worker-captcha-pg-v1": {"minimum_connections": 4, "child_admissions": 1, "budget": 32},
    "worker-expired-pg-v1": {"minimum_connections": 4, "child_admissions": 1, "budget": 32},
    "worker-resume-pg-v1": {"minimum_connections": 4, "child_admissions": 1, "budget": 32},
    "finance-import-transaction-pg-v1": {"minimum_connections": 4, "child_admissions": 0, "budget": 32, "database_pattern": r"localos_data_fin_01_[0-9a-f]{32}", "cleanup_event": "finance_import_database_cleanup_checked"},
    "service-compression-race-pg-v1": {"minimum_connections": 8, "child_admissions": 1, "budget": 512, "database_pattern": r"service_compression_race_[0-9a-f]{32}", "cleanup_event": "service_compression_database_cleanup_checked"},
}
OPERATOR_VOICE_PROFILE_RULES = {
    "operator-voice-pg-v1": {
        "minimum_connections": 389,
        "budget": 512,
        "schema_pattern": r"voice_[0-9a-f]{32}",
        "cleanup_event": "operator_voice_schema_cleanup_checked",
    },
    "operator-editorial-pg-v1": {
        "minimum_connections": 62,
        "budget": 128,
        "schema_pattern": r"voice_[0-9a-f]{32}",
        "cleanup_event": "operator_voice_schema_cleanup_checked",
    },
}
CALLBACK_RECOVERY_PROFILE_RULES = {
    "callback-recovery-pg-v1": {
        "minimum_connections": 14,
        "budget": 512,
        "schema_pattern": r"callback_recovery_[0-9a-f]{32}",
        "cleanup_event": "callback_recovery_schema_cleanup_checked",
    },
}
OLD_GUARD_SHA256 = "07d3e2dc19cbb0f9e542a6d0835ea17b5efcc5713391c152a833e6efefd61150"
MIN_START = 5 * 1024**3
MIN_LIVE = 2 * 1024**3
MAX_RUNTIME = 300
NEGATIVE_CASES = {
    "external_tcp", "foreign_local", "udp", "dns", "postgres_foreign_host",
    "postgres_foreign_database", "postgres_explicit_options", "postgres_pghostaddr",
    "postgres_pgoptions", "postgres_pgservice",
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def attempt(value: str) -> str:
    if not re.fullmatch(r"v[1-9][0-9]*", value):
        raise argparse.ArgumentTypeError("attempt must be v followed by a positive integer")
    return value


def write_exclusive(path: Path, value: object) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        raw = json.dumps(value, indent=2, sort_keys=True).encode()
        written = 0
        while written < len(raw):
            count = os.write(descriptor, raw[written:])
            if count <= 0:
                raise RuntimeError("exclusive evidence write failed")
            written += count
    finally:
        os.close(descriptor)


def copy_exclusive(source: Path, destination: Path) -> str:
    if not source.is_file() or source.is_symlink() or destination.exists() or destination.is_symlink():
        raise RuntimeError(f"refusing noncanonical or existing runtime path: {destination}")
    source_bytes = source.read_bytes()
    descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        written = 0
        while written < len(source_bytes):
            count = os.write(descriptor, source_bytes[written:])
            if count <= 0:
                raise RuntimeError("runtime extra copy failed")
            written += count
    finally:
        os.close(descriptor)
    if digest(destination) != hashlib.sha256(source_bytes).hexdigest():
        raise RuntimeError("runtime extra hash mismatch")
    return hashlib.sha256(source_bytes).hexdigest()


def replace_guard(source: Path, destination: Path, backup: Path) -> str:
    if not destination.is_file() or destination.is_symlink() or digest(destination) != OLD_GUARD_SHA256:
        raise RuntimeError("frozen sitecustomize is not the reviewed v2 guard")
    if backup.exists() or backup.is_symlink():
        raise RuntimeError("guard backup already exists")
    old_bytes = destination.read_bytes()
    copy_exclusive(destination, backup)
    staged = destination.with_name(f".{destination.name}.{os.getpid()}.tc-stage")
    if staged.exists() or staged.is_symlink():
        raise RuntimeError("guard staging path already exists")
    try:
        copy_exclusive(source, staged)
        os.replace(staged, destination)
    finally:
        if staged.exists() and not staged.is_symlink():
            staged.unlink()
    if digest(destination) != digest(source) or digest(backup) != hashlib.sha256(old_bytes).hexdigest():
        raise RuntimeError("guard replacement or backup hash mismatch")
    return digest(destination)


def restore_guard(destination: Path, backup: Path) -> None:
    if not backup.is_file() or backup.is_symlink() or digest(backup) != OLD_GUARD_SHA256:
        raise RuntimeError("guard backup cannot restore reviewed v2 bytes")
    staged = destination.with_name(f".{destination.name}.{os.getpid()}.tc-restore")
    if staged.exists() or staged.is_symlink():
        raise RuntimeError("guard restore staging path already exists")
    try:
        copy_exclusive(backup, staged)
        os.replace(staged, destination)
    finally:
        if staged.exists() and not staged.is_symlink():
            staged.unlink()
    if digest(destination) != OLD_GUARD_SHA256:
        raise RuntimeError("guard restore hash mismatch")


def stop_process(process: subprocess.Popen[str]) -> tuple[str, str, str | None]:
    problem = None
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    except BaseException:
        error = sys.exception()
        problem = f"term:{type(error).__name__}"
    try:
        return (*process.communicate(timeout=5), problem)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        except BaseException:
            error = sys.exception()
            problem = f"{problem or 'kill'};kill:{type(error).__name__}"
        try:
            return (*process.communicate(timeout=5), problem)
        except BaseException:
            error = sys.exception()
            return "", f"cleanup capture: {type(error).__name__}: {error}", f"{problem or 'capture'};capture:{type(error).__name__}"


def result(command: list[str], environment: dict[str, str], timeout: int, deadline: float) -> dict[str, object]:
    started = time.monotonic()
    process = None
    stdout = ""
    stderr = ""
    stopped = None
    try:
        if started >= deadline or shutil.disk_usage(BASE).free < MIN_LIVE:
            stopped = "deadline_or_disk_floor_before_spawn"
            return {"command": command, "exit_code": None, "stdout": stdout, "stderr": stderr, "duration_seconds": round(time.monotonic() - started, 3), "timed_out": True, "stopped_reason": stopped}
        process = subprocess.Popen(command, cwd=SOURCE, env=environment, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
        while True:
            try:
                stdout, stderr = process.communicate(timeout=5)
                break
            except subprocess.TimeoutExpired:
                if time.monotonic() - started >= timeout or time.monotonic() >= deadline or shutil.disk_usage(BASE).free < MIN_LIVE:
                    stopped = "timeout_or_disk_floor"
                    stdout, stderr, cleanup = stop_process(process)
                    if cleanup is not None:
                        stopped = f"{stopped};{cleanup}"
                    break
    except BaseException:
        error = sys.exception()
        stopped = f"runner_error:{type(error).__name__}"
        stderr = str(error)
    finally:
        if process is not None and process.poll() is None:
            stdout, stderr, cleanup = stop_process(process)
            stopped = stopped or "runner_cleanup"
            if cleanup is not None:
                stopped = f"{stopped};{cleanup}"
    return {"command": command, "exit_code": process.returncode if process is not None else None, "stdout": stdout, "stderr": stderr, "duration_seconds": round(time.monotonic() - started, 3), "timed_out": stopped is not None, "stopped_reason": stopped}


def require_probe(payload: dict[str, object], mode: str, guard_hash: str) -> None:
    if payload.get("exit_code") != 0 or payload.get("timed_out") is True:
        raise RuntimeError(f"{mode} probe did not succeed")
    output = payload.get("stdout")
    if not isinstance(output, str):
        raise RuntimeError(f"{mode} probe output missing")
    proof = json.loads(output)
    if not isinstance(proof, dict) or proof.get("guard_sha256") != guard_hash:
        raise RuntimeError(f"{mode} probe guard identity differs")
    if mode == "negative":
        checks = proof.get("checks")
        observed = {(item.get("case"), item.get("denied")) for item in checks if isinstance(item, dict)} if isinstance(checks, list) else set()
        if observed != {(case, True) for case in NEGATIVE_CASES}:
            raise RuntimeError("negative probe did not deny the exact ten cases")
    else:
        child = proof.get("child")
        parent = proof.get("provenance")
        if proof.get("child_guard_propagated") is not True or not isinstance(child, dict) or not isinstance(parent, dict):
            raise RuntimeError("child propagation result missing")
        if child.get("sha256") != guard_hash or child.get("denied") is not True or child.get("bytecode_disabled") is not True or child.get("user_site_disabled") is not True or child.get("pid") == parent.get("pid"):
            raise RuntimeError("child proof does not establish guarded distinct process")


def plugin_source(target: str | list[str], bootstrap_postgres: bool = False, callback_recovery: bool = False) -> str:
    targets = [target] if isinstance(target, str) else target
    if not targets or not all(isinstance(item, str) for item in targets) or not isinstance(bootstrap_postgres, bool) or not isinstance(callback_recovery, bool):
        raise ValueError("literal pytest targets are required")
    return """
import json
import os
import pytest
import socket
import subprocess
import sys
from _pytest.subtests import SubtestReport
state = {'collected': None, 'nodeids': [], 'passed': 0, 'failed': 0, 'skipped': 0, 'xfailed': 0, 'setup_failed': 0, 'call_failed': 0, 'child_calls': [], 'subtests_passed': 0, 'subtests_failed': 0, 'subtests_skipped': 0, 'subtests_xfailed': 0}
class Results:
    def pytest_collection_finish(self, session):
        state['collected'] = len(session.items)
        state['nodeids'] = [item.nodeid for item in session.items]
    def pytest_runtest_logreport(self, report):
        if isinstance(report, SubtestReport):
            if report.passed: state['subtests_passed'] += 1
            if report.failed: state['subtests_failed'] += 1
            if report.skipped: state['subtests_skipped'] += 1
            if getattr(report, 'wasxfail', None): state['subtests_xfailed'] += 1
            return
        if report.when == 'call':
            if report.passed: state['passed'] += 1
            if report.failed: state['failed'] += 1; state['call_failed'] += 1
            if report.skipped: state['skipped'] += 1
            if getattr(report, 'wasxfail', None): state['xfailed'] += 1
        elif report.when == 'setup':
            if report.failed: state['failed'] += 1; state['setup_failed'] += 1
            if report.skipped: state['skipped'] += 1
    def pytest_sessionfinish(self, session, exitstatus):
        state['pytest_exitstatus'] = int(exitstatus)
container = None
try:
    if %r:
        from testcontainers.postgres import PostgresContainer
        if %r:
            inherited = {
                'DATABASE_URL': 'postgresql://test:test@127.0.0.1:35418/not_owned',
                'LOCALOS_HFLYPI_TC_CALLBACK_RECOVERY_DATABASE': 'readiness_full_test_' + '0' * 32,
                'LOCALOS_HFLYPI_TC_CALLBACK_RECOVERY_RELAY_PORT': '35418',
                'LOCALOS_HFLYPI_TC_CALLBACK_RECOVERY_MIGRATION_DSN': 'postgresql://test:test@127.0.0.1:35418/readiness_full_test_' + '0' * 32,
            }
            for key, value in inherited.items():
                os.environ[key] = value
                try:
                    PostgresContainer('pgvector/pgvector:0.8.0-pg16-trixie').start()
                except PermissionError:
                    pass
                else:
                    raise RuntimeError('callback inherited configuration was accepted: ' + key)
                finally:
                    del os.environ[key]
            import native_tc_adapter_hflypi
            native_tc_adapter_hflypi.record('callback_recovery_inherited_configuration_denials', keys=sorted(inherited))
        container = PostgresContainer('pgvector/pgvector:0.8.0-pg16-trixie')
        container.start()
    if %r:
        logical_dsn = os.environ['LOCALOS_CALLBACK_RECOVERY_TEST_DATABASE_URL']
        direct = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            direct.connect(('127.0.0.1', 35418))
        except PermissionError:
            pass
        else:
            raise RuntimeError('callback logical port was directly connectable')
        finally:
            direct.close()
        import psycopg2
        original_connect = psycopg2._connect
        def terminal_libpq(*args, **kwargs):
            raise RuntimeError('callback logical keyword override reached libpq')
        psycopg2._connect = terminal_libpq
        try:
            try:
                psycopg2.connect(logical_dsn, port=35418)
            except PermissionError:
                pass
            else:
                raise RuntimeError('callback logical keyword override was accepted')
            captured = []
            def capture_libpq(dsn, *args, **kwargs):
                captured.append((dsn, kwargs))
                raise RuntimeError('callback keyword-only capture complete')
            psycopg2._connect = capture_libpq
            try:
                psycopg2.connect(host='127.0.0.1', port=35418, dbname=logical_dsn.rsplit('/', 1)[1], user='test', password='test')
            except RuntimeError:
                error = sys.exception()
                if str(error) != 'callback keyword-only capture complete':
                    raise
            else:
                raise RuntimeError('callback keyword-only logical DSN did not reach intercepted libpq')
            captured_dsn = psycopg2.extensions.parse_dsn(str(captured[0][0])) if len(captured) == 1 else {}
            transport_overrides = {'host', 'port', 'dbname', 'database', 'user', 'password'}
            relay_port = os.environ['LOCALOS_HFLYPI_TC_CALLBACK_RECOVERY_RELAY_PORT']
            if len(captured) != 1 or captured_dsn.get('host') != '127.0.0.1' or captured_dsn.get('port') != relay_port or captured_dsn.get('dbname') != logical_dsn.rsplit('/', 1)[1] or captured_dsn.get('user') != 'test' or captured_dsn.get('password') != 'test' or transport_overrides.intersection(captured[0][1]):
                raise RuntimeError('callback keyword-only logical DSN was not normalized to the private relay')
        finally:
            psycopg2._connect = original_connect
        native_tc_adapter_hflypi.record('callback_recovery_negative_controls', direct_35418_denied=True, keyword_override_denied=True, keyword_only_rewritten=True)
        migration_dsn = native_tc_adapter_hflypi.prepare_callback_recovery_database()
        migration_env = dict(os.environ)
        migration_env['DATABASE_URL'] = migration_dsn
        migration_env['FLASK_APP'] = 'src.main:app'
        migration_env['LOCALOS_HFLYPI_TC_CALLBACK_RECOVERY_MIGRATION_DSN'] = migration_dsn
        migration = subprocess.run([sys.executable, '-m', 'flask', 'db', 'upgrade'], cwd=os.environ['LOCALOS_HFLYPI_SOURCE_ROOT'], env=migration_env, text=True, capture_output=True, timeout=90)
        if migration.returncode != 0:
            raise RuntimeError('callback recovery migration failed: ' + (migration.stderr or migration.stdout)[-1000:])
        native_tc_adapter_hflypi.verify_callback_recovery_migration()
    result = pytest.main(%r + ['-q', '-p', 'no:cacheprovider'], plugins=[Results()])
finally:
    if container is not None:
        container.stop()
state['pytest_return'] = int(result)
print('HFLYPI_TC_ONE_RESULT=' + json.dumps(state, sort_keys=True))
raise SystemExit(result)
""" % (bootstrap_postgres, callback_recovery, callback_recovery, targets)


def parse_test(payload: dict[str, object], profile: dict[str, object]) -> dict[str, object]:
    stdout = payload.get("stdout")
    if not isinstance(stdout, str):
        raise RuntimeError("test stdout missing")
    rows = [line for line in stdout.splitlines() if line.startswith("HFLYPI_TC_ONE_RESULT=")]
    if len(rows) != 1:
        raise RuntimeError("test result callback payload is missing")
    parsed = json.loads(rows[0].split("=", 1)[1])
    if not isinstance(parsed, dict):
        raise RuntimeError("test callback payload invalid")
    expected = {"collected": profile["count"], "passed": profile["count"], "failed": 0, "skipped": 0, "xfailed": 0, "setup_failed": 0, "call_failed": 0, "pytest_exitstatus": 0, "pytest_return": 0, "subtests_failed": 0, "subtests_skipped": 0, "subtests_xfailed": 0}
    if any(parsed.get(key) != value for key, value in expected.items()) or payload.get("exit_code") != 0 or payload.get("timed_out") is True:
        raise RuntimeError("unchanged native slice did not pass every expected node without skip")
    if not isinstance(parsed.get("subtests_passed"), int) or parsed["subtests_passed"] < 0:
        raise RuntimeError("native slice subtest accounting missing or invalid")
    nodeids = parsed.get("nodeids")
    targets = profile.get("targets", [profile.get("target")])
    if not isinstance(targets, list) or not targets or not all(isinstance(target, str) for target in targets):
        raise RuntimeError("native slice has no literal target allowlist")
    if not isinstance(nodeids, list) or len(nodeids) != profile["count"] or len(set(nodeids)) != len(nodeids):
        raise RuntimeError("native slice did not report unique expected nodes")
    if profile.get("exact_nodeids") is True:
        if set(nodeids) != set(targets):
            raise RuntimeError("native slice did not collect the exact literal nodes")
    elif not all(isinstance(node, str) and any(node == target or node.startswith(target + "::") for target in targets) for node in nodeids):
        raise RuntimeError("native slice collected a node outside its literal target")
    return parsed


def relay_evidence(profile: str, final: object) -> tuple[int, list[object]]:
    rollback_rule = ROLLBACK_PROFILE_RULES.get(profile)
    shared_rule = SHARED_FIXTURE_PROFILE_RULES.get(profile)
    voice_rule = OPERATOR_VOICE_PROFILE_RULES.get(profile)
    callback_rule = CALLBACK_RECOVERY_PROFILE_RULES.get(profile)
    expected_budget = 1024 if profile == "capabilities-phase1-v1" else 512 if rollback_rule is not None else voice_rule["budget"] if voice_rule is not None else callback_rule["budget"] if callback_rule is not None else shared_rule["budget"] if shared_rule is not None else 32
    minimum_connections = 171 if profile == "capabilities-phase1-v1" else rollback_rule["minimum_connections"] if rollback_rule is not None else voice_rule["minimum_connections"] if voice_rule is not None else callback_rule["minimum_connections"] if callback_rule is not None else shared_rule["minimum_connections"] if shared_rule is not None else 21 if profile == "operator-service-creation-v1" else 2
    if not isinstance(final, dict):
        raise RuntimeError("relay final evidence is invalid")
    connections = final.get("connections")
    executions = final.get("exec_results")
    if not isinstance(connections, int) or connections < minimum_connections or connections > expected_budget or final.get("connection_budget") != expected_budget or final.get("active") != 0 or final.get("rejections") != 0 or final.get("failures") != [] or not isinstance(executions, list) or len(executions) != connections:
        raise RuntimeError("relay did not meet the profile connection evidence bounds")
    return connections, executions


def cleanup_owned(events: Path, relay_module: object, containers_before: list[dict[str, object]]) -> dict[str, object]:
    if not events.is_file() or events.is_symlink():
        return {"attempted": False, "reason": "no-owned-event-journal"}
    rows = [json.loads(row) for row in events.read_text().splitlines() if row]
    created = [row for row in rows if isinstance(row, dict) and row.get("event") == "container_created"]
    starts = [row for row in rows if isinstance(row, dict) and row.get("event") == "start_requested"]
    container_id = created[0].get("container_id") if len(created) == 1 else None
    session = created[0].get("session_id") if len(created) == 1 else None
    recovered = False
    if container_id is None and len(starts) == 1:
        session = starts[0].get("session_id")
        before_ids = {row.get("id") for row in containers_before}
        candidates = [row for row in docker_snapshot() if row.get("id") not in before_ids]
        if len(candidates) == 1:
            container_id = candidates[0].get("id")
            recovered = True
        elif not candidates:
            return {"attempted": True, "already_removed": True, "recovered_from_start": True}
        else:
            raise RuntimeError("refusing cleanup because more than one new container exists")
    if len(created) > 1:
        raise RuntimeError("refusing cleanup because multiple owned-container events exist")
    if not isinstance(container_id, str) or not isinstance(session, str):
        return {"attempted": False, "reason": "invalid-owned-event"}
    verifier = getattr(relay_module, "verify_container", None)
    if not callable(verifier):
        raise RuntimeError("relay has no owned-container verifier")
    import docker
    client = docker.DockerClient(base_url="unix:///Users/alexdemyanov/.docker/run/docker.sock")
    try:
        try:
            container = client.containers.get(container_id)
        except docker.errors.NotFound:
            return {"attempted": True, "container_id": container_id, "already_removed": True, "recovered_from_start": recovered}
        verifier(container_id, session, require_running=False)
        container.remove(force=True, v=False)
        try:
            client.containers.get(container_id)
        except docker.errors.NotFound:
            return {"attempted": True, "container_id": container_id, "removed": True, "recovered_from_start": recovered}
        raise RuntimeError("owned Testcontainers container remains after forced removal")
    finally:
        client.close()


def remove_owned_capability(events: Path) -> dict[str, object]:
    if not events.is_file() or events.is_symlink():
        return {"removed": False, "reason": "no-event-journal"}
    rows = [json.loads(row) for row in events.read_text().splitlines() if row]
    created = [row for row in rows if isinstance(row, dict) and row.get("event") == "container_created"]
    relays = [row for row in rows if isinstance(row, dict) and row.get("event") == "relay_started"]
    if len(created) != 1 or len(relays) != 1:
        return {"removed": False, "reason": "no-single-owned-relay"}
    container_id = created[0].get("container_id")
    session = created[0].get("session_id")
    owner_pid = created[0].get("pid")
    path_raw = relays[0].get("capability_path")
    if not isinstance(container_id, str) or not isinstance(session, str) or not isinstance(owner_pid, int) or not isinstance(path_raw, str):
        raise RuntimeError("relay ownership event is malformed")
    path = Path(path_raw)
    directory = NATIVE / "capabilities"
    if path.parent != directory or path.is_symlink() or not path.exists():
        return {"removed": False, "reason": "capability-absent"}
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict) or payload.get("nonce") != "hfLYPi" or payload.get("parent_pid") != owner_pid or payload.get("container_id") != container_id or payload.get("session_id") != session:
        raise RuntimeError("capability is not bound to the recorded owned relay")
    path.unlink()
    return {"removed": True, "path": path.name}


def audit_journals(events: Path, relay_artifact: Path, profile: str) -> dict[str, object]:
    if not events.is_file() or events.is_symlink() or not relay_artifact.is_file() or relay_artifact.is_symlink():
        raise RuntimeError("Testcontainers event or relay journal is missing")
    event_rows = [json.loads(row) for row in events.read_text().splitlines() if row]
    relay_rows = [json.loads(row) for row in relay_artifact.read_text().splitlines() if row]
    if not all(isinstance(row, dict) for row in event_rows + relay_rows):
        raise RuntimeError("Testcontainers journal row is invalid")
    start = [row for row in event_rows if row.get("event") == "start_requested"]
    created = [row for row in event_rows if row.get("event") == "container_created"]
    relay_started = [row for row in event_rows if row.get("event") == "relay_started"]
    denials = [row for row in event_rows if row.get("event") == "capability_denials"]
    admitted = [row for row in event_rows if row.get("event") == "dsn_admitted"]
    removed = [row for row in event_rows if row.get("event") == "container_removed"]
    cleanup = [row for row in event_rows if row.get("event") == "cleanup"]
    if len(start) != 1 or len(created) != 1 or len(relay_started) != 1 or len(denials) != 1 or len(removed) != 1 or len(cleanup) != 1:
        raise RuntimeError("Testcontainers lifecycle journal is incomplete")
    parent_pid = start[0].get("pid")
    container_id = created[0].get("container_id")
    session = created[0].get("session_id")
    port = relay_started[0].get("port")
    if not isinstance(parent_pid, int) or not isinstance(container_id, str) or not isinstance(session, str) or not isinstance(port, int):
        raise RuntimeError("Testcontainers lifecycle identity is invalid")
    if start[0].get("session_id") != session or relay_started[0].get("container_id") != container_id:
        raise RuntimeError("Testcontainers start, container and relay identities differ")
    if not any(row.get("pid") == parent_pid and row.get("container_id") == container_id and row.get("port") == port for row in admitted):
        raise RuntimeError("parent process did not admit its relay DSN")
    shared_rule = SHARED_FIXTURE_PROFILE_RULES.get(profile)
    voice_rule = OPERATOR_VOICE_PROFILE_RULES.get(profile)
    callback_rule = CALLBACK_RECOVERY_PROFILE_RULES.get(profile)
    child_minimum = shared_rule["child_admissions"] if shared_rule is not None else 0 if profile in {"operator-service-creation-v1", "operator-voice-pg-v1", "operator-editorial-pg-v1"} else 1
    child_admitted = [row for row in admitted if row.get("pid") != parent_pid and row.get("container_id") == container_id and row.get("port") == port]
    if len(child_admitted) < child_minimum:
        raise RuntimeError("required Flask migration child admissions are incomplete")
    if child_minimum == 0 and child_admitted:
        raise RuntimeError("profile without Flask child admitted a child relay DSN")
    expected_denials = {"stale_expiry", "nonce", "session", "container", "wrong_port", "world_readable", "foreign_path", "symlink"}
    checks = denials[0].get("checks")
    observed_denials = {(row.get("case"), row.get("denied")) for row in checks if isinstance(row, dict)} if isinstance(checks, list) else set()
    if observed_denials != {(case, True) for case in expected_denials}:
        raise RuntimeError("capability denial evidence is incomplete")
    if cleanup[0].get("errors") != []:
        raise RuntimeError("Testcontainers adapter reported cleanup errors")
    bindings = [row for row in event_rows if row.get("event") == "parent_database_bound"]
    unbindings = [row for row in event_rows if row.get("event") == "parent_database_unbound"]
    voice_bindings = [row for row in event_rows if row.get("event") == "operator_voice_test_dsn_bound"]
    voice_unbindings = [row for row in event_rows if row.get("event") == "operator_voice_test_dsn_unbound"]
    rollback_rule = ROLLBACK_PROFILE_RULES.get(profile)
    if profile in {"client-info-v1", "capabilities-phase1-v1"}:
        if len(bindings) != 1 or len(unbindings) != 1 or bindings[0].get("pid") != parent_pid or bindings[0].get("port") != port or bindings[0].get("database") != "test" or unbindings[0].get("pid") != parent_pid:
            raise RuntimeError("parent Flask database configuration lifecycle is incomplete")
    elif bindings or unbindings:
        raise RuntimeError("unexpected parent Flask database configuration")
    if profile in {"operator-service-creation-v1", "operator-voice-pg-v1", "operator-editorial-pg-v1"}:
        if len(voice_bindings) != 1 or len(voice_unbindings) != 1 or voice_bindings[0].get("pid") != parent_pid or voice_bindings[0].get("port") != port or voice_bindings[0].get("database") != "test" or voice_unbindings[0].get("pid") != parent_pid:
            raise RuntimeError("operator voice test DSN lifecycle is incomplete")
    elif voice_bindings or voice_unbindings:
        raise RuntimeError("unexpected operator voice test DSN lifecycle")
    if voice_rule is not None:
        schema_cleanup = [row for row in event_rows if row.get("event") == voice_rule["cleanup_event"]]
        if len(schema_cleanup) != 1 or schema_cleanup[0].get("pid") != parent_pid or schema_cleanup[0].get("remaining") != 0:
            raise RuntimeError("operator voice disposable schema cleanup evidence is incomplete")
    elif any(row.get("event") in {rule["cleanup_event"] for rule in OPERATOR_VOICE_PROFILE_RULES.values()} for row in event_rows):
        raise RuntimeError("unexpected operator voice disposable schema cleanup evidence")
    callback_bindings = [row for row in event_rows if row.get("event") == "callback_recovery_test_dsn_bound"]
    callback_unbindings = [row for row in event_rows if row.get("event") == "callback_recovery_test_dsn_unbound"]
    if callback_rule is not None:
        if len(callback_bindings) != 1 or len(callback_unbindings) != 1:
            raise RuntimeError("callback recovery logical DSN lifecycle is incomplete")
        binding = callback_bindings[0]
        database = binding.get("database")
        if binding.get("pid") != parent_pid or binding.get("logical_port") != 35418 or binding.get("relay_port") != port or not isinstance(database, str) or re.fullmatch(r"readiness_full_test_[a-z0-9]{32}", database) is None:
            raise RuntimeError("callback recovery logical DSN identity is invalid")
        migrated = [row for row in event_rows if row.get("event") == "callback_recovery_database_migrated" and row.get("database") == database]
        inherited_denials = [row for row in event_rows if row.get("event") == "callback_recovery_inherited_configuration_denials" and row.get("keys") == ["DATABASE_URL", "LOCALOS_HFLYPI_TC_CALLBACK_RECOVERY_DATABASE", "LOCALOS_HFLYPI_TC_CALLBACK_RECOVERY_MIGRATION_DSN", "LOCALOS_HFLYPI_TC_CALLBACK_RECOVERY_RELAY_PORT"]]
        controls = [row for row in event_rows if row.get("event") == "callback_recovery_negative_controls" and row.get("direct_35418_denied") is True and row.get("keyword_override_denied") is True and row.get("keyword_only_rewritten") is True]
        schema_cleanup = [row for row in event_rows if row.get("event") == callback_rule["cleanup_event"] and row.get("remaining") == 0]
        database_cleanup = [row for row in event_rows if row.get("event") == "callback_recovery_database_cleanup_checked" and row.get("database") == database and row.get("remaining") == 0]
        rewrites = [row for row in admitted if row.get("purpose") == "callback_logical_rewrite" and row.get("database") == database]
        if len(migrated) != 1 or len(inherited_denials) != 1 or len(controls) != 1 or len(schema_cleanup) != 1 or len(database_cleanup) != 1 or len(rewrites) < callback_rule["minimum_connections"]:
            raise RuntimeError("callback recovery migration, rewrite or cleanup evidence is incomplete")
    elif callback_bindings or callback_unbindings:
        raise RuntimeError("unexpected callback recovery logical DSN lifecycle")
    if rollback_rule is not None:
        databases = [row.get("database") for row in admitted]
        pattern = rollback_rule["database_pattern"]
        cleanup_event = rollback_rule["cleanup_event"]
        generated = {database for database in databases if isinstance(database, str) and re.fullmatch(pattern, database)}
        parent_admin = [row for row in admitted if row.get("pid") == parent_pid and row.get("database") == "postgres"]
        child_generated = [row for row in admitted if row.get("pid") != parent_pid and isinstance(row.get("database"), str) and re.fullmatch(pattern, row["database"])]
        cleanup = [row for row in event_rows if row.get("event") == cleanup_event]
        if len(generated) != 1 or len(parent_admin) != 2 or len(child_generated) < rollback_rule["child_admissions"] or len(cleanup) != 1 or cleanup[0].get("pid") != parent_pid or cleanup[0].get("remaining") != 0:
            raise RuntimeError("rollback disposable database lifecycle evidence is incomplete")
    elif any(row.get("event") in {rule["cleanup_event"] for rule in ROLLBACK_PROFILE_RULES.values()} for row in event_rows):
        raise RuntimeError("unexpected rollback disposable database cleanup evidence")
    if shared_rule is not None and "database_pattern" in shared_rule:
        pattern = shared_rule["database_pattern"]
        generated = {row.get("database") for row in admitted if isinstance(row.get("database"), str) and re.fullmatch(pattern, row["database"])}
        parent_admin = [row for row in admitted if row.get("pid") == parent_pid and row.get("database") == "postgres"]
        child_generated = [row for row in child_admitted if isinstance(row.get("database"), str) and re.fullmatch(pattern, row["database"])]
        cleanup_event = shared_rule["cleanup_event"]
        profile_cleanup = [row for row in event_rows if row.get("event") == cleanup_event]
        if len(generated) != 1 or len(parent_admin) != 2 or len(child_generated) < shared_rule["child_admissions"] or len(profile_cleanup) != 1 or profile_cleanup[0].get("pid") != parent_pid or profile_cleanup[0].get("remaining") != 0:
            raise RuntimeError("named disposable database lifecycle evidence is incomplete")
    elif shared_rule is not None and any(row.get("event") in {rule["cleanup_event"] for rule in SHARED_FIXTURE_PROFILE_RULES.values() if "cleanup_event" in rule} for row in event_rows):
        raise RuntimeError("unexpected named disposable database cleanup evidence")
    final = relay_rows[-1] if relay_rows else {}
    connections, executions = relay_evidence(profile, final)
    if not all(isinstance(row, dict) and row.get("returncode") == 0 and row.get("exit_mode") == "graceful" and row.get("stderr_bytes") == 0 for row in executions):
        raise RuntimeError("relay Docker exec evidence is incomplete")
    return {"event_rows": len(event_rows), "relay_rows": len(relay_rows), "connections": connections, "flask_child_dsn_admitted": bool(child_admitted), "operator_voice_dsn_admitted": profile in {"operator-service-creation-v1", "operator-voice-pg-v1", "operator-editorial-pg-v1"}, "operator_voice_schema_cleanup_checked": voice_rule is not None, "callback_recovery_logical_dsn_rewrite_checked": callback_rule is not None, "callback_recovery_schema_and_database_cleanup_checked": callback_rule is not None, "rollback_disposable_database_checked": rollback_rule is not None, "named_disposable_database_checked": shared_rule is not None and "database_pattern" in shared_rule, "work_review_disposable_database_checked": profile == "work-review-rollback-v1"}


def require_empty_network(relay_module: object) -> dict[str, object]:
    network_id = getattr(relay_module, "NETWORK_ID", "")
    network_name = getattr(relay_module, "NETWORK_NAME", "")
    if not isinstance(network_id, str) or not isinstance(network_name, str):
        raise RuntimeError("relay network identity is unavailable")
    import docker
    client = docker.DockerClient(base_url="unix:///Users/alexdemyanov/.docker/run/docker.sock")
    try:
        attrs = client.api.inspect_network(network_id)
    finally:
        client.close()
    if not isinstance(attrs, dict) or attrs.get("Id") != network_id or attrs.get("Name") != network_name or attrs.get("Containers") != {}:
        raise RuntimeError("owned internal network is not empty after the node")
    return {"network_id": network_id, "empty": True}


def docker_snapshot() -> list[dict[str, object]]:
    import docker
    client = docker.DockerClient(base_url="unix:///Users/alexdemyanov/.docker/run/docker.sock")
    try:
        rows = []
        for container in client.containers.list(all=True):
            rows.append({"id": container.id, "name": container.name, "running": container.status == "running"})
        return sorted(rows, key=lambda row: str(row["id"]))
    finally:
        client.close()


def capabilities_snapshot() -> list[str]:
    directory = NATIVE / "capabilities"
    if not directory.exists():
        return []
    if not directory.is_dir() or directory.is_symlink():
        raise RuntimeError("capability directory is not canonical")
    return sorted(path.name for path in directory.iterdir())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attempt", required=True, type=attempt)
    parser.add_argument("--profile", choices=tuple(PROFILES), default="card-growth-v1")
    values = parser.parse_args()
    name = values.attempt
    profile = PROFILES[values.profile]
    prefix = profile["prefix"]
    launcher = runpy.run_path(str(SUPPORT / "native_guard_checks_hflypi.py"))
    destination = EVIDENCE / f"{prefix}-{name}.json"
    journal = EVIDENCE / f"{prefix}-{name}-events.jsonl"
    relay_artifact = EVIDENCE / f"{prefix}-{name}-relay.json"
    probe_artifacts = {mode: EVIDENCE / f"{prefix}-{name}-{mode}.json" for mode in ("negative", "child")}
    backup = NATIVE / f"sitecustomize-before-{prefix}-{name}.py"
    source_guard = SUPPORT / "native_hflypi_sitecustomize.py"
    source_adapter = SUPPORT / "native_tc_adapter_hflypi.py"
    source_relay = SUPPORT / "native_tc_relay_hflypi.py"
    targets = {source_adapter: SOURCE / "src/native_tc_adapter_hflypi.py", source_relay: SOURCE / "src/native_tc_relay_hflypi.py"}
    started = time.monotonic()
    selected_targets = profile.get("targets", [profile.get("target")])
    if not isinstance(selected_targets, list) or not selected_targets or not all(isinstance(target, str) for target in selected_targets):
        raise RuntimeError("profile has no literal test targets")
    output: dict[str, object] = {"attempt": name, "profile": values.profile, "nodes": selected_targets, "expected_count": profile["count"], "phase": "preflight"}
    installed: list[Path] = []
    guard_installed = False
    relay_module = None
    containers_before: list[dict[str, object]] = []
    capabilities_before: list[str] = []
    try:
        if platform.machine() != "arm64":
            raise RuntimeError("native Testcontainers node requires arm64 parent")
        if destination.exists() or destination.is_symlink() or journal.exists() or journal.is_symlink() or relay_artifact.exists() or relay_artifact.is_symlink() or any(path.exists() or path.is_symlink() for path in probe_artifacts.values()):
            raise RuntimeError("attempt evidence path already exists")
        if shutil.disk_usage(BASE).free < MIN_START:
            raise RuntimeError("native Testcontainers node requires 5 GiB free")
        launcher["verify_endpoints"]()
        output["frozen_blobs_before"] = launcher["verify_frozen_source"]()
        if output["frozen_blobs_before"] != 5720:
            raise RuntimeError("unexpected frozen blob count")
        containers_before = docker_snapshot()
        capabilities_before = capabilities_snapshot()
        output["unrelated_containers_before"] = containers_before
        output["capabilities_before"] = capabilities_before
        for source in (source_guard, source_adapter, source_relay):
            if not source.is_file() or source.is_symlink():
                raise RuntimeError("required reviewed support source is absent")
        guard_hash = replace_guard(source_guard, SOURCE / "src/sitecustomize.py", backup)
        guard_installed = True
        hashes = {"guard": guard_hash, "support_guard": digest(source_guard), "launcher": digest(Path(__file__))}
        for source, target in targets.items():
            hashes[target.stem] = copy_exclusive(source, target)
            installed.append(target)
        output["hashes"] = hashes
        descriptor = os.open(journal, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.close(descriptor)
        environment = launcher["environment"](guard_hash)
        environment.pop("LOCALOS_HFLYPI_PROBE_DSN", None)
        environment.update({
            "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1", "LOCALOS_HFLYPI_TC_MODE": values.profile,
            "LOCALOS_HFLYPI_TC_ADAPTER_SHA256": hashes["native_tc_adapter_hflypi"],
            "LOCALOS_HFLYPI_TC_RELAY_SHA256": hashes["native_tc_relay_hflypi"],
            "LOCALOS_HFLYPI_TC_GUARD_SHA256": guard_hash,
            "LOCALOS_HFLYPI_TC_JOURNAL": str(journal),
        })
        probe = NATIVE / "native_hflypi_probe_v1.py"
        support_probe = SUPPORT / "native_hflypi_probe.py"
        if not probe.is_file() or probe.is_symlink() or not support_probe.is_file() or support_probe.is_symlink() or digest(probe) != digest(support_probe):
            raise RuntimeError("pinned native probe is absent")
        output["hashes"]["probe"] = digest(probe)
        for mode in ("negative", "child"):
            capture = result(["/usr/bin/arch", "-arm64", str(VENV), "-B", str(probe), mode], environment, 40, started + MAX_RUNTIME)
            output[f"{mode}_probe"] = capture
            write_exclusive(probe_artifacts[mode], capture)
            require_probe(capture, mode, guard_hash)
        if shutil.disk_usage(BASE).free < MIN_LIVE:
            raise RuntimeError("disk floor reached before native node")
        output["phase"] = "test"
        capture = result(["/usr/bin/arch", "-arm64", str(VENV), "-B", "-c", plugin_source(selected_targets, profile.get("bootstrap_postgres", False), values.profile == "callback-recovery-pg-v1")], environment, MAX_RUNTIME, started + MAX_RUNTIME)
        output["test"] = capture
        output["test_callbacks"] = parse_test(capture, profile)
        output["journals"] = audit_journals(journal, relay_artifact, values.profile)
        if str(SOURCE / "src") not in sys.path:
            sys.path.insert(0, str(SOURCE / "src"))
        relay_module = importlib.import_module("native_tc_relay_hflypi")
        output["network_after_test"] = require_empty_network(relay_module)
        output["phase"] = "passed"
    except BaseException:
        error = sys.exception()
        output["phase"] = "failed"
        output["error"] = f"{type(error).__name__}: {error}"
    finally:
        try:
            if str(SOURCE / "src") not in sys.path:
                sys.path.insert(0, str(SOURCE / "src"))
            relay_module = importlib.import_module("native_tc_relay_hflypi")
            output["owned_cleanup"] = cleanup_owned(journal, relay_module, containers_before)
            output["capability_cleanup"] = remove_owned_capability(journal)
            output["network_after_cleanup"] = require_empty_network(relay_module)
            if capabilities_snapshot() != capabilities_before:
                raise RuntimeError("Testcontainers capability files remain after cleanup")
            containers_after = docker_snapshot()
            output["unrelated_containers_after"] = containers_after
            if containers_after != containers_before:
                raise RuntimeError("unrelated Docker container identity changed")
        except BaseException:
            error = sys.exception()
            output["owned_cleanup_error"] = f"{type(error).__name__}: {error}"
            output["phase"] = "failed"
        try:
            if guard_installed:
                if digest(SOURCE / "src/sitecustomize.py") != output.get("hashes", {}).get("guard"):
                    raise RuntimeError("refusing to restore over an unknown guard replacement")
                restore_guard(SOURCE / "src/sitecustomize.py", backup)
            for target in installed:
                expected = output.get("hashes", {}).get(target.stem)
                if not isinstance(expected, str) or not target.is_file() or target.is_symlink() or digest(target) != expected:
                    raise RuntimeError("refusing to delete an unknown runtime extra")
                target.unlink()
            output["frozen_blobs_after"] = launcher["verify_frozen_source"]()
            if output["frozen_blobs_after"] != 5720:
                raise RuntimeError("frozen blob count changed after cleanup")
        except BaseException:
            error = sys.exception()
            output["restore_error"] = f"{type(error).__name__}: {error}"
            output["phase"] = "failed"
        output["duration_seconds"] = round(time.monotonic() - started, 3)
        output["free_bytes_after"] = shutil.disk_usage(BASE).free
        write_exclusive(destination, output)
    return 0 if output.get("phase") == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
