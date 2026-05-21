from services.operator_paid_action_adapter import (
    ADAPTER_STAGES,
    build_paid_action_adapter_plan,
    run_paid_action_adapter_stub,
    run_paid_action_internal_fake,
)


def test_adapter_plan_has_all_execution_stages_without_side_effects() -> None:
    plan = build_paid_action_adapter_plan(
        action_key="map_reviews_refresh",
        business_id="biz-1",
        user_id="user-1",
        estimated_credits=10,
    )

    assert plan["adapter_status"] == "planned"
    assert plan["runtime_mode"] == "internal_stub"
    assert plan["dry_run"] is True
    assert [stage["stage"] for stage in plan["stages"]] == list(ADAPTER_STAGES)
    assert plan["stages"][0]["details"]["estimated_credits"] == 10
    assert plan["stages"][1]["details"]["credit_reservation_required"] is True
    assert plan["stages"][2]["details"]["provider_call_allowed"] is False
    assert plan["side_effects"]["credit_reserved"] is False
    assert plan["side_effects"]["credit_charged"] is False
    assert plan["side_effects"]["external_calls_performed"] is False
    assert plan["side_effects"]["parsequeue_jobs_created"] is False


def test_adapter_stub_completes_dry_run_stages_only() -> None:
    plan = build_paid_action_adapter_plan(
        action_key="map_reviews_refresh",
        business_id="biz-1",
        user_id="user-1",
        estimated_credits=10,
        idempotency_key="idem-1",
    )

    result = run_paid_action_adapter_stub(plan)

    assert result["adapter_status"] == "dry_run_completed"
    assert result["idempotency_key"] == "idem-1"
    assert all(stage["dry_run"] is True for stage in result["stages"])
    assert all(stage["status"] == "dry_run_completed" for stage in result["stages"])
    assert result["side_effects"]["paid_actions_performed"] is False
    assert result["side_effects"]["ai_generation_performed"] is False


def test_adapter_internal_fake_completes_without_external_side_effects() -> None:
    plan = build_paid_action_adapter_plan(
        action_key="map_reviews_refresh",
        business_id="biz-1",
        user_id="user-1",
        estimated_credits=10,
        idempotency_key="idem-1",
    )

    result = run_paid_action_internal_fake(plan, actual_credits=1)

    assert result["adapter_status"] == "internal_fake_completed"
    assert result["runtime_mode"] == "internal_fake"
    assert result["dry_run"] is False
    assert result["actual_credits"] == 1
    assert [stage["status"] for stage in result["stages"]] == [
        "internal_fake_estimate_confirmed",
        "reserved_before_internal_fake",
        "internal_fake_completed",
        "ready_for_credit_finalization",
    ]
    assert result["side_effects"]["internal_fake_execution_performed"] is True
    assert result["side_effects"]["external_calls_performed"] is False
    assert result["side_effects"]["external_writes_performed"] is False
    assert result["side_effects"]["parsequeue_jobs_created"] is False
    assert result["side_effects"]["ai_generation_performed"] is False


def test_adapter_plan_rejects_unknown_action_without_side_effects() -> None:
    plan = build_paid_action_adapter_plan(
        action_key="unknown",
        business_id="biz-1",
        user_id="user-1",
        estimated_credits=10,
    )

    assert plan["adapter_status"] == "unsupported_action"
    assert all(stage["status"] == "skipped" for stage in plan["stages"])
    assert all(stage["details"]["reason"] == "unsupported_action" for stage in plan["stages"])
    assert plan["side_effects"]["external_writes_performed"] is False
