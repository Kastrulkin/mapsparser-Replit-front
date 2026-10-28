"""Resolve explicit outreach controls from tenant-scoped conversation history."""
import re

COMMANDS = ('повтори подготовку писем', 'повтори проверку сайтов', 'повтори исследование',
            'продолжи поиск', 'продолжи', 'приостанови', 'останови поиск', 'покажи этот поиск')
UUID = r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'


def resolve(message, history):
    text = str(message or '').strip().rstrip('.!').casefold()
    for command in COMMANDS:
        match = re.fullmatch(re.escape(command) + r'(?:\s+(?:задач[иу]\s+)?(' + UUID + r'))?', text)
        if not match:
            continue
        if match[1]:
            return {'task_id': match[1], 'command': command}
        # Caller supplies history from exactly this actor/business/conversation.
        # Do not inspect global last-task state or borrow another channel's task.
        for row in reversed(history or []):
            if row.get('role') not in {'operator', 'assistant'}:
                continue
            result = row.get('result_json') or {}
            task = result.get('task') or {}
            envelope = (result.get('approval') or {}).get('envelope') or {}
            task_id = result.get('search_task_id') or task.get('id') or envelope.get('task_id')
            if not task_id and str(result.get('capability') or '').startswith('partnerships.'):
                task_id = result.get('job_id')
            if task_id and re.fullmatch(UUID, str(task_id), re.I):
                return {'task_id': str(task_id), 'command': command}
        return None
    return None
