"""Voice/text stories update existing content-plan items and media references."""
import json
import uuid
from datetime import date

from services import operator_workday, operator_attachments, operator_editorial
from services.operator_conversations import _row


def context(cursor,business,user,args):
    operator_workday.authorize(cursor,business,user)
    result=operator_editorial.read_context(cursor,business,user,{'plan_id':args.get('plan_id'),'include_details':True})
    item_id=args.get('item_id')
    if item_id:
        cursor.execute('SELECT id,draft_text,metadata_json,updated_at FROM contentplanitems WHERE id=%s AND business_id=%s',(item_id,business))
        selected=_row(cursor,cursor.fetchone())
        if not selected:raise PermissionError('Пост недоступен.')
        result['selected_item']=selected
    return result


def save(cursor,business,user,args,conversation_id,request_id):
    operator_workday.authorize(cursor,business,user)
    title=str(args.get('theme') or '').strip()
    text=str(args.get('draft_text') or '').strip()
    if not 1<=len(title)<=120 or not 1<=len(text)<=10000:
        raise ValueError('Укажите тему и текст черновика.')
    item_id=args.get('item_id')
    plan_id=args.get('plan_id')
    cursor.execute('SELECT * FROM contentplans WHERE id=%s AND business_id=%s FOR UPDATE',(plan_id,business))
    plan=_row(cursor,cursor.fetchone())
    if not plan or plan['plan_status']=='archived':raise ValueError('Выберите действующий контент-план.')
    existing={}
    if item_id:
        cursor.execute('SELECT * FROM contentplanitems WHERE id=%s AND plan_id=%s AND business_id=%s FOR UPDATE',(item_id,plan_id,business))
        existing=_row(cursor,cursor.fetchone())
        if not existing or existing['status'] not in operator_editorial.EDITABLE:
            raise ValueError('Выберите неопубликованный черновик.')
        if str(existing['updated_at'])!=args.get('version'):
            if len(str(args.get('version') or ''))!=64:
                raise ValueError('Черновик изменился. Прочитайте актуальную версию.')
            canonical=operator_editorial._items(cursor,business,plan_id,item_id=item_id)
            if not canonical or operator_editorial._version(canonical[0])!=args.get('version'):
                raise ValueError('Черновик изменился. Прочитайте актуальную версию.')
        cursor.execute("SELECT status FROM social_posts WHERE content_plan_item_id=%s AND business_id=%s FOR UPDATE",(item_id,business))
        if any(_row(cursor,row)['status'] in {'publishing','published'} for row in cursor.fetchall()):raise ValueError('Материал уже публикуется или опубликован. Создайте отдельный черновик.')
    raw_date=args.get('scheduled_for') or existing.get('scheduled_for')
    if not raw_date:raise ValueError('Укажите дату поста в контент-плане.')
    scheduled=date.fromisoformat(str(raw_date)[:10])
    if not plan['period_start']<=scheduled<=plan['period_end']:
        raise ValueError('Дата за пределами контент-плана. Выберите другой план или дату.')
    attachments=args.get('attachment_ids')
    if attachments is None:
        attachments=[]
    if not isinstance(attachments,list) or len(attachments)>10:
        raise ValueError('Выберите до 10 фотографий.')
    selected_attachments=[]
    for identifier in attachments:
        attachment=operator_attachments.load(cursor,business,user,identifier,conversation_id)
        if attachment['purpose']=='unknown' and attachment.get('mime_type') in {'image/jpeg','image/png','image/webp'}:
            selected_attachments.append((identifier,attachment))
        elif attachment['purpose']=='content' and attachment.get('photo_asset_id'):
            selected_attachments.append((identifier,attachment))
        else:
            raise ValueError('Сначала укажите, что выбранное фото предназначено для поста.')
    photos=[]
    for identifier,attachment in selected_attachments:
        # Saving an explicitly selected photo in a post establishes its purpose.
        # The content classification stores media only; it never runs OCR/vision.
        if attachment['purpose']=='unknown':
            operator_attachments.classify(cursor,business,user,identifier,'content',conversation_id)
            attachment=operator_attachments.load(cursor,business,user,identifier,conversation_id)
        photos.append(attachment['photo_asset_id'])
    metadata=dict(existing.get('metadata_json') or {})
    if existing:
        history=list(metadata.get('operator_edit_history') or [])
        history.append({'theme':existing['theme'],'draft_text':existing.get('draft_text'),
                        'scheduled_for':str(existing['scheduled_for']),'actor_id':user,'version':str(existing['updated_at'])})
        metadata['operator_edit_history']=history
    else:
        generated=plan.get('generated_plan_json') or {}
        channels=generated.get('selected_channels') or (generated.get('meta') or {}).get('selected_channels')
        if channels:metadata['selected_channels']=channels
    metadata['story_source']={'conversation_id':conversation_id,'request_id':request_id,'attachment_ids':attachments}
    if 'attachment_ids' in args:metadata['operator_photo_asset_ids']=photos
    identifier=item_id or str(uuid.uuid5(uuid.NAMESPACE_URL,':'.join(['operator-story',business,user,conversation_id,request_id])))
    if existing:
        cursor.execute("UPDATE contentplanitems SET theme=%s,draft_text=%s,scheduled_for=%s,metadata_json=%s::jsonb,status='draft_generated',updated_at=clock_timestamp() WHERE id=%s AND business_id=%s",
                       (title,text,scheduled,json.dumps(metadata,ensure_ascii=False),identifier,business))
    else:
        cursor.execute("""INSERT INTO contentplanitems(id,plan_id,business_id,theme,goal,scheduled_for,status,content_type,source_kind,draft_text,metadata_json)
            VALUES (%s,%s,%s,%s,%s,%s,'draft_generated','news','editorial_brief',%s,%s::jsonb) ON CONFLICT(id) DO NOTHING""",
            (identifier,plan_id,business,title,'Материал из текущей работы',scheduled,text,json.dumps(metadata,ensure_ascii=False)))
    cursor.execute("""UPDATE social_posts SET status='needs_review',approved_at=NULL,approval_id=NULL,automation_task_id=NULL,
        base_text=%s,platform_text=%s,scheduled_for=%s,
        media_json=CASE WHEN %s THEN '[]'::jsonb ELSE media_json END,
        updated_at=NOW() WHERE business_id=%s AND content_plan_item_id=%s AND status NOT IN ('published','publishing')""",
        (text,text,scheduled,'attachment_ids' in args,business,identifier))
    if 'attachment_ids' in args:
        cursor.execute("UPDATE photo_asset_usage_events SET usage_type='superseded_publication' WHERE business_id=%s AND target_id=%s AND usage_type='publication' AND NOT (photo_asset_id=ANY(%s))",
                       (business,identifier,photos))
    from services.media_intelligence import record_photo_usage
    for photo_id in photos:
        cursor.execute("SELECT id FROM photo_asset_usage_events WHERE business_id=%s AND target_id=%s AND photo_asset_id=%s AND usage_type='publication'",(business,identifier,photo_id))
        if not cursor.fetchone():
            record_photo_usage(cursor,business_id=business,photo_asset_id=photo_id,usage_type='publication',target_id=identifier)
    cursor.execute('UPDATE contentplans SET updated_at=clock_timestamp() WHERE id=%s',(plan_id,))
    cursor.execute('UPDATE operatorconversations SET input_context_json=%s::jsonb WHERE id=%s AND user_id=%s AND business_id=%s',
        (json.dumps({'selected_object':{'type':'content_item','id':identifier}}),conversation_id,user,business))
    if args.get('copy_text_to_channels') is True:
        from services.social_post_service import _upsert_social_post, _existing_social_posts_for_item, CONTENT_PUBLICATION_PLATFORMS
        channels=metadata.get('selected_channels') or []
        if not channels or any(channel not in CONTENT_PUBLICATION_PLATFORMS for channel in channels):
            raise ValueError('Выберите поддерживаемые площадки перед подготовкой комплекта.')
        current=_existing_social_posts_for_item(cursor,identifier)
        item={'id':identifier,'plan_id':plan_id,'business_id':business,'scheduled_for':scheduled,
              'draft_text':text,'metadata_json':metadata}
        for channel in channels:
            # Existing channel copy is never replaced by this no-generation path.
            if channel not in current:
                _upsert_social_post(cursor,user,item,channel,text,
                    {'text':text,'metadata':{'manually_edited':True,'variant_source':'user_supplied'}})
        if photos:
            cursor.execute("""UPDATE social_posts SET media_json=%s::jsonb,updated_at=NOW()
                WHERE business_id=%s AND content_plan_item_id=%s AND status='needs_review'""",
                (json.dumps([{'photo_asset_id':photo_id} for photo_id in photos]),business,identifier))
    return {'status':'completed','capability':'content.item.edit','chat_response':'Черновик сохранён в контент-плане. Проверьте текст, фотографии и выбранные каналы перед публикацией.',
            'item_id':identifier,'result_ref':{'entity_id':identifier,'href':'/dashboard/content?business_id='+business+'&item_id='+identifier,'label':'Открыть контент-план'},'draft_text':text}


