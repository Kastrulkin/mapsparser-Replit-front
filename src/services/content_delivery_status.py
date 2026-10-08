"""Read-only projection of the existing bot receipts; never publication proof."""
import json


def delivery_status(metadata):
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except (ValueError, TypeError):
            metadata = {}
    handoff = metadata.get('staff_handoff') if isinstance(metadata, dict) else {}
    deliveries = handoff.get('telegram_deliveries') if isinstance(handoff, dict) else {}
    receipts = [value for value in (deliveries or {}).values() if isinstance(value, dict)] if isinstance(deliveries, dict) else []
    states = [part.get('status') for receipt in receipts
              for part in (receipt.get('parts') or {}).values()
              if isinstance(receipt.get('parts'), dict) and isinstance(part, dict)]
    if any(state in {'attempting', 'uncertain'} for state in states):
        return 'needs_reconciliation'
    if receipts and all(receipt.get('sent_at') for receipt in receipts):
        return 'delivered'
    if 'sent' in states or any(receipt.get('sent_at') for receipt in receipts):
        return 'partially_delivered'
    if 'not_sent' in states:
        return 'failed'
    return 'not_sent'
