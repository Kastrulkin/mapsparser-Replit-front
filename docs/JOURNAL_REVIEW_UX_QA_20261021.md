# Journal author and filtered empty state

The ordinary journal list did not identify the author, although the review inbox did. The existing scoped query now includes the author's name, and the shared Telegram/MAX/web list displays it beside the date. Record visibility, editing permissions and recipient settings are unchanged.

An empty filtered result previously said that no records existed and suggested creating a new one. It now explains that the search/date has no matches and offers Reset filters. The genuinely empty journal retains a short example without requiring command syntax.

Validation: production-based journal, briefing and voice component suites passed 32 tests; frontend build passed. Regression coverage includes author display and restoring existing entries after a filter reset. No observations, employee tasks or messages were created by this patch. No database migration was required.

On an isolated loopback PostgreSQL with synthetic data: 62 journal/review tests, 32 Organika regression tests and 12 Telegram/MAX handoff tests passed. These are technical checks, not 106 live client acceptance cases. Live Telegram verification also confirmed author display and filter reset. No real MAX provider delivery was tested.
