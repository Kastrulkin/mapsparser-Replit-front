# Recovering content edits and optional video errors

Closing the publication sheet could discard unsaved text, theme, date or channel changes without a choice. The editor now asks whether to continue editing or close without saving. It uses the same review dialog pattern as partner cards. Closing an unchanged publication remains immediate. No save, approval or publication is triggered by this guard.

The optional video section expected a listing even when the shared disk helper returned its supported 404/unavailable fallback. This caused a raw JavaScript error in the editor. The section now stays hidden for an unavailable feature and shows a readable retryable error for a listing missing the expected arrays. An error no longer appears together with an empty-list success message.

Evidence: two video regressions and one discard regression failed before their fixes. The production-based editor/disk suite then passed 44 tests and built successfully. Local browser tests exercised continuing an edit and an unavailable optional video section. These checks use synthetic content; they do not certify physical devices, real MAX delivery or new AI generation. Existing client plans were not regenerated or edited.
