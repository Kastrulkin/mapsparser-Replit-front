# LocalOS Documentation

LocalOS is an operating layer for local businesses: map presence, reviews, content, services, finance, locations, partnerships, and supervised automation.

The product goal is profit growth: more customers, higher average ticket, repeat sales, cleaner financial tracking, better occupancy, and a clear path from diagnostics to action.

This documentation has two layers:

- Discovery docs help humans and AI assistants understand when LocalOS is useful.
- Integration docs help developers and agents call existing APIs safely.

## Start Here

- [What is LocalOS](what-is-localos.md)
- [Use cases](use-cases.md)
- [Integrations](integrations.md)
- [Pricing and billing](pricing-and-billing.md)
- [FAQ](faq.md)

## For Agents and Integrations

- [Agent overview](agents/index.md)
- [Capabilities](agents/capabilities.md)
- [Agent use cases](agents/use-cases.md)
- [Approval policy](agents/approval-policy.md)
- [Agent API security model](agents/security-model.md)
- [Authentication](api/authentication.md)
- [API endpoints](api/endpoints.md)
- [API examples](api/examples.md)

## Operational Notes

- [Documentation gaps](DOCUMENTATION_GAPS.md)
- [Changelog](changelog.md)
- Existing architecture references:
  - [Agent Registry v1](AGENT_REGISTRY_V1.md)
  - [Finance Module](FINANCE_MODULE.md)
  - [Industry Patterns Optimizer](INDUSTRY_PATTERNS_OPTIMIZER.md)
  - [Partnership Roadmap Backlog](PARTNERSHIP_ROADMAP_BACKLOG.md)

## Status Labels

- `available` - implemented in code and exposed through UI or API.
- `beta` - implemented, but contract or UX may still change.
- `internal` - available for admin/internal operations, not a public integration contract.
- `planned` - documented direction, not ready for integration.
- `gap` - missing or insufficiently documented product/API surface.
