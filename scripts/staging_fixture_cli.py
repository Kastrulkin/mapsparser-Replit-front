#!/usr/bin/env python3
"""Narrow fixture controls for the isolated LocalOS staging database."""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import time
import uuid
from urllib.parse import urlencode, urlsplit

from database_manager import get_db_connection


FIXTURE_NAMESPACE = uuid.UUID("e48b07f6-e923-4d6d-9a70-b1de982d2f11")
FLOWS = {"maps", "influencer", "partnership", "content", "automation"}
OWNER_EMAIL = "owner@localos-e2e.invalid"
OWNER_TELEGRAM_ID = "900000001"
OWNER_BUSINESS_NAME = "[E2E] Салон Север"
FINANCE_FIXTURE_FILE = "localos-e2e-finance.csv"
OWNER_NETWORK_NAME = "[E2E] Сеть салонов"
FOREIGN_BUSINESS_NAME = "[E2E] Чужая точка"
FOREIGN_NETWORK_NAME = "[E2E] Чужая сеть"
SOCIAL_RECONCILIATION_PLAN_LABEL = "social-publication-reconciliation-plan"
SOCIAL_RECONCILIATION_ITEM_LABEL = "social-publication-reconciliation-item"
SOCIAL_RECONCILIATION_POST_LABEL = "social-publication-reconciliation-post"
SOCIAL_RECONCILIATION_APPROVAL_LABEL = "social-publication-reconciliation-approval"
SOCIAL_RECONCILIATION_ATTEMPT_LABEL = "social-publication-reconciliation-attempt"


def fixture_id(label: str) -> str:
    return str(uuid.uuid5(FIXTURE_NAMESPACE, label))


def require_isolated_staging() -> None:
    database_url = os.getenv("DATABASE_URL", "")
    if os.getenv("APP_ENV") != "staging" or "localos_staging" not in database_url:
        raise RuntimeError("Fixture controls are available only in isolated staging")


def require_social_publication_reconciliation_fixture() -> None:
    if os.getenv("LOCALOS_STAGING_FIXTURE_MODE") != "1":
        raise RuntimeError("Social publication reconciliation fixture requires explicit staging fixture mode")
    if any(os.getenv(key) for key in ("PGHOSTADDR", "PGSERVICE", "PGSERVICEFILE", "PGOPTIONS")):
        raise RuntimeError("Social publication reconciliation fixture refuses libpq overrides")
    database_url = os.getenv("DATABASE_URL", "")
    parsed = urlsplit(database_url)
    if parsed.scheme not in {"postgresql", "postgres"} or parsed.query or parsed.fragment:
        raise RuntimeError("Social publication reconciliation fixture requires an exact isolated staging database URL")
    try:
        port = parsed.port
    except ValueError:
        raise RuntimeError("Social publication reconciliation fixture requires an exact isolated staging database URL")
    database_name = parsed.path.lstrip("/")
    docker_target = (
        parsed.hostname == "postgres"
        and port == 5432
        and parsed.username == "localos_staging"
        and database_name == "localos_staging"
    )
    native_target = (
        parsed.hostname in {"127.0.0.1", "::1"}
        and port is not None
        and port >= 32768
        and database_name.startswith("localos_staging_")
        and database_name.endswith("test")
    )
    if not docker_target and not native_target:
        raise RuntimeError("Social publication reconciliation fixture requires an exact isolated staging database URL")


def verification_token(email: str) -> None:
    if not email.endswith("@localos-e2e.invalid"):
        raise RuntimeError("Only synthetic .invalid accounts are supported")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT verification_token FROM users WHERE lower(email) = lower(%s) LIMIT 1",
        (email,),
    )
    row = cursor.fetchone()
    conn.close()
    if not row or not row[0]:
        raise RuntimeError("Verification token was not found")
    print(row[0])


