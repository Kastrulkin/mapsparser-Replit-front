# Live health and Mac TLS observation — 2026-09-21T12:07:39Z

Scope: one read-only production baseline on `root@80.78.242.105` from
`/opt/seo-app`, plus bounded local network observations. No containers were
restarted, no deployment, provider call, database/schema/data, credential, or
network configuration change was made.

## Production baseline

`docker compose ps` reported `app`, `worker`, PostgreSQL, Redis, ClamAV,
operator-worker, and compliance-worker running. PostgreSQL, Redis, and ClamAV
were healthy. The app and worker had zero restarts and `OOMKilled=false`.

The `telegram-bot` was already `unhealthy`, with 51 restarts and
`OOMKilled=false`; its health-log output was empty, so this run cannot assign a
root cause. It is an existing service concern, not evidence that the public
web release regressed. The bounded app log had no error-signature lines. The
worker log contained two delivery failures:
`[BILLING_RECONCILE] telegram send failed ... <urlopen error timed out>`.
The chat identifier was intentionally omitted from this evidence. This is an
external Telegram-delivery timeout and needs separate operational follow-up;
it is not a LocalOS HTTP failure.

Server-local endpoint timings (all HTTP 200):

| URL | connect | TLS | total |
| --- | ---: | ---: | ---: |
| `http://localhost:8000/` | 0.000286s | n/a | 0.017235s |
| `http://localhost:8000/health` | 0.000162s | n/a | 0.006458s |
| `http://localhost:8000/ready` | 0.000154s | n/a | 0.231651s |
| `https://localos.pro/` | 0.017064s | 0.072691s | 0.083675s |
| `https://localos.pro/about` | 0.012273s | 0.054482s | 0.064381s |
| `https://localos.pro/pricing` | 0.013528s | 0.056203s | 0.065960s |

## Mac-side TLS observation

Outside the filesystem sandbox, IPv4 DNS resolved `localos.pro` to
`80.78.242.105`. For `/`, `/about`, and `/pricing`, TCP connection succeeded
in 0.002–0.013 seconds, then the TLS handshake hit the five-second bound
(`curl: (28) SSL connection timeout`; HTTP code 000). The sandbox itself cannot
perform DNS; that was not used to classify the result.

This combination leaves the external client-to-server path unresolved. It
does not identify TLS interception or isolate client, network, ingress or
server behavior. The same three HTTPS routes completed with HTTP 200 and
normal TLS timings from the production host, but that vantage point cannot
prove external reachability. No DNS, VPN, proxy, route, certificate, or
firewall setting was changed during this audit.

## Verdict

- Public LocalOS web routes: **healthy from production host**.
- Mac external browser/curl reachability: **unresolved; failure boundary unknown**.
- Telegram bot health: **needs separate operational diagnosis**; no causal
  explanation was safely observable in this bounded read-only pass.

## Telegram-bot follow-up (read only)

The live container is running with exit code `0`, `OOMKilled=false`, and has
been continuously started since `2026-09-20T02:00:07Z`. Its restart policy is
`unless-stopped`. The reported `restart_count=51` is cumulative and predates
that current 34-hour process lifetime; no evidence from this check attributes
those restarts to the current healthcheck failures.

The live healthcheck is exactly:

```
python -m core.telegram_healthcheck
```

with a 60-second interval, 12-second timeout, 30-second start period and three
retries. The five most recent attempts at `15:04`–`15:08 MSK` each finished in
under 0.6 seconds with exit code `1` and no output. Docker health failures do
not themselves restart a container, so these checks do not explain the historic
restart count.

The repository compose definition and `src/core/telegram_healthcheck.py` match
this command. When a bot token is configured, that code intentionally requires
all of: the bot process as PID 1, a recent successful polling marker, and a
successful read-only `getMe` request. It suppresses exception details and exits
1, explaining the empty health output. It does not consume updates.

Conclusion: this is neither a confirmed process crash nor a proven Telegram
outage. The current process is alive, while the health contract is failing
because either polling freshness is absent or its provider-readiness `getMe`
probe cannot succeed (or both). The healthcheck is not demonstrably inaccurate:
the failure correctly represents an unmet declared liveness/readiness contract.
Next safe diagnostic, requiring a separately scoped operational decision, is to
observe the bot's polling freshness and proxy/network path without exposing its
token or invoking a provider action. No such check was run here.

### Polling-marker refinement

A direct read of the exact files used by the live healthcheck found
`/proc/1/cmdline` contains `telegram_bot.py`, so the expected PID 1 process is
present. The polling heartbeat file
`/tmp/localos-telegram-poll.heartbeat` is absent. Under the live contract this
makes `recent_poll=false`; the stale threshold is 180 seconds. No healthcheck
module was imported and no provider request was made for this observation.

This narrows the current `unhealthy` result: **stale or absent polling is
already sufficient**, before the `getMe` readiness probe is considered. It
does not prove why polling stopped, nor does it distinguish a Telegram route,
proxy, polling-loop, or upstream issue.

### Mac TLS-mode comparison

Three certificate-verifying, five-second IPv4 requests to
`https://localos.pro/pricing` were attempted: default TLS, `--tls-max 1.2`,
and `--http1.1`. All returned HTTP `000` and timed out at approximately five
seconds. In this later sample the connection timing itself remained zero while
the resolved remote IP was `80.78.242.105`; it therefore did not reproduce a
completed TCP connection as the earlier Mac sample did. Neither limiting TLS
to 1.2 nor forcing HTTP/1.1 changed the outcome. Certificate verification was
never disabled.

The external Mac reachability condition remains open; this comparison does not
identify a TLS-version or HTTP/2 negotiation regression. Server-side verified
HTTPS remains the evidence for the deployed LocalOS web service.
