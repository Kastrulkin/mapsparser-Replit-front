from scripts.rewrite_localos_beauty_outreach import _available_sequence


def test_missing_max_skips_channel_but_keeps_case_touch():
    sequence = _available_sequence(
        {
            "email": {"status": "ready"},
            "telegram": {"status": "ready"},
            "max": {"status": "recipient_missing"},
            "vk_manual": {"status": "manual"},
            "phone": {"status": "manual"},
        },
        workstream_id="workstream-1",
        lead_name="Салон",
    )

    assert [item["channel"] for item in sequence] == [
        "email", "telegram", "vk_manual", "phone", "email",
    ]
    assert [item["angle"] for item in sequence] == [
        "signal", "content_operations", "average_ticket", "reviews_service", "integrated_system",
    ]


def test_all_reviewed_channels_keep_full_six_touch_sequence():
    sequence = _available_sequence(
        {
            "email": {"status": "ready"},
            "telegram": {"status": "ready"},
            "max": {"status": "manual"},
            "vk_manual": {"status": "manual"},
            "phone": {"status": "manual"},
        },
        workstream_id="workstream-1",
        lead_name="Салон",
    )

    assert [item["channel"] for item in sequence] == [
        "email", "telegram", "max", "vk_manual", "phone", "email",
    ]
    assert [item["angle"] for item in sequence] == [
        "signal", "content_operations", "average_ticket", "reviews_service",
        "integrated_system", "founder_origin",
    ]
