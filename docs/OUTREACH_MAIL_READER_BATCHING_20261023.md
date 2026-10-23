# Legacy Inbox/Sent reader: bounded batches

The legacy reader fetched the latest messages through one full-message request
per UID. It now reuses the existing strict UID batch reader, with at most twenty
bodies per request. It reads the same limited message set and retains the existing
parsing, matching, suppression and reply checks. UID responses are validated
exactly; an incomplete batch fails rather than being recorded as a successful
sync. BODY.PEEK avoids marking incoming messages read during synchronization.

UIDs are sorted numerically before selecting the latest messages. The body phase
uses a bounded deadline. No send limit, sender permission, recipient scope or
approval boundary changes. Existing complete-window/DSN search code is preserved.

Validation: 26 focused batching and receipt tests pass, including sparse complete
windows, missing/duplicate UIDs and preservation of the legacy latest-message
selection. A separate worker-scope fixture fails without DATABASE_URL on both the
unchanged baseline and this change; it is not counted as passing.

## Prior inbound without a current sent-touch match

A complete scoped read can find an earlier inbound from an exact authorized
recipient before the current touch was sent. It is not evidence of a reply to
the new touch. The reader now durably records such incoming events and pauses
only their exact recipient-linked campaigns for review. It does not mark a
message sent, fabricate a current reply, or discard the incoming event.

Unknown peers, missing durable context, and persistence failures still reject
the complete-sync receipt. Replay uses the existing provider-event unique key.
No mail credentials, recipient lists, or client message bodies are in this change.

Validation: 31 focused tests pass across strict IMAP batching, complete reply
receipts, and exact-recipient prior-inbound quarantine. Production sending
continues to depend on a successful complete mailbox read.
