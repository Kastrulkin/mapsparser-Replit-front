"""Reviewed corrections of existing drafts, never publication or replacement plans."""
import json
import re
import sys
from datetime import date
from services.operator_conversations import _row
from services import operator_editorial


def context(cursor,business,user,args):
    operator_editorial.authorize_actor(cursor,user,business)
    items=operator_editorial._items(cursor,business,args.get('plan_id'))
    editable=[row for row in items if row['status'] in operator_editorial.EDITABLE and row['plan_status']!='archived']
    cursor.execute('SELECT id,source_text,generated_text,approved,updated_at FROM usernews WHERE business_id=%s AND COALESCE(approved,0)=0 ORDER BY created_at DESC LIMIT 30',(business,))
    news=[_row(cursor,row) for row in cursor.fetchall()]
    records=[{'kind':'item','id':row['id'],'version':operator_editorial._version(row),'date':str(row['scheduled_for']),'theme':row['theme'],'text':row.get('draft_text') or ''} for row in editable]
    records.extend({'kind':'news','id':row['id'],'version':operator_editorial._version(row),'text':row['generated_text'],'source':row['source_text']} for row in news)
    return operator_editorial._result('Черновики для исправления. Выберите связанные с поручением записи, остальные не меняйте.',drafts=records)


def load(cursor,business,change,lock=False):
    if change.get('kind')=='item':
        rows=operator_editorial._items(cursor,business,item_id=change.get('id'),lock=lock)
        row=rows[0] if rows else {}
        if not row or row['status'] not in operator_editorial.EDITABLE or row['plan_status']=='archived':raise ValueError('Пост недоступен или уже утверждён.')
    elif change.get('kind')=='news':
        cursor.execute('SELECT id,source_text,generated_text,approved,updated_at FROM usernews WHERE business_id=%s AND id=%s'+(' FOR UPDATE' if lock else ''),(business,change.get('id')))
        row=_row(cursor,cursor.fetchone())
        if not row or row['approved']:raise ValueError('Черновик недоступен или уже утверждён.')
    else:raise ValueError('Выберите черновик поста или запись плана.')
    return row


def prepare(cursor,business,user,message,args):
    operator_editorial.authorize_actor(cursor,user,business)
    quote=operator_editorial._quote(args.get('quote'),message)
    promotion_end=args.get('promotion_end')
    if promotion_end:
        from services.operator_owner_actions import source_dates
        from services.finance_daily import settings
        promotion_end=date.fromisoformat(promotion_end).isoformat()
        positive=re.split(r'\bа\s+не\b',quote,flags=re.I)[0]
        if promotion_end not in source_dates(positive,settings(cursor,business).get('timezone') or 'UTC'):
            raise ValueError('Дата окончания акции должна быть явно указана в поручении.')
    changes=args.get('changes')
    if not isinstance(changes,list) or not 1<=len(changes)<=20:raise ValueError('Выберите от 1 до 20 черновиков.')
    seen=set();checked=[];lines=[]
    for change in changes:
        key=(change.get('kind'),change.get('id'))
        if key in seen:raise ValueError('Черновик указан дважды.')
        seen.add(key)
        row=load(cursor,business,change)
        if operator_editorial._version(row)!=change.get('version'):raise ValueError('Черновик изменился. Прочитайте его снова.')
        fields={key:str(change[key]).strip() for key in ('theme','text') if key in change}
        if not fields or any(not value or len(value)>6000 for value in fields.values()):raise ValueError('Проверьте новый текст.')
        if change['kind']=='news' and set(fields)!={'text'}:raise ValueError('Для поста вне плана изменяется текст.')
        if promotion_end and change['kind']=='item' and str(row['scheduled_for'])[:10]>promotion_end:
            if re.search(r'скидк|акци|выгодн|успей', ' '.join(fields.values()),re.I):
                # This is a proposal, never an automatic publication. Clear the
                # stale promotional draft through _change after approval.
                fields={'theme':'Совет по уходу' if re.search(r'совет.{0,15}уход',quote,re.I) else 'Совет по выбору услуги и подготовке к визиту'}
        checked.append({**{key:change[key] for key in ('kind','id','version')},**fields})
        old=row.get('theme') or row.get('generated_text') or ''
        lines.append((str(row['scheduled_for'])+': ' if change['kind']=='item' else '')+old+' → '+(fields.get('theme') or fields.get('text') or ''))
    envelope={'kind':'draft_corrections','business_id':business,'user_id':user,'quote':quote,'changes':checked}
    return operator_editorial._result('Предлагаю исправить существующие черновики:\n\n'+'\n\n'.join(lines)+'\n\nПодтвердите. Публикаций не будет.','approval_required',approval={'envelope':envelope})


