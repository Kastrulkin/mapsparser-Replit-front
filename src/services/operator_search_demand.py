"""Stored Wordstat evidence for chat and service previews; no provider calls."""
import re
from datetime import date, datetime
from core.seo_keywords import collect_ranked_keywords
from core.service_safe_wordstat import detect_service_keyword_category, filter_wordstat_candidates, normalize_query_text
from services.operator_query import query_business_ids, _row


def relevant_candidates(items, services):
    allowed = {}
    for service in services:
        category = detect_service_keyword_category(service)
        filtered = filter_wordstat_candidates(items, category, limit=50)['allowed']
        if category == 'grooming':
            filtered = [item for item in filtered if not re.search(r'\b(?:паста|корм|брит|таблетки|витамины|купить|доставка)\b|вывода шерсти', normalize_query_text(item.get('keyword')))]
        if category == 'generic':
            terms = [word for word in normalize_query_text(str(service.get('name') or '')).split()
                     if len(word) >= 4 and word not in {'услуга', 'услуги', 'маска'}]
            filtered = [item for item in filtered if any(term in normalize_query_text(item.get('keyword')) for term in terms)]
        for item in filtered:
            allowed[str(item.get('keyword') or '').casefold()] = item
    return sorted(allowed.values(), key=lambda item: item.get('views') or 0, reverse=True)


def stored_demand(cursor, business_id, user_id, services=None, limit=20):
    targets = query_business_ids(cursor, business_id, user_id)
    collected = []
    for target in targets:
        cursor.execute('SELECT name, city FROM businesses WHERE id=%s', (target,))
        business = _row(cursor, cursor.fetchone())
        target_services = services
        if target_services is None:
            cursor.execute('SELECT name, description, category FROM userservices WHERE business_id=%s AND COALESCE(is_active,TRUE)=TRUE LIMIT 200', (target,))
            target_services = [_row(cursor, row) for row in cursor.fetchall()]
        payload = collect_ranked_keywords(cursor, business_id=target, user_id=user_id,
                                          limit=600, fallback_global_when_empty_terms=False)
        relevant = relevant_candidates(payload.get('items') or [], target_services)
        for item in relevant[:limit]:
            collected.append({**item, 'business_id': target, 'business_name': business.get('name'),
                              'business_city': business.get('city'),
                              'updated_at': item.get('updated_at').isoformat() if isinstance(item.get('updated_at'), (date, datetime)) else item.get('updated_at')})
    # Keep each location's provenance; never imply these are newly fetched trends.
    collected.sort(key=lambda item: item.get('views') or 0, reverse=True)
    return {'items': collected[:limit], 'period_comparison_available': False,
            'freshness': 'stored_snapshot', 'external_calls_performed': False}


def read_demand(cursor, business_id, user_id, arguments):
    limit = arguments.get('limit', 20)
    if not isinstance(limit, int) or isinstance(limit, bool):
        limit = 20
    evidence = stored_demand(cursor, business_id, user_id, limit=max(1, min(limit, 50)))
    lines = ['Сохранённые релевантные запросы Wordstat:']
    for item in evidence['items']:
        lines.append(f"• {item['keyword']} — {item.get('views') or 0} показов/месяц; обновлено {str(item.get('updated_at') or 'неизвестно')[:10]}; {item.get('business_name')}; город бизнеса: {item.get('business_city') or 'не указан'}.")
    if not evidence['items']:
        lines.append('Релевантных сохранённых запросов для доступных услуг не найдено.')
    lines.append('Это сохранённый снимок. Новизна и рост не подтверждены: история периодов недоступна. Город бизнеса не подтверждает регион частотности источника. Нерелевантные запросы исключены из предложений.')
    return {'status': 'completed', 'chat_response': '\n'.join(lines), **evidence,
            'external_writes_performed': False, 'result_ref': {'href': '/dashboard/card?tab=keywords', 'label': 'Открыть Wordstat'}}


def tools(cursor, business_id, user_id):
    return [{'name': 'seo.search_demand', 'capability': 'services.read', 'title': 'Поисковые запросы Wordstat',
             'description': 'Читает сохранённые релевантные запросы Wordstat, частотность, дату и доступные точки. Не обновляет источник. Новизна, рост и регион частотности не подтверждены без истории и метаданных источника.',
             'input_schema': {'type': 'object', 'properties': {'limit': {'type': 'integer', 'minimum': 1, 'maximum': 50}}},
             'risk_class': 'read_only', 'approval_required': False,
             'execute': lambda arguments: read_demand(cursor, business_id, user_id, arguments)}]


def matches(message):
    return bool(re.search(r'wordstat|вордстат|поисков.{0,15}запрос|seo|сео', str(message), re.I))


def review_refresh_preview(cursor, business_id, user_id):
    from services.operator_map_refresh import build_operator_map_refresh_plan
    from services.operator_map_refresh import DEFAULT_MAP_REFRESH_ESTIMATED_CREDITS
    targets = query_business_ids(cursor, business_id, user_id)
    plans = [build_operator_map_refresh_plan(cursor, business_id=target, user_id=user_id) for target in targets]
    lines = ['Обновление пока не запущено. Возможность обновления по доступным точкам:']
    for plan in plans:
        reason = ', '.join(plan.get('blocked_reasons') or [])
        lines.append(f"• {plan['business_id']}: {plan.get('url') or 'ссылка карты не задана'}; " + (f"недоступно ({reason})" if reason else f"оценка до {DEFAULT_MAP_REFRESH_ESTIMATED_CREDITS} кредитов за карточку"))
    lines.append('Фактическая стоимость зависит от объёма данных. Для запуска выберите конкретную доступную точку и подтвердите платное обновление. Публикации в карты не выполняются.')
    return {'status': 'completed', 'chat_response': '\n'.join(lines), 'refresh_plans': plans,
            'external_calls_performed': False, 'external_writes_performed': False, 'paid_actions_performed': False,
            'result_ref': {'href': '/dashboard/card?tab=reviews', 'label': 'Открыть отзывы'}}
