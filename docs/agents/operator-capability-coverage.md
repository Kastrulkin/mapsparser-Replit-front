# Operator capability coverage

Source of truth: `src/services/operator_core.py`. Web and Telegram call the same
`route_operator_message` entrypoint. This manifest describes the user-visible
coverage boundary; it must not be used to imply unsupported provider writes.

| Domain | Capability | Status | Execution boundary | Result URL |
| --- | --- | --- | --- | --- |
| Operator | `operator.help` | `available` | Operator Core | `/dashboard/operator` |
| Maps | `maps.refresh` | `available` | Existing refresh handler and credit policy | `/dashboard/card` |
| Reviews | `reviews.read` | `available` | Existing read handler | `/dashboard/card?tab=reviews&review_filter=needs_reply` |
| Reviews | `reviews.reply.draft` | `draft_only` | Existing paid draft handler | `/dashboard/card?tab=reviews&review_filter=needs_reply` |
| Reviews | `reviews.manual.add` | `available` | Existing narrow internal-write handler | `/dashboard/card?tab=reviews&review_filter=needs_reply` |
| Reviews | `reviews.publish_external` | `gap` | No provider write; manual handoff only | `/dashboard/card?tab=reviews` |
| Content | `news.generate` | `draft_only` | Existing paid draft handler | `/dashboard/content` |
| Content | `social_post.generate` | `draft_only` | Existing paid draft handler | `/dashboard/content` |
| Content | `content_plan.generate` | `available` | Existing content-plan service | `/dashboard/content` |
| Content | `content.publish_external` | `gap` | No generic provider write; manual handoff only | `/dashboard/content` |
| Services | `services.read` | `available` | Tenant-scoped active-service read in dashboard order | `/dashboard/card?tab=services` |
| Services | `services.price.update` | `available` | Tenant-scoped narrow internal write | `/dashboard/card?tab=services` |
| Services | `services.optimize` | `draft_only` | Existing paid preview handler | `/dashboard/card?tab=services` |
| Services | `services.apply` | `approval_required` | Stored action envelope and idempotent confirm | `/dashboard/card?tab=services` |
| Bookings | `appointments.manage` | `available` for reads | `ActionOrchestrator` and canonical `appointments.read` handler | `/dashboard/bookings` |
| Finance | `finance.manage` | `request_only` | Manual section until typed proposal/apply UX is connected | `/dashboard/finance` |
| Communications | `communications.manage` | `request_only` | Draft/request boundary; external send needs approval | `/dashboard/chats` |
| Partnerships | `partnerships.manage` | `request_only` | Draft/request boundary; outreach send needs approval | `/dashboard/partnerships` |
| Average ticket | `average_ticket.manage` | `manual` | Manual section | `/dashboard/average-ticket` |
| Network | `network.manage` | `manual` | Manual section | `/dashboard/network` |
| Agents | `agents.manage` | `manual` | Manual section | `/dashboard/agents` |
| Settings | `settings.manage` | `manual` | Manual section | `/dashboard/settings` |
| Support | `support.manage` | `manual` | Manual section with support-safe details | `/dashboard/settings/integrations` |

## Status contract

- `available`: Operator performs the supported read or one narrow internal action.
- `draft_only`: Operator creates a LocalOS draft; nothing is published externally.
- `request_only`: the typed backend boundary exists, but the complete conversational
  input/preview/confirmation flow is not yet connected.
- `approval_required`: Operator stores a preview/action envelope and executes only
  through an explicit confirm endpoint or Telegram callback.
- `manual`: Operator explains the manual step and links to the correct section.
- `gap`: LocalOS has no safe execution path and must not claim completion.

Publish, send, payment, delete, bulk mutation, access changes and provider writes
always require a dedicated typed handler and explicit approval. A free-form SQL or
generic HTTP tool is intentionally not part of Operator Core.
