"""Telegram voice transport; durable jobs and review state live in PostgreSQL."""
import asyncio
import json
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ForceReply
from database_manager import DatabaseManager
from services.operator_audio import (MAX_BYTES, create_transcription, create_speech, load_asset,
    private_path, authorize_actor, enabled)
from services.operator_conversations import _row

logger = logging.getLogger(__name__)


def review_markup(asset_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton('Отправить Оператору', callback_data='voice_send:'+asset_id)],
        [InlineKeyboardButton('Исправить',callback_data='voice_edit:'+asset_id),InlineKeyboardButton('Отменить',callback_data='voice_cancel:'+asset_id)]])


def transaction(operation):
    db=DatabaseManager()
    try:
        value=operation(db.conn.cursor())
        db.conn.commit()
        return value
    finally:
        db.close()


async def receive_voice(update, context, host):
    if update.effective_chat.type != 'private' or update.effective_user.is_bot:
        return
    telegram_id=str(update.effective_user.id)
    business=host._control_scope_business_context(telegram_id)
    if not business:
        await update.message.reply_text('Привяжите аккаунт и выберите конкретный бизнес через /control.')
        return
    if host.user_states.get(telegram_id,{}).get('state','idle') not in {'','idle'}:
        await update.message.reply_text('Сейчас ожидается ответ в открытой форме. Завершите её или нажмите /cancel, затем отправьте голосовое.')
        return
    voice=update.message.voice
    if voice.duration>120 or (voice.file_size or 0)>MAX_BYTES:
        await update.message.reply_text('Запись должна быть не длиннее 2 минут и не больше 10 МБ.')
        return
    try:
        await asyncio.to_thread(transaction,lambda cursor:authorize_actor(cursor,business['user_id'],business['business_id']))
        if not enabled('transcription',business['business_id']):
            await update.message.reply_text('Голосовой ввод пока недоступен для этого бизнеса. Напишите команду текстом.')
            return
        file=await context.bot.get_file(voice.file_id)
        content=bytes(await file.download_as_bytearray())
        await asyncio.to_thread(transaction,lambda cursor:create_transcription(cursor,content=content,user_id=business['user_id'],business_id=business['business_id'],
            channel='telegram',conversation_id=None,request_id=f'tg:{update.effective_chat.id}:{update.message.message_id}',
            metadata={'chat_id':update.effective_chat.id,'business_name':business['business_name'],'delivery':'pending'}))
        await update.message.reply_text('Распознаю запись. Затем покажу текст для проверки.')
    except (ValueError,PermissionError):
        await update.message.reply_text('Не удалось принять голосовое. Проверьте доступ, лимит запросов или отправьте команду текстом.')


async def queue_reply_speech(result,business,context):
    if not result.get('message_id') or not enabled('speech',business['business_id']):
        return
    def queue(cursor):
        asset=create_speech(cursor,user_id=business['user_id'],message_id=result['message_id'])
        cursor.execute("UPDATE operator_audio_assets SET metadata_json=metadata_json || %s::jsonb WHERE id=%s AND NOT (metadata_json ? 'delivery')",
                       (json.dumps({'chat_id':int(business['telegram_id']),'delivery':'pending'}),asset['asset_id']))
    try:
        await asyncio.to_thread(transaction,queue)
    except (ValueError,PermissionError):
        await context.bot.send_message(chat_id=business['telegram_id'],text='Озвучивание недоступно. Текст ответа сохранён.')


async def callback(update,context,host):
    data=update.callback_query.data or ''
    if not data.startswith(('voice_send:','voice_edit:','voice_cancel:','voice_speech:')):
        return False
    query=update.callback_query
    if query.message.chat.type != 'private':
        return True
    business=host._control_scope_business_context(str(query.from_user.id))
    if not business:
        await query.message.reply_text('Выберите бизнес через /control.')
        return True
    action,asset_id=data.split(':',1)
    try:
        if action=='voice_speech':
            await queue_reply_speech({'message_id':asset_id},business,context)
            return True
        asset=await asyncio.to_thread(transaction,lambda cursor:load_asset(cursor,asset_id,business['user_id'],business['business_id']))
        if asset['channel']!='telegram' or asset['status']!='ready':
            await query.message.reply_text('Запись уже отправлена, отменена или ещё не готова.')
            return True
        if action=='voice_cancel':
            await asyncio.to_thread(transaction,lambda cursor:cursor.execute("UPDATE operator_audio_assets SET status='cancelled' WHERE id=%s AND status='ready'",(asset_id,)))
            await query.edit_message_reply_markup(reply_markup=None)
        elif action=='voice_edit':
            prompt=await query.message.reply_text('Ответьте на это сообщение исправленным текстом команды.',reply_markup=ForceReply(selective=True))
            await asyncio.to_thread(transaction,lambda cursor:cursor.execute("UPDATE operator_audio_assets SET metadata_json=metadata_json || %s::jsonb WHERE id=%s",(json.dumps({'correction_message_id':prompt.message_id}),asset_id)))
        else:
            text=asset.get('corrected_text') or asset['transcript']
            business['operator_payload']={'conversation_id':asset['conversation_id'],'transcription_id':asset_id,'request_id':'voice:'+asset_id}
            payload=await asyncio.to_thread(host.build_operator_chat_payload,business,text)
            await query.message.reply_text(payload['text'],reply_markup=host._build_operator_result_markup(payload['result']))
            if not payload['result'].get('error_code'):
                await query.edit_message_reply_markup(reply_markup=None)
                await queue_reply_speech(payload['result'],business,context)
    except (ValueError,PermissionError):
        await query.message.reply_text('Запись недоступна. Проверьте выбранный бизнес или отправьте новую команду.')
    return True


