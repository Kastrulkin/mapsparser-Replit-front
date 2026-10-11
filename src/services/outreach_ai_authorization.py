"""Versioned AI outreach rules in the existing sender permission-event journal.

This permission is deliberately distinct from any approved template permission.
No grant is inferred from a sender connection, a model response or a prior send.
"""
import hashlib
import json
import uuid
from datetime import datetime, timezone

from psycopg2.extras import Json

from services.riderra_template_authorization_service import BUSINESS_ID, SENDER_ACCOUNT_ID, DAILY_LIMIT

PERMISSION_KIND = 'outreach_ai_rules_v1'
APPROVAL_MODE = 'ai_rules'


class AuthorizationBusy(ValueError):
    """A transient lock conflict, never a revoked permission."""



def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


def normalize_rules(raw):
    if not isinstance(raw, dict):
        raise ValueError('ai_rules_required')
    result = {'schema': PERMISSION_KIND, 'business_id': BUSINESS_ID,
              'sender_account_id': SENDER_ACCOUNT_ID, 'channels': ['email'],
              'stop_on_any_reply': True, 'automatic_replies': False,
              'followups': False}
    if raw.get('business_id') != BUSINESS_ID or raw.get('sender_account_id') != SENDER_ACCOUNT_ID:
        raise ValueError('ai_rules_sender_scope_invalid')
    if raw.get('mode') != 'auto_send':
        raise ValueError('ai_rules_auto_send_intent_required')
    result['mode'] = 'auto_send'
    if raw.get('channels') != ['email'] or raw.get('followups', False) is not False:
        raise ValueError('ai_rules_first_email_only')
    for key in ('audience', 'agency_country', 'sold_destination', 'offer', 'language'):
        value = raw.get(key)
        if not isinstance(value, str) or not value.strip() or len(value) > 2000:
            raise ValueError('ai_rules_' + key + '_required')
        result[key] = value.strip()
    for key in ('requirements', 'search_geography'):
        if key in raw:
            value = raw[key]
            if not isinstance(value, list) or len(value) > 20 or any(not isinstance(item, str) or not item.strip() or len(item) > 300 for item in value):
                raise ValueError('ai_rules_' + key + '_invalid')
            result[key] = value
    for key, maximum in (('target_count', 1000), ('daily_limit', DAILY_LIMIT),
                         ('max_qualification_calls', 10000), ('max_draft_attempts', 10000), ('max_search_calls', 20), ('search_budget_cents', 1000)):
        value = raw.get(key)
        if type(value) is not int or not 1 <= value <= maximum:
            raise ValueError('ai_rules_' + key + '_invalid')
        result[key] = value
    claims = raw.get('allowed_claims')
    if not isinstance(claims, list) or not 1 <= len(claims) <= 30:
        raise ValueError('ai_rules_claims_required')
    result['allowed_claims'] = []
    for claim in claims:
        if not isinstance(claim, dict) or not all(isinstance(claim.get(key), str) and claim[key].strip() for key in ('text', 'source')):
            raise ValueError('ai_rules_claim_source_required')
        normalized = {'text': claim['text'].strip(), 'source': claim['source'].strip()}
        if len(normalized['text']) > 2000 or len(normalized['source']) > 1000:
            raise ValueError('ai_rules_claim_too_long')
        if claim.get('valid_until'):
            expiry = datetime.fromisoformat(claim['valid_until'])
            if not expiry.tzinfo:
                raise ValueError('ai_rules_claim_timezone_required')
            normalized['valid_until'] = expiry.isoformat()
        result['allowed_claims'].append(normalized)
    process = raw.get('process') or {}
    if process.get('type') not in {'automation', 'one_off'}:
        raise ValueError('ai_rules_process_required')
    if not all(isinstance(process.get(key), str) and process[key] for key in ('id', 'revision')):
        raise ValueError('ai_rules_process_revision_required')
    result['process'] = {key: process[key] for key in ('type', 'id', 'revision')}
    return result


