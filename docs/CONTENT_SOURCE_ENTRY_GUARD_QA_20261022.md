# Sources and approaches: direct entry and safe note editing

The source research was hidden inside company/content settings. A live miniapp pass also reproduced silent loss of an unfinished reference URL and explanation after closing and reopening the panel. Per-source review dates were only available in an additional disclosure.

Web content and the shared Telegram/MAX module now open the existing Sources and approaches panel directly. This reuses the same catalogue, research and permissions; it does not create or regenerate a plan. The per-source reviewed date is visible next to the analysis. Unfinished reference and moderation notes require an explicit discard decision before closing. Continue editing retains the fields; successful submission clears the relevant dirty state. Closing the direct panel returns keyboard focus to its opening button.

Validation: the initial focused suite failed four cases before the fix (three transport variants of unfinished-note close, one visible-date expectation). Final focused source, content-settings and mobile-entry suites passed on production-based and common sources, 32 cases each. The production-based frontend build passed and was partially deployed with exact source/index guards. Live Telegram confirmed direct entry, visible date, unfinished URL retention, explicit discard and focus return without saving client test data.

The private research report and existing client plans were not changed or published. This frontend check is not a fresh verification of every external source or physical-device/live MAX acceptance. No client or partner messages were sent.