def owner_business_id() -> str:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT b.id
        FROM businesses b
        JOIN users u ON u.id = b.owner_id
        WHERE lower(u.email) = lower(%s) AND b.name = %s
        LIMIT 1
        """,
        (OWNER_EMAIL, OWNER_BUSINESS_NAME),
    )
    row = cursor.fetchone()
    conn.close()
    if not row:
        raise RuntimeError("Synthetic owner business was not found")
    return str(row[0])


def owner_user_id() -> str:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE lower(email) = lower(%s) LIMIT 1", (OWNER_EMAIL,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        raise RuntimeError("Synthetic owner was not found")
    return str(row[0])


def reset_finance() -> None:
    business_id = owner_business_id()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id FROM finance_import_batches WHERE business_id = %s AND file_name = %s",
        (business_id, FINANCE_FIXTURE_FILE),
    )
    batch_ids = [str(row[0]) for row in cursor.fetchall()]
    if batch_ids:
        for table_name in (
            "finance_entries",
            "finance_service_metrics",
            "finance_staff_metrics",
            "finance_workplace_metrics",
        ):
            cursor.execute(
                f"DELETE FROM {table_name} WHERE business_id = %s AND import_batch_id = ANY(%s)",
                (business_id, batch_ids),
            )
        cursor.execute(
            "DELETE FROM finance_import_batches WHERE business_id = %s AND id = ANY(%s)",
            (business_id, batch_ids),
        )
    conn.commit()
    conn.close()
    print(business_id)


def social_publication_reconciliation_ids() -> dict[str, str]:
    return {
        "plan_id": fixture_id(SOCIAL_RECONCILIATION_PLAN_LABEL),
        "item_id": fixture_id(SOCIAL_RECONCILIATION_ITEM_LABEL),
        "post_id": fixture_id(SOCIAL_RECONCILIATION_POST_LABEL),
        "approval_id": fixture_id(SOCIAL_RECONCILIATION_APPROVAL_LABEL),
        "attempt_id": fixture_id(SOCIAL_RECONCILIATION_ATTEMPT_LABEL),
    }


def is_social_publication_reconciliation_metadata(value: object) -> bool:
    if isinstance(value, dict):
        return value.get("fixture") == "social-publication-reconciliation"
    try:
        parsed = json.loads(str(value or "{}"))
    except (TypeError, ValueError):
        return False
    return isinstance(parsed, dict) and parsed.get("fixture") == "social-publication-reconciliation"


def reset_social_publication_reconciliation() -> None:
    require_social_publication_reconciliation_fixture()
    business_id = owner_business_id()
    user_id = owner_user_id()
    ids = social_publication_reconciliation_ids()
    metadata = {
        "fixture": "social-publication-reconciliation",
        "publish_attempt": {
            "id": ids["attempt_id"],
            "state": "uncertain",
            "actor_id": user_id,
            "approval_id": ids["approval_id"],
            "content_business_fingerprint": "staging-fixture-content-business-fingerprint",
            "intent_committed_at": "2026-09-18T00:00:00+00:00",
            "source": "staging_fixture_cli",
        },
    }
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT business_id, title, input_snapshot_json FROM contentplans WHERE id = %s",
            (ids["plan_id"],),
        )
        existing_plan = cursor.fetchone()
        if existing_plan and str(existing_plan[0] or "") != business_id:
            raise RuntimeError("Synthetic social publication reconciliation plan belongs to another business")
        if existing_plan and (
            str(existing_plan[1] or "") != "E2E publication reconciliation"
            or not is_social_publication_reconciliation_metadata(existing_plan[2])
        ):
            raise RuntimeError("Synthetic social publication reconciliation plan fixture identity does not match")
        cursor.execute(
            "SELECT business_id, plan_id, source_kind, source_ref FROM contentplanitems WHERE id = %s",
            (ids["item_id"],),
        )
        existing_item = cursor.fetchone()
        if existing_item and str(existing_item[0] or "") != business_id:
            raise RuntimeError("Synthetic social publication reconciliation item belongs to another business")
        if existing_item and (
            str(existing_item[1] or "") != ids["plan_id"]
            or str(existing_item[2] or "") != "e2e_fixture"
            or str(existing_item[3] or "") != "social-publication-reconciliation"
        ):
            raise RuntimeError("Synthetic social publication reconciliation item fixture identity does not match")
        cursor.execute(
            "SELECT business_id, content_plan_id, content_plan_item_id, metadata_json FROM social_posts WHERE id = %s",
            (ids["post_id"],),
        )
        existing_post = cursor.fetchone()
        if existing_post and str(existing_post[0] or "") != business_id:
            raise RuntimeError("Synthetic social publication reconciliation ID belongs to another business")
        if existing_post and (
            str(existing_post[1] or "") != ids["plan_id"]
            or str(existing_post[2] or "") != ids["item_id"]
            or not is_social_publication_reconciliation_metadata(existing_post[3])
        ):
            raise RuntimeError("Synthetic social publication reconciliation post fixture identity does not match")
        cursor.execute(
            "SELECT id, business_id, content_plan_id, metadata_json FROM social_posts "
            "WHERE content_plan_item_id = %s AND platform = 'telegram'",
            (ids["item_id"],),
        )
        existing_item_platform = cursor.fetchone()
        if existing_item_platform and (
            str(existing_item_platform[0] or "") != ids["post_id"]
            or str(existing_item_platform[1] or "") != business_id
            or str(existing_item_platform[2] or "") != ids["plan_id"]
            or not is_social_publication_reconciliation_metadata(existing_item_platform[3])
        ):
            raise RuntimeError("Synthetic social publication reconciliation item platform belongs to another post")
        cursor.execute(
            """
            INSERT INTO contentplans (
                id, business_id, scope_type, title, period_days, period_start, period_end,
                plan_status, generation_mode, input_snapshot_json, created_by
            ) VALUES (%s, %s, 'single_business', 'E2E publication reconciliation', 14, CURRENT_DATE,
                      CURRENT_DATE + 13, 'draft', 'journey', %s::jsonb, %s)
            ON CONFLICT (id) DO UPDATE SET business_id = EXCLUDED.business_id,
                title = EXCLUDED.title, created_at = NOW(), updated_at = NOW()
            """,
            (ids["plan_id"], business_id, json.dumps({"fixture": "social-publication-reconciliation"}), user_id),
        )
        cursor.execute(
            """
            INSERT INTO contentplanitems (
                id, plan_id, business_id, scheduled_for, content_type, theme, goal,
                source_kind, source_ref, draft_text, status, metadata_json
            ) VALUES (%s, %s, %s, CURRENT_DATE, 'news', 'E2E сверка публикации',
                      'Проверить подтверждённую публикацию', 'e2e_fixture',
                      'social-publication-reconciliation', 'Синтетический текст для сверки публикации.',
                      'approved', %s::jsonb)
            ON CONFLICT (id) DO UPDATE SET plan_id = EXCLUDED.plan_id,
                business_id = EXCLUDED.business_id, scheduled_for = EXCLUDED.scheduled_for,
                draft_text = EXCLUDED.draft_text, status = 'approved', updated_at = NOW()
            """,
            (ids["item_id"], ids["plan_id"], business_id, json.dumps({"fixture": "social-publication-reconciliation"})),
        )
        cursor.execute(
            """
            INSERT INTO social_posts (
                id, business_id, content_plan_id, content_plan_item_id, platform, publish_mode,
                status, scheduled_for, approved_at, approval_id, base_text, platform_text,
                media_json, metadata_json, created_by, provider_post_id, provider_post_url, last_error
            ) VALUES (%s, %s, %s, %s, 'telegram', 'api', 'publishing', NOW(), NOW(), %s,
                      'Синтетический текст для сверки публикации.', 'Синтетический текст для сверки публикации.',
                      '[]'::jsonb, %s::jsonb, %s, NULL, NULL, 'Synthetic uncertain provider outcome')
            ON CONFLICT (content_plan_item_id, platform) DO UPDATE SET
                status = 'publishing', scheduled_for = NOW(), approved_at = NOW(),
                approval_id = EXCLUDED.approval_id, base_text = EXCLUDED.base_text,
                platform_text = EXCLUDED.platform_text, media_json = EXCLUDED.media_json,
                metadata_json = EXCLUDED.metadata_json, created_by = EXCLUDED.created_by,
                provider_post_id = NULL, provider_post_url = NULL,
                last_error = 'Synthetic uncertain provider outcome', updated_at = NOW()
            """,
            (
                ids["post_id"], business_id, ids["plan_id"], ids["item_id"], ids["approval_id"],
                json.dumps(metadata, ensure_ascii=False), user_id,
            ),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    print(json.dumps({"business_id": business_id, **ids}, ensure_ascii=False))


def inspect_social_publication_reconciliation() -> None:
    require_social_publication_reconciliation_fixture()
    ids = social_publication_reconciliation_ids()
    business_id = owner_business_id()
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT id, business_id, status, provider_post_id, provider_post_url, metadata_json
            FROM social_posts
            WHERE id = %s
            """,
            (ids["post_id"],),
        )
        row = cursor.fetchone()
        columns = [description[0] for description in cursor.description or []]
    finally:
        conn.close()
    if not row:
        raise RuntimeError("Synthetic social publication reconciliation post was not found")
    payload = {column: row[index] for index, column in enumerate(columns)}
    if str(payload.get("business_id") or "") != business_id:
        raise RuntimeError("Synthetic social publication reconciliation post is outside the owner business")
    payload["post_id"] = ids["post_id"]
    payload["attempt_id"] = ids["attempt_id"]
    print(json.dumps(payload, ensure_ascii=False, default=str))