def tools(cursor,business,user,conversation_id,request_id,photo_brief_ids=None):
    def save_selected(arguments):
        if photo_brief_ids is not None:
            if arguments.get('item_id'):
                raise ValueError('Для нового фото создаётся отдельный черновик.')
            arguments = {**arguments, 'attachment_ids': list(photo_brief_ids), 'copy_text_to_channels': False}
        result = save(cursor,business,user,arguments,conversation_id,request_id)
        if photo_brief_ids is not None:
            text = result['draft_text']
            result['chat_response'] = ('Черновик поста:\n\n' + text[:2800]
                + ('\n\nПолный текст сохранён в контент-плане.' if len(text) > 2800 else '')
                + '\n\nФото прикреплено. Проверьте текст и площадки в контент-плане. Ничего не опубликовано.')
        return result
    text={'type':'string'}
    return [
        {'name':'content.story_context','title':'Материалы контент-плана','capability':'content.item.edit','risk_class':'read_only',
         'description':'Прочитать планы и выбранный черновик с updated_at перед голосовым исправлением. Если планов несколько — уточни выбор.',
         'input_schema':{'type':'object','properties':{'plan_id':text,'item_id':text}},'execute':lambda a:context(cursor,business,user,a)},
        {'name':'content.save_story','title':'Сохранить материал в контент-план','capability':'content.item.edit','risk_class':'internal_draft_write',
         'description':'По явной просьбе создать или исправить пост сохрани текст в существующем плане. До этого story_context. Для правки нужны item_id и version=updated_at; дату сохраняй, если не просили изменить. Не выдумывай результаты процедур, не включай имена клиентов, внутреннюю выручку и расходы. Каналы сохраняет сервер. Фото только из явно выбранных attachment_ids назначения content. Это не публикация. Если канал не выбран, пользователь выберет его в контент-плане.',
         'input_schema':{'type':'object','required':['plan_id','theme','draft_text'],'properties':{'plan_id':text,'item_id':text,'version':text,'theme':text,'draft_text':text,'scheduled_for':text,'attachment_ids':{'type':'array','items':text},'copy_text_to_channels':{'type':'boolean','description':'Только по явной просьбе использовать готовый текст дословно для выбранных площадок без генерации. Создаёт недостающие версии на проверку, не утверждает и не публикует.'}}},
         'execute':save_selected,'deterministic_response':True},
    ]
