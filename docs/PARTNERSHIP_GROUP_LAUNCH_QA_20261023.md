# Saved partnership group launch

The shared web/Telegram/MAX screen reviews an existing saved collection. It does
not discover recipients, regenerate copy, grant account access, or send messages.

- Preview resolves the business through the existing session/actor/tariff checks,
  reuses saved campaigns and native history/source/recipient checks, and returns
  exact copy, contacts, account labels and Moscow-time dates without a commit.
- First contacts use Telegram for companies already assigned that channel, then
  email for the remaining companies. A company is not enrolled in both channels.
  Slots are spaced and rolled into weekday 10:00–18:00 windows; old draft dates
  are replaced only after an explicit final confirmation.
- Changed inputs invalidate the preview. The final screen has separate text/
  recipient/account review and delivery-queue consent controls. Confirmation
  rechecks the digest, rights, account permissions and configured dispatcher cohort.
- Confirmation locks the collection, uses the existing exact-copy review and
  native campaign approval, and enrolls all campaigns into one existing send batch
  in a single transaction. A failure rolls back the whole transaction. A replay
  returns the same receipt and cannot create another batch. There is no direct
  provider call or new dispatcher.
- Native stop-on-reply, idempotency, runtime preflight and existing send limits
  remain in force. Queued is not sent or delivered. Worker/provider scheduling
  can delay execution beyond the displayed earliest times.
- Platform Telegram settings now follow the connected global binding, rather than
  the selected client's credential container. The actor must still be superadmin
  to request platform settings. Summary labels use the actual first-touch sender.

Validation: focused Python and shared component tests cover read-only preview,
channel order, working windows, stale versions, permissions, partial failure,
idempotency and explicit confirmation. Live acceptance stops at the final review:
no live approval, enrollment, delivery or provider-generation call is performed.
Private recipient lists, copy, screenshots and provider account data are excluded.
