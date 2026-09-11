"""Resolve a continuation against saved business data before generating any plan."""
import re
from datetime import date, timedelta


class PlanClarification(ValueError):
    pass


def continuation_requested(message):
    text = message.lower().replace('-', ' ')
    return bool(re.search(r'следующ\w*|продолж\w*|заканчива\w*|законч\w*|истека\w*', text))


def resolve_continuation(cursor, business_id, message):
    cursor.execute("""SELECT p.id, p.period_end, p.generated_plan_json,
        (SELECT MAX(i.scheduled_for) FROM contentplanitems i WHERE i.plan_id=p.id AND i.business_id=%s) last_date
        FROM contentplans p WHERE p.business_id=%s ORDER BY p.created_at DESC,p.id DESC LIMIT 1""", (business_id,business_id))
    plan = cursor.fetchone()
    if not plan:
        raise PlanClarification('Не нашёл предыдущий контент-план. Укажите дату начала нового плана.')
    last = plan.get('last_date') or plan.get('period_end')
    if not last:
        raise PlanClarification('В предыдущем плане нет даты окончания. Укажите дату начала нового плана.')
    end = date.fromisoformat(str(last)[:10])
    # A day without month refers to the saved plan's actual final scheduled date.
    months = ('января','февраля','марта','апреля','мая','июня','июля','августа','сентября','октября','ноября','декабря')
    date_pattern = r'(\d{1,2})\s*(?:[-‐‑–]?\s*го)?(?:\s*('+'|'.join(months)+r'))?(?:\s+(20\d{2}))?'
    ending = r'(?:заканчива\w*|законч\w*|истека\w*)'
    match = re.search(r'\b'+date_pattern+r'\s*(?:числа\s*)?'+ending, message.lower())
    if not match:
        match = re.search(ending+r'\s+'+date_pattern, message.lower())
    if match:
        try:
            stated = date(int(match.group(3) or end.year), months.index(match.group(2))+1 if match.group(2) else end.month, int(match.group(1)))
        except ValueError:
            raise PlanClarification('В команде указана некорректная дата окончания. Уточните её.')
        if stated != end:
            raise PlanClarification(f'Последняя запись текущего плана датирована {end.isoformat()}, а в команде указан другой день. Уточните дату начала нового плана.')
    cursor.execute('SELECT theme FROM contentplanitems WHERE plan_id=%s AND business_id=%s ORDER BY scheduled_for,id', (plan['id'],business_id))
    themes = [str(row['theme']) for row in cursor.fetchall() if row.get('theme')]
    saved = plan.get('generated_plan_json') or {}
    channels = saved.get('selected_channels') or (saved.get('meta') or {}).get('selected_channels') or []
    return {'previous_plan_id': str(plan['id']), 'period_start': end+timedelta(days=1), 'excluded_themes': themes, 'channels': channels}
