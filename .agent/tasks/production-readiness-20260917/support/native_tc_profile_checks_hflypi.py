#!/usr/bin/env python3
"""Pure profile/result acceptance checks; no Docker, sockets or test startup."""

import ast
import json
from pathlib import Path
import re
import runpy
from types import SimpleNamespace


def check_parent_database() -> None:
    source = Path(__file__).with_name("native_tc_adapter_hflypi.py")
    names = {"deny", "bind_parent_database", "unbind_parent_database", "bind_operator_voice_test_dsn", "unbind_operator_voice_test_dsn"}
    tree = ast.parse(source.read_text())
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
    environment = {"LOCALOS_HFLYPI_TC_MODE": "client-info-v1", "LOCALOS_HFLYPI_TC_OWNER_PID": "42"}
    validated = []
    events = []
    namespace = {"os": SimpleNamespace(environ=environment, getpid=lambda: 42), "PREFIX": "LOCALOS_HFLYPI_TC_", "_database_url": None,
                 "PARENT_DATABASE_PROFILES": frozenset({"client-info-v1", "capabilities-phase1-v1"}),
                 "OPERATOR_VOICE_TEST_DSN_PROFILES": frozenset({"operator-service-creation-v1"}), "_operator_voice_test_dsn": None,
                 "validate_dsn": lambda parsed: validated.append(parsed), "record": lambda event, **fields: events.append(event)}
    exec(compile(ast.Module(body=functions, type_ignores=[]), str(source), "exec"), namespace)
    bind, unbind = namespace["bind_parent_database"], namespace["unbind_parent_database"]
    bind_voice, unbind_voice = namespace["bind_operator_voice_test_dsn"], namespace["unbind_operator_voice_test_dsn"]
    for key, value in (("DATABASE_URL", ""), ("DATABASE_URL", "foreign"), ("LOCALOS_HFLYPI_TC_OWNER_PID", "43")):
        previous = environment.get(key)
        environment[key] = value
        try:
            bind(12345)
        except PermissionError:
            pass
        else:
            raise AssertionError("foreign configuration was replaced")
        assert environment[key] == value and not validated
        if previous is None:
            del environment[key]
        else:
            environment[key] = previous
    def deny_capability(parsed):
        raise PermissionError("synthetic invalid capability")
    namespace["validate_dsn"] = deny_capability
    try:
        bind(12345)
    except PermissionError:
        pass
    else:
        raise AssertionError("invalid capability allowed parent configuration")
    assert "DATABASE_URL" not in environment and namespace["_database_url"] is None
    namespace["validate_dsn"] = lambda parsed: validated.append(parsed)
    for mode in ("client-info-v1", "capabilities-phase1-v1"):
        environment["LOCALOS_HFLYPI_TC_MODE"] = mode
        bind(12345)
        assert validated[-1] == {"host": "127.0.0.1", "port": "12345", "dbname": "test", "user": "test", "password": "test"}
        assert environment["DATABASE_URL"] == "postgresql://test:test@127.0.0.1:12345/test"
        environment["DATABASE_URL"] = "changed"
        try:
            unbind()
        except PermissionError:
            pass
        else:
            raise AssertionError("changed configuration was removed")
        assert environment["DATABASE_URL"] == "changed"
        environment["DATABASE_URL"] = namespace["_database_url"]
        unbind()
        assert "DATABASE_URL" not in environment and namespace["_database_url"] is None
    assert events == ["parent_database_bound", "parent_database_unbound"] * 2
    environment["LOCALOS_HFLYPI_TC_MODE"] = "card-growth-v1"
    bind(12345)
    assert "DATABASE_URL" not in environment and len(validated) == 2
    environment["LOCALOS_HFLYPI_TC_MODE"] = "operator-service-creation-v1"
    for value in ("", "foreign"):
        environment["OPERATOR_VOICE_TEST_DSN"] = value
        try:
            bind_voice(12345)
        except PermissionError:
            pass
        else:
            raise AssertionError("foreign operator voice DSN was replaced")
        assert environment["OPERATOR_VOICE_TEST_DSN"] == value and namespace["_operator_voice_test_dsn"] is None
        del environment["OPERATOR_VOICE_TEST_DSN"]
    namespace["validate_dsn"] = deny_capability
    try:
        bind_voice(12345)
    except PermissionError:
        pass
    else:
        raise AssertionError("invalid capability bound operator voice DSN")
    namespace["validate_dsn"] = lambda parsed: validated.append(parsed)
    bind_voice(12345)
    assert environment["OPERATOR_VOICE_TEST_DSN"] == "postgresql://test:test@127.0.0.1:12345/test"
    environment["OPERATOR_VOICE_TEST_DSN"] = "changed"
    try:
        unbind_voice()
    except PermissionError:
        pass
    else:
        raise AssertionError("changed operator voice DSN was removed")
    environment["OPERATOR_VOICE_TEST_DSN"] = namespace["_operator_voice_test_dsn"]
    unbind_voice()
    assert "OPERATOR_VOICE_TEST_DSN" not in environment and namespace["_operator_voice_test_dsn"] is None
    assert events == ["parent_database_bound", "parent_database_unbound"] * 2 + ["operator_voice_test_dsn_bound", "operator_voice_test_dsn_unbound"]


