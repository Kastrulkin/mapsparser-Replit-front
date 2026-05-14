# Pricing and Billing

Status: `gap`

This repository contains payment and subscription-related code, but this documentation does not define a current public pricing model.

Do not infer pricing, included limits, countries, or guarantees from code alone.

## What Can Be Documented Safely

- LocalOS has user accounts, business accounts, and subscription/payment-related modules.
- Some billing status and tariff operations exist in the product.
- Agent actions should eventually map to entitlements, limits, and audit/billing events.

## What Is Not Yet a Public Contract

- public tariff names and exact prices;
- API quotas;
- agent-run pricing;
- country-specific taxes and payment methods;
- refund rules.

## Required Before Public Agent Billing

- tariff catalog;
- entitlement matrix;
- API usage limits;
- payment approval policy;
- billing event ledger for agent actions;
- user-visible usage report.
