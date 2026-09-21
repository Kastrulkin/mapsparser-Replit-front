# Isolated Linux capability tests — 22 September

## Result: 13/13 passed in the stated test profile

All eleven previously offline-denied tests now pass: five ingress-proxy checks,
five compiled-runner transport/execution checks, and the Telegram unused-transport
watchdog check. Both frontend-dist fixture checks pass as well. Exact13 v4 reports
13 setup, 13 call and 13 teardown passes, no skips/xfails, zero callback reasons,
no timeout or output truncation; wrapper 13,256.059 ms. Independent runtime review
accepted these exact counts, unchanged manifests and isolation, not whole readiness.

The Python HTTP listeners and subprocesses execute inside a fresh network-none
Linux container. It has no published ports, host network, Docker socket, existing
database, provider credentials or application entrypoint. Read-only source,
dependency and runner mounts; non-root UID501:GID20; dropped capabilities;
no-new-privileges; 1 CPU, 1 GiB memory, 128 PIDs; 512 MiB /tmp tmpfs. The owned
container is automatically removed. Root compared the 23 pre-existing container
IDs and running/stopped states before/after: preserved. No additional cache prune.

## Preserve the failures and their actual causes

1. Initial macOS repeat: six scoped leaf tests and the negative dist fixture pass;
   positive dist fixture fails because Bash cannot create its heredoc temporary
   file under that OS policy. A direct mktemp positive control in the owned TMPDIR
   succeeded. This is not the previously fixed global test hook.
2. Docker metadata probe: pytest absent in this runtime image. A read-only,
   compatible pure-Python test dependency mount resolves that prerequisite.
3. Exact13 v1: manifest serialization mismatch, no pytest execution. Corrected
   digest computation, without changing source bytes or assertions.
4. Exact13 v2: collection failure because the app image does not include the
   separate Telegram runtime package. No test bodies executed. Its pure-Python
   dependency closure was copied from the existing local environment, reviewed
   and import-probed without downloads or network.
5. Exact13 v3: real execution, 11 passed / 2 failed. The snapshot's privacy-mode
   normalization had removed the dist script's tracked execute bit. Git100755 and
   unchanged script SHA were confirmed; only the owned snapshot script changed
   0600→0700. This is a harness mode defect, not a product permission defect.
6. Exact13 v4: unchanged selectors/assertions, mode-aware input manifests, 13/13 pass.

No application or test assertion was modified for this lane. Original failures
are archived, not replaced with a green summary.

## Identity and limits

Snapshot is b12cfcb2 plus exactly the two explicitly named parser/author test
overlays; 6,216 regular files. This is not the entire foreign dirty tree. Image
SHA starts9d6edac8 (full digest and every argv are in raw captures). Executed
runner SHA `f9ababbb9a3c54ef86295ac9552837d312acc44f53c205ae0be1bebf647b2c1e`.
Final source and dependency mode-aware digests:

```
323c3de031dd2c9213759cf988da46fa47ce933db0d45f6e115d2540222d1405
ed4f33f3a1d7a99b8d965bbdf53ea84455b36a1762e316b99aba136a57407117
```

Exact dependency versions and two overlay hashes are in provenance-v4.txt.
Host-sourced pure-Python packages (including PTB20.8/httpx0.26.0) are mounted for
this test profile: this does NOT certify the stock image's dependency completeness,
dependency security or the deployment's Telegram runtime. No image build/install,
Compose integration, PostgreSQL, live browser or production proof is implied.
Historical full-backend NONPASS and broad remaining gates are unchanged.

Preceding frontend package committed locally as5b7f63a9: strict188,847-byte staged
diff scan found0 secrets in664.769ms; normal commit181.999ms. Those captures are
also retained here. No push/deploy. Next substantive unknown is the separate
13-node native PostgreSQL callback-recovery family, not another replay of these tests.
