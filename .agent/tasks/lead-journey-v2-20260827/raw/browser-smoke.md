# Browser smoke — 2026-08-27

Local runtime:

- frontend: `http://127.0.0.1:4178`
- deterministic mock API: `http://localhost:8000`
- journey and navigation Vite flags enabled only in the local test process

Verified with the in-app browser:

1. `/start/test-influencer` automatically selected `influencers`, showed
   “Анна о Петербурге” and one “Подготовить сообщение автору” CTA.
2. `/start/test-partnership` automatically selected `partnerships`, showed
   “Кофейня рядом” and one “Подготовить предложение партнёру” CTA.
3. `/start/test-maps` automatically selected `maps`, showed “Обновить услуги в
   карточке” and one “Показать первое исправление” CTA.
4. `/start/test-content` automatically selected `content`, showed the safe topic,
   a short excerpt/public source, and one “Подготовить черновик” CTA.
5. Every selected-flow screen rendered other areas only as disabled secondary
   discovery and repeated the manual approval boundary.
6. Login + claim returned the allowlisted influencer route with
   `journey_action=action-1`. A full unavailable influencer workspace no longer
   redirected to Partnerships: the exact action stayed visible and the expanded
   workspace became a readable block-level upgrade preview.
7. `/dashboard/growth-paths` placed the active influencer path first, rendered
   all four paths, and kept the locked Content value, reason, and CTA readable.
8. `/dashboard/bazich/journeys` completed client -> path -> three preview modes ->
   generated link/message for `[TEST] Journey Pilot 1 — Варвара` without SQL.
9. Mini App rendered `Today / Growth paths / Results / More`, showed Maps,
   Content, Influencers and Partnerships, and opened Influencers with a prepared
   operator request.
10. After the local mock CORS setup was corrected, no new application console
    errors appeared during the final admin, Growth paths, selected workspace,
    Mini App, or four-flow public passes. The one retained console error is the
    earlier failed local login at `2026-08-27T13:05:21.389Z`, before that setup.

Artifacts:

- `screenshot-public-content.png`
- `screenshot-admin-builder.jpg`
- `screenshot-growth-paths-viewport.jpg`
- `screenshot-influencer-block-access.jpg`
- `screenshot-mini-app-viewport.jpg`

This is a local acceptance pass with deterministic API data. Production schema,
flags, and customer data were not mutated.
