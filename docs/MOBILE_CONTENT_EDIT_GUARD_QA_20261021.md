# Preserve an open mobile publication editor

The mobile content workspace had two paths that silently discarded an open edit: the top Edit publications action cleared the editor, and navigation could unmount it. A live Telegram check reproduced the loss with temporary unsaved text; the stored publication was not changed.

While editing, the top action becomes Return to editing and scrolls to the open publication without resetting it. An explicit callback reports the open editor to the parent workspace. Menu navigation, module Back (including the messenger back control), and the business picker retain the editor and explain that the user must save or cancel editing first. Successful save or explicit cancel removes the guard. No draft is stored in a shared browser cache and no new permission is granted.

The common branch also retains the deployed module return-origin behavior, so Back returns to the tab from which the module was opened. Server source updates are partial and preserve the deployed search/finance changes.

Validation: navigation regressions failed on the previous version for both Telegram and MAX. Six targeted mobile tests passed after the change, including a concurrent post update, linked-post editing and the top-button path. The production-based frontend build passed. This guards in-app navigation; it does not certify native host window closing, physical devices or live MAX delivery.
