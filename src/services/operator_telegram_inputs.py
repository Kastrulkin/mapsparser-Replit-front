"""Telegram attachments enter the same conversation as voice and text."""
import asyncio
import json
from services import operator_workday, operator_attachments
from services.operator_conversations import _row
from services.operator_telegram_voice import transaction


async def receive(update,context,host):
    if update.effective_chat.type!='private' or update.effective_user.is_bot:return False
    business=host._control_scope_business_context(str(update.effective_user.id))
    if not business or not operator_workday.enabled(business['business_id']):return False
    if host.user_states.get(str(update.effective_user.id),{}).get('state','idle') not in {'','idle'}:return False
    media=update.message.document or (update.message.photo[-1] if update.message.photo else None)
    if not media:return False
    if (media.file_size or 0)>operator_attachments.MAX_BYTES:
        await update.message.reply_text('Файл должен быть не больше 10 МБ.');return True
    try:
        def check(c):return operator_workday.authorize(c,business['business_id'],business['user_id'])
        await asyncio.to_thread(transaction,check)
        file=await context.bot.get_file(media.file_id)
        content=bytes(await file.download_as_bytearray())
        def save(c):
            item=operator_attachments.receive(c,business_id=business['business_id'],user_id=business['user_id'],channel='telegram',
                content=content,name=getattr(media,'file_name',None) or 'photo.jpg',mime_type=getattr(media,'mime_type',None) or 'image/jpeg',
                request_key=f'tg:{update.effective_chat.id}:{update.message.message_id}')
            c.execute('SELECT input_context_json FROM operatorconversations WHERE id=%s FOR UPDATE',(item['conversation_id'],))
            selected=_row(c,c.fetchone()).get('input_context_json') or {}
            ids=list(dict.fromkeys((selected.get('attachment_ids') or [])+[item['id']]))
            if len(ids)>10:raise ValueError('Завершите текущий материал: допускается до 10 файлов.')
            selected['attachment_ids']=ids
            if update.message.caption:
                notes=dict(selected.get('attachment_notes') or {})
                notes[item['id']]=update.message.caption[:4000]
                selected['attachment_notes']=notes
            c.execute('UPDATE operatorconversations SET input_context_json=%s::jsonb WHERE id=%s',(json.dumps(selected),item['conversation_id']))
            return item
        item=await asyncio.to_thread(transaction,save)
        await update.message.reply_text('Файл «'+item['original_name']+'» сохранён в LocalOS. Напишите или наговорите, что с ним сделать: пост, расписание или финансовые итоги.')
    except (ValueError,PermissionError):
        await update.message.reply_text('Не удалось принять файл. Проверьте доступ, формат и размер; поддерживаются фото, PDF, XLSX и CSV до 10 МБ.')
    return True
