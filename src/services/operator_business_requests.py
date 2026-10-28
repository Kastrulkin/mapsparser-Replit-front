"""Read existing partner evidence and open the existing CRM request form."""
import re
from urllib.parse import urlencode

from services.operator_conversations import _row


STAGES = {
    'new': 'Новый кандидат', 'audited': 'Проверка компании выполнена',
    'matched': 'Подобран кандидат', 'draft': 'Письмо готовится',
    'ready': 'Готов к проверке перед отправкой', 'sent': 'Есть отметка об отправке',
    'replied': 'Есть ответ', 'interested': 'Обсуждаем условия',
    'rejected': 'Отказ', 'excluded': 'Исключён',
}


def request_kind(message):
    if re.search(r'crm|срм|yclients|dikidi', message, re.I) and re.search(r'подключ|заявк|запрос', message, re.I):
        return 'crm'
    if re.search(r'письм|сообщени|касани|черновик|отправк|батч|групп|подборк', message, re.I):
        return None
    if re.search(r'партн[её]ров|партн[её]ры|партн[её]рств', message, re.I) and re.search(r'покажи|выведи|порекомендуй|рекомендац', message, re.I):
        return 'partners'
    return None


def partners(cursor, business_id, message):
    from services.partnership_results import read_results, is_confirmed_partner
    confirmed = [item for item in read_results(cursor, [business_id]) if is_confirmed_partner(item)]
    lines = []
    active_only = bool(re.search(r'действующ|согласованн|текущие условия', message, re.I))
    recommend = bool(re.search(r'порекомендуй|рекомендац|следующ', message, re.I))
    if active_only:
        lines.append('Действующие партнёры с подтверждёнными договорённостями:')
        for item in confirmed[:20]:
            terms = (item.get('agreement_json') or {}).get('terms') or {}
            lines.append(str(item['name']) + '\nУсловия: ' + str(terms.get('details') or 'Не внесены') +
                '\nНаши действия: ' + str(terms.get('our_actions') or 'Не внесены') +
                '\nДействия партнёра: ' + str(terms.get('partner_actions') or 'Не внесены') +
                '\nСрок: ' + str(terms.get('validity') or 'Не указан'))
        if not confirmed:
            lines.append('В LocalOS нет подтверждённых договорённостей для этой точки. Отправленное предложение само по себе не означает действующее партнёрство.')
    if not active_only or recommend:
        cursor.execute("""SELECT id,name,category,status,selected_channel,rating,reviews_count
            FROM prospectingleads WHERE business_id=%s
            AND COALESCE(intent,'client_outreach')='partnership_outreach'
            ORDER BY updated_at DESC NULLS LAST LIMIT 50""", (business_id,))
        candidates = [_row(cursor, row) for row in cursor.fetchall()]
        if recommend:
            candidates = [item for item in candidates if item.get('status') in {'new', 'audited', 'matched', 'ready'}][:3]
        lines.append('Кого проверить следующим:' if recommend else 'Сохранённые кандидаты:')
        for item in candidates[:20]:
            stage = STAGES.get(item.get('status'), 'Статус нужно уточнить')
            category = str(item.get('category') or 'Категория не указана')
            lines.append(str(item['name']) + ' · ' + category + '\nЭтап: ' + stage +
                ('\nОснование: компания есть в сохранённой подборке этой точки; договорённость ещё нужно согласовать.' if recommend else ''))
        if not candidates:
            lines.append('Подходящих сохранённых кандидатов в этой выборке нет. Можно открыть историю или запустить отдельный поиск.')
        lines.append('Перед новым письмом проверьте контакт и историю обращений в карточке. Статус подбора не подтверждает готовность к отправке.')
    return '\n\n'.join(lines)


def route(cursor, *, business_id, user_id, message):
    kind = request_kind(message)
    if not kind:
        return None
    from services.business_permissions import require_permission, load_actor
    require_permission(cursor, business_id, load_actor(cursor, user_id), 'business.read')
    if kind == 'partners':
        return {'status': 'completed', 'capability': 'partnerships.read',
            'chat_response': partners(cursor, business_id, message), 'external_writes_performed': False,
            'result_ref': {'href': '/dashboard/partnerships?' + urlencode({'business_id': business_id}), 'label': 'Открыть партнёров и условия'}}
    return {'status': 'clarification_required', 'capability': 'crm.stats', 'external_writes_performed': False,
        'chat_response': 'Заявка на подключение CRM оформляется в «Финансах»: откройте ввод данных и блок подключения CRM, укажите название вашей CRM, ссылку и контакт для связи, затем проверьте и отправьте запрос. YCLIENTS и DIKIDI указывайте по названию; наличие готового подключения нужно проверить в этом разделе. Сейчас заявка не отправлена.',
        'result_ref': {'href': '/dashboard/finance?' + urlencode({'business_id': business_id, 'section': 'import'}), 'label': 'Открыть подключение CRM'}}
