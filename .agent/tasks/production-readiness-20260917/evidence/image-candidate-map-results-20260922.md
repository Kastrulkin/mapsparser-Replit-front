# Image candidate mapping and bounded source triage — 22 September

## Outcome

All 219 redacted candidates from the earlier image scan are now linked to exact
historical layer members or the whole canonical OCI config. Thirteen source
findings inherit an earlier non-secret classification only after exact whole-file
SHA-256 equality. **206 remain untriaged; the image is not certified clean.**
No credential was tested against a provider. No image/container/volume was changed.

## Exact scope and evidence

- Image: `sha256:9d6edac8b6948e239c0bab54564f92f829e5b9dfc93f3ca0626060ffb4e60853`.
- Input capture SHA-256: `02fa7241514f55ae81ce184f6df88733696eca17927169b771dc0f4c4229a95e`.
- Mapper: `3f55167f80900fc08e32484e5fe9b169ee50b3b2f29f12ab0df4b110d11f4a59`;
  private-layer dependency: `57a1ba58876f35797708071ba88b2387a0e15888ac0f7034868cbb017da3a8f7`.
  Both before/after bindings match.
- Named tmux `audit-image-map-v1`: 37.123 seconds, status `mapped`, 20 layers,
  archive 1,074,089,472 bytes, expanded 2,919,512,576 bytes.
- Archive SHA-256: `35d4ad6e70b812698c42698c6c93f16256da4ef3963b285f6c2333576aaffb2c`,
  exactly equal to the original credential scan archive.
- Private result: `/private/tmp/localos-readiness-20260921.hfLYPi/native/evidence/image-candidate-map-v1.json`,
  SHA-256 `3b2f050ac7e336db62626f7c4a34a5ac27213453f0192b6871a9da8d2e7d713c`.
  Its normalized member names are private metadata, not copied into Git.
- `image-candidate-map-20260922/mapping-redacted.json` removes only
  `normalized_path` from each candidate and adds derivation metadata. All candidate
  identities, file digests and runtime bindings remain. It is a derivative, not
  the original capture. Config line 1 maps to the whole canonical config, not a
  particular field.
- Synthetic mapper controls pass; `controls-v2.txt` retains terminal `EXIT=0`.
  Their source SHA is `8ac42d32ac04be91a69323a26f4b9a042fdef1825d6ac8ee1a240a4970d3982e`.
  Root rerun `root-controls.json` independently passes in250.946ms, exit0,
  no timeout/truncation; both support files pass Ruff.

## Source-triage transfer

`source_join_executed.py.txt` is the exact executed source (SHA-256
`5620180d388fba4fe7e14e7b311d9889fa466e566724b15a004f755829399f35`).
It pins the image, capture, mapper/dependency, archive and 20-layer count, then
joins candidate path hash + start line + rule to the prior ledger. For each
match it hashes the entire file from Git commit
`334c9d4bf69cc9e96fd13a39d9eba8ff32c9f3d6` and requires equality with the image member.
Prior ledger SHA is `5659a93122fac1a7b6e90f4f880558e73c0df8a02baec47d521b7825d213f92d`.

The complete second capture `source-join-v2.json` reports exit 0, no timeout or
truncation, 724.824 ms. Thirteen transferred findings comprise seven deterministic
source/test fixtures, three prose/example identifiers, two idempotency examples,
and one documented bearer placeholder. Every other candidate remains explicitly
`no_prior_locator`. The transfer does not reconstruct an original Match range;
its boundary is exact member bytes plus the original StartLine/rule coordinate.

The first source-join capture used the capture helper's default 6,000-character
limit and truncated otherwise valid JSON. It is retained privately as
`/private/tmp/localos-image-triage-gtfjWr/source-join.json`; no conclusion relies on
that truncated envelope. The second run changes only the capture limit to 50,000.

## Independent review and next step

Independent read-only runtime/transfer review PASS: all 219 identities accounted
for; exact image/archive/runtime bindings; no credential values retained in the
mapping; all 206 unresolved candidates preserved. A separate private-key predicate
analyzer is being prepared for the 17 private-key labels. Those labels are not
confirmed private keys and are not cleared by filenames alone. Whole-goal status
remains OPEN/FAIL. Production, existing databases and all Docker volumes untouched.