def check_adapter_profile_bindings() -> None:
    source = Path(__file__).with_name("native_tc_adapter_hflypi.py")
    tree = ast.parse(source.read_text())
    assignments = {
        target.id: node.value
        for node in tree.body
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Name) and target.id in {"PROFILE_PREFIXES", "PARENT_DATABASE_PROFILES", "OPERATOR_VOICE_TEST_DSN_PROFILES", "INHERITED_DATABASE_URL_REFUSAL_PROFILES"}
    }
    assert ast.literal_eval(assignments["PROFILE_PREFIXES"]) == {
        "card-growth-v1": "native-tc-one",
        "client-info-v1": "native-tc-client-info",
        "capabilities-phase1-v1": "native-tc-capabilities-phase1",
        "operator-service-creation-v1": "native-tc-operator-service-creation",
        "work-review-rollback-v1": "native-tc-work-review-rollback",
        "creator-portal-rollback-v1": "native-tc-creator-portal-rollback",
        "creator-offer-rollback-v1": "native-tc-creator-offer-rollback",
        "author-daily-gate-pg-v1": "native-tc-author-daily-gate-pg",
        "knowledge-schema-pg-v1": "native-tc-knowledge-schema-pg",
        "outreach-pain-library-pg-v1": "native-tc-outreach-pain-library-pg",
        "riderra-template-pg-v1": "native-tc-riderra-template-pg",
        "sales-room-proposal-race-pg-v1": "native-tc-sales-room-proposal-race-pg",
        "sales-room-deadlock-pg-v1": "native-tc-sales-room-deadlock-pg",
        "telegram-shared-audience-pg-v1": "native-tc-telegram-shared-audience-pg",
        "web-tracking-pg-v1": "native-tc-web-tracking-pg",
        "worker-captcha-pg-v1": "native-tc-worker-captcha-pg",
        "worker-expired-pg-v1": "native-tc-worker-expired-pg",
        "worker-resume-pg-v1": "native-tc-worker-resume-pg",
        "finance-import-transaction-pg-v1": "native-tc-finance-import-transaction-pg",
        "service-compression-race-pg-v1": "native-tc-service-compression-race-pg",
    }
    parent_profiles = assignments["PARENT_DATABASE_PROFILES"]
    assert isinstance(parent_profiles, ast.Call) and len(parent_profiles.args) == 1
    assert ast.literal_eval(parent_profiles.args[0]) == {"client-info-v1", "capabilities-phase1-v1"}
    voice_profiles = assignments["OPERATOR_VOICE_TEST_DSN_PROFILES"]
    assert isinstance(voice_profiles, ast.Call) and len(voice_profiles.args) == 1
    assert ast.literal_eval(voice_profiles.args[0]) == {"operator-service-creation-v1"}
    inherited = assignments["INHERITED_DATABASE_URL_REFUSAL_PROFILES"]
    assert isinstance(inherited, ast.Call) and len(inherited.args) == 1
    assert ast.literal_eval(inherited.args[0]) == {
        "author-daily-gate-pg-v1", "knowledge-schema-pg-v1", "outreach-pain-library-pg-v1",
        "riderra-template-pg-v1", "sales-room-proposal-race-pg-v1", "sales-room-deadlock-pg-v1",
        "telegram-shared-audience-pg-v1", "web-tracking-pg-v1", "worker-captcha-pg-v1",
        "worker-expired-pg-v1", "worker-resume-pg-v1", "finance-import-transaction-pg-v1",
        "service-compression-race-pg-v1",
    }


