# Pinned image credentials — findings require review

The local Linux/arm64 image
`sha256:9d6edac8b6948e239c0bab54564f92f829e5b9dfc93f3ca0626060ffb4e60853`
(application frozen at `99849935`) was streamed through installed Gitleaks
8.30.1 default rules. No extraction, container execution, external upload,
production access or credential validation was performed.

## Actual results

| Attempt | Time | Result |
| --- | ---: | --- |
| v1 | 123.521 s | BrokenPipeError; incomplete, not clean |
| v2 | 913.092 s | all 20 historical layers and OCI config scanned; 219 candidates |

V2 traverses 1,074,089,472 OCI archive bytes and 2,919,512,576 expanded layer
bytes. The layers contain 61,500 regular entries totaling 2,866,391,223 bytes,
3,574 links and 79 whiteouts. These are historical entry totals, not unique
final-rootfs files. Descriptor sizes, blob digests, layer ordering and diff IDs
are validated; before/after inspect identities agree. Independent runtime
review accepts coverage/accounting, not credential absence.

There are 217 layer findings and 2 config findings: 200 generic-api-key,
17 private-key, one JWT and one curl-auth-header. These are detector categories,
**not 219 confirmed secrets**. None is triaged by this package. Each persisted
candidate retains only path SHA-256, positive line number and rule identifier;
neither Match nor Secret nor plaintext file contents is retained.

The initial 120-second internal limit is a suspected cause of v1, not proven:
its stderr was discarded. V2 uses 600 seconds internally per Gitleaks process,
630 seconds watchdog and 1,200 seconds export deadline. The byte limits and
default detection rules were not relaxed. Binary bytes are fed to the scanner,
but arbitrary binary/encoded credential detection is not claimed.

## Runtime provenance qualification

V2 started in tmux `audit-image-credentials-v2` at 00:54:34+0300 on 22 September.
The pre-execution reviewed scanner was SHA-256
`919a983f870943fced1db2e60ce249317f617856f14ce815b7abf1a8d76e1170`.
Its exact bytes are archived as `image_credentials_hflypi_v2_runtime.py.txt`;
the reviewed controls snapshot is `5566414d...71316`. The imported tracked
private-layer helper stayed unchanged at `57a1ba58...a8f7`.

During execution a worker added three exception-path type checks at 00:55:28.
No scan, redaction or success-path logic changed. Consequently raw v2's
`controller_sha256=c76f17cd...19e8` is the **post-start on-disk hash**, computed
in finally, not a self-contained runtime-source identity. Bind the observed
execution to the archived 919a snapshot and prelaunch/start/edit timeline;
do not claim that v2 executed current c76 source. Independent provenance review
confirmed this exact difference. This external provenance qualification must
travel with the raw result; a future standalone proof needs a frozen controller
and all imported helpers, with their hashes captured before execution.

Current pure controls were rerun after terminal v2. `controls-v6.json` passes
in 2,833.075 ms with Ruff F821/F822/F823: clean input, renamed file, deleted
lower-layer key, config key, multiple-member line mapping, chunk/binary boundary,
and watchdog rejection. Scanner remains c76; controls now 77144c7d after using
explicit try/finally tar close. Historical v5 stdout is retained but is not a
current-source proof. V1 exact source/control snapshots remain separately bound.

## Next gate

Map the exact 219 candidates to verified layer/member metadata in one bounded
read-only stream of this same pinned image. Then distinguish public examples,
test fixtures, code expressions and genuine credentials using exact source
evidence. Do not suppress by detector rule or call a path-name guess a dismissal.
Never output credential values or test them against a live provider. Any real
credential or private material needs an explicit scoped remediation decision;
rotation, history rewrite and deployed-image changes are not authorized here.

SEC-BUILD-CONTEXT-02 and the broader security gate remain OPEN. Earlier bounded
private-artifact zero findings do not override these untriaged credential
candidates. Original whole readiness stays FAIL. The 12-entry manifest binds
raw results, snapshots, control evidence and three current/imported helpers.
