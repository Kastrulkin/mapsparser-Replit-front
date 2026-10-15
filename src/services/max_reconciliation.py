"""Inspect provider evidence for a delivery; never resend a message or business action."""
import re
import time
from urllib.parse import quote
from services.max_transport import MaxTransportError


def inspect_delivery(reply, message_ids, transport):
    from services.max_bot import split_reply
    if not isinstance(reply, dict) or not str(reply.get('user_id') or '').isdigit():
        return {'verified': False, 'reason': 'delivery_evidence_missing'}
    messages = reply.get('messages') or [{'text': reply.get('text') or '', 'attachments': reply.get('attachments') or []}]
    expected = []
    for item in messages:
        parts = split_reply(item.get('text') or '')
        expected.extend({'text': text, 'attachments': item.get('attachments') or [] if index == len(parts)-1 else []}
            for index, text in enumerate(parts))
    if not expected or len(message_ids) != len(expected) or len(expected) > 12 or len(set(message_ids)) != len(message_ids):
        return {'verified': False, 'reason': 'incomplete_message_ids'}
    if any(not isinstance(mid, str) or not re.fullmatch(r'[A-Za-z0-9_.:-]{1,256}', mid) for mid in message_ids):
        return {'verified': False, 'reason': 'invalid_message_ids'}
    evidence = []
    deadline = time.monotonic() + 20
    for mid, item in zip(message_ids, expected):
        if time.monotonic() >= deadline:
            return {'verified': False, 'reason': 'verification_timeout', 'messages': evidence}
        try:
            result = transport.call('GET', '/messages/' + quote(mid, safe=''))
        except MaxTransportError:
            return {'verified': False, 'reason': 'provider_unavailable', 'messages': evidence}
        body = result.get('body') or {}
        matches = (str(body.get('mid')) == mid and str((result.get('recipient') or {}).get('user_id')) == str(reply['user_id'])
            and body.get('text') == item['text'] and (body.get('attachments') or []) == item['attachments'])
        evidence.append({'mid': mid, 'matches': matches})
        if not matches:
            return {'verified': False, 'reason': 'provider_content_or_recipient_mismatch', 'messages': evidence}
    return {'verified': True, 'reason': 'provider_confirmed', 'messages': evidence}
