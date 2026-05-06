# Industry Patterns Optimizer

This note records the current sources of truth for LocalOS copy optimization and
the new integration point for industry-specific working patterns.

## Existing Sources

- `src/core/service_optimization_verticals.py` is the entrypoint for service
  vertical rules used by `/api/services/optimize`.
- `src/core/beauty_service_optimization.py` is the protective guardrail layer
  for beauty services. It preserves zones, hair length, gender, age, product or
  drug names, volume, dose, session counts, and service format.
- `src/core/service_keyword_scoring.py` evaluates SEO keyword coverage and
  service quality issues.
- `src/main.py` contains the manual service optimization endpoint, manual news
  generation, and manual review reply generation.
- `src/services/content_plan_service.py` generates content-plan draft news.
- `src/core/card_automation.py` generates scheduled card news and review reply
  drafts.
- `src/core/learning_patterns.py` currently extracts human-reviewed service
  edit candidates from `ailearningevents`.
- `aiprompts` stores DB-editable prompt templates. File prompts still exist and
  must receive the same pattern context when used.

## New Source

`src/core/industry_patterns.py` is the shared source for industry pattern
context. It is not a parallel prompt. It provides compact context blocks for:

- service optimization;
- news and card posts;
- review replies;
- pattern-fit scoring;
- monthly recalibration proposals.

## Priority Order

The optimizer must apply rules in this order:

1. Source facts from the original card/service/review.
2. Guardrails and fact preservation.
3. Industry restrictions and forbidden drift.
4. SEO keywords.
5. Working industry patterns.
6. User tone and style examples.

Monthly recalibration may create `pending_review` proposals, but it must not
activate or change patterns without superadmin approval.
