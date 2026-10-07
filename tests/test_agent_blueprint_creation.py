import json

from services import agent_blueprint_creation


class CreationCursor:
    def __init__(self):
        self.query = ""
        self.params = ()
        self.row = None
        self.blueprints = {}

    def execute(self, query, params=()):
        self.query = " ".join(query.split()).lower()
        self.params = params or ()
        self.row = None
        if self.query.startswith("select pg_advisory_xact_lock"):
            return
        if "metadata_json->>'create_request_key'" in self.query:
            self.row = next(({"id": key, "metadata_json": value["metadata_json"]}
                for key, value in self.blueprints.items()
                if value["business_id"] == self.params[0]
                and value["metadata_json"].get("create_request_key") == self.params[1]), None)
            return
        if self.query.startswith("insert into agent_blueprints"):
            self.blueprints[self.params[0]] = {
                "business_id": self.params[1],
                "metadata_json": json.loads(self.params[6]),
            }
            return
        raise AssertionError(self.query)

    def fetchone(self):
        return self.row

    def fetchall(self):
        return []


def test_prepare_creation_preflights_builder_and_paid_cost_before_approval(monkeypatch):
    calls = []
    monkeypatch.setattr(agent_blueprint_creation, "preview_creation", lambda *_args, **_kwargs: {
        "status": "ready", "preview": {"feasibility": {"status": "ready"}, "connection_summary": {"items": []}},
        "feasibility": {"status": "ready"}, "setup_flow": {"can_create_draft": True},
        "selected_provider_routes": {}, "selected_bindings": {},
    })
    monkeypatch.setattr("services.agent_builder_billing.build_paid_action_preflight",
        lambda *_args, **_kwargs: {"status": "ready", "estimated_credits": 3})
    result = agent_blueprint_creation.prepare_creation(None, business_id="b-1", user_id="u-1",
        actor_context={}, payload={"description": "Подготовить ежедневную сводку"})
    assert result["status"] == "approval_required"
    assert result["approval"]["capability"] == "agents.create"
    assert result["approval"]["paid_preflight"]["status"] == "ready"
    assert result["approval"]["envelope"]["idempotency_key"]
    assert result["external_writes_performed"] is False


def test_create_draft_uses_one_stable_blueprint_and_billing_key(monkeypatch):
    cursor = CreationCursor()
    charges = []
    monkeypatch.setattr(agent_blueprint_creation, "verify_business_write_access", lambda *_args: (True, "u-1"))
    monkeypatch.setattr(agent_blueprint_creation, "preview_creation", lambda *_args, **_kwargs: {
        "status": "ready", "preview": {"feasibility": {}, "connection_summary": {}},
        "feasibility": {}, "setup_flow": {"can_create_draft": True},
        "selected_bindings": {}, "selected_provider_routes": {},
        "planner_context": {}, "planner_loop": {}, "clone_metadata": {},
    })
    monkeypatch.setattr(agent_blueprint_creation, "build_agent_blueprint_draft", lambda *_args, **_kwargs: {
        "name": "Daily summary", "category": "custom", "description": "Подготовить ежедневную сводку",
        "metadata": {}, "summary": {},
        "version_payload": {"goal": "Сводка", "steps": [], "trigger": "manual.run", "required_integration_bindings": []},
    })
    monkeypatch.setattr(agent_blueprint_creation, "charge_agent_creation_credits", lambda _cursor, **kwargs:
        charges.append(kwargs) or {"status": "charged", "reservation_id": "r-1"})
    monkeypatch.setattr(agent_blueprint_creation, "insert_version", lambda *_args, **_kwargs: {
        "id": "v-1", "version_number": 1, "goal": "Сводка", "trigger": "manual.run"})
    args = {"business_id": "b-1", "user_id": "u-1", "actor_context": {"operator_confirmation": True},
            "payload": {"description": "Подготовить ежедневную сводку"}, "idempotency_key": "request-1"}
    first = agent_blueprint_creation.create_draft(cursor, **args)
    second = agent_blueprint_creation.create_draft(cursor, **args)
    assert first["status"] == second["status"] == "completed"
    assert first["blueprint_id"] == second["blueprint_id"]
    assert second["idempotent_replay"] is True
    assert len(charges) == 1
    assert charges[0]["source_id"] == first["blueprint_id"]