def network_fixture() -> None:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT n.id, n.name,
               ARRAY_AGG(b.id ORDER BY b.name) AS business_ids,
               ARRAY_AGG(b.name ORDER BY b.name) AS business_names
        FROM networks n
        JOIN businesses b ON b.network_id = n.id
        WHERE n.name = %s
        GROUP BY n.id, n.name
        """,
        (OWNER_NETWORK_NAME,),
    )
    owner_row = cursor.fetchone()
    cursor.execute(
        """
        SELECT n.id AS network_id, b.id AS business_id
        FROM networks n
        JOIN businesses b ON b.network_id = n.id
        WHERE n.name = %s AND b.name = %s
        LIMIT 1
        """,
        (FOREIGN_NETWORK_NAME, FOREIGN_BUSINESS_NAME),
    )
    foreign_row = cursor.fetchone()
    conn.close()
    if not owner_row or not foreign_row:
        raise RuntimeError("Synthetic network fixtures were not found")
    print(json.dumps({
        "network_id": str(owner_row[0]),
        "network_name": str(owner_row[1]),
        "business_ids": [str(item) for item in owner_row[2]],
        "business_names": [str(item) for item in owner_row[3]],
        "foreign_network_id": str(foreign_row[0]),
        "foreign_business_id": str(foreign_row[1]),
        "foreign_business_name": FOREIGN_BUSINESS_NAME,
    }, ensure_ascii=False))


def reset_journey(flow: str) -> None:
    if flow not in FLOWS:
        raise RuntimeError("Unknown synthetic journey flow")
    journey_id = fixture_id(f"journey:{flow}")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM journey_actions WHERE journey_id = %s", (journey_id,))
    if flow == "content":
        cursor.execute(
            """
            UPDATE contentplanitems
            SET draft_text = NULL, status = 'planned', metadata_json = '{"fixture": true}'::jsonb,
                updated_at = NOW()
            WHERE id = %s
            """,
            (fixture_id("content-item:owner"),),
        )
    elif flow == "partnership":
        cursor.execute(
            """
            UPDATE lead_workstreams
            SET partnership_outcome_json = '{}'::jsonb, partnership_launched_at = NULL,
                updated_at = NOW()
            WHERE id = %s
            """,
            (fixture_id("workstream:partnership"),),
        )
    elif flow == "influencer":
        cursor.execute(
            "UPDATE creator_search_results SET shortlist_status = 'shortlisted', updated_at = NOW() WHERE id = %s",
            (fixture_id("creator-result:anna"),),
        )
    elif flow == "automation":
        cursor.execute(
            "DELETE FROM agent_runs WHERE id LIKE 'localos-e2e-journey-run-%%' AND business_id = %s",
            (owner_business_id(),),
        )
    cursor.execute(
        """
        UPDATE lead_journeys
        SET status = 'preview', claimed_user_id = NULL, claimed_business_id = NULL,
            claimed_at = NULL, revoked_at = NULL, updated_at = NOW()
        WHERE id = %s AND source = 'e2e_fixture'
        """,
        (journey_id,),
    )
    if cursor.rowcount != 1:
        conn.rollback()
        conn.close()
        raise RuntimeError("Synthetic journey was not found")
    conn.commit()
    conn.close()
    print(journey_id)


def complete_map_refresh() -> None:
    business_id = owner_business_id()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT action.payload_json->>'refresh_queue_id'
        FROM journey_actions action
        WHERE action.business_id = %s AND action.flow_type = 'maps'
          AND action.action_type = 'compare_snapshot' AND action.status = 'waiting'
        ORDER BY action.created_at DESC LIMIT 1
        """,
        (business_id,),
    )
    row = cursor.fetchone()
    queue_id = str(row[0] or "") if row else ""
    if not queue_id:
        conn.close()
        raise RuntimeError("Waiting synthetic map refresh was not found")
    cursor.execute(
        """
        UPDATE parsequeue
        SET status = 'completed', error_message = NULL, updated_at = NOW()
        WHERE id = %s AND business_id = %s
        """,
        (queue_id, business_id),
    )
    if cursor.rowcount != 1:
        conn.rollback()
        conn.close()
        raise RuntimeError("Synthetic map refresh queue was not found")
    conn.commit()
    conn.close()
    print(queue_id)


