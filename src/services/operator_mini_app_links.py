"""Map internal Operator results to Telegram Web Apps, retaining scoped filters."""
import os
from urllib.parse import urlsplit, urlunsplit, parse_qs, urlencode

SCREENS = {'/dashboard/partnerships':'partnerships','/dashboard/operator':'operator',
           '/dashboard/content':'content','/dashboard/card':'cards','/dashboard/influencers':'influencers',
           '/dashboard/agents':'agents','/dashboard/progress':'progress','/dashboard/finance':'finance',
           '/dashboard/settings':'settings','/dashboard/today':'today'}


def result_mini_app_url(result, *, public_base=None, mini_app_base=None):
    ref=result.get('result_ref') or {}
    href=str(ref.get('href') or '').strip()
    public=urlsplit(public_base or os.getenv('PUBLIC_BASE_URL') or 'https://localos.pro')
    target=urlsplit(href)
    if target.netloc and (target.netloc!=public.netloc or target.scheme!='https'):
        return None
    if not target.path.startswith('/dashboard/') or target.path not in SCREENS:
        return None
    query=parse_qs(target.query)
    base=urlsplit(mini_app_base or os.getenv('TELEGRAM_MINI_APP_URL') or 'https://localos.pro/telegram/control')
    if base.scheme!='https' or base.netloc!=public.netloc:
        return None
    params={k:v[-1] for k,v in parse_qs(base.query).items() if v}
    params['screen']=SCREENS[target.path]
    if target.path == '/dashboard/card' and (query.get('tab') or [''])[0] in {'services', 'reviews'}:
        params['screen'] = query['tab'][0]
    business=(query.get('business_id') or [result.get('business_id') or (result.get('task') or {}).get('business_id')])[-1]
    if business:params.update(scope_type='business',scope_id=str(business))
    for old,new in [('search_task_id','filter_search_task_id'),('section','filter_section'),('draft_id','filter_draft_id')]:
        value=(query.get(old) or [None])[-1]
        if value:params[new]=value
    return urlunsplit((base.scheme,base.netloc,base.path,urlencode(params),''))
