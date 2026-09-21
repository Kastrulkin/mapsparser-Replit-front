# Native child guard draft review — 21 September

Scope: support/native_hflypi_sitecustomize.py and the AST-only
support/native_hflypi_child_checks.py. No application code changed.

The independent read-only reviewer first rejected an executable-readiness
claim: unsafe Python startup flags, executable overrides and Docker kwargs
were insufficiently constrained, and internal-only Testcontainers host
connectivity had not been proved. The implementation now:

- rejects Python `-E`, `-I`, `-S`, combined flags and shell-Python;
- rejects all extra positional Popen options and keyword executable overrides;
- pins child PYTHONPATH, guard hashes and the literal Docker socket/DOCKER_HOST;
- preserves caller DATABASE_URL and rejects conflicting guarded values/libpq
  overrides;
- restricts helper Docker kwargs and deliberately denies all Testcontainers
  starts until the owned network profile is proved.

The root independently ran:

```sh
/usr/bin/env -i PATH=/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -I -B .agent/tasks/production-readiness-20260917/support/native_hflypi_child_checks.py
```

Exit 0; stdout:

```text
native_hflypi_child_checks: negative_control=expected_unpatched_assertion green=pure_helpers_passed
```

macOS emitted two temp-directory lookup warnings and fell back to /tmp. The
check executes extracted helper AST with fake Popen and temporary guard bytes;
it does not import the guard, launch a child, load the app, open sockets or
contact Docker/DBs. Its negative control is not immutable-source or real-child
RED evidence. The older green note is explicitly historical/superseded.

After the final positional-executable correction, the independent reviewer
accepted this **DRAFT / UNEXECUTED checkpoint only**. Installation remains
forbidden until actual initialization and positive/negative child probes are
reviewed and pass. Direct os.spawn/posix_spawn/exec, renamed/bytes Python and
native libraries are outside demonstrated coverage; this is not an adversarial
sandbox. Docker daemon access is privileged and not constrained by a Python
socket guard alone. Full native collection/integration is still unexecuted.

The separate network-profile plan records remaining Testcontainers connectivity
and container-egress tradeoffs; no network was created or modified here.
