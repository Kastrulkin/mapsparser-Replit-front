"""Manual map-card transfer: run-scoped progress and local export, no provider writes."""
import base64
import csv
import io
import json
import re
import uuid
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

PROVIDERS = {'google', 'yandex', '2gis'}
STEPS = ('data', 'services', 'photos', 'submission', 'verification')
FIELDS = {'name', 'address', 'phone', 'website', 'schedule', 'description'}
ARTIFACT = 'map_card_transfer_progress'


def record(value):
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except ValueError:
            pass
    return {}


def load_report(cursor, run_id):
    cursor.execute("""SELECT payload_json FROM agent_artifacts WHERE run_id=%s
        AND artifact_type='agent_final_result' ORDER BY created_at DESC LIMIT 1""", (run_id,))
    row = cursor.fetchone()
    report = record(record((row or {}).get('payload_json')).get('result'))
    if report.get('schema') != 'map_card_report_v1' or report.get('kind') != 'preparation' or report.get('preview'):
        raise ValueError('Мастер доступен для сохранённого рабочего пакета оформления, а не тестового примера.')
    return report


def load_progress(cursor, run_id):
    cursor.execute('SELECT id, payload_json FROM agent_artifacts WHERE run_id=%s AND artifact_type=%s ORDER BY created_at DESC LIMIT 1', (run_id, ARTIFACT))
    row = cursor.fetchone() or {}
    data = record(row.get('payload_json'))
    return row.get('id'), {'revision': data.get('revision', 0), 'platforms': data.get('platforms', {})}


def clean_state(value):
    if not isinstance(value, dict):
        raise ValueError('Некорректные данные шага.')
    fields = value.get('fields', {})
    steps = value.get('steps', {})
    services = value.get('services', [])
    if not isinstance(fields, dict) or not isinstance(steps, dict) or not isinstance(services, list) or len(services) > 100:
        raise ValueError('Не более 100 услуг; поля и отметки должны быть объектами.')
    if set(fields) - FIELDS or set(steps) - set(STEPS):
        raise ValueError('Неизвестное поле или шаг.')
    if any(not isinstance(v, str) or len(v) > 5000 for v in fields.values()):
        raise ValueError('Текст поля должен быть не длиннее 5000 символов.')
    if any(not isinstance(v, bool) for v in steps.values()):
        raise ValueError('Отметка выполнения должна быть логическим значением.')
    normalized_services = []
    for item in services:
        if not isinstance(item, dict) or set(item) - {'name', 'price', 'description'}:
            raise ValueError('Некорректная услуга.')
        service = {key: item.get(key, '') for key in ('name', 'price', 'description')}
        if any(not isinstance(v, str) or len(v) > 3000 for v in service.values()) or len(service['name']) > 250:
            raise ValueError('Проверьте длину названия и описания услуги.')
        normalized_services.append(service)
    if steps.get('submission') and not all(steps.get(key) for key in STEPS[:3]):
        raise ValueError('Сначала подтвердите данные, услуги и фотографии.')
    if steps.get('verification') and not steps.get('submission'):
        raise ValueError('Сначала отметьте ручной перенос в кабинет площадки.')
    return {'fields': fields, 'steps': steps, 'services': normalized_services}


def save_progress(cursor, run_id, provider, state, expected_revision, user_id):
    if provider not in PROVIDERS:
        raise ValueError('Неизвестная площадка.')
    state = clean_state(state)
    artifact_id, progress = load_progress(cursor, run_id)
    if type(expected_revision) is not int or progress['revision'] != expected_revision:
        return None
    state.update({'updated_by': str(user_id), 'updated_at': datetime.now(timezone.utc).isoformat(),
                  'confirmation': 'manual_user_mark', 'provider_write_performed': False})
    progress['platforms'][provider] = state
    progress['revision'] += 1
    payload = json.dumps(progress, ensure_ascii=False)
    if artifact_id:
        cursor.execute('UPDATE agent_artifacts SET payload_json=%s::jsonb WHERE id=%s AND run_id=%s', (payload, artifact_id, run_id))
    else:
        cursor.execute('INSERT INTO agent_artifacts (id, run_id, artifact_type, title, payload_json) VALUES (%s,%s,%s,%s,%s::jsonb)',
                       (str(uuid.uuid4()), run_id, ARTIFACT, 'Ручной перенос карточек', payload))
    return progress


