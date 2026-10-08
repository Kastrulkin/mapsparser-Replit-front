"""Pure content selection plus the existing, consent-gated delivery boundary.

Generated source sees immutable post data, never a bot token or a connection.
The host independently validates every returned request before dispatch.
"""
import json
import os
import uuid
from datetime import datetime, timezone

from services.compiled_content_handoff import handoff_scope, has_active_consent
from services.compiled_input_snapshots import content_hash, SnapshotUnavailable

SCHEMA = 'localos_content_handoff_input_v1'


def delivery_context(cursor, contract):
    scope = contract['scope']
    cursor.execute('''SELECT p.telegram_id,u.name,u.is_active FROM telegramcontrolpreferences p
        JOIN users u ON u.id=p.user_id WHERE p.user_id=%s''', (scope['recipient_user_id'],))
    recipient = cursor.fetchone() or {}
    if not recipient.get('is_active') or not recipient.get('telegram_id'):
        raise SnapshotUnavailable('compiled_content_recipient_not_connected')
    cursor.execute('SELECT name,address FROM businesses WHERE id=%s', (scope['business_id'],))
    business = cursor.fetchone() or {}
    value = {'scope': scope, 'telegram_id': str(recipient['telegram_id']),
             'recipient_name': str(recipient.get('name') or ''),
             'business_name': str(business.get('name') or ''), 'address': str(business.get('address') or '')}
    return {**value, 'digest': content_hash(value)}


def program_allowed(business_id, blueprint_id):
    from services.compiled_pilot_access import compiled_pilot_allowed
    ids = {value.strip() for value in os.getenv('COMPILED_CONTENT_HANDOFF_BLUEPRINT_IDS', '').split(',') if value.strip()}
    return compiled_pilot_allowed(business_id, execute=True) and str(blueprint_id) in ids


def contract_for(version, business_id):
    scope = handoff_scope(version, business_id)
    if not scope:
        raise ValueError('compiled_content_scope_invalid')
    return {'version': 1, 'scope': scope, 'capability': 'content.publish_handoff'}


def manifest_for(contract, runner_digest):
    scope = contract.get('scope') if isinstance(contract, dict) else None
    if not scope or contract.get('version') != 1 or contract.get('capability') != 'content.publish_handoff':
        raise ValueError('compiled_content_contract_invalid')
    request_schema = {'type': 'object', 'required': ['post_id', 'revision'], 'additionalProperties': False,
                      'properties': {'post_id': {'type': 'string'}, 'revision': {'type': 'string'}}}
    return {'kind': 'localos.python_transform.v1', 'runtime_version': 'python-3.12-restricted-v1',
            'runner_image_digest': runner_digest, 'dependencies': [], 'uses_model': False,
            'external_effects': False, 'content_handoff_contract': contract,
            'input_schema': {'type': 'object', 'required': ['posts'], 'additionalProperties': False,
                'properties': {'posts': {'type': 'array', 'maxItems': 100,
                    'items': {'type': 'object', 'required': ['post_id', 'revision', 'eligible'],
                        'properties': {'post_id': {'type': 'string'}, 'revision': {'type': 'string'},
                            'eligible': {'type': 'boolean'}, 'text': {'type': 'string'},
                            'platform': {'type': 'string'}, 'photo_asset_id': {'type': 'string'},
                            'blocked_reason': {'type': 'string'}}}}}},
            'output_schema': {'type': 'object', 'required': ['requests'], 'additionalProperties': False,
                'properties': {'requests': {'type': 'array', 'maxItems': 100, 'items': request_schema}}}}


def validation_fixtures():
    # Expected outputs are platform-owned examples of the reviewed send rules,
    # not expectations invented by the generator.
    return [
        {'source': 'platform', 'input': {'posts': []}, 'expected': {'requests': []}},
        {'source': 'platform', 'input': {'posts': [
            {'post_id': 'ready', 'revision': 'r1', 'eligible': True},
            {'post_id': 'draft', 'revision': 'r2', 'eligible': False}]},
         'expected': {'requests': [{'post_id': 'ready', 'revision': 'r1'}]}},
    ]


def validate_requests(result, input_payload):
    requests = result.get('requests')
    if not isinstance(requests, list) or len(requests) > 100:
        raise ValueError('compiled_content_requests_invalid')
    allowed = {(row['post_id'], row['revision']) for row in input_payload.get('posts', [])
               if row.get('eligible') is True}
    seen = set()
    for request in requests:
        if not isinstance(request, dict) or set(request) != {'post_id', 'revision'}:
            raise ValueError('compiled_content_request_invalid')
        key = (request['post_id'], request['revision'])
        if key not in allowed or key in seen:
            raise ValueError('compiled_content_request_out_of_scope')
        seen.add(key)
    return requests


def collect_input(conn, contract, now=None):
    from services.content_publish_notifications import collect_due_content_publish_handoffs
    scope = contract['scope']
    cursor = conn.cursor()
    cursor.execute('SELECT telegram_id FROM telegramcontrolpreferences WHERE user_id=%s',
                   (scope['recipient_user_id'],))
    row = cursor.fetchone()
    if not row or not row.get('telegram_id'):
        raise SnapshotUnavailable('compiled_content_recipient_not_connected')
    send_scope = {**scope, 'user_id': scope['recipient_user_id'], 'telegram_id': str(row['telegram_id']),
                  'handoff_time': scope['time'], 'lead_days': str(scope['lead_days']),
                  'required_platforms': scope['platforms'], 'business_timezone': scope['timezone']}
    due = collect_due_content_publish_handoffs(conn, now=now, limit=100,
        business_id=scope['business_id'], recipient_user_id=scope['recipient_user_id'], compiled_scope=send_scope)
    return {'posts': [{'post_id': str(post['id']), 'revision': post['revision'],
        'eligible': not bool(post.get('blocked_reason')), 'blocked_reason': post.get('blocked_reason') or '',
        'text': str(post.get('platform_text') or post.get('base_text') or ''),
        'platform': post.get('platform'),
        'photo_asset_id': str((post.get('selected_photo') or {}).get('id') or '')} for post in due]}


