# Documentation Changelog

## 2026-07-23

- Added a scoped manual MAX sender binding: LocalOS stores the account phone, prepares MAX touches and records operator-confirmed delivery/reply states without direct send or access to personal chats.
- Documented that the official MAX integration surface is a moderated Bot API, not a personal-account API by phone; a future bot connection is an inbound/opt-in channel rather than a cold-outreach substitute.
- Documented the production VK community sender: encrypted community key, actual sender name/avatar, separate outreach permission, campaign-scoped reply sync and no-send connection preflight.
- Corrected outdated statements that treated VK as a manual-only outreach channel or recommended personal-profile VK ID OAuth for outreach.
- Documented the two current VK beta bindings: `outreach_sender_accounts` with `messages` and `externalbusinessaccounts` with `wall`.
- Marked one shared VK connection with independent publishing/outreach permissions as the target model and an explicit current gap.
- Added the messaging rule that useful community content may support trust but cannot replace lead-specific evidence or disguise an unrelated sender name.

## 2026-07-22

- Added the canonical `OUTREACH_SYSTEM.md` lifecycle from lead search and public contact enrichment through evidence, sender identity, versioned multichannel drafts, approval, stop-on-reply and outcome learning.
- Documented the three explicit sender modes: `localos`, `partner_business` and transparent `localos_for_partner` representation.
- Documented Telegram entity API classification, the shared account with independent radar/outreach permissions, and the rule that channels/groups are evidence sources rather than DM recipients.
- Clarified that Telegram/email are the current automatic adapter boundary, other channels remain manual, and saved evidence/outcomes do not imply automatic model fine-tuning.
- Updated README, product model, use cases, agent registry, Telegram proxy runbook and partnership roadmap references to use the same current contract.

## 2026-07-19

- Documented the new Google Cloud project `localos-gbp` and kept it separate from the current production OAuth client while review is pending.
- Recorded the LocalOS GBP agency organization, the verified managed profile «Веселая расческа» at Проспект Энгельса, 154, and the no-ownership-transfer manager access model.
- Recorded Basic API Access case `7-6688000041542`, submitted 18 July 2026, and added the post-approval production checklist.

## 2026-06-17

- Updated the main project description after reviewing the last three months of changes.
- Reflected LocalOS scope beyond map SEO: Google Business Profile, compiled agents, OpenClaw boundary, supervised outreach, finance, Telegram/WhatsApp, content planning, parser reliability, and approval requirements.
- Marked Google Business Profile as `beta / Google approval pending` and kept external publishing behind explicit approval.

## 2026-05-14

- Added discovery documentation entrypoint.
- Added agent and integration documentation.
- Added capability status labels.
- Added approval policy for AI-agent actions.
- Added API endpoint catalog and examples based on current Flask routes.
- Added documentation gap list for future API/MCP hardening.