def complete_automation_run() -> None:
    business_id = owner_business_id()
    user_id = owner_user_id()
    blueprint_id = fixture_id("automation-blueprint:owner")
    version_id = fixture_id("automation-blueprint-version:owner")
    run_id = f"localos-e2e-journey-run-{uuid.uuid4()}"
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO agent_runs (
            id, blueprint_id, blueprint_version_id, business_id, status,
            input_json, output_json, created_by_user_id, started_at, completed_at, updated_at
        ) VALUES (%s, %s, %s, %s, 'completed', %s::jsonb, %s::jsonb, %s, NOW(), NOW(), NOW())
        """,
        (
            run_id,
            blueprint_id,
            version_id,
            business_id,
            json.dumps({"fixture": True}),
            json.dumps({"summary": "Подготовлены черновики для ручной проверки"}, ensure_ascii=False),
            user_id,
        ),
    )
    conn.commit()
    conn.close()
    print(run_id)


def journey_domain_state(flow: str) -> None:
    if flow not in FLOWS:
        raise RuntimeError("Unknown synthetic journey flow")
    business_id = owner_business_id()
    conn = get_db_connection()
    cursor = conn.cursor()
    if flow == "maps":
        cursor.execute(
            """
            SELECT action.action_type, action.status, action.payload_json,
                   queue.status AS queue_status
            FROM journey_actions action
            LEFT JOIN parsequeue queue ON queue.id = action.payload_json->>'refresh_queue_id'
            WHERE action.journey_id = %s
            ORDER BY action.created_at DESC LIMIT 1
            """,
            (fixture_id("journey:maps"),),
        )
    elif flow == "influencer":
        cursor.execute(
            """
            SELECT COUNT(*)::INT AS shortlisted_count
            FROM creator_search_results result
            JOIN creator_search_jobs job ON job.id = result.search_job_id
            WHERE job.business_id = %s AND result.shortlist_status = 'shortlisted'
            """,
            (business_id,),
        )
    elif flow == "partnership":
        cursor.execute(
            "SELECT partnership_launched_at, partnership_outcome_json FROM lead_workstreams WHERE id = %s",
            (fixture_id("workstream:partnership"),),
        )
    elif flow == "content":
        cursor.execute(
            "SELECT status, draft_text, scheduled_for, metadata_json FROM contentplanitems WHERE id = %s",
            (fixture_id("content-item:owner"),),
        )
    else:
        cursor.execute(
            """
            SELECT id, status, output_json
            FROM agent_runs
            WHERE business_id = %s AND id LIKE 'localos-e2e-journey-run-%%'
            ORDER BY completed_at DESC LIMIT 1
            """,
            (business_id,),
        )
    row = cursor.fetchone()
    columns = [description[0] for description in cursor.description or []]
    conn.close()
    if not row:
        raise RuntimeError("Synthetic journey domain state was not found")
    payload = {}
    for index, column in enumerate(columns):
        value = row[index]
        if hasattr(value, "isoformat"):
            value = value.isoformat()
        payload[column] = value
    print(json.dumps(payload, ensure_ascii=False, default=str))


def cleanup_admin_journeys() -> None:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        DELETE FROM lead_journeys journey
        USING prospectingleads lead
        WHERE journey.prospect_lead_id = lead.id
          AND journey.source = 'admin_journey_builder'
          AND lead.source = 'e2e_fixture'
        """
    )
    deleted = cursor.rowcount
    conn.commit()
    conn.close()
    print(deleted)


