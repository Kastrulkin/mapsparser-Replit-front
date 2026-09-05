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
