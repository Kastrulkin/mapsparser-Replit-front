"""Verify explicitly spoken revenue before presenting a financial approval."""
import re
from decimal import Decimal

_UNITS = dict(zip('ноль один одна два две три четыре пять шесть семь восемь девять десять одиннадцать двенадцать тринадцать четырнадцать пятнадцать шестнадцать семнадцать восемнадцать девятнадцать'.split(), [0,1,1,2,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19]))
_UNITS.update(dict(zip('двадцать тридцать сорок пятьдесят шестьдесят семьдесят восемьдесят девяносто сто двести триста четыреста пятьсот шестьсот семьсот восемьсот девятьсот'.split(), [20,30,40,50,60,70,80,90,100,200,300,400,500,600,700,800,900])))
_SCALES = {'тысяча':1000,'тысячи':1000,'тысяч':1000,'миллион':1000000,'миллиона':1000000,'миллионов':1000000}
_WORD = '(?:'+'|'.join(_UNITS.keys() | _SCALES.keys())+')'
_AMOUNT = r'(?:\d+(?:[ \u00a0]\d{3})*(?:[.,]\d+)?(?:\s+(?:тысяч[аи]?|миллион(?:а|ов)?))?\b|'+_WORD+r'(?:\s+'+_WORD+r')*\b)'


def verify_currency(message, arguments):
    """Keep explicit currency even when the planner omits it or STT abbreviates it."""
    result = dict(arguments)
    if result.get('kind', 'daily') not in {'daily', 'transaction'}:
        return result
    currencies = set(re.findall(r'\b(?:RUB|EUR|USD|BYN|KZT|GBP|GEL|AMD|AED|UZS|KGS|TRY|THB)\b', message.upper()))
    text = message.casefold()
    if re.search(r'белорусск\w*\s+рубл\w*', text):
        currencies.add('BYN')
        text = re.sub(r'белорусск\w*\s+рубл\w*', '', text)
    for pattern, currency in [
        (r'\bруб(?:ль|ли|ля|лей|лях|лями)?\b|₽|\d\s*р\b', 'RUB'),
        (r'\bевро\b|€', 'EUR'),
        (r'\bдоллар\w*\b|\$', 'USD'),
        (r'\bтенге\b', 'KZT'),
    ]:
        if re.search(pattern, text):
            currencies.add(currency)
    if len(currencies) > 1:
        raise ValueError('Укажите данные отдельно для каждой валюты — суммы разных валют не складываются.')
    if currencies:
        result['currency'] = next(iter(currencies))
        if isinstance(result.get('values'),dict) and 'currency' in result['values']:
            result['values'] = {key:value for key,value in result['values'].items() if key!='currency'}
    return result


def _number(text):
    words=text.split()
    if words[0][0].isdigit():
        scale=_SCALES.get(words[-1],1)
        return Decimal(''.join(words[:-1] if scale!=1 else words).replace(',','.'))*scale
    total=part=0
    for word in words:
        if word in _SCALES:
            total+=(part or 1)*_SCALES[word];part=0
        else:part+=_UNITS[word]
    return Decimal(total+part)


def verify_revenue(message, arguments):
    result=dict(arguments)
    if result.get('kind','daily')!='daily' or result.get('mode','set')!='set':
        return result
    values=dict(result.get('values') or {})
    if 'revenue' not in values or not re.search(r'выручк',message,re.I):return result
    matches=list(re.finditer(r'выручк[аиу]?(?P<qualifier>\s*(?:(?:до|после)\s+возврат(?:ов|а\s+в|а)?)?\s*(?:составила|была|стала|итого)?\s*[:—=–-]?\s*)(?P<amount>'+_AMOUNT+')',message,re.I))
    if len(matches)>1 and 'Уточнение:' in message:
        matches=[matches[-1]]
    if len(matches)!=1:
        raise ValueError('Уточните сумму выручки до возвратов и сумму возвратов — покажу итог перед сохранением.')
    match=matches[0]
    if '-' in match['qualifier'] or re.match(r'\s*(?:[%]|[–—-]\s*\d|тыс\b)', message[match.end():], re.I) or re.search(r'цент|копе',message,re.I):
        raise ValueError('Укажите точную сумму выручки числом, например 350,50 евро.')
    amount=_number(match['amount'].lower())
    after=message[match.end():]
    net=bool(re.search(r'после\s+возврат',match['qualifier'],re.I) or re.match(r'\s*(?:евро|рублей|рубля|руб|eur|₽|€)?\s*(?:после\s+возврат|за\s+вычетом\s+возврат)',after,re.I))
    refunds=[item for item in re.finditer(r'\bвозврат(?:ы|ов)?\s*[:—=-]?\s*('+_AMOUNT+')',message,re.I) if item.start() < match.start() or item.start() >= match.end()]
    if len(refunds)>1:raise ValueError('Уточните общую сумму возвратов за этот день.')
    if refunds:values['refunds']=str(_number(refunds[0][1].lower()))
    if net:
        if not refunds:raise ValueError('Укажите сумму возвратов, чтобы рассчитать выручку до возвратов.')
        amount+=_number(refunds[0][1].lower())
    values['revenue']=str(amount)
    result['values']=values
    return result


def daily_statement(message, previous=None):
    """Parse only explicit local-day totals; ambiguous or detailed sales use the planner."""
    if re.search(r'\?|\b(?:если|допустим|пример)\b|не (?:записывай|сохраняй)|итог месяца|за месяц',message,re.I):
        return None
    if not re.search(r'\b(?:сегодня|вчера)\b',message,re.I) or not re.search(r'выручк|чек',message,re.I):
        return None
    if re.search(r'добавь|ещ[её]|увелич|отмен',message,re.I):
        return None
    result={'kind':'daily','date':'yesterday' if re.search(r'\bвчера\b',message,re.I) else 'today','mode':'set'}
    values=dict((previous or {}).get('data') or {})
    for key,pattern in [
        ('checks',r'('+_AMOUNT+r')\s+чек(?:а|ов)?\b(?!\s+с\s+доп)'),
        ('upsell_checks',r'('+_AMOUNT+r')\s+(?:(?:чек(?:а|ов)?\s+)?с\s+доп\w*|допродаж\w*|до\s+продаж\w*)'),
        ('refunds',r'\bвозврат(?:ы|ов)?\s*[:—=]?\s*('+_AMOUNT+r')'),
        ('expenses',r'\bрасход(?:ы|ов)?\s*[:—=]?\s*('+_AMOUNT+r')'),
    ]:
        found=list(re.finditer(pattern,message,re.I))
        if found:values[key]=str(_number(found[-1][1].lower()))
    if re.search(r'выручк',message,re.I) and not re.search(r'выручк[ауи]?\s+(?:пока\s+)?не\s+знаю',message,re.I):
        values['revenue']='0'  # Replaced by the source verifier or rejected; never persisted as a guess.
    if not values:return None
    result['values']=values
    if previous:
        result['date']=previous['date'];result['currency']=previous['currency']
    return verify_revenue(message,verify_currency(message,result))
