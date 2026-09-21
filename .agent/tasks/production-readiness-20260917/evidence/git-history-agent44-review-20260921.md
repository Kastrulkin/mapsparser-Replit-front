# Frozen GH-AGENT-044 review plan — 2026-09-21

Root follow-up: the original pending plan below is now executed by
`git-history-agent44-proof-verified-20260921.json` (exit 0, 3280.118 ms):
35 exact historical blob digests nonsecret, 9 UNKNOWN. The final helper omits
the unbounded reference-path output and confirms missing paths with a successful
empty literal/full-tree listing. See `git-history-batch-review-20260921.md` for
the independent final review and preserved initial capture.

## Frozen scope

This review covers exactly IDs **5, 8–20, and 62–91** from the immutable
711-row history report with SHA-256
`7fbbbdb37d231b6b5a32d56d66d6ec24f4a5f0f64f95d4a6113f448f8acc2732`.
The reproducibility checker is
`support/git_history_agent44_20260921.py`. It has not itself been treated as a
passing capture in this record; root-owned execution must provide that evidence.

The checker uses only isolated, no-replace Git `cat-file` reads. Per row it
asserts the report commit/path/line tuple, Git object hash, raw source SHA-1
and SHA-256, one exact default-rule candidate, and equality of the reconstructed
whole redacted Match with the report. It emits metadata and classifications only.

## Proposed classifications pending checker capture

| Frozen IDs | Count | Semantic origin / required proof | Proposed classification |
| --- | ---: | --- | --- |
| 8–20, 62–83 | 35 | Candidate is a SHA-256 digest in a JSON mapping whose property names a file. The exact candidate must equal bytes of that same path's historical Git blob at the recorded commit. | `HISTORICAL_REFERENCED_BLOB_SHA256_DIGEST_NONSECRET` |
| 84–91 | 8 | Candidate is digest-shaped, but the named generated artifact is absent from the recorded historical tree; no byte-equality proof exists. | `HISTORICAL_UNVERIFIED_BUILD_OUTPUT_DIGEST_UNKNOWN` |
| 5 | 1 | Singleton literal in readiness evidence has no established nonsecret value semantics. | `HISTORICAL_EVIDENCE_LITERAL_UNKNOWN` |

Only the first group is eligible to leave the security queue after the script's
assertions pass and a root-owned capture is retained. Digest shape, an ignored
path, a fixture name, or generated-asset provenance alone does not clear a row.

## Limits

No historical data is executed, no app/DB/provider code is imported, and no
network, scanner rerun, Docker action, or mutation is part of this review.
The nine unknown rows remain unknown unless a separate value-safe proof binds
them to nonsecret semantics.
