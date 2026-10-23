"""Read completed source collections without enabling automated search or sends."""
COLLECTION_KIND = 'partnership_source_collection'


def load_collections(cursor, *, business_id, task_id=None):
    clause = ' AND id=%s' if task_id else ''
    params = (COLLECTION_KIND, business_id, task_id) if task_id else (COLLECTION_KIND, business_id)
    cursor.execute("SELECT * FROM operator_async_jobs WHERE kind=%s AND business_id=%s AND status='completed'" + clause + ' ORDER BY created_at DESC LIMIT 50', params)
    return [dict(row) for row in cursor.fetchall()]


def collection_state(cursor, row):
    state = dict(row.get('result_json') or {})
    lead_ids = list(dict.fromkeys(str(value) for value in state.get('lead_ids') or []))
    state['campaign_results'] = {}
    if lead_ids:
        cursor.execute('''SELECT DISTINCT ON (c.workstream_id) c.id,c.workstream_id,c.lead_id,c.status
            FROM outreach_campaigns c WHERE c.business_id=%s
              AND c.lead_id IN (''' + ','.join(['%s'] * len(lead_ids)) + ''')
              AND c.policy_json->>'human_copy_hash' IS NOT NULL
            ORDER BY c.workstream_id,c.version DESC''', (row['business_id'], *lead_ids))
        state['campaign_results'] = {str(item['workstream_id']): {
            'campaign_id': str(item['id']), 'lead_id': str(item['lead_id']),
            'status': 'needs_manual_review', 'manual_review_required': True,
        } for item in cursor.fetchall()}
    return state


def collection_view(cursor, row, *, viewer_id):
    from services.outreach_continuation import view, delivery_report
    from services.partnership_group_view import enrich_group
    state = collection_state(cursor, row)
    result = view({**row, 'result_json': state})
    result['read_only_collection'] = True
    result['report'].update(delivery_report(cursor, result))
    enrich_group(cursor, result, viewer_id=viewer_id)
    return result


def saved_collection_response(cursor, *, business_id, viewer_id, task_id=None):
    """Caller retains normal tenant, business-write and tariff checks."""
    rows = load_collections(cursor, business_id=business_id, task_id=task_id)
    if task_id:
        if not rows:
            return {'error': 'task_not_found'}, 404
        return collection_view(cursor, rows[0], viewer_id=viewer_id), 200
    return {'enabled': False, 'read_only_collections': True,
            'items': [collection_view(cursor, row, viewer_id=viewer_id) for row in rows]}, 200
