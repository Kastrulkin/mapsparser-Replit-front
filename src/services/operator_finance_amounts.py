"""Verify explicitly spoken revenue before presenting a financial approval."""
import re
from decimal import Decimal

_UNITS = dict(zip('ноль один одна два две три четыре пять шесть семь восемь девять десять одиннадцать двенадцать тринадцать четырнадцать пятнадцать шестнадцать семнадцать восемнадцать девятнадцать'.split(), [0,1,1,2,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19]))
_UNITS.update(dict(zip('двадцать тридцать сорок пятьдесят шестьдесят семьдесят восемьдесят девяносто сто двести триста четыреста пятьсот шестьсот семьсот восемьсот девятьсот'.split(), [20,30,40,50,60,70,80,90,100,200,300,400,500,600,700,800,900])))
_SCALES = {'тысяча':1000,'тысячи':1000,'тысяч':1000,'миллион':1000000,'миллиона':1000000,'миллионов':1000000}
_WORD = '(?:'+'|'.join(_UNITS.keys() | _SCALES.keys())+')'
_AMOUNT = r'(?:\d+(?:[ \u00a0]\d{3})*(?:[.,]\d+)?(?:\s+(?:тысяч[аи]?|миллион(?:а|ов)?))?\b|'+_WORD+r'(?:\s+'+_WORD+r')*\b)'


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
    matches=list(re.finditer(r'выручк[аиу]?(?P<qualifier>\s*(?:(?:до|после)\s+возвратов)?\s*(?:составила|была|стала|итого)?\s*[:—=–-]?\s*)(?P<amount>'+_AMOUNT+')',message,re.I))
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
