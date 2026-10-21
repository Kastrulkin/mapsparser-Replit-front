# Safe publication-save errors

The item-update endpoint returned the raw exception string for an unexpected server failure. It now uses the existing traceable API error helper: a readable save message and request ID are returned, while the exception remains in the server log. Permission errors, missing resources and version conflicts keep their existing 403/404/409 responses.

The regression failed before the fix. All 16 targeted API tests passed afterward, including ordinary identity context, safe error output and unchanged actionable domain errors. Local browser verification retained unsaved text after a synthetic failure and saved it on an explicit retry, without invoking generation, approval or publication. No client records or provider calls were used by these tests.