def check_owned_dsn_admission() -> None:
    source = Path(__file__).with_name("native_tc_adapter_hflypi.py")
    tree = ast.parse(source.read_text())
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in {"deny", "validate_dsn"}]
    assignments = {
        target.id: node.value
        for node in tree.body
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Name) and target.id == "OWNED_DATABASE_PATTERNS"
    }
    pattern_namespace = {"re": re}
    pattern_module = ast.fix_missing_locations(ast.Module(body=[ast.Assign(targets=[ast.Name(id="OWNED_DATABASE_PATTERNS", ctx=ast.Store())], value=assignments["OWNED_DATABASE_PATTERNS"], type_comment=None)], type_ignores=[]))
    exec(compile(pattern_module, str(source), "exec"), pattern_namespace)
    patterns = pattern_namespace["OWNED_DATABASE_PATTERNS"]
    assert set(patterns) == {"work-review-rollback-v1", "creator-portal-rollback-v1", "creator-offer-rollback-v1", "finance-import-transaction-pg-v1", "service-compression-race-pg-v1"}
    environment = {
        "LOCALOS_HFLYPI_TC_MODE": "work-review-rollback-v1",
        "LOCALOS_HFLYPI_TC_CAPABILITY": "/private/tmp/capability.json",
        "LOCALOS_HFLYPI_TESTCONTAINERS_SESSION_ID": "abcdefgh",
    }
    events = []
    namespace = {
        "os": SimpleNamespace(environ=environment),
        "Path": Path,
        "re": re,
        "PREFIX": "LOCALOS_HFLYPI_TC_",
        "OWNED_DATABASE_PATTERNS": patterns,
        "native_tc_relay_hflypi": SimpleNamespace(validate_capability=lambda path, port: {"session_id": "abcdefgh", "container_id": "owned"}),
        "record": lambda event, **fields: events.append((event, fields)),
    }
    exec(compile(ast.Module(body=functions, type_ignores=[]), str(source), "exec"), namespace)
    validate = namespace["validate_dsn"]
    base = {"host": "127.0.0.1", "port": "12345", "user": "test", "password": "test"}
    valid_databases = {
        "work-review-rollback-v1": "work_review_rollback_0123456789abcdef0123456789abcdef",
        "creator-portal-rollback-v1": "creator_portal_rollback_0123456789abcdef0123456789abcdef",
        "creator-offer-rollback-v1": "creator_offer_rollback_0123456789abcdef0123456789abcdef",
        "finance-import-transaction-pg-v1": "localos_data_fin_01_0123456789abcdef0123456789abcdef",
        "service-compression-race-pg-v1": "service_compression_race_0123456789abcdef0123456789abcdef",
    }
    for profile, generated in valid_databases.items():
        environment["LOCALOS_HFLYPI_TC_MODE"] = profile
        validate({**base, "dbname": "postgres"})
        validate({**base, "dbname": generated})
        for foreign in set(valid_databases.values()) - {generated}:
            try:
                validate({**base, "dbname": foreign})
            except PermissionError:
                pass
            else:
                raise AssertionError("profile admitted another profile's disposable database")
        for malformed in (generated.upper(), generated[:-1], generated + "_extra"):
            try:
                validate({**base, "dbname": malformed})
            except PermissionError:
                pass
            else:
                raise AssertionError("profile admitted malformed disposable database")
    environment["LOCALOS_HFLYPI_TC_MODE"] = "client-info-v1"
    validate({**base, "dbname": "test"})
    for generated in valid_databases.values():
        try:
            validate({**base, "dbname": generated})
        except PermissionError:
            pass
        else:
            raise AssertionError("legacy test-only profile admitted owned disposable database")