def _process_config(cursor, rules, *, require_running):
    process = rules['process']
    if process['type'] == 'one_off':
        cursor.execute("SELECT * FROM operator_async_jobs WHERE id=%s AND business_id=%s AND kind='outreach_continue' FOR SHARE",
                       (process['id'], rules['business_id']))
        row = dict(cursor.fetchone() or {})
        config = row.get('payload_json') or {}
        # The grant identifier is an execution reference, not part of the rules.
        config = {key: value for key, value in config.items() if key != 'ai_authorization_id'}
        from services.outreach_continuation import config_hash
        if not row or config_hash(config) != process['revision']:
            return None
        if require_running and row.get('status') not in {'queued', 'running', 'completed'}:
            return None
        if row.get('status') == 'cancelled':
            return None
        return config
    cursor.execute('SELECT status,metadata_json FROM agent_blueprints WHERE id=%s AND business_id=%s FOR SHARE',
                   (process['id'], rules['business_id']))
    blueprint = dict(cursor.fetchone() or {})
    if not blueprint or blueprint.get('status') == 'archived':
        return None
    if require_running and (blueprint.get('status') != 'active' or
            (blueprint.get('metadata_json') or {}).get('active_version_id') != process['revision']):
        return None
    cursor.execute('SELECT runtime_config_json FROM agent_blueprint_versions WHERE id=%s AND blueprint_id=%s',
                   (process['revision'], process['id']))
    version = dict(cursor.fetchone() or {})
    return (version.get('runtime_config_json') or {}).get('outreach_config')


def process_matches(cursor, rules, *, require_running):
    config = _process_config(cursor, rules, require_running=require_running)
    if not isinstance(config, dict):
        return False
    return all(config.get(key) == rules[key] for key in
               ('mode', 'audience', 'agency_country', 'sold_destination', 'offer', 'language', 'target_count', 'search_budget_cents', 'max_qualification_calls', 'max_draft_attempts', 'max_search_calls'))


def _sender_and_actor(cursor, actor_id, *, require_ready=True):
    cursor.execute('SELECT id FROM users WHERE id=%s AND is_active=TRUE AND is_superadmin=TRUE', (actor_id,))
    if not cursor.fetchone():
        return False
    from services.riderra_template_authorization_service import _canonical_sender
    sender = _canonical_sender(cursor, SENDER_ACCOUNT_ID)
    caps = sender.get('capabilities_json') or {}
    return bool(sender and (not require_ready or (sender.get('status') == 'connected'
        and sender.get('outreach_enabled') and sender.get('health_status') not in {'paused', 'blocked'}
        and caps.get('direct_send') is True and caps.get('reply_sync') is True)))


def _lock(cursor, rules):
    process = rules['process']
    cursor.execute('SELECT pg_try_advisory_xact_lock(hashtext(%s)) AS acquired',
                   (f"ai-outreach:{rules['sender_account_id']}:{process['type']}:{process['id']}",))
    return bool((cursor.fetchone() or {}).get('acquired'))


def _latest(cursor, rules):
    process = rules['process']
    cursor.execute("""SELECT * FROM outreach_sender_account_events
        WHERE sender_account_id=%s AND event_type='permission_changed'
          AND payload_json->>'permission_kind'=%s
          AND payload_json->'rules'->'process'->>'type'=%s
          AND payload_json->'rules'->'process'->>'id'=%s
        ORDER BY created_at DESC,id DESC LIMIT 1""",
        (rules['sender_account_id'], PERMISSION_KIND, process['type'], process['id']))
    return dict(cursor.fetchone() or {})


def preview(cursor, *, rules, actor_id, actor_context, enabled=True):
    if not actor_context or actor_context.get('session_kind', 'standard') != 'standard' or actor_context.get('impersonating') or actor_context.get('impersonated_by'):
        raise PermissionError('ai_rules_direct_session_required')
    rules = normalize_rules(rules)
    if not _sender_and_actor(cursor, actor_id, require_ready=enabled):
        raise PermissionError('ai_rules_authority_or_sender_unavailable')
    if enabled and not process_matches(cursor, rules, require_running=False):
        raise ValueError('ai_rules_process_conditions_changed')
    return {'rules': rules, 'rules_hash': digest(rules), 'permission_kind': PERMISSION_KIND,
            'model_cost': None, 'model_cost_status': 'not_estimated',
            'requires_explicit_confirmation': True, 'enabled': enabled}


