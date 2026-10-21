# Media errors and selected-work entry

A failed publication photo previously left a blank/broken image with no explanation. Enlarged-photo review now explains the failure and offers an explicit retry. Authenticated image loading has a 15-second deadline, cancels on unmount and handles network failures without an unhandled promise rejection. Closing or retrying the photo retains the unsaved publication text. Error/loading surfaces use existing interface tokens.

A direct link to a specific partner, publication, day briefing or finance input now opens that selection without automatically stacking a restored background-job modal on top. This changes presentation only: the background job is not stopped, retried, approved or removed. Default startup retains its existing restoration behavior.

Validation: unavailable-photo behavior was reproduced in the isolated browser (completed image with zero intrinsic size and no error message). After the fix, the error and retry are visible and typed text remains on return. Selected-work regressions reproduced the extra modal for both messenger routes. Ten focused frontend tests and both common/production-based builds passed. Live platform/device checks remain separate from isolated browser coverage. No client content was saved, generated or published during this verification.