def fixture_nodeids() -> list[str]:
    source = Path("/private/tmp/localos-readiness-20260921.hfLYPi/source/tests/test_capabilities_api_phase1.py")
    tree = ast.parse(source.read_text())
    return [
        "tests/test_capabilities_api_phase1.py::" + node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name.startswith("test_")
        and any(argument.arg == "capabilities_client" for argument in node.args.args)
    ]


def sitecustomize_modes() -> set[str]:
    source = Path(__file__).with_name("native_hflypi_sitecustomize.py")
    tree = ast.parse(source.read_text())
    modes = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Set):
            values = {value.value for value in node.elts if isinstance(value, ast.Constant) and isinstance(value.value, str)}
            if {"card-growth-v1", "client-info-v1", "capabilities-phase1-v1", "operator-service-creation-v1"}.issubset(values):
                modes.update(values)
    return modes


def check_relay_budgets() -> None:
    source = Path(__file__).with_name("native_tc_relay_hflypi.py")
    tree = ast.parse(source.read_text())
    assignments = [node for node in tree.body if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "PROFILE_CONNECTION_BUDGETS" for target in node.targets)]
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "connection_budget"]
    assert len(assignments) == 1 and len(functions) == 1
    budgets = ast.literal_eval(assignments[0].value)
    assert budgets == {
        "card-growth-v1": 32, "client-info-v1": 32, "capabilities-phase1-v1": 1024,
        "operator-service-creation-v1": 32, "work-review-rollback-v1": 512,
        "creator-portal-rollback-v1": 512, "creator-offer-rollback-v1": 512,
        "author-daily-gate-pg-v1": 32, "knowledge-schema-pg-v1": 32,
        "outreach-pain-library-pg-v1": 32, "riderra-template-pg-v1": 32,
        "sales-room-proposal-race-pg-v1": 32, "sales-room-deadlock-pg-v1": 32,
        "telegram-shared-audience-pg-v1": 32, "web-tracking-pg-v1": 32,
        "worker-captcha-pg-v1": 32, "worker-expired-pg-v1": 32,
        "worker-resume-pg-v1": 32, "finance-import-transaction-pg-v1": 32,
        "service-compression-race-pg-v1": 512,
    }
    namespace = {"MAX_CONNECTIONS": 32, "PROFILE_CONNECTION_BUDGETS": budgets}
    exec(compile(ast.Module(body=functions, type_ignores=[]), str(source), "exec"), namespace)
    budget = namespace["connection_budget"]
    assert budget("") == 32
    assert budget("card-growth-v1") == 32
    assert budget("client-info-v1") == 32
    assert budget("capabilities-phase1-v1") == 1024
    assert budget("operator-service-creation-v1") == 32
    assert budget("work-review-rollback-v1") == 512
    assert budget("creator-portal-rollback-v1") == 512
    assert budget("creator-offer-rollback-v1") == 512
    for profile, expected in budgets.items():
        assert budget(profile) == expected
    for foreign in ("unknown", "capabilities-phase1-v2"):
        try:
            budget(foreign)
        except PermissionError:
            pass
        else:
            raise AssertionError("foreign relay profile received a budget")