def confirm(cursor, *, rules, rules_hash, actor_id, actor_context, action_id, enabled=True):
    """Called only while confirming the persisted existing Operator action."""
    if type(enabled) is not bool:
        raise ValueError('ai_rules_decision_invalid')
    reviewed = preview(cursor, rules=rules, actor_id=actor_id, actor_context=actor_context, enabled=enabled)
    rules = reviewed['rules']
    if rules_hash != reviewed['rules_hash']:
        raise ValueError('ai_rules_preview_changed')
    cursor.execute('SELECT * FROM operatoractions WHERE id=%s AND user_id=%s FOR UPDATE', (action_id, actor_id))
    action = dict(cursor.fetchone() or {})
    envelope = action.get('envelope_json') or {}
    if (action.get('capability') != 'outreach.ai_rules' or action.get('business_id') != rules['business_id']
            or envelope.get('rules_hash') != rules_hash or envelope.get('rules') != rules
            or type(envelope.get('enabled')) is not bool or envelope['enabled'] != enabled
            or action.get('status') not in {'pending', 'pending_approval', 'confirmed', 'completed'}):
        raise PermissionError('ai_rules_explicit_confirmation_required')
    expires = action.get('expires_at')
    if not expires or expires <= datetime.now(timezone.utc):
        raise PermissionError('ai_rules_confirmation_expired')
    if not _lock(cursor, rules):
        raise AuthorizationBusy('ai_rules_permission_busy')
    previous = _latest(cursor, rules)
    if (previous.get('payload_json') or {}).get('action_id') == action_id:
        return previous
    cursor.execute("SELECT id FROM outreach_sender_account_events WHERE sender_account_id=%s AND event_type='permission_changed' AND payload_json->>'permission_kind'=%s AND payload_json->>'action_id'=%s LIMIT 1",
                   (rules['sender_account_id'],PERMISSION_KIND,action_id))
    if cursor.fetchone() or action.get('status') not in {'pending', 'pending_approval'}:
        raise PermissionError('ai_rules_confirmation_already_used')
    event_id = str(uuid.uuid4())
    payload = {'permission_kind': PERMISSION_KIND, 'state': 'active' if enabled else 'revoked',
               'rules': rules, 'rules_hash': rules_hash, 'action_id': action_id,
               'replaces_event_id': str(previous.get('id') or '')}
    cursor.execute("""INSERT INTO outreach_sender_account_events
        (id,sender_account_id,event_type,actor_id,payload_json,created_at)
        VALUES(%s,%s,'permission_changed',%s,%s,clock_timestamp()) RETURNING *""",
        (event_id, rules['sender_account_id'], actor_id, Json(payload)))
    return dict(cursor.fetchone())


def load(cursor, authorization_id, *, require_running=True):
    cursor.execute("SELECT * FROM outreach_sender_account_events WHERE id=%s AND event_type='permission_changed' AND payload_json->>'permission_kind'=%s",
                   (authorization_id, PERMISSION_KIND))
    event = dict(cursor.fetchone() or {})
    payload = event.get('payload_json') or {}
    if not event or payload.get('state') != 'active':
        return None
    try:
        rules = normalize_rules(payload.get('rules'))
    except (ValueError, TypeError):
        return None
    if not _lock(cursor, rules):
        raise AuthorizationBusy('ai_rules_permission_busy')
    if str(_latest(cursor, rules).get('id') or '') != str(event['id']):
        return None
    if payload.get('rules_hash') != digest(rules) or not _sender_and_actor(cursor, event.get('actor_id')):
        return None
    if any(claim.get('valid_until') and datetime.fromisoformat(claim['valid_until']) <= datetime.now(timezone.utc)
           for claim in rules['allowed_claims']):
        return None
    if not process_matches(cursor, rules, require_running=require_running):
        return None
    return {**event, 'rules': rules, 'rules_hash': payload['rules_hash']}