def create_content_snapshot(cursor, *, blueprint, version, user_id, now=None):
    from services.operator_audio import authorize_actor
    business_id = str(blueprint['business_id'])
    authorize_actor(cursor, user_id, business_id, check_subscription=False)
    artifact = version.get('compiled_artifact_json') or {}
    if isinstance(artifact, str):
        artifact = json.loads(artifact)
    contract = (artifact.get('manifest') or {}).get('content_handoff_contract')
    if contract != contract_for(version, business_id):
        raise SnapshotUnavailable('compiled_content_contract_changed')
    authorize_actor(cursor, contract['scope']['recipient_user_id'], business_id, check_subscription=False)
    from services.compiled_input_snapshots import SnapshotQuotaExceeded
    cursor.execute('SELECT pg_advisory_xact_lock(hashtext(%s))', (f'compiled-snapshots:{business_id}:{user_id}',))
    cursor.execute('SELECT COUNT(*) count FROM compiled_input_snapshots WHERE business_id=%s AND user_id=%s AND expires_at>NOW()', (business_id, user_id))
    if cursor.fetchone()['count'] >= 100:
        raise SnapshotQuotaExceeded('compiled_snapshot_quota_exceeded')
    context = delivery_context(cursor, contract)
    value = collect_input(cursor.connection, contract, now)
    digest = content_hash(value)
    snapshot_id = str(uuid.uuid4())
    cursor.execute('''INSERT INTO compiled_input_snapshots
        (id,business_id,user_id,blueprint_id,source_kind,source_name,schema_version,content_hash,input_json,row_count)
        VALUES (%s,%s,%s,%s,'content_plan','Публикации из плана',%s,%s,%s::jsonb,%s)''',
        (snapshot_id, business_id, user_id, str(blueprint['id']), SCHEMA, digest,
         json.dumps(value, ensure_ascii=False), len(value['posts'])))
    return {'snapshot_id': snapshot_id, 'content_hash': digest, 'schema_version': SCHEMA,
            'source_kind': 'content_plan', 'input': value, 'delivery_context': context}


def dispatch_result(prepared, result):
    """No new transport: invoke the registered, approved capability handler."""
    from services.agent_capability_handlers import _handle_content_publish_handoff
    from database_manager import DatabaseManager
    run = prepared['run']
    artifact = prepared['artifact']
    contract = artifact['manifest']['content_handoff_contract']
    requests = validate_requests(result, prepared['input'])
    if not program_allowed(str(run['business_id']), str(run['blueprint_id'])):
        raise ValueError('compiled_content_pilot_not_allowed')
    database = DatabaseManager()
    try:
        cursor = database.conn.cursor()
        if not dispatch_fence(cursor, run, artifact['artifact_hash'], contract['scope']):
            raise ValueError('compiled_content_dispatch_revoked')
    finally:
        database.rollback_and_close()
    envelope = {'tenant_id': str(run['business_id']),
        'actor': {'user_id': str(run['created_by_user_id'])},
        'approval': {'content_handoff_consent': True},
        'payload': {**contract['scope'], 'requested_post_versions': requests,
            'compiled_dispatch': {'run_id': str(run['id']), 'lease_token': run['lease_token'],
                'blueprint_id': str(run['blueprint_id']), 'version_id': str(run['blueprint_version_id']),
                'artifact_hash': artifact['artifact_hash']}}}
    delivery = _handle_content_publish_handoff(envelope, {'user_id': str(run['created_by_user_id']), 'is_superadmin': False})
    return {**result, 'handoff': delivery, 'publication_status_unchanged': True}


def dispatch_fence(cursor, run, artifact_hash, scope):
    cursor.execute('''SELECT r.status,r.lease_token,b.status AS blueprint_status,b.metadata_json,
        b.compiled_approved_version_id,v.compiled_artifact_hash,v.compiled_state
        FROM agent_runs r JOIN agent_blueprints b ON b.id=r.blueprint_id
        JOIN agent_blueprint_versions v ON v.id=r.blueprint_version_id
        WHERE r.id=%s AND r.blueprint_id=%s AND r.blueprint_version_id=%s''',
        (run['id'], run['blueprint_id'], run['blueprint_version_id']))
    row = cursor.fetchone() or {}
    metadata = row.get('metadata_json') or {}
    if isinstance(metadata, str):
        metadata = json.loads(metadata)
    consent = metadata.get('compiled_content_handoff_consent') or {}
    cursor.execute('SELECT telegram_id FROM telegramcontrolpreferences WHERE user_id=%s', (scope['recipient_user_id'],))
    binding = cursor.fetchone() or {}
    return (row.get('status') == 'running' and row.get('lease_token') == run['lease_token']
        and row.get('blueprint_status') in {'draft', 'active'}
        and str(row.get('compiled_approved_version_id')) == str(run['blueprint_version_id'])
        and row.get('compiled_artifact_hash') == artifact_hash
        and consent.get('artifact_hash') == artifact_hash
        and bool(consent.get('telegram_id'))
        and consent.get('telegram_id') == str(binding.get('telegram_id') or '')
        and row.get('compiled_state') in {'approved', 'active'}
        and has_active_consent(metadata, version_id=str(run['blueprint_version_id']), scope=scope))
