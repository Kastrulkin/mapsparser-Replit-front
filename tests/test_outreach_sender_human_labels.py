from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_sender_options_never_expose_internal_ids_and_show_concrete_identity():
    source = (ROOT / "frontend/src/components/prospecting/AdminLeadRegistry.tsx").read_text()

    assert "outreachSenderDisplayLabel(account)" in source
    assert "account.display_name || account.sender_identity || account.id" not in source
    assert "Подключённый Telegram-аккаунт" in source
    assert "providerSenderIdentityPattern" in source


def test_sender_account_api_enriches_telegram_binding_with_human_identity():
    source = (ROOT / "src/services/outreach_sender_service.py").read_text()
    list_start = source.index("def list_sender_accounts(")
    list_end = source.index("\n\ndef load_sender_account", list_start)
    list_block = source[list_start:list_end]

    assert "externalbusinessaccounts" in list_block
    assert "external_account.external_id" in list_block
    assert "external_account.display_name" in list_block
    assert "COALESCE" in list_block


def test_current_sender_selection_clears_saved_campaign_sender_blocker():
    source = (ROOT / "frontend/src/components/prospecting/AdminLeadRegistry.tsx").read_text()
    blocker_start = source.index("const savedCampaignChannelBlockers")
    blocker_end = source.index("\n  const savedCampaignNeedsChannelSetup", blocker_start)
    blocker_block = source[blocker_start:blocker_end]

    assert "if (!selectedSenderId)" in blocker_block
    assert "if (!touch.sender_account_id || channelStatus === 'sender_selection_required')" not in blocker_block