def for_job(cursor, job, *, require_running=True):
    state = job.get('result_json') or {}
    process_type, process_id, process_revision = 'one_off', str(job['id']), None
    if state.get('agent_run_id'):
        cursor.execute('SELECT blueprint_id,blueprint_version_id FROM agent_runs WHERE id=%s AND business_id=%s',
                       (state['agent_run_id'], job['business_id']))
        run = dict(cursor.fetchone() or {})
        if not run:
            return None
        process_type, process_id, process_revision = 'automation', str(run['blueprint_id']), str(run['blueprint_version_id'])
    event_id = state.get('ai_authorization_id')
    if not event_id:
        cursor.execute("""SELECT id FROM outreach_sender_account_events WHERE sender_account_id=%s
            AND event_type='permission_changed' AND payload_json->>'permission_kind'=%s
            AND payload_json->'rules'->'process'->>'type'=%s AND payload_json->'rules'->'process'->>'id'=%s
            ORDER BY created_at DESC,id DESC LIMIT 1""", (SENDER_ACCOUNT_ID,PERMISSION_KIND,process_type,process_id))
        event_id = dict(cursor.fetchone() or {}).get('id')
    grant = load(cursor,str(event_id),require_running=require_running) if event_id else None
    if not grant:
        return None
    config = job.get('payload_json') or {}
    if any(config.get(key) != grant['rules'].get(key) for key in ('requirements', 'search_geography')):
        return None
    process = grant['rules']['process']
    if process['type'] != process_type or process['id'] != process_id or (process_revision and process['revision'] != process_revision):
        return None
    config = job.get('payload_json') or {}
    if not all(config.get(key) == grant['rules'][key] for key in ('mode','audience','agency_country','sold_destination','offer','language',
            'target_count','search_budget_cents','max_qualification_calls','max_draft_attempts','max_search_calls')):
        return None
    return grant


def operator_preview(cursor, *, business_id, user_id, arguments, actor_context=None):
    """Prepare the existing Operator confirmation; never grant inside a tool call."""
    if business_id != BUSINESS_ID:
        return {'status':'blocked','blocked_reasons':['ai_rules_business_scope_invalid']}
    try:
        enabled=arguments.get('enabled')
        if type(enabled) is not bool:raise ValueError('ai_rules_decision_required')
        rules=arguments.get('rules')
        if not enabled and arguments.get('authorization_id'):
            cursor.execute("SELECT payload_json FROM outreach_sender_account_events WHERE id=%s AND sender_account_id=%s AND payload_json->>'permission_kind'=%s",
                           (arguments['authorization_id'],SENDER_ACCOUNT_ID,PERMISSION_KIND))
            rules=(dict(cursor.fetchone() or {}).get('payload_json') or {}).get('rules')
        checked=preview(cursor,rules=rules,actor_id=user_id,actor_context=actor_context,enabled=enabled)
        rules=checked['rules']
        claims='; '.join(claim['text']+' [источник: '+claim['source']+']' for claim in rules['allowed_claims'])
        summary=(f"{'Разрешить' if enabled else 'Отозвать разрешение'} AI-писем Riderra. "
            f"Аудитория: {rules['audience']}; страна компаний: {rules['agency_country']}; продаваемое направление: {rules['sold_destination']}. "
            f"Цель {rules['target_count']} новых компаний; язык {rules['language']}; предложение: {rules['offer']}. "
            f"Отправитель riderracs@gmail.com; одно первое письмо; до {rules['daily_limit']} компаний в день в пределах общего лимита отправителя. "
            f"Поиск до {rules['search_budget_cents']/100:.2f} USD и {rules['max_search_calls']} вызовов; "
            f"до {rules['max_qualification_calls']} проверок и {rules['max_draft_attempts']} подготовок. Стоимость моделей пока не оценена. "
            f"Допустимые утверждения: {claims}. Ответ или отказ прекращает дальнейшие касания. Самостоятельных ответов и follow-up нет.")
        return {'status':'approval_required','chat_response':summary,
                'approval':{'status':'pending','capability':'outreach.ai_rules','summary':summary,
                    'envelope':{'business_id':business_id,'rules':rules,'rules_hash':checked['rules_hash'],'enabled':enabled}},
                'external_writes_performed':False}
    except (ValueError,TypeError,PermissionError) as exc:
        return {'status':'blocked','blocked_reasons':[str(exc)]}