async def correction(update,context,host):
    reply=update.message.reply_to_message
    if not reply or update.effective_chat.type!='private':
        return False
    user_id=host.get_user_id_from_telegram(str(update.effective_user.id))
    if not user_id:
        return False
    def find(cursor):
        cursor.execute("SELECT * FROM operator_audio_assets WHERE user_id=%s AND channel='telegram' AND status='ready' AND metadata_json->>'correction_message_id'=%s AND metadata_json->>'chat_id'=%s AND expires_at>NOW()",(user_id,str(reply.message_id),str(update.effective_chat.id)))
        asset=_row(cursor,cursor.fetchone())
        if asset:
            authorize_actor(cursor,user_id,asset['business_id'])
            cursor.execute("UPDATE operator_audio_assets SET corrected_text=%s WHERE id=%s",(update.message.text,asset['id']))
        return asset
    try:
        asset=await asyncio.to_thread(transaction,find)
        if not asset:
            return False
        await update.message.reply_text('Проверьте команду для '+str(asset['metadata_json'].get('business_name') or 'бизнеса')+':\n\n'+update.message.text,reply_markup=review_markup(asset['id']))
        return True
    except PermissionError:
        await update.message.reply_text('Доступ к этому бизнесу изменился.')
        return True


async def delivery_loop(application):
    while True:
        try:
            def pending(cursor):
                cursor.execute("SELECT to_regclass('public.operator_audio_assets')")
                row=cursor.fetchone()
                if not row or not (next(iter(row.values())) if isinstance(row,dict) else row[0]):
                    return []
                cursor.execute("""SELECT asset.*,job.status job_status FROM operator_audio_assets asset
                    JOIN operator_async_jobs job ON job.id=asset.job_id
                    WHERE asset.channel='telegram' AND asset.metadata_json->>'delivery'='pending'
                    AND asset.expires_at>NOW() AND job.status IN ('completed','failed','cancelled') LIMIT 10""")
                return [_row(cursor,row) for row in cursor.fetchall()]
            assets=await asyncio.to_thread(transaction,pending)
            for asset in assets:
                try:
                    await asyncio.to_thread(transaction,lambda cursor:authorize_actor(cursor,asset['user_id'],asset['business_id']))
                except PermissionError:
                    await asyncio.to_thread(transaction,lambda cursor:cursor.execute("UPDATE operator_audio_assets SET metadata_json=metadata_json || '{\"delivery\":\"blocked\"}'::jsonb WHERE id=%s",(asset['id'],)))
                    continue
                metadata=asset['metadata_json']; chat_id=metadata['chat_id']
                if asset['job_status']!='completed':
                    await application.bot.send_message(chat_id=chat_id,text='Не удалось обработать аудио. Текстовые команды доступны; попробуйте новую запись.')
                elif asset['kind']=='transcription' and asset['status']=='ready':
                    await application.bot.send_message(chat_id=chat_id,text='Проверьте команду для '+str(metadata.get('business_name') or 'бизнеса')+':\n\n'+asset['transcript'][:3500],reply_markup=review_markup(asset['id']))
                elif asset['kind']=='speech' and asset.get('path'):
                    content=await asyncio.to_thread(private_path(asset['path']).read_bytes)
                    await application.bot.send_voice(chat_id=chat_id,voice=content)
                await asyncio.to_thread(transaction,lambda cursor:cursor.execute("UPDATE operator_audio_assets SET metadata_json=metadata_json || '{\"delivery\":\"sent\"}'::jsonb WHERE id=%s",(asset['id'],)))
        except asyncio.CancelledError:
            return
        except Exception:
            logger.warning('Operator audio delivery failed; retrying without message content')
        await asyncio.sleep(3)
