"""Bounded lexical retrieval for client chat; no model call or provider spend."""
import re

SERVICE_CONTEXT_BYTES = 12000
MAX_SERVICES = 12
STOP_WORDS = {'сколько', 'стоит', 'стоимость', 'цена', 'хочу', 'можно', 'меня', 'есть', 'услуги', 'услуга', 'здравствуйте', 'привет', 'пожалуйста', 'какие', 'вас', 'нужно', 'записаться', 'запись', 'спасибо', 'добрый', 'день'}


def _terms(text):
    return {word[:5] if len(word) > 5 else word for word in re.findall(r'[а-яёa-z0-9]+', str(text).lower().replace('ё', 'е')) if len(word) >= 3 and word not in STOP_WORDS}


def service_context(services, message, history):
    query = _terms(message)
    # Follow-ups such as "а сколько стоит?" inherit the client's recent subject.
    if not query:
        for item in reversed(history[-4:]):
            if item.get('sender') == 'client' or item.get('role') in ('client', 'user'):
                query = _terms(item.get('content', ''))
                if query:
                    break
    ranked = []
    for index, service in enumerate(services):
        name = str(service.get('name') or '')
        name_hits = len(query & _terms(name))
        description_hits = len(query & _terms(service.get('description') or ''))
        score = name_hits * 10 + description_hits
        if score:
            ranked.append((-score, index, service))
    ranked.sort(key=lambda item: (item[0], item[1]))
    if not ranked:
        return 'По вопросу не выбрана конкретная услуга. Уточни направление или название; не придумывай услуги и цены. Полный каталог не помещён в контекст.\n'
    lines = ['Подборка по вопросу клиента; это часть каталога. Не утверждай, что других услуг нет. Цены и варианты относятся только к указанной строке.\n']
    size = len(lines[0].encode('utf-8'))
    for _, _, service in ranked[:MAX_SERVICES]:
        name = str(service.get('name') or '')
        price = service.get('price')
        duration = service.get('duration')
        description = re.sub(r'\s+', ' ', str(service.get('description') or ''))[:350]
        line = f"- {name[:240]}: {price if price is not None else 'Цена по запросу'}; длительность: {duration if duration else 'не указана'}. {description}\n"
        if size + len(line.encode('utf-8')) > SERVICE_CONTEXT_BYTES:
            break
        lines.append(line)
        size += len(line.encode('utf-8'))
    return ''.join(lines)
