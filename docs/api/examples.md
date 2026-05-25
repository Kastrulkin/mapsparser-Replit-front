# API Examples

Examples are minimal and should be adapted to the exact endpoint schema in code.

## Card Audit

```bash
curl -s -X POST "https://localos.pro/api/analyze" \
  -H "Authorization: Bearer $LOCALOS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://yandex.ru/maps/org/example",
    "business_id": "business-id"
  }'
```

Expected result: queue or analysis response. Poll status:

```bash
curl -s "https://localos.pro/api/business/business-id/parse-status" \
  -H "Authorization: Bearer $LOCALOS_TOKEN"
```

## Optimize Services

```bash
curl -s -X POST "https://localos.pro/api/services/optimize" \
  -H "Authorization: Bearer $LOCALOS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "business_id": "business-id",
    "services": [
      {
        "id": "service-id",
        "name": "Ваксинг (восковая депиляция) - 1 зона",
        "description": "Current description",
        "category": "Брови и ресницы"
      }
    ]
  }'
```

Expected result: generated suggestions plus quality/guardrail metadata where available.

Agent rule: do not apply externally without approval.

## Generate Review Reply

```bash
curl -s -X POST "https://localos.pro/api/reviews/reply" \
  -H "Authorization: Bearer $LOCALOS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "business_id": "business-id",
    "review_text": "Спасибо мастеру за аккуратную работу",
    "rating": 5
  }'
```

Expected result: reply draft.

## Generate News Draft

```bash
curl -s -X POST "https://localos.pro/api/news/generate" \
  -H "Authorization: Bearer $LOCALOS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "business_id": "business-id",
    "topic": "как проходит первичный прием",
    "platform": "maps"
  }'
```

Expected result: news draft. Publishing needs approval.

## Finance Dashboard

```bash
curl -s "https://localos.pro/api/finance/dashboard?business_id=business-id&from=2026-02-01&to=2026-05-14" \
  -H "Authorization: Bearer $LOCALOS_TOKEN"
```

All available data:

```bash
curl -s "https://localos.pro/api/finance/dashboard?business_id=business-id&range=all" \
  -H "Authorization: Bearer $LOCALOS_TOKEN"
```

Expected result includes `kpis`, `data_quality`, `recommendations`, `period_history`, and `source_data`.

## Finance Import Preview

```bash
curl -s -X POST "https://localos.pro/api/finance/import-preview" \
  -H "Authorization: Bearer $LOCALOS_TOKEN" \
  -F "business_id=business-id" \
  -F "file=@finance.csv"
```

Agent rule: preview first, ask approval, then import.

## Agent API Quickstart

Fetch the contract:

```bash
curl -s "https://localos.pro/api/agent-api/openapi.json"
```

Read policy:

```bash
curl -s "https://localos.pro/api/agent-api/security/policy"
```

Run sandbox self-test:

```bash
curl -s -X POST "https://localos.pro/api/agent-api/self-test" \
  -H "X-LocalOS-Agent-Key: $LOCALOS_AGENT_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "purpose": "sandbox onboarding",
    "checks": ["auth", "scopes", "ledger"]
  }'
```

Create a test approval request:

```bash
curl -s -X POST "https://localos.pro/api/agent-api/approvals/request" \
  -H "X-LocalOS-Agent-Key: $LOCALOS_AGENT_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "action_type": "test_publish_review_reply",
    "capability": "reviews.reply.publish",
    "risk_level": "high",
    "requested_scope": "publish:request",
    "input_summary": {
      "source": "sandbox quickstart"
    },
    "proposed_output": "Test approval request only."
  }'
```

Request live promotion:

```bash
curl -s -X POST "https://localos.pro/api/agent-api/clients/promotion/request" \
  -H "X-LocalOS-Agent-Key: $LOCALOS_AGENT_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "requested_scopes": ["audit:read", "reviews:draft", "approvals:create"],
    "use_case": "Read audits and draft review replies under human approval.",
    "contact": "ops@example.com"
  }'
```

Superadmin can confirm the flow in `GET /api/agent-api/ledger`.

## Partnership Draft Offer

```bash
curl -s -X POST "https://localos.pro/api/partnership/leads/lead-id/draft-offer" \
  -H "Authorization: Bearer $LOCALOS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "business_id": "business-id",
    "channel": "whatsapp"
  }'
```

Expected result: draft offer. Sending requires approval.

## Industry Pattern Proposal Decision

```bash
curl -s -X POST "https://localos.pro/api/admin/industry-patterns/proposals/proposal-id/decision" \
  -H "Authorization: Bearer $LOCALOS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "decision": "approve",
    "comment": "Accepted for beauty services"
  }'
```

Requires superadmin.
