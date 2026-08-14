#!/usr/bin/env python3

import argparse
import json

from services.agent_template_pilot_plan import build_agent_template_pilot_plan


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a read-only, credit-bounded plan for the first-wave Compiled AI pilot."
    )
    parser.add_argument(
        "--business",
        action="append",
        default=[],
        metavar="KEY|UUID|NAME",
        help="Pilot business. UUID may be empty while identity verification is pending.",
    )
    parser.add_argument(
        "--template",
        action="append",
        default=[],
        help="First-wave template key. When omitted, beta keys are loaded from the catalog.",
    )
    parser.add_argument(
        "--funding",
        action="append",
        default=[],
        metavar="BUSINESS_KEY|OWNER_UUID|AVAILABLE_CREDITS",
        help="Read-only owner funding snapshot for one pilot business.",
    )
    args = parser.parse_args()
    businesses = [_parse_business(value) for value in args.business]
    businesses = _apply_funding(businesses, args.funding)
    template_keys = args.template or _beta_template_keys()
    plan = build_agent_template_pilot_plan(template_keys, businesses)
    print(json.dumps(plan, ensure_ascii=False, indent=2))
    return 0


def _beta_template_keys() -> list[str]:
    from services.agent_template_catalog import build_agent_template_catalog

    return [
        str(template["key"])
        for template in build_agent_template_catalog()
        if template.get("certification_status") == "beta"
    ]


def _parse_business(value: str) -> dict:
    parts = value.split("|", 2)
    if len(parts) != 3:
        raise argparse.ArgumentTypeError("--business must use KEY|UUID|NAME")
    return {
        "business_key": parts[0].strip(),
        "business_id": parts[1].strip(),
        "business_name": parts[2].strip(),
    }


def _apply_funding(businesses: list[dict], values: list[str]) -> list[dict]:
    funding = {}
    for value in values:
        parts = value.split("|", 2)
        if len(parts) != 3:
            raise argparse.ArgumentTypeError(
                "--funding must use BUSINESS_KEY|OWNER_UUID|AVAILABLE_CREDITS"
            )
        business_key = parts[0].strip()
        owner_id = parts[1].strip()
        try:
            available_credits = int(parts[2].strip())
        except ValueError:
            raise argparse.ArgumentTypeError("AVAILABLE_CREDITS must be an integer")
        if not business_key or not owner_id or available_credits < 0:
            raise argparse.ArgumentTypeError("--funding values must be non-empty and nonnegative")
        if business_key in funding:
            raise argparse.ArgumentTypeError("duplicate --funding business key")
        funding[business_key] = {
            "owner_id": owner_id,
            "available_credits": available_credits,
        }
    known_businesses = {item["business_key"] for item in businesses}
    unknown_keys = sorted(set(funding) - known_businesses)
    if unknown_keys:
        raise argparse.ArgumentTypeError(f"unknown --funding business key: {unknown_keys[0]}")
    return [{**item, **funding.get(item["business_key"], {})} for item in businesses]


if __name__ == "__main__":
    raise SystemExit(main())
