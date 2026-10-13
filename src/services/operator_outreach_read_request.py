"""Recognize explicit read requests before an AI can answer from stale history."""
import re


def send_review_request(message):
    text = str(message or '').strip().casefold()
    if not re.match(r'^(?:для\s+[^.!?\n]{1,100}?\s+)?(?:подготовь|обнови|покажи)\s+(?:единый\s+)?(?:предварительный\s+)?просмотр\s+отправки\b', text):
        return None
    task_ids = re.findall(r'\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b', text)
    return {'operation': 'review_send', 'task_ids': sorted(set(task_ids))}


def letter_request(message):
    text = str(message or '').strip().casefold()
    if not re.match(r'^(?:для\s+[^.!?\n]{1,100}?\s+)?(?:покажи|показать|покажите)\s+(?:полные\s+)?(?:тексты\s+)?(?:писем|письма|черновики)\b', text):
        return None
    task_ids = re.findall(r'\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b', text)
    if len(set(task_ids)) > 1:
        return {'operation': 'letters', 'ambiguous': True}
    return {'operation': 'letters', 'task_id': task_ids[0] if task_ids else None}
