# Maton account drift: NO_BUG_PROVEN

Read-only trace after191488ba; no tests or source changes for this hypothesis.
Initial independent tracer proposed authorized route/account A-to-B change while
a communications_send approval is pending. Root found counterevidence; tracer
rechecked and withdrew that proposal. Do not count the first trace as reproduced.

The access-checked writer is src/api/agent_blueprints_api.py:5830–5907. It validates
blueprint access and an active business Maton account, then calls
_apply_agent_provider_route_metadata:2699–2752. That helper changes only
agent_binding_provider_routes and agent_binding_integrations.

src/services/agent_blueprint_runner.py:1411–1430 resolves current metadata but
selects handler.external_account_id OR route.external_account_id. The unchanged-A
fixture in tests/test_agent_blueprint_reviews_outreach.py:534–617 explicitly sets
handler account A. Thus changing only the route to B still resolves A. The
proposed regression's claimed B envelope is not reachable through that writer.

Handler construction was traced to src/api/agent_builder_api.py:420–492 and
_connector_action_handler_payload:495+, called by new-blueprint creation at841+
and1046; the import at src/api/agent_blueprints_api.py:3666 also creates a new
blueprint. No supported in-place handler update was found. Root read these source
branches; the independent tracer confirmed the correction.

Generic approval lookup remains run/type-based (runner3367–3382); generic
payload construction reads some current integration configuration. The tracer
found no replacement concrete legacy writer-to-write-target drift: Sheets is
already snapshot-bound, trigger-only Telegram/WhatsApp config is not such a
path, Maton account remains handler-bound, and finance mode/type lacks a proven
affected write template. Therefore broad AI-APPROVAL-BINDING-03 remains a
CANDIDATE only. This is not proof of global approval safety. No authorization
bypass, provider send, financial effect, DB mutation or production action tested.
