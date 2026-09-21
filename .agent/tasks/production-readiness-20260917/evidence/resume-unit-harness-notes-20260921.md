# Current frontend verification and test-harness timing

The initial complete unit capture has 828 passes and two failures across 143
files. It is retained, not relabelled green. Both failures occurred while the
intended test data already existed but the harness had not reached its final
rendered state: the first schedule test still displayed Suspense while its
async mock imported the real employee panel; the preferred-plan test had the
correct heading beneath Framer Motion's initial `opacity: 0` in JSDOM.

Only two test files changed. The schedule harness now statically imports the
same real panel and uses a synchronous view mock. Today navigation/scope tests
render through the public `AnimatePresence initial={false}` boundary. All
schedule, tenant, priority, visibility, stale-data and no-save assertions are
retained; timeouts are not increased. These tests deliberately do not certify
entrance-animation timing. Application components were not modified.

## Captured results

| Capture prefix (all dated 20260921) | Result |
| --- | --- |
| `resume-frontend-unit` | 828 passed / 2 failed; 172.827 s captured |
| `resume-unit-harness-targeted` | 11/11 passed; 8.418 s captured |
| `resume-frontend-final-unit` | 830/830 passed, 143/143 files; 172.232 s captured |
| `resume-frontend-final-types` | app and tooling TypeScript pass |
| `resume-frontend-final-lint` | pass, zero errors / one existing legacy transport `any` warning |
| `resume-frontend-build` | application build passes |
| `resume-frontend-public-build` | public-audit build passes |

The final independent read-only reviewer accepted the scoped change and
reported a separate 11/11 rerun in 2.82 s. Its rerun is reviewer testimony,
distinct from the retained builder captures. The full-suite captures contain
expected fixture-error diagnostics; they are not a production clean-console
claim. Neither a product defect nor a product performance improvement is
established by these timing corrections.

The source checkpoint was `f90241b9`; concurrent commit `dee9978c` contains no
frontend changes (`git diff --name-only f90241b9 dee9978c -- frontend` empty).
Dependencies are the existing local frontend installation, not a fresh npm
install or immutable image. Both builds preceded the test-only patch, so their
runtime source is unchanged. Native backend, real-API aggregate, clean install,
image, restore, performance and demo acceptance remain separate pending gates.

The retained support launcher was hardened after these captures to propagate
failed command status and refuse overwriting an existing capture; `bash -n`
passes. Its original wrapper status was not used to judge command outcomes:
each JSON's actual `exit_code`, timeout and output fields are authoritative.
Do not replay completed capture labels.