def test_review_pins_schedule_country_destination_and_full_request_hash(monkeypatch):
    monkeypatch.setattr('services.business_input_settings.resolve',lambda *args:{'timezone':'Asia/Kolkata'})
    cfg={'audience':'Tour operators','mode':'find_only','target_count':100,
         'agency_country':'India','sold_destination':'Phuket',
         'queries':[{'query':'travel agency','city':'Delhi'}]}
    def preview(cursor,**kwargs):
        return {'status':'ready','conditions':agent_blueprint_creation._conditions(cursor,kwargs['business_id'],kwargs['payload'])}
    monkeypatch.setattr(agent_blueprint_creation,'preview_creation',preview)
    monkeypatch.setattr('services.agent_builder_billing.build_paid_action_preflight',lambda *a,**kw:{'status':'ready'})
    payload={'description':'Искать новые туристические компании каждый понедельник',
             'execution_mode':'scheduled','schedule':{'trigger':'schedule.weekly','weekday':0},'outreach_config':cfg}
    result=agent_blueprint_creation.prepare_creation(None,business_id='b',user_id='u',actor_context={},payload=payload)
    envelope=result['approval']['envelope']
    assert envelope['payload']['schedule']=={'trigger':'schedule.weekly','weekday':0,'time':'09:00','timezone':'Asia/Kolkata'}
    assert envelope['payload']['outreach_config']['agency_country']=='India'
    assert envelope['payload']['outreach_config']['sold_destination']=='Phuket'
    changed=agent_blueprint_creation.prepare_creation(None,business_id='b',user_id='u',actor_context={},payload={**payload,'outreach_config':{**cfg,'target_count':50}})
    assert envelope['idempotency_key']!=changed['approval']['envelope']['idempotency_key']
    changed=agent_blueprint_creation.prepare_creation(None,business_id='b',user_id='u',actor_context={},payload={**payload,'schedule':{**payload['schedule'],'time':'10:00'}})
    assert envelope['idempotency_key']!=changed['approval']['envelope']['idempotency_key']


def test_outreach_workflow_uses_native_durable_step_with_no_input_override():
    from services.outreach_continuation import normalize_config
    config=normalize_config({'audience':'Agencies','mode':'find_only','target_count':100,'queries':[{'query':'travel','city':'Delhi'}]})
    version=agent_blueprint_creation._outreach_version({},config,'Search 100 agencies')
    assert version['steps'][0]['capability']=='outreach.continue'
    assert version['capability_allowlist']==['outreach.continue']
    assert version['inputs_schema']['additionalProperties'] is False
    assert version['runtime_config']['outreach_config']==config
    assert version['approval_policy']['external_delivery']=='separate_ai_rules_required'


def test_structured_outreach_preview_uses_actual_workflow_without_generic_questions(monkeypatch):
    monkeypatch.setattr(agent_blueprint_creation, 'verify_business_write_access', lambda *a: (True, 'u'))
    monkeypatch.setattr(agent_blueprint_creation, '_inventory', lambda *a: [])
    monkeypatch.setattr('services.business_input_settings.resolve', lambda *a: {'timezone': 'Asia/Kolkata'})
    payload = {'description': 'Каждый понедельник ищи 100 новых турагентств в Индии для Пхукета',
               'execution_mode': 'scheduled', 'schedule': {'trigger': 'schedule.weekly', 'weekday': 0},
               'outreach_config': {'audience': 'tour agencies', 'target_count': 100, 'mode': 'find_only',
                                   'agency_country': 'India', 'sold_destination': 'Phuket',
                                   'queries': [{'query': 'travel agency', 'city': 'Delhi'}]}}
    result = agent_blueprint_creation.preview_creation(None, business_id='b', user_id='u', actor_context={}, payload=payload)
    assert result['status'] == 'ready'
    assert result['feasibility']['status'] == 'ready'
    assert result['setup_flow']['can_create_draft'] is True
    assert result['preview']['compiler_questions'] == []
    assert result['preview']['capability_allowlist'] == ['outreach.continue']
    conditions = result['conditions']
    draft = agent_blueprint_creation._outreach_draft(payload['description'], conditions['outreach_config'], conditions)
    assert draft['version_payload']['steps'][0]['capability'] == 'outreach.continue'
    assert draft['summary']['steps'][0]['key'] == 'outreach'
    assert draft['metadata']['compiled_validation']['valid'] is True
    assert draft['metadata']['compiler_contract']['runtime_llm_required'] is True
    assert draft['version_payload']['schedule']['time'] == '09:00'
