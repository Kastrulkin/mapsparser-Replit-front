# Private-key detector: bounded structural observations

One37.381-second read-only image stream inspected the exact six members behind
all17 `private-key` candidate IDs. It matched the original archive SHA-256
`35d4ad6e70b812698c42698c6c93f16256da4ef3963b285f6c2333576aaffb2c` and the mapped
whole-file digests/line coordinates. All helper/mapping hashes match before/after.
No extraction, bytecode deserialization, container run, external request or key
validation took place. Selected bytes lived only in bounded memory; no content,
private member paths, PEM bodies or candidate values appear in the result.

## Three narrowly explained detector hits

Independent review accepts the following finding-level observations, not a
statement that either whole file or the image is free of secrets:

| Candidate | Exact member/coordinate | Observation |
| --- | --- | --- |
|`candidate-ef9de94eb925a7c1887763aa`|path hash389ab762, file131ab3f4, line39|Python AST constant is exactly a BEGIN delimiter, not a key body|
|`candidate-37cab0d21124fee998869fb1`|path hash836c54bd, file26474dbf, line1219|ELF string marker bounded by NUL before and after optional newline|
|`candidate-fe4d14db0e2382fcfb1d0a27`|same exact member/line|same bounded delimiter predicate; distinct original finding occurrence retained|

Neither member contains a complete base64-decodable PEM envelope under this
bounded recognizer. That negative observation alone is not clearance: escaped,
encrypted or unsupported representations are not excluded. The positive delimiter
structure explains these three specific detector hits only.

The other14 private-key-labelled hits remain unclassified:10 in another ELF file
do not satisfy the strict delimiter predicate;2 bytecode markers have only magic/
marker observations;2 source hits do not satisfy the all-lines literal predicates.
No rule/path-level suppression and no image/security gate is closed. The earlier
13 prior source classifications remain separate; all206 non-transferred image
candidates stay in the open triage ledger, with these3 structural notes attached.

## Verification and preserved limits

Executed v2 sourceb8b6e1f8 imports pinned v1fe282988 only for stream/identity
functions, never its marshal or old predicate functions. Both exact sources are
archived as text. The v2 default output intentionally retains
`structural_observation_only_unknown_not_cleared` for every member.
Independent pre-execution and runtime review PASS at this bounded scope.
Root pure controls pass256.495ms, no timeout/truncation; Ruff/compilation pass.
The control called 'actual PEM' is only a synthetic base64 envelope, not a
generated real private key; it tests that body-shaped input is not cleared.

Artifacts and six-entry manifest: `image-pem-observations-20260922/`.
No production/existing DB/provider mutations or repeated cleanup. Remaining image,
history, dependency and current-runtime security gates are explicitly open.
