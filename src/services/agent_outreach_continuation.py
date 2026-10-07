"""Bridge an existing workflow step to the existing durable outreach worker."""
from psycopg2.extras import Json


def request(envelope, user_data):
    # The public orchestrator cannot enqueue a paid search. Only the runner can
    # bind the request to its persisted, active, version-pinned workflow step.
    return {'status': 'outreach_continuation_request', 'external_dispatch_performed': False}


def bind(cursor, *, run, version, step_id):
    from services.outreach_continuation import normalize_config, KIND, _require_current_actor
    from services.operator_async_jobs import create_operator_async_job
    cursor.execute('SELECT status,metadata_json FROM agent_blueprints WHERE id=%s AND business_id=%s FOR SHARE',
                   (run['blueprint_id'], run['business_id']))
    blueprint = dict(cursor.fetchone() or {})
    if (blueprint.get('status') != 'active' or
            str((blueprint.get('metadata_json') or {}).get('active_version_id')) != str(run['blueprint_version_id']) or
            str(version.get('id')) != str(run['blueprint_version_id'])):
        raise ValueError('outreach_active_version_required')
    raw_config = (version.get('runtime_config_json') or {}).get('outreach_config')
    config = normalize_config(raw_config)
    if config != raw_config:
        raise ValueError('outreach_reviewed_config_required')
    actor_id = str(run.get('created_by_user_id') or '')
    _require_current_actor(cursor, {'user_id':actor_id, 'business_id':run['business_id']})
    cursor.execute("SELECT id FROM agent_run_steps WHERE id=%s AND run_id=%s AND status='running'", (step_id,run['id']))
    if not cursor.fetchone():
        raise ValueError('outreach_running_step_required')
    job = create_operator_async_job(cursor, user_id=actor_id, business_id=run['business_id'], action_id=None,
        kind=KIND, payload=config, idempotency_key=f"agent-outreach:{run['id']}:{step_id}",
        stage='Поиск и проверка компаний по условиям автоматизации', max_attempts=3)
    state = {'phase':'search','started':True,'search_calls':0,'workstream_ids':[],'lead_ids':[],
             'history':[],'agent_run_id':str(run['id']),'agent_step_id':str(step_id)}
    cursor.execute("""UPDATE operator_async_jobs SET result_json=%s WHERE id=%s
                      AND result_json='{}'::jsonb AND status='queued'""",(Json(state),job['id']))
    cursor.execute('SELECT * FROM operator_async_jobs WHERE id=%s', (job['id'],))
    job = dict(cursor.fetchone())
    if config['mode'] == 'auto_send':
        from services.outreach_ai_authorization import for_job
        grant = for_job(cursor,job)
        if not grant:
            raise ValueError('outreach_ai_rules_required')
        cursor.execute("UPDATE operator_async_jobs SET result_json=result_json || %s WHERE id=%s",
                       (Json({'ai_authorization_id':str(grant['id'])}),job['id']))
    cursor.execute("UPDATE agent_run_steps SET status='waiting_provider',output_json=%s WHERE id=%s",
                   (Json({'capability':'outreach.continue','job_id':str(job['id'])}),step_id))
    cursor.execute("UPDATE agent_runs SET status='waiting_provider',updated_at=NOW() WHERE id=%s",(run['id'],))
    return str(job['id'])


def parent_state(cursor, row):
    state = row.get('result_json') or {}
    if not state.get('agent_run_id'):
        return 'active'
    cursor.execute("""SELECT r.status AS run_status,b.status AS blueprint_status,r.blueprint_version_id,
        b.metadata_json->>'active_version_id' AS active_version_id,s.status AS step_status,
        s.output_json->>'job_id' AS job_id
        FROM agent_runs r JOIN agent_blueprints b ON b.id=r.blueprint_id
        LEFT JOIN agent_run_steps s ON s.id=%s AND s.run_id=r.id
        WHERE r.id=%s AND r.business_id=%s""",
        (state.get('agent_step_id'),state['agent_run_id'],row['business_id']))
    parent=dict(cursor.fetchone() or {})
    if (parent.get('run_status')!='waiting_provider' or parent.get('step_status')!='waiting_provider'
            or parent.get('job_id')!=str(row['id']) or str(parent.get('active_version_id'))!=str(parent.get('blueprint_version_id'))):
        return 'changed'
    if parent.get('blueprint_status')=='paused':return 'paused'
    return 'active' if parent.get('blueprint_status')=='active' else 'changed'


