"""Typed values and bounded document extraction; no implicit truth from free text."""
import io
import math
from datetime import date, datetime, timezone
from urllib.parse import urlsplit

TYPES = {'text','long_text','integer','decimal','boolean','date','url','select','multi_select'}


def field_definition(data):
    if not isinstance(data, dict):
        raise ValueError('Укажите параметры поля.')
    label = str(data.get('label') or '').strip()
    if not label or len(label) > 200 or data.get('type') not in TYPES:
        raise ValueError('Укажите название и поддерживаемый тип поля.')
    options = data.get('options') or []
    if not isinstance(options,list) or len(options)>100:
        raise ValueError('Допустимо до 100 вариантов выбора.')
    clean_options=[]
    for option in options:
        if not isinstance(option,dict) or not option.get('id') or not str(option.get('label') or '').strip():
            raise ValueError('Укажите идентификатор и название варианта.')
        if any(existing['id']==option['id'] for existing in clean_options):
            raise ValueError('Варианты выбора повторяются.')
        if not isinstance(option['id'],str) or len(option['id'])>100 or len(str(option['label']))>200:
            raise ValueError('Название варианта — до 200 символов; идентификатор — до 100.')
        clean_options.append({'id':option['id'],'label':str(option['label']), 'archived':option.get('archived') is True})
    if data['type'] in {'select','multi_select'} and not clean_options:
        raise ValueError('Добавьте варианты выбора.')
    result = {'type':data['type'],'label':label,'options':clean_options,
              'group':str(data.get('group') or 'Общие сведения')[:200],
              'unit':str(data.get('unit') or '')[:50], 'hint':str(data.get('hint') or '')[:1000],
              'location_only':data.get('location_only') is not False}
    result.update({key:data[key] for key in ('min','max','template_key') if key in data})
    for key in ('min','max'):
        value=data.get(key)
        if value is not None and (type(value) not in (int,float) or not math.isfinite(value)):
            raise ValueError('Граница значения должна быть числом.')
    if data.get('min') is not None and data.get('max') is not None and data['min']>data['max']:
        raise ValueError('Минимум должен быть не больше максимума.')
    return result


def typed_value(definition, data, previous=None):
    state=data.get('state','set')
    if state not in {'set','unknown','not_applicable'}:
        raise ValueError('Выберите значение, «Не указано» или «Не применяется».')
    value=data.get('value')
    if data.get('valid_until'):date.fromisoformat(data['valid_until'])
    if state!='set':
        return {**data,'state':state,'value':None}
    kind=definition['type']
    if kind in {'integer','decimal'}:
        if type(value) not in (int,float) or not math.isfinite(value) or (kind=='integer' and type(value) is not int):
            raise ValueError('Укажите число подходящего типа.')
        if definition.get('min') is not None and value<definition['min'] or definition.get('max') is not None and value>definition['max']:
            raise ValueError('Значение выходит за допустимые границы.')
    elif kind=='boolean':
        if type(value) is not bool:raise ValueError('Выберите да или нет.')
    elif kind in {'select','multi_select'}:
        selected=value if kind=='multi_select' else [value]
        if not isinstance(selected,list) or any(not isinstance(item,str) for item in selected) or len(selected)!=len(set(selected)):
            raise ValueError('Выберите неповторяющиеся варианты.')
        all_options={option['id'] for option in definition['options']}
        active={option['id'] for option in definition['options'] if not option['archived']}
        old=(previous or {}).get('value',[])
        old=old if isinstance(old,list) else [old]
        if any(not isinstance(item,str) or item not in all_options or (item not in active and item not in old) for item in selected):
            raise ValueError('Вариант недоступен. Обновите поле.')
    else:
        if not isinstance(value,str) or not value.strip() or len(value)> (10000 if kind=='long_text' else 2000):
            raise ValueError('Укажите непустой текст допустимой длины.')
        if kind=='date':date.fromisoformat(value)
        if kind=='url':
            parsed=urlsplit(value)
            if parsed.scheme not in {'http','https'} or not parsed.hostname or parsed.username or parsed.password:
                raise ValueError('Укажите ссылку HTTP или HTTPS.')
    expires=data.get('valid_until')
    if expires:date.fromisoformat(expires)
    return {**data,'state':state,'value':value}


def document_text(content, filename):
    from services.agent_source_ingestion import extract_text_from_agent_source_bytes
    extension=filename.rsplit('.',1)[-1].lower()
    if extension not in {'pdf','docx','txt'}:raise ValueError('Поддерживаются PDF, DOCX и TXT.')
    if not content or len(content)>10*1024*1024:raise ValueError('Файл должен быть непустым и не больше 10 МБ.')
    if extension=='pdf':
        from pypdf import PdfReader
        try:
            reader=PdfReader(io.BytesIO(content))
            if reader.is_encrypted:raise ValueError('Снимите пароль с документа перед загрузкой.')
            if len(reader.pages)>50:raise ValueError('PDF содержит больше 50 страниц. Разделите документ.')
        except ValueError:raise
        except Exception:raise ValueError('Не удалось прочитать PDF. Проверьте файл.') from None
    text,error=extract_text_from_agent_source_bytes(content,filename)
    if error:raise ValueError(error['message'])
    if len(text)>30000:raise ValueError('Текст превышает 30 000 символов. Разделите документ.')
    return text, 'needs_review' if text.strip() else 'text_unavailable'


def is_current(payload):
    expires=payload.get('valid_until')
    try:return not expires or date.fromisoformat(expires)>=datetime.now(timezone.utc).date()
    except (TypeError,ValueError):return False
