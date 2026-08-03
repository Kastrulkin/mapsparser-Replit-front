from scripts import configure_localos_beauty_outreach_profile


def test_beauty_profile_uses_only_operator_approved_founder_facts() -> None:
    assert "десять лет предпринимательства" in configure_localos_beauty_outreach_profile.COMPETENCE_STORY
    assert "240 точках малого бизнеса" in configure_localos_beauty_outreach_profile.PROOF_POINT["fact"]
    assert configure_localos_beauty_outreach_profile.PROOF_POINT["status"] == "approved"
    assert configure_localos_beauty_outreach_profile.PAIN_FRAMEWORK["rule"].startswith(
        "Это язык рынка, а не факт о конкретном получателе"
    )
    assert len(configure_localos_beauty_outreach_profile.PAIN_FRAMEWORK["themes"]) == 10


def test_profile_voice_examples_avoid_ai_typography() -> None:
    texts = " ".join(
        item["text"] for item in configure_localos_beauty_outreach_profile.VOICE_EXAMPLES
    )
    assert "—" not in texts
    assert "«" not in texts
    assert "»" not in texts
