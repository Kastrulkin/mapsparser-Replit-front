# Lead journey: product UX architecture

## Product job

LocalOS must let an operator choose the client's current growth problem, send one
personal link, and know exactly which useful result the client will see next.
The client follows one recommended path without losing access to the rest of the
product or having to understand the product's internal structure.

## Four growth paths

| Client problem | Public promise | Authenticated destination | First useful result |
| --- | --- | --- | --- |
| Influencers | Show a relevant local author and a realistic collaboration mechanic | `/dashboard/promotion/influencers` | Prepared offer and a filtered author list |
| Partnerships | Show a relevant nearby business and a mutually useful mechanic | `/dashboard/promotion/partnerships` | Prepared proposal and a filtered partner list |
| Maps | Show the most important listing problem and why it matters | `/dashboard/card` or the focused maps section in Progress | One concrete fix and the weekly plan |
| Content | Show a relevant topic or draft based on the business, season, services, reviews, and channels | `/dashboard/content` | One prepared draft and the next content-plan step |

The chosen path is stored as `selected_flow` on the journey. A public journey
must not force the client to choose again when the operator already selected the
problem. Other paths remain visible later as secondary growth opportunities.

## Operator flow

The admin entry point is **Create client path**, not a generic workflow builder.

1. Select a lead or business.
2. Select one problem: influencers, partnerships, maps, or content.
3. Select or confirm the example shown publicly: author, partner, listing issue,
   or content topic/draft.
4. Preview the exact client sequence and access boundaries.
5. Create the personal link and copy the prepared first message.
6. Track the current step, last activity, blocker, and next operator action.

The preview must show both unauthenticated and authenticated states. The link is
versioned and resolves only to allowlisted LocalOS destinations; an arbitrary
redirect URL is never accepted from a public token.

## Client flow

### Before registration

The public `/start/:token` surface is a focused continuation of the message:

- the selected problem and one concrete example;
- why the example fits this business;
- a partial result that demonstrates value without exposing private contacts,
  complete outreach text, or paid output;
- one dominant action;
- a quiet secondary section, **What else LocalOS can improve**, with the other
  paths shown as previews.

There is no full dashboard sidebar on this surface.

### Registration boundary

Registration appears only when the client asks to open the complete result or
continue the work. The journey token and selected flow survive email
verification and login.

After claim, the resolver opens the chosen workspace and focuses the journey
action. It must not send the client to the generic dashboard or require another
search through navigation.

Target contract:

`/start/:token -> login/registration when needed -> claim -> selected workspace?action=:id`

### After registration

The chosen path remains primary, but the client can open any other available
area. The product never behaves as a closed wizard that traps the user in one
flow. Returning to Today restores the canonical next action.

## Content path

The content path uses the existing content domain and `/dashboard/content`.
It does not introduce a second content-plan system.

Recommended sequence:

1. Show one relevant topic or short draft publicly.
2. Ask one question only when required: the immediate goal or publication
   channel. This may be answered in the operator's message thread.
3. Show the partial result and explain what opens next.
4. Register or sign in.
5. Open the content workspace directly with the prepared draft in focus.
6. Let the client edit and approve it.
7. Save it to the calendar or hand it to the existing supervised publication
   flow.
8. Record the real result and propose the next content cycle.

Publishing remains manual or approval-gated according to the provider contract.

## Product information architecture

The permanent sidebar is not the primary product model. The first layer is
organized around user outcomes:

### Primary navigation

- **Today** — the one action that needs attention now and a short queue.
- **Growth paths** — Maps, Content, Influencers, and Partnerships, each with a
  lifecycle status and next result.
- **Results** — verified progress, completed cycles, and business outcomes.
- **More** — finance, agents, chats, business profile, integrations, access, and
  settings.

On desktop this may remain a compact sidebar. On mobile it becomes a bottom
navigation with More as the secondary directory. The navigation labels and
order must remain the same across web and Mini App.

### Local navigation inside a path

Each growth path owns a small, outcome-based secondary navigation:

