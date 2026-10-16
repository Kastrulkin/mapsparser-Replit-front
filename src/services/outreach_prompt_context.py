"""Project sales copy inputs without mutating stored evidence or draft contracts."""

from typing import Any


def sales_prompt_record(record: dict[str, Any], *, review: bool = False) -> dict[str, Any]:
    request = record.get("request") if review else record
    if not isinstance(request, dict) or request.get("motion") != "localos_sales":
        return record
    projected = dict(request)
    personalization = request.get("personalization") or {}
    sequence = request.get("sequence") or []
    angles = {item.get("angle") for item in sequence}
    selected_hypotheses = {
        personalization.get("signal_hypothesis_key"), personalization.get("signal_combo")
    } - {None, ""}
    selected_contract = personalization.get("approved_copy_contract")
    playbook = request.get("outreach_playbook")
    if isinstance(playbook, dict):
        guidance = {
            key: value for key, value in playbook.items()
            if key not in {"source_refs", "approved_message_examples"}
        }
        # Corpus citations support library compilation, not facts about this lead.
        # The selected retrieval sources/status stay in personalization.language_support.
        guidance["pain_library"] = [
            {key: value for key, value in pain.items() if key != "candidate_source_phrases"}
            for pain in playbook.get("pain_library") or [] if isinstance(pain, dict)
        ]
        guidance["pain_signal_hypotheses"] = [
            item for item in playbook.get("pain_signal_hypotheses") or []
            if isinstance(item, dict) and item.get("key") in selected_hypotheses
        ]
        guidance["approved_copy_contracts"] = [
            item for item in playbook.get("approved_copy_contracts") or []
            if isinstance(item, dict) and item.get("key") == selected_contract
        ]
        guidance["outreach_templates"] = [
            item for item in playbook.get("outreach_templates") or []
            if isinstance(item, dict) and angles.intersection(item.get("angles") or [])
        ]
        projected["outreach_playbook"] = guidance
    if not review:
        return projected
    # The final text is reviewed once in touches; draft text is not another message.
    projected["sequence"] = [
        {key: value for key, value in item.items()
         if key not in {"deterministic_draft", "deterministic_subject"}}
        for item in sequence
    ]
    touches = []
    for touch in record.get("touches") or []:
        item = dict(touch)
        for key, canonical in (
            ("observation", "observation"),
            ("relevance_bridge", "relevance_to_offer"),
            ("problem_hypothesis", "problem_hypothesis"),
        ):
            if key in item and item[key] == personalization.get(canonical):
                del item[key]
        touches.append(item)
    return {**record, "request": projected, "touches": touches}
