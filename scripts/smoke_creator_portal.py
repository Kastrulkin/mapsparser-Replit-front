#!/usr/bin/env python3
"""Transactional smoke test for creator accounts, offers and tenant isolation."""

from __future__ import annotations

import os
import uuid

import psycopg2
from psycopg2.extras import Json, RealDictCursor

import services.creator_portal_service as portal


def identifier(label: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"localos-creator-smoke:{label}"))


def main() -> int:
    database_url = str(os.environ.get("CREATOR_PORTAL_TEST_DATABASE_URL") or "").strip()
    explicitly_transactional = str(os.environ.get("CREATOR_PORTAL_TRANSACTIONAL_SMOKE") or "").lower() == "true"
    if "creator_portal_test" not in database_url and not explicitly_transactional:
        raise RuntimeError("Use a disposable creator_portal_test database or explicitly enable the rollback-only transactional smoke")
    connection = psycopg2.connect(database_url)
    cursor = connection.cursor(cursor_factory=RealDictCursor)
    portal.send_email = lambda *_args, **_kwargs: True
    user_id = "creator-smoke-user"
    business_id = "creator-smoke-business"
    other_business_id = "creator-smoke-other-business"
    profile_id = identifier("profile-email")
    telegram_profile_id = identifier("profile-telegram")
    campaign_id = identifier("campaign")
    candidate_id = identifier("candidate")
    approved_id = identifier("approved-offer")
    draft_candidate_id = identifier("draft-candidate")
    draft_id = identifier("draft-offer")
    try:
        cursor.execute("INSERT INTO users (id, email, name, is_superadmin) VALUES (%s, %s, %s, TRUE)", (user_id, "smoke@localos.test", "Smoke"))
        cursor.execute("INSERT INTO businesses (id, owner_id, name, city, entity_group) VALUES (%s, %s, %s, %s, 'client')", (business_id, user_id, "Тестовый клиент", "Санкт-Петербург"))
        cursor.execute("INSERT INTO businesses (id, owner_id, name, city, entity_group) VALUES (%s, %s, %s, %s, 'client')", (other_business_id, user_id, "Другой клиент", "Москва"))
        for current_profile, name in ((profile_id, "Тестовый автор"), (telegram_profile_id, "Telegram автор")):
            cursor.execute("INSERT INTO creator_profiles (id, display_name, primary_city) VALUES (%s, %s, 'Санкт-Петербург')", (current_profile, name))
            cursor.execute("INSERT INTO creator_relationships (creator_profile_id, stage, primary_channel, contact_value) VALUES (%s, 'contact_ready', 'email', 'hidden@example.test')", (current_profile,))
        cursor.execute("INSERT INTO creator_campaigns (id, business_id, title, goal, status, offer_json, created_by) VALUES (%s, %s, %s, %s, 'approved', %s, %s)", (campaign_id, business_id, "Стрижка за результат", "Три новых клиента", Json({"service": "стрижка", "threshold": 3}), user_id))
        cursor.execute("INSERT INTO creator_campaign_candidates (id, campaign_id, creator_profile_id, status) VALUES (%s, %s, %s, 'shortlisted')", (candidate_id, campaign_id, profile_id))
        cursor.execute("INSERT INTO creator_collaborations (id, campaign_id, campaign_candidate_id, business_id, creator_profile_id, status, review_status) VALUES (%s, %s, %s, %s, %s, 'draft', 'approved')", (approved_id, campaign_id, candidate_id, business_id, profile_id))
        cursor.execute("INSERT INTO creator_campaign_candidates (id, campaign_id, creator_profile_id, status) VALUES (%s, %s, %s, 'shortlisted')", (draft_candidate_id, campaign_id, telegram_profile_id))
        cursor.execute("INSERT INTO creator_collaborations (id, campaign_id, campaign_candidate_id, business_id, creator_profile_id, status, review_status) VALUES (%s, %s, %s, %s, %s, 'draft', 'needs_review')", (draft_id, campaign_id, draft_candidate_id, business_id, telegram_profile_id))

        invite = portal.create_invite(cursor, profile_id=profile_id, created_by=user_id)
        invite_token = invite["invite_url"].rsplit("/", 1)[-1]
        claim = portal.claim_email(cursor, invite_token=invite_token, email="author@example.test", password="strong-password")
        assert claim["verification_required"] is True
        try:
            portal.claim_email(cursor, invite_token=invite_token, email="author2@example.test", password="strong-password")
            raise AssertionError("invite was reusable")
        except LookupError:
            pass
        verify_token = portal._new_token(cursor, profile_id=profile_id, purpose="email_verify", email="author@example.test", created_by=None, hours=1)
        session = portal.verify_email(cursor, verify_token)
        account = portal.authenticate_creator(cursor, session["token"])
        assert portal.login_email(cursor, email="author@example.test", password="strong-password")["token"]
        home = portal.portal_home(cursor, account)
        assert [item["id"] for item in home["offers"]["new"]] == [approved_id]
        assert all(item["id"] != draft_id for group in home["offers"].values() for item in group)

        visible = portal.list_relationships(cursor, business_id=business_id, is_superadmin=False, stages=["contact_ready"], limit=20)
        assert visible["items"] and "contact_value" not in visible["items"][0]
        isolated = portal.list_relationships(cursor, business_id=other_business_id, is_superadmin=False, limit=20)
        assert isolated["items"] == []

        cursor.execute("INSERT INTO creator_notification_outbox (id, creator_account_id, collaboration_id, channel, event_type, dedupe_key) SELECT %s, id, %s, 'email', 'reminder', %s FROM creator_accounts WHERE creator_profile_id = %s", (identifier("notice"), approved_id, "smoke-reminder", profile_id))
        updated = portal.creator_respond(cursor, account=account, collaboration_id=approved_id, action="accept", message="Готов обсудить")
        assert updated["status"] == "agreed"
        cursor.execute("SELECT stage FROM creator_relationships WHERE creator_profile_id = %s", (profile_id,))
        assert cursor.fetchone()["stage"] == "interested"
        cursor.execute("SELECT status FROM creator_notification_outbox WHERE dedupe_key = 'smoke-reminder'")
        assert cursor.fetchone()["status"] == "cancelled"

        telegram_invite = portal.create_invite(cursor, profile_id=telegram_profile_id, created_by=user_id)
        telegram_token = telegram_invite["invite_url"].rsplit("/", 1)[-1]
        telegram_claim = portal.claim_telegram(cursor, invite_token=telegram_token, telegram_id="123456789", telegram_username="smoke_creator")
        assert "/creator/login/telegram?token=" in telegram_claim["portal_url"]
        assert portal.telegram_creator_portal_link(cursor, "123456789")

        portal.update_creator_profile(cursor, account=account, payload={"home_district": "Выборгский", "accepts_barter": True})
        cursor.execute("SELECT COUNT(*) AS count FROM creator_profile_change_events WHERE creator_profile_id = %s", (profile_id,))
        assert cursor.fetchone()["count"] == 1
        print("OK: invite-once, email login, Telegram login, approved-only offers, tenant isolation, hidden contacts, stop-on-reply, profile audit")
        return 0
    finally:
        connection.rollback()
        connection.close()


if __name__ == "__main__":
    raise SystemExit(main())
