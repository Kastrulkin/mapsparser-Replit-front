from datetime import datetime,timezone
from services.outreach_email_reply_service import _match_queue_item


def test_same_address_across_groups_without_thread_is_not_assigned_arbitrarily():
    candidates=[{'id':'a','recipient_value':'shared@example.org','provider_message_id':'<a@mail>','sent_at':datetime(2026,10,1,tzinfo=timezone.utc)},
                {'id':'b','recipient_value':'shared@example.org','provider_message_id':'<b@mail>','sent_at':datetime(2026,10,1,tzinfo=timezone.utc)}]
    assert _match_queue_item({'from_email':'shared@example.org'},candidates) is None
    assert _match_queue_item({'from_email':'shared@example.org','in_reply_to':'<b@mail>'},candidates)['id']=='b'


def test_overlapping_recipient_is_read_once_but_native_campaign_identity_is_retained():
    from services.outreach_email_reply_service import partition_reply_scopes
    ordinary=[{'id':'regular','recipient_value':'SHARED@example.org','provider_message_id':'<regular@mail>'},
              {'id':'other','recipient_value':'other@example.org','provider_message_id':'<other@mail>'}]
    addresses,overlap=partition_reply_scopes(['shared@example.org'],ordinary)
    assert addresses==['other@example.org']
    assert overlap==[ordinary[0]]
    scoped=[{'id':'template','recipient_value':'shared@example.org','provider_message_id':'<template@mail>'}]+overlap
    assert _match_queue_item({'in_reply_to':'<regular@mail>','from_email':'shared@example.org'},scoped)['id']=='regular'
    assert _match_queue_item({'in_reply_to':'<template@mail>','from_email':'shared@example.org'},scoped)['id']=='template'
    assert _match_queue_item({'from_email':'shared@example.org'},scoped) is None


def test_direct_parent_takes_priority_over_old_messages_quoted_in_thread():
    rows=[{'id':'old','provider_message_id':'<old@mail>'},{'id':'new','provider_message_id':'<new@mail>'}]
    assert _match_queue_item({'in_reply_to':'<new@mail>','references':'<old@mail> <new@mail>'},rows)['id']=='new'
    assert _match_queue_item({'references':'<old@mail> <new@mail>'},rows) is None
