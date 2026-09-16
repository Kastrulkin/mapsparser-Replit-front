"""Explicit dates and counts override the default publication density."""
import re
from datetime import date, timedelta
from services.operator_plan_continuation import PlanClarification

WORDS={'один':'1','одна':'1','одну':'1','одному':'1','одной':'1','два':'2','две':'2','три':'3','четыре':'4','пять':'5','шесть':'6','семь':'7','восемь':'8','девять':'9','десять':'10'}
MONTHS=['января','февраля','марта','апреля','мая','июня','июля','августа','сентября','октября','ноября','декабря']


def extract(message):
    text=str(message or '').lower()
    for word,number in WORDS.items():text=re.sub(r'\b'+word+r'\b',number,text)
    frequency=re.search(r'\b(\d+)\s+пост\w*\s+в\s+недел',text)
    if not frequency:
        if re.search(r'\bс\s+\d|\bна\s+\d+\s+(?:недел|пост)',text):
            raise PlanClarification('Как часто публиковать посты в указанном периоде? Например: один пост в неделю.')
        return None
    if int(frequency[1])!=1:raise PlanClarification('Для точного расписания укажите даты постов или интервал в днях. Сейчас поддерживается один пост в неделю.')
    start_match=re.search(r'\bс\s+(\d{4}-\d{2}-\d{2})',text)
    try:
        if start_match:start=date.fromisoformat(start_match[1])
        else:
            match=re.search(r'\bс\s+(\d{1,2})\s+('+'|'.join(MONTHS)+r')\s+(\d{4})',text)
            if not match:raise PlanClarification('С какой даты и года начать еженедельные публикации?')
            start=date(int(match[3]),MONTHS.index(match[2])+1,int(match[1]))
    except ValueError:raise PlanClarification('Укажите существующую дату начала публикаций.') from None
    weeks=re.search(r'(?:на\s+)?\b(\d+)\s+недел',text)
    days=re.search(r'(?:на\s+)?\b(\d+)\s+дн',text)
    count_match=re.search(r'(?:всего\s+|на\s+)(\d+)\s+пост',text)
    period=int(weeks[1])*7 if weeks else int(days[1]) if days else int(count_match[1])*7 if count_match else None
    if not period:raise PlanClarification('На сколько недель подготовить план?')
    if not 1<=period<=90:raise PlanClarification('Укажите период от 1 до 90 дней.')
    count=(period+6)//7
    if count_match and int(count_match[1])!=count:raise PlanClarification('Количество постов не совпадает с периодом и частотой один раз в неделю. Что изменить?')
    groups=[]
    for m in re.finditer(r'\b(\d+)\s+(?:пост\w*\s+)?(?:про|о)\s+(.+?)(?=\s+\d+\s+(?:пост\w*\s+)?(?:про|о)\s+|[,.;]|$)',text):
        groups.append({'label':m[2].strip(),'mode':'count','value':int(m[1])})
    if groups and sum(g['value'] for g in groups)!=count:
        raise PlanClarification('Количество постов по темам не совпадает с расписанием. Уточните распределение или период.')
    return {'start':start,'period_days':period,'dates':[(start+timedelta(days=i*7)).isoformat() for i in range(count)],'groups':groups}