def export_file(report, progress, provider, kind):
    if provider not in PROVIDERS:
        raise ValueError('Неизвестная площадка.')
    state = progress.get('platforms', {}).get(provider, {})
    card = next((c for c in report.get('cards', []) if c.get('provider') == provider), {})
    defaults = {f['field']: f.get('proposed') or '' for f in card.get('fields', [])}
    fields = {**defaults, **state.get('fields', {})}
    services = state.get('services')
    if services is None:
        services = [{k: str(s.get(k) or '') for k in ('name', 'price', 'description')} for s in report.get('services', [])]
    if kind == 'instructions':
        labels = {'name': 'Название', 'address': 'Адрес', 'phone': 'Телефон', 'website': 'Сайт', 'schedule': 'Часы работы', 'description': 'Описание'}
        content = f'Пакет для {provider}. Подготовлено в LocalOS. Размещение вручную.\n\n'
        content += '\n\n'.join(f'{label}\n{fields.get(key) or "Уточнить у владельца"}' for key, label in labels.items())
        content += '\n\nУслуги\n' + '\n'.join(f'{s.get("name", "")} | {s.get("price", "")} | {s.get("description", "")}' for s in services)
        content += '\n\nПосле переноса дождитесь проверки площадки и отдельно проверьте публичную карточку.\n'
        return _file(provider+'-card.txt', 'text/plain;charset=utf-8', content.encode('utf-8'))
    if kind != 'services' or provider == 'google':
        raise ValueError('Этот формат выгрузки для площадки не поддерживается.')
    # An empty workbook is explicitly a template, never invented catalogue rows.
    for item in services:
        try:
            raw_price = str(item.get('price') or '').strip()
            if len(raw_price) > 20 or not re.fullmatch(r'\d+(?:[.,]\d+)?', raw_price):
                raise InvalidOperation
            price = Decimal(raw_price.replace(',', '.'))
            if not price.is_finite() or price <= 0 or not str(item.get('name') or '').strip():
                raise InvalidOperation
            item['price'] = format(price, 'f')
        except InvalidOperation:
            raise ValueError('Для выгрузки у каждой услуги нужны название и точная цена больше нуля. Или удалите незаполненные строки и скачайте пустой шаблон.')
    if provider == 'yandex':
        from openpyxl import Workbook
        book = Workbook(); sheet = book.active; sheet.title = 'Прайс-лист'
        sheet.append(['Категория', 'Название', 'Идентификатор', 'Описание', 'Короткое описание', 'Цена', 'Ссылка', 'Фотография', 'Популярный товар', 'В наличии', 'Количество', 'Единицы измерения'])
        for index, item in enumerate(services):
            sheet.append(['Услуги', item['name'], 'service-'+str(index+1), item.get('description', ''), '', str(item['price']), '', '', '', '', '', ''])
        for row in sheet:
            for cell in row:
                if isinstance(cell.value, str):
                    cell.data_type = 's'  # Untrusted text must never become an Excel formula.
        sheet.freeze_panes = 'A2'; sheet.auto_filter.ref = sheet.dimensions
        stream = io.BytesIO(); book.save(stream)
        return _file('yandex-services'+('-template' if not services else '')+'.xlsx', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', stream.getvalue())
    stream = io.StringIO(); writer = csv.writer(stream, delimiter=';')
    writer.writerow(['name', 'price', 'currencyId', 'measure', 'available', 'category', 'url', 'picture', 'vendor', 'id', 'description'])
    for item in services:
        writer.writerow([safe_csv(item['name']), safe_csv(item['price']), 'RUB', '', '', 'Услуги', '', '', '', '', safe_csv(item.get('description', ''))])
    return _file('2gis-services'+('-template' if not services else '')+'.csv', 'text/csv;charset=utf-8', stream.getvalue().encode('utf-8-sig'))


def safe_csv(value):
    text = str(value)
    return "'"+text if re.match(r'^\s*[=+@\-]', text) else text


def _file(name, mime, content):
    return {'filename': name, 'mime': mime, 'content_base64': base64.b64encode(content).decode('ascii')}