def parent_current(cursor,row):
    return parent_state(cursor,row)=='active'


def terminate(cursor, row, *, reason, superseded=False):
    state=row.get('result_json') or {}
    if not state.get('agent_run_id'):return
    cursor.execute("""SELECT r.* FROM agent_runs r JOIN agent_run_steps s ON s.run_id=r.id
        WHERE r.id=%s AND r.business_id=%s AND r.status='waiting_provider'
          AND s.id=%s AND s.status='waiting_provider' AND s.output_json->>'job_id'=%s
        FOR UPDATE OF r,s""",(state['agent_run_id'],row['business_id'],state.get('agent_step_id'),str(row['id'])))
    run=dict(cursor.fetchone() or {})
    if not run:return
    status='superseded' if superseded else 'failed' if row.get('status')=='failed' else 'rejected'
    cursor.execute("UPDATE agent_run_steps SET status='failed',completed_at=NOW(),output_json=output_json || %s WHERE id=%s",
                   (Json({'termination_reason':reason}),state['agent_step_id']))
    cursor.execute("""UPDATE agent_runs SET status=%s,completed_at=NOW(),lease_token=NULL,error_text=%s,updated_at=NOW()
                      WHERE id=%s AND status='waiting_provider'""",(status,reason,run['id']))
    from services.agent_run_billing import finalize_agent_run_credits
    billing=finalize_agent_run_credits(cursor,run={**run,'status':status})
    cursor.execute("UPDATE agent_runs SET output_json=COALESCE(output_json,'{}'::jsonb) || %s WHERE id=%s",
                   (Json({'outreach_termination':reason,'run_billing':billing}),run['id']))


def complete(cursor, row, state):
    if not state.get('agent_run_id'):
        return
    from services.outreach_continuation import preparation_report
    report = preparation_report(row['payload_json'],state)
    cursor.execute("""UPDATE agent_run_steps SET status='completed',completed_at=NOW(),
                      output_json=output_json || %s WHERE id=%s AND run_id=%s
                      AND status='waiting_provider' AND output_json->>'job_id'=%s""",
                   (Json({'preparation_report':report}),state.get('agent_step_id'),state['agent_run_id'],str(row['id'])))
    if cursor.rowcount:
        cursor.execute("""UPDATE agent_runs SET status='queued',lease_token=NULL,heartbeat_at=NOW(),
                          next_attempt_at=NOW(),updated_at=NOW() WHERE id=%s AND business_id=%s AND status='waiting_provider'""",
                       (state['agent_run_id'],row['business_id']))


def supersede_previous_version(cursor, blueprint_id, active_version_id):
    """Called under the shared lifecycle fence, including nonclaimable children."""
    cursor.execute("""SELECT j.* FROM operator_async_jobs j JOIN agent_runs r
        ON r.id::text=j.result_json->>'agent_run_id' AND r.business_id=j.business_id
        WHERE r.blueprint_id=%s AND r.blueprint_version_id<>%s AND r.status='waiting_provider'
          AND j.kind='outreach_continue' FOR UPDATE OF j""",(blueprint_id,active_version_id))
    rows=[dict(row) for row in cursor.fetchall()]
    for row in rows:
        state={**(row.get('result_json') or {}),'blocker':'parent_version_changed'}
        cursor.execute("""UPDATE operator_async_jobs SET status='cancelled',lease_token=NULL,result_json=%s,
            completed_at=NOW(),updated_at=NOW(),stage='Прежняя версия автоматизации остановлена' WHERE id=%s""",
            (Json(state),row['id']))
        terminate(cursor,{**row,'status':'cancelled','result_json':state},reason='parent_version_changed',superseded=True)
    return len(rows)
