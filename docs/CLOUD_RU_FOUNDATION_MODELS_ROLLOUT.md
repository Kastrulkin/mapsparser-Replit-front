# Cloud.ru Foundation Models rollout

Status: `prepared / disabled by default`

Date: 22 November 2026

## Decision

Current commercial GigaChat packages on `developers.sber.ru` continue working
until their expiry date or token exhaustion. LocalOS keeps that integration
unchanged while preparing Cloud.ru as the successor route. No automatic provider
cutover is allowed.

Cloud.ru is introduced as a separate provider identity, with separate model IDs,
budgets, telemetry and rollout flags. Existing DeepSeek and GigaChat environment
variables must not be silently repointed to Cloud.ru.

Official references:

- catalog: <https://cloud.ru/products/evolution-ai-factory/catalog-foundation-models>;
- OpenAI-compatible chat API: <https://cloud.ru/docs/foundation-models/ug/topics/api-ref__specs>;
- embedding overview: <https://cloud.ru/blog/embeddingi>.

## Implemented foundation

- `CloudRuFoundationClient` supports the documented model catalog and chat
  endpoints plus the embedding endpoint advertised by Cloud.ru. The live
  embedding contract must still be verified after account recovery.
- Chat routing is opt-in and tenant-scoped. It cannot activate without an API
  key, `CLOUD_RU_CHAT_ROUTER_ENABLED=true`, and an explicit business allowlist.
- External catalog models are blocked by default. The prepared defaults use
  internal `ai-sage/*` models only.
- Giga Embeddings 3B is stored in a parallel 2048-dimensional table. The current
  `EmbeddingsGigaR` index remains untouched at 2560 dimensions.
- Cloud.ru chat and embedding calls have separate conservative spend ledgers.
- The worker path is disabled by default and does not enqueue or call Cloud.ru
  until its rollout flag is explicitly enabled after the schema gate.

## Configuration

```dotenv
CLOUD_RU_API_KEY=
CLOUD_RU_BASE_URL=https://foundation-models.api.cloud.ru/v1
CLOUD_RU_CHAT_MODEL=ai-sage/GigaChat3-10B-A1.8B
CLOUD_RU_EMBEDDING_MODEL=ai-sage/Giga-Embeddings-instruct-3B
CLOUD_RU_EMBEDDING_DIMENSIONS=2048
CLOUD_RU_EXTERNAL_MODELS_ENABLED=false

# Chat pilot: all three are required.
CLOUD_RU_CHAT_ROUTER_ENABLED=false
LLM_CLOUD_RU_BUSINESS_IDS=

# Parallel embedding backfill: requires the Alembic migration first.
CLOUD_RU_EMBEDDINGS_ENABLED=false
CLOUD_RU_EMBEDDING_VERSION=cloudru_giga_embeddings_3b_v1
CLOUD_RU_EMBEDDING_BATCH_SIZE=16

# Keep true while the current Sber package is available. Turning it off stops
# new legacy jobs/provider calls but keeps chunk creation for the Cloud.ru space.
KNOWLEDGE_GIGACHAT_EMBEDDINGS_ENABLED=true
```

Secrets belong only in protected runtime configuration. Do not add an API key
to Git, documentation, Compose JSON snapshots or task evidence.

## Why this is a direct LocalOS adapter

The checked OpenClaw catalog does not expose Cloud.ru model inference as an
execution action. LLM routing, tenant policy, PII protection, budget reservations
and usage history are already LocalOS responsibilities. The adapter therefore
extends the existing LocalOS provider boundary rather than creating a second
campaign or action runtime in OpenClaw.

## Embedding migration

`EmbeddingsGigaR` produces 2560-dimensional vectors. The prepared Giga
Embeddings 3B space uses 2048 dimensions. These vectors are not comparable and
must never share a similarity index.

The migration adds `knowledge_embedding_vectors`, linked to the existing
redacted chunks. It contains a separate HNSW index for Cloud.ru vectors. The
existing `knowledge_embedding_chunks.embedding HALFVEC(2560)` column, jobs and
retrieval behavior remain unchanged.

Safe sequence:

1. Recover the Cloud.ru account and create a scoped service-account key.
2. Confirm the model IDs through `GET /v1/models` and make one bounded sandbox
   request. Do not include production PII.
3. Create and verify a PostgreSQL backup.
4. Apply the Alembic migration in an approved maintenance window.
5. Enable a small parallel backfill with the default 10-million-token monthly
   pilot cap.
6. Compare retrieval quality on real Russian queries while production reads the
   old 2560-dimensional index.
7. Add and approve a separate read-switch only after coverage, quality, cost and
   rollback evidence pass.
8. After the Sber package is exhausted, set
   `KNOWLEDGE_GIGACHAT_EMBEDDINGS_ENABLED=false`; do not delete its index.
9. Retire the old index only after a later explicit data-retention decision.

## Production gates

The following are intentionally not performed by this preparation:

- no Cloud.ru API key was created or stored;
- no paid provider request was made;
- no production schema or data was changed;
- no existing embedding job was moved or deleted;
- no GigaChat or DeepSeek route was disabled;
- no external model was enabled;
- no production deployment was performed.

Before the schema step, explicit approval and a verified production database
backup are mandatory under `AGENTS.md`.
