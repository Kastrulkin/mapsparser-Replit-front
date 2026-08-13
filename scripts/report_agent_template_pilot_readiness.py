#!/usr/bin/env python3

import argparse
import json

from database_manager import DatabaseManager
from services.agent_template_catalog import build_agent_template_catalog
from services.agent_template_pilot_readiness import build_agent_template_pilot_readiness


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a read-only Compiled AI pilot readiness report from LocalOS run history.")
    parser.add_argument("--template", action="append", default=[], help="Limit the report to one or more template keys.")
    args = parser.parse_args()
    beta_keys = [
        str(template["key"])
        for template in build_agent_template_catalog()
        if template.get("certification_status") == "beta"
    ]
    selected = [key for key in beta_keys if not args.template or key in set(args.template)]
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        cursor.execute(
            """
            SELECT blueprint.metadata_json->>'template_key' template_key,
                   blueprint.metadata_json->>'template_version' template_version,
                   run.id run_id,
                   blueprint.id blueprint_id,
                   run.business_id,
                   run.status,
                   run.idempotency_key,
                   run.input_json,
                   run.output_json,
                   version.trigger,
                   TO_CHAR(run.completed_at AT TIME ZONE 'UTC', 'YYYY-MM-DD') completed_utc_date,
                   evaluation->>'rating' evaluation_rating
            FROM agent_runs run
            JOIN agent_blueprints blueprint ON blueprint.id = run.blueprint_id
            JOIN agent_blueprint_versions version ON version.id = run.blueprint_version_id
            LEFT JOIN LATERAL (
                SELECT item evaluation
                FROM jsonb_array_elements(
                    CASE
                        WHEN jsonb_typeof(blueprint.metadata_json->'run_evaluations') = 'array'
                        THEN blueprint.metadata_json->'run_evaluations'
                        ELSE '[]'::jsonb
                    END
                ) item
                WHERE item->>'kind' = 'run_evaluation'
                  AND item->>'run_id' = run.id
                ORDER BY item->>'created_at' DESC
                LIMIT 1
            ) feedback ON TRUE
            WHERE blueprint.metadata_json->>'template_key' = ANY(%s)
            ORDER BY run.created_at ASC
            """,
            (selected,),
        )
        rows = [dict(row) for row in (cursor.fetchall() or [])]
    finally:
        db.close()
    print(json.dumps(build_agent_template_pilot_readiness(rows, selected), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
