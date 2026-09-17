---
name: audit-localos-production
description: Run or review a comprehensive LocalOS production health audit and safe restoration. Use for scheduled daily production checks, incident recovery, or a full production smoke audit; do not use for ordinary feature development or isolated local tests.
---

# Audit LocalOS production

Produce a concise evidence-backed production verdict, and restore confirmed
LocalOS regressions when the user has authorized fixes and deployment.

## Establish scope

Read the current repository `AGENTS.md` and the deployment and verification
sections of `README.md`. Read `DESIGN.md` only when a user-facing flow must be
checked or changed. Preserve unrelated working-tree changes.

Separate three outcomes before changing anything:

- a LocalOS regression that can be reproduced and safely fixed;
- an external provider, quota, credential, or billing blocker;
- expected operational noise that needs no action.

## Gather one baseline

Batch the initial read-only checks. Every server command block starts with
`cd /opt/seo-app`. Capture container status, recent app and worker errors, the
local HTTP response, restart and OOM state, database and queue health, and the
specific public or authenticated route under review.

Do not reread the full project documentation or repeat broad log searches
during the same run. Narrow later checks to the confirmed error signature,
route, job, or service.

## Prove and restore

For a suspected code regression, create or run the smallest reproduction that
would fail before the fix. Respect any separate approval required by the
active bug-reproduction workflow. Apply the smallest safe correction, run the
targeted check plus one high-risk adjacent check, deploy only affected
services, and verify the live container file and production behavior.

Never change production data, schema, access, external messages, publications,
payments, or provider configuration without the authorization required by the
project rules and current user request.

## Report

Return one status per finding: fixed, healthy, external blocker, or needs
attention. Include the observed evidence, the verification performed, and the
remaining owner or next action. Do not present external provider failures as
LocalOS code defects.
