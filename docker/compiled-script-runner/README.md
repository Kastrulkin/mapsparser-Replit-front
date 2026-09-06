# Compiled script runner boundary

Compiled artifacts are untrusted user input. The runner is a separate internal
service with a read-only root filesystem, no Docker socket, no database or
provider secrets, no public port, internal-only network, CPU/memory/PID and
wall-time limits. Its gateway keeps the transport secret; each script runs in
a separate UID with an empty environment. The web process authenticates each
short-lived request with timestamp/nonce HMAC, verifies the response HMAC and
requires the configured image digest before it accepts a result.

Deploy the fragment with a digest-pinned image and set
`COMPILED_SCRIPT_RUNNER_URL=http://compiled-script-runner:8091`, the digest and
shared secret in app and worker. Until those values and the internal service
exist, production execution and preview fail closed with
`COMPILED_RUNTIME_UNAVAILABLE`. The fixed sheet implementation is an oracle
only; preview always executes the approved source in the runner.


Production image verification (required before preview/execute rollout):

1. Build and publish the image separately; the production fragment never builds it.
2. Set `COMPILED_SCRIPT_RUNNER_IMAGE=repository@sha256:<manifest-digest>` and the
   same manifest digest in `COMPILED_SCRIPT_RUNNER_IMAGE_DIGEST`.
3. Run `python3 scripts/check_compiled_runner_deployment.py` before pulling the image.
4. After starting the container, run the same command with `--container <runner>`.
   It checks the actual image ID/RepoDigests, internal networks, resource limits,
   mounts, privileges and credential names without printing secret values.
5. Only then enable the backend cohort allowlist and the relevant stage flag.

The response digest/HMAC is a transport integrity check, not independent hardware
attestation. Host-side image evidence is required. A missing/mismatched digest
must block rollout, not be replaced with a guessed value. Local integration tests
build a disposable image and pin its actual image ID; they are not evidence that
any production container has been changed.

The service accepts two requests concurrently, rejects overload with 503, times
out incomplete bodies after two seconds, and limits each child to three seconds.
Native child credential switching avoids preexec functions in the threaded parent.
The CPU/RAM/PID/output limits remain active in each child; a fresh clean environment
contains no application, provider or database credentials. Retry of pure read-only
work is bounded by the persisted run attempt limit.