def check_relay_evidence_bounds(namespace) -> None:
    validate = namespace["relay_evidence"]

    def final(connections: int, budget: int) -> dict:
        return {
            "connections": connections,
            "connection_budget": budget,
            "active": 0,
            "rejections": 0,
            "failures": [],
            "exec_results": [{} for _ in range(connections)],
        }

    assert validate("card-growth-v1", final(2, 32))[0] == 2
    assert validate("capabilities-phase1-v1", final(171, 1024))[0] == 171
    assert validate("operator-service-creation-v1", final(21, 32))[0] == 21
    assert validate("work-review-rollback-v1", final(75, 512))[0] == 75
    assert validate("creator-portal-rollback-v1", final(54, 512))[0] == 54
    assert validate("creator-offer-rollback-v1", final(159, 512))[0] == 159
    for candidate in (final(170, 1024), final(1025, 1024), final(171, 32)):
        try:
            validate("capabilities-phase1-v1", candidate)
        except RuntimeError:
            pass
        else:
            raise AssertionError("capabilities relay evidence outside its literal bounds was accepted")
    for candidate in (final(20, 32), final(33, 32), final(21, 1024)):
        try:
            validate("operator-service-creation-v1", candidate)
        except RuntimeError:
            pass
        else:
            raise AssertionError("operator service creation relay evidence outside its literal bounds was accepted")
    for candidate in (final(74, 512), final(513, 512), final(75, 32)):
        try:
            validate("work-review-rollback-v1", candidate)
        except RuntimeError:
            pass
        else:
            raise AssertionError("work-review relay evidence outside its literal bounds was accepted")
    for profile, minimum in (("creator-portal-rollback-v1", 54), ("creator-offer-rollback-v1", 159)):
        for candidate in (final(minimum - 1, 512), final(513, 512), final(minimum, 32)):
            try:
                validate(profile, candidate)
            except RuntimeError:
                pass
            else:
                raise AssertionError("creator rollback relay evidence outside its literal bounds was accepted")
    rules = namespace["SHARED_FIXTURE_PROFILE_RULES"]
    for profile, rule in rules.items():
        minimum = rule["minimum_connections"]
        budget = rule["budget"]
        assert validate(profile, final(minimum, budget))[0] == minimum
        for candidate in (final(minimum - 1, budget), final(budget + 1, budget), final(minimum, 512 if budget == 32 else 32)):
            try:
                validate(profile, candidate)
            except RuntimeError:
                pass
            else:
                raise AssertionError("shared fixture relay evidence outside its literal bounds was accepted")


def check_shared_fixture_contracts(namespace) -> None:
    rules = namespace["SHARED_FIXTURE_PROFILE_RULES"]
    no_child_profiles = {"riderra-template-pg-v1", "finance-import-transaction-pg-v1"}
    assert {profile for profile, rule in rules.items() if rule["child_admissions"] == 0} == no_child_profiles
    assert rules["finance-import-transaction-pg-v1"]["minimum_connections"] == 4
    assert rules["finance-import-transaction-pg-v1"]["budget"] == 32
    assert rules["service-compression-race-pg-v1"]["minimum_connections"] == 8
    assert rules["service-compression-race-pg-v1"]["budget"] == 512
    for profile in ("outreach-pain-library-pg-v1", "worker-captcha-pg-v1", "worker-expired-pg-v1", "worker-resume-pg-v1"):
        assert rules[profile]["minimum_connections"] == 4
    source = Path(__file__).with_name("native_tc_one_hflypi.py").read_text()
    assert "if child_minimum == 0 and child_admitted:" in source
    assert "len(child_generated) < shared_rule[\"child_admissions\"]" in source
    assert "named disposable database lifecycle evidence is incomplete" in source
    adapter = Path(__file__).with_name("native_tc_adapter_hflypi.py").read_text()
    assert "inherited database configuration must be absent before owned start" in adapter
    assert "owned disposable database remains before container cleanup" in adapter