- Influencers: `Selection -> Offers -> Conversations -> Results`.
- Partnerships: `Candidates -> Offers -> Launches -> Results`.
- Maps: `What to fix -> This week's plan -> Verification -> Result`.
- Content: `Plan -> Drafts -> Calendar -> Results`.

Only the stages needed for the current job appear in the first layer. Advanced
filters, raw history, integrations, and technical diagnostics stay in the
secondary layer.

## Access and progressive disclosure

Access is evaluated per block, not only per route.

| Access state | What stays readable | What is restricted | Primary action |
| --- | --- | --- | --- |
| Public preview | Title, reason, safe example, partial result | Contacts, full copy, operational controls | Continue or register |
| Registration required | Value explanation and representative preview | Saved workspace and personalized continuation | Create account |
| Payment required | Existing result, example output, expected benefit | Paid generation, repeated work, premium analytics | Choose plan |
| Setup required | Why the block matters and current blocker | Actions that need provider data or connection | Connect source |
| Approval required | Complete draft and consequences | External send, publish, payment, destructive or bulk operation | Review and approve |
| Available | Current status and next result | Nothing beyond existing safety boundaries | Perform next action |

Locked areas may use a visually softened or blurred representative preview, but
the title, value, unlock condition, and CTA must remain sharp and readable.
Blur is not used to hide the reason for a lock, and disabled controls are not
focusable. A lock opens a focused explanation or drawer instead of a dead end.

## Growth paths screen

The screen job is: **understand where growth is currently blocked and open the
best next action**.

Each path is one row or bounded section with:

- lifecycle status: not started, preview available, in progress, waiting,
  blocked, result ready, or completed;
- one-sentence opportunity;
- latest verified result or missing input;
- one dominant CTA;
- the access condition when the next block is locked.

The active journey is first. Due replies and blocked work outrank discovery.
The remaining paths are visible below without competing with the active CTA.

## Required state integrity

- The operator-selected flow is set when the link is created, not only after a
  public preview click.
- The public response exposes only allowlisted fields and filters to the chosen
  path for the main presentation.
- The journey keeps an allowlisted destination and focused entity/action.
- Login and email verification resolve the saved journey before applying a
  generic dashboard redirect.
- Web and Mini App render the same action contract and allowed commands.
- Reopening the link returns to the current action rather than restarting the
  scenario.
- Block access is derived from authentication, entitlement, setup, and approval
  state; CSS blur is never the authorization mechanism.

## Implementation implications

1. Add `content` to journey flow validation, database constraints, analytics,
   feature flags, API types, and the shared web/Mini App action contract.
2. Extend journey creation so admin must select one flow and one safe preview
   entity before generating the link.
3. Filter the primary public experience to `selected_flow`; keep other paths as
   explicit secondary previews only.
4. Add a post-auth journey resolver that claims the token and navigates to the
   allowlisted workspace with the focused action.
5. Replace route-wide paid overlays where mixed preview and paid blocks are
   useful with block-level access states.
6. Reorganize the flat dashboard menu into Today, Growth paths, Results, and
   More, while preserving direct URLs and backward-compatible routes.
7. Add an admin client preview for public, registered-free, and paid states.

## Acceptance scenarios

### Influencer link

The operator chooses Influencers, previews the sequence, copies the link, and
sends it. A new client sees the selected author, registers, confirms email, and
lands on the prepared offer and author list without using global navigation.

### Content link

The operator chooses Content and a prepared topic. A new client sees a partial
draft, registers, and lands on that draft in Content. Paid generation is visibly
explained and unlocked only by entitlement; publication still requires review.

### Cross-area exploration

A client in the Influencers path opens Growth paths, sees Content and Maps, and
can open any available block. A paid block shows its value and unlock condition
without losing the current influencer action. Today still restores the correct
next influencer step.

### Access safety

A guest cannot obtain a full message, private contact, paid result, or arbitrary
redirect by changing URL parameters. A blurred block cannot be unlocked by
client-side CSS changes because backend authorization remains authoritative.

## Deliberately deferred

- a user-configurable workflow builder;
- autonomous external publication or outreach;
- a full visual redesign before the path, access, and redirect contracts are
  implemented and tested;
- removal of existing direct routes during the navigation transition.
