# Review the recipient beside a partnership draft

A native partnership draft could show its message without the stored contact or contact source. The candidate card displayed the service-address warning, but the letter editor did not. This made it difficult to review who would receive the message.

The list API now returns the draft's contact value and source, joined by both contact ID and lead ID. Telegram and MAX use the same editor and show these fields beside the draft. Service and legal email addresses receive the same warning as the candidate card. Existing contact-research displays remain intact in the deployed version. No recipient, message, approval or delivery record is changed.

Two presentation fixes accompany this change: ratings display one decimal place instead of database floating-point precision, and the batch button no longer floats over the letter on short viewports.

Validation: actual Telegram editor opened after deployment; recipient, source and warning were visible. The production-based component suite passed 8 tests, and the common-branch suite passed 9 tests. Frontend build passed. Database access remains scoped to the selected business; no database migration was needed. This does not certify all client acceptance scenarios or live MAX delivery.
