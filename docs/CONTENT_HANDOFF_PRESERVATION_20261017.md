# Content changes preservation — 17 October 2026

## Coordinated base

Public base: `4c65389fb69d401fbb057c37cb1cdbc0573a6fdb` on
`codex/meliora-content-voice-20261017` and `codex/max-owner-parity-20261015`.
Its tree equals local `04d42e106`: `73a40396df52aa9654480c25991557ad59c10570`.
The neighboring Mini App owner confirmed the handoff and stopped editing these files.
The base already preserves content references, personalization, moderation,
industry guidance and their Mini App integration. Do not replace it with the
older files from the shared dirty production-readiness checkout.

## This follow-up

- Preserve the already deployed sender's scoped ID-only media resolution,
  independent recipient receipts and explicit single-post recovery path.
- Preserve the production queue's content dispatch, cohort/consent fences,
  immutable input snapshots and truthful unsuccessful handoff status.
- Preserve `unless-stopped` on the existing isolated compiled runner.
- Add the existing website reader and unit tests from
  `codex/openclaw-reuse-20261012`; the public base imported this module without
  including it. No new connector or automatic paid fallback was introduced.
- Preserve current generation test fixtures for a single candidate and mocked
  editorial pattern lookup. No paid generation was run.
- Preserve the existing draft API's explicit additional-variants options,
  request identifier and stale-content conflict response.

Runtime Python source matches the deployed versions inspected read-only:

| File | SHA-256 |
| --- | --- |
| `src/services/content_publish_notifications.py` | `851f59a257d1d091b327d958f03edc23a5ad16f635c100917541e5f552f90b83` |
| `src/services/agent_run_queue.py` | `5e0e336b11a96620a26dbb5c9cc3c403fb78984cfc4f1d0800ec4a92100e1dc2` |
| `docker/compiled-script-runner/compose.fragment.yml` | `75276122c09e9d336866bda91d21249910ecf6f2d37bffb51eaf2e4b48c1b8bd` |

## Verification and boundaries

Tests run from an isolated export of the public base plus this follow-up,
not from the shared dirty workspace:

- Handoff recovery, notification and compiled contract: 26 passed.
- SSRF media delivery, independent process: 13 passed.
- Content generation plus website reader: 74 passed after restoring the
  missing dependency (four generation tests previously failed on its import).
- Combined references, industry guidance, voice access, generation and
  website-reader verification: 171 passed.
- The preserved `test_content_single_generation.py`: 7 passed, 4 failed.
  The four failures concern the pre-existing provider configuration:
  `thinking_enabled=None` rather than `False` for two task definitions, and
  missing `services.llm.adapters.guarded_post` in two DeepSeek payload tests.
  They are not caused by the restored reader or handoff files. No assertions
  were removed or weakened and no provider/model settings were changed.
  This Git preservation task is not a claim that every AI-provider test passes.

No frontend/Mini App file is changed by this follow-up. No deployment,
publication, Telegram delivery, schedule activation, production data write,
paid model request or change of existing approvals is part of this Git task.
The shared checkout, branch and ordinary Git index remain untouched.