def telegram_init_data() -> None:
    bot_token = str(os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
    if not bot_token:
        raise RuntimeError("Synthetic Telegram bot token is not configured")
    values = {
        "auth_date": str(int(time.time())),
        "query_id": "localos-staging-e2e-query",
        "user": json.dumps({
            "id": int(OWNER_TELEGRAM_ID),
            "first_name": "E2E",
            "last_name": "Владелец",
            "username": "localos_e2e_owner",
        }, ensure_ascii=False, separators=(",", ":")),
    }
    data_check_string = "\n".join(f"{key}={values[key]}" for key in sorted(values))
    secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
    values["hash"] = hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()
    print(urlencode(values))


def main() -> None:
    require_isolated_staging()
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    token_parser = subparsers.add_parser("verification-token")
    token_parser.add_argument("email")
    reset_parser = subparsers.add_parser("reset-journey")
    reset_parser.add_argument("flow", choices=sorted(FLOWS))
    subparsers.add_parser("owner-business-id")
    subparsers.add_parser("owner-user-id")
    subparsers.add_parser("reset-finance")
    subparsers.add_parser("reset-social-publication-reconciliation")
    subparsers.add_parser("inspect-social-publication-reconciliation")
    subparsers.add_parser("network-fixture")
    subparsers.add_parser("telegram-init-data")
    subparsers.add_parser("cleanup-admin-journeys")
    subparsers.add_parser("complete-map-refresh")
    subparsers.add_parser("complete-automation-run")
    domain_parser = subparsers.add_parser("journey-domain-state")
    domain_parser.add_argument("flow", choices=sorted(FLOWS))
    args = parser.parse_args()

    if args.command == "verification-token":
        verification_token(args.email)
        return
    if args.command == "owner-business-id":
        print(owner_business_id())
        return
    if args.command == "owner-user-id":
        print(owner_user_id())
        return
    if args.command == "reset-finance":
        reset_finance()
        return
    if args.command == "reset-social-publication-reconciliation":
        reset_social_publication_reconciliation()
        return
    if args.command == "inspect-social-publication-reconciliation":
        inspect_social_publication_reconciliation()
        return
    if args.command == "network-fixture":
        network_fixture()
        return
    if args.command == "telegram-init-data":
        telegram_init_data()
        return
    if args.command == "cleanup-admin-journeys":
        cleanup_admin_journeys()
        return
    if args.command == "complete-map-refresh":
        complete_map_refresh()
        return
    if args.command == "complete-automation-run":
        complete_automation_run()
        return
    if args.command == "journey-domain-state":
        journey_domain_state(args.flow)
        return
    reset_journey(args.flow)


if __name__ == "__main__":
    main()
