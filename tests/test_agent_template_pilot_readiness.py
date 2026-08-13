def test_pilot_readiness_counts_only_safe_previews_and_unique_useful_businesses():
    from services.agent_template_pilot_readiness import build_agent_template_pilot_readiness

    rows = []
    for index in range(10):
        rows.append(
            {
                "template_key": "daily_owner_digest",
                "run_id": f"preview-{index}",
                "business_id": "pilot-1",
                "status": "completed",
                "idempotency_key": f"preview-key-{index}",
                "input_json": {"preview_mode": True},
                "output_json": {"external_dispatch_performed": False, "provider_write_performed": False},
            }
        )
    for index, business_id in enumerate(("pilot-1", "pilot-2", "pilot-3", "pilot-1", "pilot-2")):
        rows.append(
            {
                "template_key": "daily_owner_digest",
                "run_id": f"production-{index}",
                "business_id": business_id,
                "status": "completed",
                "idempotency_key": f"production-key-{index}",
                "input_json": {"preview_mode": False},
                "output_json": {},
                "evaluation_rating": "useful",
                "trigger": "schedule.daily",
                "completed_utc_date": f"2026-08-{index + 1:02d}",
            }
        )

    report = build_agent_template_pilot_readiness(rows, ["daily_owner_digest"])
    template = report["templates"][0]

    assert template["safe_preview_runs"] == 10
    assert template["successful_production_runs"] == 5
    assert template["useful_pilot_businesses"] == 3
    assert template["meets_collection_minimums"] is True
    assert report["preview_violations"] == 0


def test_pilot_readiness_surfaces_preview_writes_and_duplicate_keys():
    from services.agent_template_pilot_readiness import build_agent_template_pilot_readiness

    rows = [
        {
            "template_key": "negative_review_reply",
            "run_id": "preview-unsafe",
            "business_id": "pilot-1",
            "status": "completed",
            "idempotency_key": "duplicate",
            "input_json": {"preview_mode": True},
            "output_json": {"external_dispatch_performed": True},
        },
        {
            "template_key": "negative_review_reply",
            "run_id": "production-1",
            "business_id": "pilot-1",
            "status": "completed",
            "idempotency_key": "duplicate",
            "input_json": {"preview_mode": False},
            "output_json": {},
        },
    ]

    report = build_agent_template_pilot_readiness(rows, ["negative_review_reply"])
    template = report["templates"][0]

    assert template["preview_violation_run_ids"] == ["preview-unsafe"]
    assert template["duplicate_idempotency_keys"] == ["pilot-1::duplicate"]
    assert template["meets_collection_minimums"] is False