def apply(cursor,business,user,envelope):
    operator_editorial.authorize_actor(cursor,user,business)
    if envelope.get('business_id')!=business or envelope.get('user_id')!=user:raise PermissionError('Чужое подтверждение.')
    changes=envelope['changes']
    rows=[load(cursor,business,change,lock=True) for change in sorted(changes,key=lambda value:(value['kind'],value['id']))]
    by_id={row['id']:row for row in rows}
    if any(operator_editorial._version(by_id[change['id']])!=change['version'] for change in changes):raise ValueError('Черновик изменился после просмотра. Ничего не сохранено.')
    for change in changes:
        row=by_id[change['id']]
        if change['kind']=='news':
            cursor.execute('UPDATE usernews SET generated_text=%s,edited_before_approve=TRUE,updated_at=clock_timestamp() WHERE id=%s AND business_id=%s',(change['text'],change['id'],business))
        else:
            operator_editorial._change(cursor,row,change.get('theme') or row['theme'],envelope['quote'],user)
            if change.get('text'):
                cursor.execute("UPDATE contentplanitems SET draft_text=%s,status='draft_generated',updated_at=clock_timestamp() WHERE id=%s AND business_id=%s",(change['text'],change['id'],business))
            cursor.execute('UPDATE contentplans SET updated_at=clock_timestamp() WHERE id=%s AND business_id=%s',(row['plan_id'],business))
    return operator_editorial._result('Исправлено черновиков: '+str(len(changes))+'. Ничего не опубликовано.')


def tools(cursor,business,user,message):
    string={'type':'string'}
    def preview(args):
        try:
            return prepare(cursor,business,user,message,args)
        except ValueError:
            return operator_editorial._result(str(sys.exception()),'error',retryable_preparation=True)
    return [
        {'name':'content.read_correction_drafts','capability':'content.history','title':'Черновики для исправления','description':'Читает неопубликованные посты и темы плана с id/version и текстами. Используй для изменения фактов или срока акции в уже подготовленных черновиках. Если указан план — plan_id. Не создавай новую заметку или план вместо исправления.', 'input_schema':{'type':'object','properties':{'plan_id':string}},'risk_class':'read_only','execute':lambda args:context(cursor,business,user,args)},
        {'name':'content.prepare_corrections','capability':'content.plan.refocus','title':'Подтвердить исправления черновиков','description':'После read_correction_drafts предложи изменения связанных черновиков. quote точная цитата поручения; changes kind=item/news,id,version,theme и/или text. При изменении срока акции укажи promotion_end (ISO). Сравни дату каждой записи с окончанием: после окончания замени тему и текст на совет БЕЗ обещаний скидки, не называй будущую дату последним днём уже закончившейся акции. Новые формулировки предложи сам с учётом поручения и исходного текста, не выдумывай фактов. Сохраняет те же записи после подтверждения, не публикует.', 'input_schema':{'type':'object','required':['quote','changes'],'properties':{'quote':string,'promotion_end':string,'changes':{'type':'array','maxItems':20,'items':{'type':'object','required':['kind','id','version'],'properties':{key:string for key in ('kind','id','version','theme','text')}}}}},'risk_class':'bulk_write','approval_required':True,'prepare_approval':preview,'deterministic_preparation_response':True}
    ]
