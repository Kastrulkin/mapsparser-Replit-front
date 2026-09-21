# Frozen history finding triage plan — 2026-09-21

## Scope and invariant

This is a metadata-only, **pre-triage baseline** over the frozen all-refs
history result at current-tree reference `bf277dbf`:
711 findings total, less the 20 rows already classified in
`git-all-refs-priority-triage-20260921.json`, leaves **691 unreviewed rows**.
It neither reads nor reproduces a Match, Secret, URI, or source line.  A
Gitleaks rule/path-family grouping is a prioritisation aid, not a verdict that
each row is an active credential or that any value remains valid.

The counts below are intentionally the original 691-row planning baseline, not
the live remaining queue. In particular, subsequent work classified the
572-row debug group; this document does not reverse or supersede that result.

The earlier 20-row sidecar retained one opaque access-material class, 17
public-role JWT-shape rows, and two privileged-role JWT-shape rows.  Its stated
limits (no signature validation, use, revocation, or provider contact) remain
in force.

## Exact remaining groups

Group IDs below are stable plan identifiers, not secret values.  Finding IDs
inside a group are non-contiguous in the frozen report; counts are exact.

| Plan group ID | Frozen finding IDs | Rule / path family | Rows | Distinct historical paths | Exact current-HEAD path intersection | Priority |
| --- | --- | --- | ---: | ---: | ---: | --- |
| GH-DBG-572 | 102–168, 176–680 | `generic-api-key` / debug capture family | 572 | 301 | 0 | P0 volume / historical provider-debug material |
| GH-AGENT-044 | 5, 8–20, 62–91 | `generic-api-key` / agent evidence and raw-capture family | 44 | 3 | 3 | P0 current-evidence boundary |
| GH-OUTPUT-040 | 21–43, 45–61 | `generic-api-key` / release-output manifest family | 40 | 3 | 3 | P0 current retained artifact family |
| CAH-CURSOR-007 | 169–175 | `curl-auth-header` / legacy Cursor runbook family | 7 | 2 | 0 | P1 command-exposure pattern |
| GH-RUNTIME-006 | 92–95, 684, 686 | `generic-api-key` / backend-source family | 6 | 3 | 3 | P0 possible current runtime-source boundary |
| GH-DOC-005 | 4, 7, 97, 100–101 | `generic-api-key` / documentation family | 5 | 5 | 5 | P1 current documentation boundary |
| CAH-RUNBOOK-004 | 681–683, 692 | `curl-auth-header` / root runbook family | 4 | 4 | 0 | P1 command-exposure pattern |
| GH-RAW-PROVIDER-003 | 1–3 | `generic-api-key` / readiness provider-response capture | 3 | 1 | 1 | P0 provider-response proof first |
| GH-TEST-003 | 44, 96, 99 | `generic-api-key` / test family | 3 | 3 | 2 | P1 fixture/test boundary |
| GH-ROOT-006 | 6, 689–691, 693–694 | `generic-api-key` / remaining root utility family | 6 | 6 | 1 | P1 utility-script boundary |
| GH-SCRIPT-001 | 98 | `generic-api-key` / scripts family | 1 | 1 | 1 | P1 script boundary |
| **Total** |  |  | **691** |  |  |  |

Current-HEAD comparison is deliberately limited to path presence: 19 distinct
remaining-sidecar paths overlap the current tree (agent/evidence 3, backend
source 3, docs 5, outputs 3, readiness provider response 1, root utility 1,
scripts 1, tests 2). The frozen
remaining debug-capture paths have zero current-HEAD overlap.  Path presence
does not establish that a finding is still present; ignored/untracked working
files are also outside this HEAD-only comparison.

## Recommended bounded proof order

1. **GH-RAW-PROVIDER-003.** For the one readiness provider-response path,
   collect only existence, index/ignore status, byte count, and a redacted
   content fingerprint comparison to its classified historical object.  Do
   not contact the provider or expose the response.  This distinguishes a
   retained local artifact from a history-only record, but cannot prove
   revocation.
2. **GH-RUNTIME-006 and GH-OUTPUT-040.** Produce separate current-tree,
   value-free presence/fingerprint sidecars for each family.  Treat a current
   match as an escalation to rotation/removal ownership; do not mutate sources
   or release outputs from this triage task.
3. **GH-DBG-572.** Capture a metadata-only family inventory: historical row
   and path count, current-HEAD overlap (currently zero), and applicable
   ignore/build-context boundaries.  This is the largest historical
   provider/debug cluster, but bulk cleanup or history rewriting requires
   separate explicit authority and still would not erase remote clones.
4. **GH-AGENT-044, GH-DOC-005, GH-TEST-003, GH-SCRIPT-001, GH-ROOT-006.**
   Use the same per-family current-presence/fingerprint method, beginning with
   the 19-path current overlap.  Do not infer a live secret merely from a
   generic-rule result.
5. **CAH-CURSOR-007 and CAH-RUNBOOK-004.** Classify each as a historical
   command-template/documentation exposure pattern versus retained current
   material using redacted structural metadata.  If a current example embeds
   credential material, a documentation correction and a safe synthetic
   regression contract are the smallest next change; provider validation is
   not authorised by this plan.

## Acceptance boundary

Each bounded proof may close only its own local-retention question.  None can
turn the all-refs scan into a clean result, validate a credential, establish
revocation, prove production/image/log absence, or remove historical findings.
The frozen history scanner's nonzero finding result and the release-level
security verdict therefore remain unchanged.
