"""Telegram presentation of canonical outreach results, never a draft generator."""

def is_outreach_result(result):
    return (isinstance(result.get('task'), dict) and 'report' in result['task'] and 'presentation' in result['task']) or any(
        isinstance(draft, dict) and draft.get('campaign_id')
        for draft in result.get('drafts') or [])


def summary(result):
    task = result.get('task') or {}
    report = task.get('report') or {}
    presentation = task.get('presentation') or {}
    title = task.get('display_name') or 'Аутрич'
    lines = [title, presentation.get('label') or 'Результат сохранён', '',
        f"Найдено: {report.get('found', 0)} · Подходят: {report.get('eligible', 0)}/{report.get('target') or '—'}",
        f"Писем: {report.get('prepared', 0)}"]
    credits = report.get('credits_charged')
    lines.append('Списано: ' + (f'{credits} кр.' if credits is not None else 'пока неизвестно'))
    reason = presentation.get('reason')
    if reason:
        lines.extend(['', str(reason)])
    action = presentation.get('next_action') or {}
    if action.get('label'):
        lines.extend(['', 'Далее: ' + str(action['label'])])
    if report.get('prepared'):
        lines.append('Чтобы прочитать тексты здесь, напишите «Покажи письма».')
    return '\n'.join(lines)


def messages(result):
    """Requested letters are separate cards; ordinary status remains a short card."""
    cards = [summary(result)]
    drafts = result.get('drafts') or []
    statuses = {str(item.get('campaign_id')): item.get('status')
        for item in ((result.get('task') or {}).get('state', {}).get('campaign_results') or {}).values()}
    labels = {'draft': 'Черновик', 'ready': 'Готово к просмотру', 'needs_revision': 'Нужна правка',
              'sent': 'Отправлено', 'queued': 'В очереди', 'failed': 'Ошибка'}
    for number, draft in enumerate(drafts, 1):
        if not isinstance(draft, dict) or not draft.get('campaign_id'):
            continue
        status = statuses.get(str(draft['campaign_id'])) or draft.get('status')
        header = f"Письмо {number}/{len(drafts)} · {labels.get(status, 'Требует проверки')}"
        parts = [header, '', 'Кому: ' + str(draft.get('recipient') or 'не выбран'),
                 'От: ' + str(draft.get('sender') or 'не выбран'), '',
                 'Тема: ' + str(draft.get('subject') or 'не указана'), '',
                 str(draft.get('generated_text') or 'Текст ещё не подготовлен')]
        source = (draft.get('message_brief_json') or {}).get('source_url')
        if source:
            parts.extend(['', 'Основание персонализации:', str(source)])
        parts.extend(['', 'Отправка — после отдельного подтверждения.'])
        cards.append('\n'.join(parts))
    return cards
