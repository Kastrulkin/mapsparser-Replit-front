#!/usr/bin/env python3
"""Narrow fixture controls for the isolated LocalOS staging database."""

from __future__ import annotations

import argparse
import os
import uuid

from database_manager import get_db_connection


FIXTURE_NAMESPACE = uuid.UUID("e48b07f6-e923-4d6d-9a70-b1de982d2f11")
FLOWS = {"maps", "influencer", "partnership", "content", "automation"}


def fixture_id(label: str) -> str:
    return str(uuid.uuid5(FIXTURE_NAMESPACE, label))


def require_isolated_staging() -> None:
    database_url = os.getenv("DATABASE_URL", "")
    if os.getenv("APP_ENV") != "staging" or "localos_staging" not in database_url:
        raise RuntimeError("Fixture controls are available only in isolated staging")


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


def reset_journey(flow: str) -> None:
    if flow not in FLOWS:
        raise RuntimeError("Unknown synthetic journey flow")
    journey_id = fixture_id(f"journey:{flow}")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM journey_actions WHERE journey_id = %s", (journey_id,))
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


def main() -> None:
    require_isolated_staging()
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    token_parser = subparsers.add_parser("verification-token")
    token_parser.add_argument("email")
    reset_parser = subparsers.add_parser("reset-journey")
    reset_parser.add_argument("flow", choices=sorted(FLOWS))
    args = parser.parse_args()

    if args.command == "verification-token":
        verification_token(args.email)
        return
    reset_journey(args.flow)


if __name__ == "__main__":
    main()
