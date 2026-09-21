# RESTORE-PORTS-TEMP-01 — restore binding admission fails closed

## Confirmed defect

The restore helper checked each published PostgreSQL binding with
`while read ...; done <<< "$ports"`. On the actual macOS shell used by the
isolated run, here-string temporary-file creation can be denied. Bash reported
that failure but the loop did not reject, so the script continued to the fake
CREATE DATABASE and restore commands despite a non-loopback binding.

This is a conditionalP1 admission defect with high causal confidence, not evidence
of a production incident. Every execution used a fake Docker executable and
synthetic archive/identity/target under OS network/write denial. Real Docker,
existing databases and production were never invoked or changed.

## Minimal correction

`scripts/postgres-restore-latest.sh` now iterates the captured string with Bash
parameter expansion. Every binding still matches the exact original loopback
regex, before any target query/create/stream. There is no stdin, pipe or temporary
file in this validation path. Original identity, context, project, target,
confirmation and trusted-archive gates are unchanged. Leading/internal blank
bindings and later non-loopback lines still reject; command substitution strips
trailing newlines as before.

Helper SHA-256 `e0ff17d52dc828bdfbc6919b54d5e4e2e2cfdcd430aa48f15d7f0aaf95573fc3`;
test SHA-256 `9033247b3d4f56318d698b0dd02b451030753b2e94815ea57ebb02cb0bb5e530`.
Two test cases add unusable-TMP valid admission and injected-read-failure unsafe
admission; no assertions were weakened. The BASH_ENV fixture returning2 from read
is synthetic failure injection, not a claim to defend arbitrary attacker shell code.

## Causal and adjacent verification

- Original mixed-binding case under real OS temp denial: RED, helper proceeds to
  fake create/stream; exact patched case GREEN, rejects before either marker.
- Same deterministic negative wrapper/fixture on frozen baseline vs patch:
  baseline helper returns0 and marks create+stream, semantic RED exit1;
  patched helper returns1 with no create/stream, GREEN exit0.
- Full fake-helper safety suite:13pass,2.34s pytest/2623.398ms capture, exit0.
- Root exact39-case regression after both fixes:39pass,16.44s pytest/17101.33ms
  capture, exit0,39unique nodes/117passing stages, no skip/xfail or leaked hook.
  Prior38pass/1fail adjacentv2 stays preserved with the leaf fix.
- Root Bash syntax, Ruff and diff-check pass. Exact sources remain frozen.

Independent source/policy/read-wrapper, final outcome and12-entry package review
PASS confirms this narrow local fail-closed correction, not real recovery readiness.
Artifacts `restore-ports-temp-20260922/` retain original failing captures, exact
baseline/wrapper/policies, full safety suite and root regression result.
Earlier attempted diagnostic wrappers remain private; no result relies on them.

This does not rerun the full5487 offline aggregate, prove a real backup restore,
authorize production execution or close other operational/security gates. Native
integration and final built-current-source aggregate remain required. No deploy,
push, real DB/provider mutation, credential checks or repeated Docker cleanup.
