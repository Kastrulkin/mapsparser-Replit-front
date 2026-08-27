# Lead Journey v2: production rollout

## Scope

This runbook releases deterministic journeys for `influencer`, `partnership`,
`maps`, and `content` without changing existing journey data or bypassing manual
approval for external sends, publication, payment, or destructive operations.

The release is reversible through feature flags. Database rows created while a
flag is enabled remain intact when the flag is disabled.

## Required preflight

1. Obtain explicit approval for the production schema migration and rollout.
2. Create and verify a PostgreSQL backup before running Alembic.
3. Record the current image/tag, Git SHA, Alembic head, and enabled journey flags.
4. Confirm the internal test lead and test business IDs. Do not use a customer
   account for the first pass.
5. Build the frontend with all new Vite flags disabled unless that release stage
   explicitly enables them.

Run every server command from `/opt/seo-app` and use a named `tmux` session for
backup, build, migration, and deployment work.

## Release order

### 1. Backup and migration

Create a timestamped PostgreSQL backup using the deployment's existing database
credentials, verify that the dump is non-empty, and record its restore command.
Then deploy backend source and migration
`20260827_002_add_content_journey_flow`, run `alembic upgrade head`, and confirm
the current revision.

Do not edit constraints manually in production. Do not run the migration before
the backup is verified.

### 2. Backend foundation, flags off

Deploy `src/` to both `app` and `worker`, restart only those services, and leave
all new flags off:

- `CONTENT_JOURNEY_ENABLED=0`
- `JOURNEY_ADMIN_BUILDER_ENABLED=0`
- `JOURNEY_POST_AUTH_REDIRECT_ENABLED=0`
- `GROWTH_PATHS_NAVIGATION_ENABLED=0`
- `BLOCK_ACCESS_V2_ENABLED=0`

Keep the existing journey vertical flags off until their staged checks begin.
Verify `docker compose ps`, recent `app` logs, `curl -I
http://localhost:8000`, migration revision, and the journey diagnostics endpoint.

### 3. Internal deterministic-link pilot

Enable the existing foundation and only the selected vertical needed for the
internal test. Enable the admin builder for superadmins. Keep the new global
navigation, notifications, and upsell disabled.

Create the journey through `/dashboard/bazich/journeys`:

1. choose the test lead;
2. choose one flow;
3. choose a safe example;
4. inspect public, registered, and paid preview states;
5. copy the generated message and `/start/:token` URL;
6. verify that the public response contains no contact details or full private
   message;
7. revoke the link after the test if it will not be reused.

Run the same sequence separately for influencer, partnership, maps, and content.
Do not enable automatic provider sends.

### 4. Post-auth continuity

Enable `JOURNEY_POST_AUTH_REDIRECT_ENABLED` for the internal cohort. Test:

- guest link -> registration -> email verification -> exact workspace/action;
- existing user link -> login -> exact workspace/action;
- refresh/back and retry after a temporary claim failure;
- repeated claim and stale action version;
- web -> Mini App and Mini App -> web.

The token must be cleared only after a successful claim. A failure must leave a
retry path and must not redirect to a different growth area.

### 5. Content pilot

Enable `CONTENT_JOURNEY_ENABLED` only for internal journeys and complete:

`safe preview -> draft -> review -> calendar -> manual/provider-confirmed
publication -> result -> next cycle`.

Confirm that the content plan/item remains the domain source of truth and that
the action transition occurs in the same transaction. Publication stays behind
the existing approval/preflight boundary.

### 6. Navigation and block access

Build and deploy the frontend with:

- `VITE_GROWTH_PATHS_NAVIGATION_ENABLED=true`
- `VITE_BLOCK_ACCESS_V2_ENABLED=true`

Start with internal users. Confirm the top-level IA is `Today / Growth paths /
Results / More`, old URLs and bookmarks still open, and a locked block keeps its
title, value, reason, and CTA readable. Do not remove a legacy route-wide gate
until that screen owns both block-level UI and backend entitlement checks.

### 7. Mini App, notifications, and monetization

After web action state is stable, verify the same action ID/version and allowed
commands in Mini App. Enable journey notifications only after dedupe checks.
Enable upsell actions only after the existing eligibility rule is satisfied;
never open a paywall automatically.

## Smoke checks after each stage

1. `docker compose ps`
2. recent `app` and, when relevant, `worker` logs
3. `curl -I http://localhost:8000`
4. targeted API checks for public preview, claim, action detail, growth paths,
   diagnostics, and the enabled vertical
5. browser pass with an internal journey token
6. browser console without new application errors
7. diagnostics: no unexpected orphan actions, stale-action growth, or
   action/domain mismatches

For a maps refresh, a provider hard-limit response must produce a visible
`blocked` action. A retry can use the native Yandex Maps parser; it must not
invent a verified comparison when no fresh snapshot exists.

## Immediate rollback

For a behavioral problem, turn off the narrowest affected flag first. Restart
only `app` and `worker` when backend environment values changed. Rebuild/sync the
frontend only when Vite flags changed.

Do not delete journey rows during rollback. Do not downgrade the migration while
content actions exist. A database restore is reserved for a confirmed schema or
data-integrity incident and requires separate explicit approval.

## Evidence to retain

- backup path and verification result;
- deployed Git SHA and Alembic revision;
- exact enabled flags and cohort IDs;
- one redacted public response per flow;
- screenshots of public preview, exact post-auth destination, Growth paths, and
  Mini App;
- targeted backend/frontend test output and build output;
- diagnostics snapshot before and after the pilot;
- known provider limits or blocked actions and their recovery result.