def main() -> None:
    check_parent_database()
    check_adapter_profile_bindings()
    check_owned_dsn_admission()
    check_relay_budgets()
    namespace = runpy.run_path(str(Path(__file__).with_name("native_tc_one_hflypi.py")))
    profiles = namespace["PROFILES"]
    parse = namespace["parse_test"]
    check_relay_evidence_bounds(namespace)
    check_shared_fixture_contracts(namespace)
    shared_profiles = {
        "author-daily-gate-pg-v1": [
            "tests/test_author_daily_gate.py::test_author_gate_query_executes_on_migrated_postgres",
            "tests/test_author_daily_gate.py::test_author_gate_null_predicates_are_conservative_on_postgres",
        ],
        "knowledge-schema-pg-v1": ["tests/test_knowledge_layer.py::test_knowledge_schema_applies_on_postgres"],
        "outreach-pain-library-pg-v1": [
            "tests/test_outreach_human_language_gate.py::test_pain_library_refresh_executes_with_real_psycopg2",
            "tests/test_outreach_human_language_gate.py::test_language_retrieval_executes_with_real_psycopg2_without_vector",
        ],
        "riderra-template-pg-v1": [
            "tests/test_riderra_template_authorization.py::test_migrated_event_allowlist_accepts_snapshot_and_rejects_unknown",
            "tests/test_riderra_template_authorization.py::test_daily_company_cap_sql_executes_atomically_on_isolated_postgres",
            "tests/test_riderra_template_authorization.py::test_dispatch_claims_author_and_noncreator_riderra_on_isolated_postgres",
        ],
        "sales-room-proposal-race-pg-v1": ["tests/test_sales_room_proposal_version_concurrency.py::test_concurrent_first_reads_create_one_proposal_version_without_errors"],
        "sales-room-deadlock-pg-v1": ["tests/test_sales_rooms_concurrency.py::test_concurrent_public_sales_room_reads_do_not_deadlock"],
        "telegram-shared-audience-pg-v1": ["tests/test_telegram_research.py::test_shared_audience_decision_does_not_leak_between_businesses"],
        "web-tracking-pg-v1": ["tests/test_web_tracking_postgres.py::test_postgres_migration_idempotent_ingestion_and_tenant_isolation"],
        "worker-captcha-pg-v1": ["tests/test_worker_captcha_flow.py::test_worker_schedules_automatic_captcha_retry"],
        "worker-expired-pg-v1": ["tests/test_worker_expired_flow.py::test_worker_marks_captcha_expired_after_ttl"],
        "worker-resume-pg-v1": ["tests/test_worker_resume_flow.py::test_worker_resume_clears_captcha_fields"],
        "finance-import-transaction-pg-v1": ["tests/test_finance_import_transaction_pg.py::test_concurrent_duplicate_does_not_poison_following_finance_import_row"],
        "service-compression-race-pg-v1": ["tests/test_service_compression_apply_concurrency_pg.py::test_second_compression_apply_blocks_then_returns_idempotent_result"],
    }
    assert set(profiles) == {"card-growth-v1", "client-info-v1", "capabilities-phase1-v1", "operator-service-creation-v1", "work-review-rollback-v1", "creator-portal-rollback-v1", "creator-offer-rollback-v1", *shared_profiles}
    assert profiles["card-growth-v1"]["count"] == 1
    assert profiles["client-info-v1"] == {"target": "tests/test_client_info_gate.py", "count": 8, "prefix": "native-tc-client-info"}
    capabilities = profiles["capabilities-phase1-v1"]
    expected_nodeids = fixture_nodeids()
    assert len(expected_nodeids) == 57 and len(set(expected_nodeids)) == 57
    assert capabilities == {
        "targets": expected_nodeids,
        "count": 57,
        "exact_nodeids": True,
        "prefix": "native-tc-capabilities-phase1",
    }
    assert profiles["operator-service-creation-v1"] == {"target": "tests/test_operator_service_creation.py", "count": 28, "prefix": "native-tc-operator-service-creation", "bootstrap_postgres": True}
    assert profiles["work-review-rollback-v1"] == {
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
    }
    assert profiles["creator-portal-rollback-v1"] == {
        "targets": [
            "tests/test_creator_portal_migration_rollback.py::test_empty_creator_portal_schema_downgrades_without_cascade",
            "tests/test_creator_portal_migration_rollback.py::test_creator_portal_data_blocks_downgrade_and_remains_present[relationship]",
            "tests/test_creator_portal_migration_rollback.py::test_creator_portal_data_blocks_downgrade_and_remains_present[review_field]",
            "tests/test_creator_portal_migration_rollback.py::test_concurrent_portal_writer_cannot_commit_during_downgrade",
        ],
        "count": 4,
        "exact_nodeids": True,
        "prefix": "native-tc-creator-portal-rollback",
    }
    assert profiles["creator-offer-rollback-v1"] == {
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
    }
    assert namespace["ROLLBACK_PROFILE_RULES"] == {
        "work-review-rollback-v1": {"database_pattern": r"work_review_rollback_[0-9a-f]{32}", "child_admissions": 14, "minimum_connections": 75, "cleanup_event": "work_review_database_cleanup_checked"},
        "creator-portal-rollback-v1": {"database_pattern": r"creator_portal_rollback_[0-9a-f]{32}", "child_admissions": 8, "minimum_connections": 54, "cleanup_event": "creator_portal_database_cleanup_checked"},
        "creator-offer-rollback-v1": {"database_pattern": r"creator_offer_rollback_[0-9a-f]{32}", "child_admissions": 21, "minimum_connections": 159, "cleanup_event": "creator_offer_database_cleanup_checked"},
    }
    assert namespace["SHARED_FIXTURE_PROFILE_RULES"] == {
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
    for name, targets in shared_profiles.items():
        profile = profiles[name]
        assert profile["count"] == len(targets) and profile["exact_nodeids"] is True
        if len(targets) > 1:
            assert profile["targets"] == targets
        else:
            assert profile["target"] == targets[0]
    assert sitecustomize_modes() == set(profiles)

    def capture(state):
        return {"stdout": "HFLYPI_TC_ONE_RESULT=" + json.dumps(state), "exit_code": 0, "timed_out": False}

    def denied(state, profile):
        try:
            parse(capture(state), profile)
        except RuntimeError:
            return
        raise AssertionError("invalid result was accepted")

    for profile in profiles.values():
        count = profile["count"]
        targets = profile.get("targets", [profile.get("target")])
        nodeids = targets if profile.get("exact_nodeids") is True else ([targets[0]] if count == 1 else [targets[0] + "::test_case_" + str(index) for index in range(count)])
        state = {"collected": count, "passed": count, "failed": 0, "skipped": 0, "xfailed": 0, "setup_failed": 0, "call_failed": 0, "pytest_exitstatus": 0, "pytest_return": 0, "nodeids": nodeids}
        state.update(subtests_passed=0, subtests_failed=0, subtests_skipped=0, subtests_xfailed=0)
        assert parse(capture(state), profile) == state
        for key in ("failed", "skipped", "xfailed", "setup_failed", "call_failed", "pytest_exitstatus", "pytest_return", "subtests_failed", "subtests_skipped", "subtests_xfailed"):
            denied({**state, key: 1}, profile)
        denied({**state, "passed": count - 1}, profile)
        denied({**state, "collected": count + 1}, profile)
        denied({**state, "nodeids": ["tests/test_foreign.py::test_other"] * count}, profile)
        denied({**state, "nodeids": []}, profile)
        if count > 1:
            denied({**state, "nodeids": [nodeids[0]] * count}, profile)
        if profile.get("exact_nodeids") is True:
            denied({**state, "nodeids": ["tests/test_foreign.py::test_other"] + nodeids[1:]}, profile)
            denied({**state, "nodeids": [nodeids[0] + "::foreign_child"] + nodeids[1:]}, profile)
        compile(namespace["plugin_source"](targets, profile.get("bootstrap_postgres", False)), "<reviewed-profile-runner>", "exec")
    for malformed in ([], ["tests/test_capabilities_api_phase1.py::test_ok", 1]):
        try:
            namespace["plugin_source"](malformed)
        except ValueError:
            pass
        else:
            raise AssertionError("malformed target allowlist was accepted")
    try:
        namespace["plugin_source"](["tests/test_operator_service_creation.py"], "yes")
    except ValueError:
        pass
    else:
        raise AssertionError("non-boolean bootstrap mode was accepted")
    print("native TC profiles: 20 exact profiles, owned-DSN isolation and negative result gates passed")


if __name__ == "__main__":
    main()
