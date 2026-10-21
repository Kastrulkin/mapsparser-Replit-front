# Read a selected saved post without AI

A live messenger request to show the selected publication entered the editorial AI loop. The planner received metadata without the draft text and replied that it could not show the post, even though the same authorized user could read it in the miniapp.

Literal read commands now load the exact selected item through the existing business-scoped content query. Business access, content entitlement, item identity and archived-plan checks run before text is returned. The reply preserves the saved paragraphs, identifies the current saved version and retains the selection for further discussion. Empty drafts are reported as empty rather than replaced with another post. This read path does not invoke AI, change a draft, regenerate a plan or publish. Other editorial commands retain their existing approval boundaries.

The result button carries the selected item and business into the miniapp. The fix uses the shared routing code for Telegram and MAX; live MAX still requires platform acceptance.

Validation: 54 focused and adjacent backend checks passed, including all four messenger channels bypassing the paid AI loop, denied access, missing/foreign/archived items, version refresh, preserved paragraphs and scoped return links. Deployment uses the current production source with only these changes applied; no client content or access settings are changed.
