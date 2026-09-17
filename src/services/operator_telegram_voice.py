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
        from services.operator_async_jobs import create_operator_async_job
        receipt = await asyncio.to_thread(transaction, lambda cursor: create_operator_async_job(cursor,
            user_id=business['user_id'], business_id=business['business_id'], action_id=None,
            kind='voice_receive', idempotency_key=f'tg:{update.effective_chat.id}:{update.message.message_id}',
            stage='Голосовое получено', payload={'file_id': voice.file_id, 'metadata': {
                'chat_id': update.effective_chat.id, 'business_name': business['business_name'],
                'delivery': 'pending', 'auto_submit': True, 'durable_execution': True}}))
        def acknowledged(cursor):
            cursor.execute('SELECT payload_json FROM operator_async_jobs WHERE id=%s',(receipt['id'],))
            return ((_row(cursor,cursor.fetchone()).get('payload_json') or {}).get('metadata') or {}).get('status_message_id')
        if await asyncio.to_thread(transaction,acknowledged):
            return
        notice = await update.message.reply_text('Голосовое получено. Распознаю и обработаю команду.')
        await asyncio.to_thread(transaction,lambda cursor:cursor.execute(
            "UPDATE operator_async_jobs SET payload_json=jsonb_set(payload_json,'{metadata,status_message_id}',to_jsonb(%s::bigint)) WHERE id=%s",(notice.message_id,receipt['id'])))
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
        logger.info('Operator reply speech skipped; text response retained')


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


async def submit_recognized_voice(application, host, asset):
    """Replay uses the same journal key, including after a delivery restart."""
    metadata = asset['metadata_json']
    chat_id = metadata['chat_id']
    if metadata.get('durable_execution'):
        if not metadata.get('status_message_id') and asset.get('request_id'):
            def receipt_metadata(cursor):
                cursor.execute('SELECT payload_json FROM operator_async_jobs WHERE user_id=%s AND idempotency_key=%s',(asset['user_id'],asset['request_id']))
                return (_row(cursor,cursor.fetchone()).get('payload_json') or {}).get('metadata') or {}
            receipt=await asyncio.to_thread(transaction,receipt_metadata)
            metadata={**metadata,'status_message_id':receipt.get('status_message_id')}
        payload = metadata.get('operator_payload')
        if not payload:
            return False
        business = {'user_id': asset['user_id'], 'business_id': asset['business_id'], 'telegram_id': str(chat_id)}
    else:
        business = await asyncio.to_thread(host._control_scope_business_context, str(chat_id))
        if not business or business['business_id'] != asset['business_id'] or business['user_id'] != asset['user_id']:
            await application.bot.send_message(chat_id=chat_id, text='Выбранный бизнес изменился. Отправьте команду заново для нужного бизнеса.')
            return
        if not metadata.get('transcript_delivered'):
            await application.bot.send_message(chat_id=chat_id, text='Распознано · '+str(metadata.get('business_name') or 'бизнес')+':\n\n'+asset['transcript'][:3500])
            await asyncio.to_thread(transaction, lambda cursor: cursor.execute(
                "UPDATE operator_audio_assets SET metadata_json=metadata_json || '{\"transcript_delivered\":true}'::jsonb WHERE id=%s", (asset['id'],)))
        business = dict(business)
        business['operator_payload'] = {'conversation_id': asset['conversation_id'], 'transcription_id': asset['id'], 'request_id': 'voice:'+asset['id']}
        payload = await asyncio.to_thread(host.build_operator_chat_payload, business, asset['transcript'])
    if not metadata.get('result_delivered'):
        from services.operator_request_history import mark_delivery
        try:
            if metadata.get('durable_execution') and metadata.get('status_message_id') and len(payload['text'])<=3500:
                await edit_progress(application,chat_id,metadata['status_message_id'],payload['text'],host._build_operator_result_markup(payload['result']))
            else:
                await application.bot.send_message(chat_id=chat_id, text=payload['text'], reply_markup=host._build_operator_result_markup(payload['result']))

        except Exception:
            await asyncio.to_thread(mark_delivery, payload['result'].get('request_audit_id'), 'failed')
            raise
        await asyncio.to_thread(mark_delivery, payload['result'].get('request_audit_id'), 'delivered')
        if metadata.get('durable_execution'):
            await asyncio.to_thread(transaction,lambda cursor:cursor.execute(
                "UPDATE operator_async_jobs SET result_json=COALESCE(result_json,'{}'::jsonb)||'{\"delivery_status\":\"delivered\"}'::jsonb WHERE user_id=%s AND idempotency_key=%s",
                (asset['user_id'],'voice-execute:'+asset['id'])))
        await asyncio.to_thread(transaction, lambda cursor: cursor.execute(
            "UPDATE operator_audio_assets SET metadata_json=metadata_json || '{\"result_delivered\":true}'::jsonb WHERE id=%s", (asset['id'],)))
        if metadata.get('durable_execution') and metadata.get('status_message_id') and len(payload['text'])>3500:
            try:
                await edit_progress(application,chat_id,metadata['status_message_id'],'Обработка завершена. Результат ниже.')
            except Exception:
                # The result is already delivered. A failed cosmetic status update must not resend it.
                logger.warning('Voice completion status update pending')

    if not payload['result'].get('error_code'):
        await queue_reply_speech(payload['result'], business, application)


async def delivery_loop(application, host):
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
                    AND asset.expires_at>NOW() AND job.status IN ('completed','failed','cancelled') ORDER BY asset.created_at, asset.id LIMIT 10""")
                return [_row(cursor,row) for row in cursor.fetchall()]
            await deliver_voice_progress(application)
            await deliver_plan_previews(application,host)
            assets=await asyncio.to_thread(transaction,pending)
            for asset in assets:
                try:
                    try:
                        await asyncio.to_thread(transaction,lambda cursor:authorize_actor(cursor,asset['user_id'],asset['business_id']))
                    except PermissionError:
                        await asyncio.to_thread(transaction,lambda cursor:cursor.execute("UPDATE operator_audio_assets SET metadata_json=metadata_json || '{\"delivery\":\"blocked\"}'::jsonb WHERE id=%s",(asset['id'],)))
                        continue
                    metadata=asset['metadata_json']; chat_id=metadata['chat_id']
                    def binding_matches(cursor):
                        cursor.execute('SELECT telegram_id FROM users WHERE id=%s',(asset['user_id'],))
                        return str(_row(cursor,cursor.fetchone()).get('telegram_id'))==str(chat_id)
                    if not await asyncio.to_thread(transaction,binding_matches):
                        await asyncio.to_thread(transaction,lambda cursor:cursor.execute(
                            "UPDATE operator_audio_assets SET metadata_json=metadata_json || '{\"delivery\":\"blocked\"}'::jsonb WHERE id=%s",(asset['id'],)))
                        continue

                    if asset['job_status']!='completed':
                        if asset['kind']=='speech':
                            await asyncio.to_thread(transaction,lambda cursor:cursor.execute("UPDATE operator_audio_assets SET metadata_json=metadata_json || '{\"delivery\":\"sent\"}'::jsonb WHERE id=%s",(asset['id'],)))
                            continue
                        await application.bot.send_message(chat_id=chat_id,text='Не удалось обработать аудио. Текстовые команды доступны; попробуйте новую запись.')
                    elif asset['kind']=='transcription' and metadata.get('auto_submit') and asset['status'] in {'ready','submitted'}:
                        delivered = await submit_recognized_voice(application, host, asset)
                        if delivered is False:
                            continue
                    elif asset['kind']=='transcription' and asset['status']=='ready':
                        await application.bot.send_message(chat_id=chat_id,text='Проверьте команду для '+str(metadata.get('business_name') or 'бизнеса')+':\n\n'+asset['transcript'][:3500],reply_markup=review_markup(asset['id']))
                    elif asset['kind']=='speech' and asset.get('path'):
                        content=await asyncio.to_thread(private_path(asset['path']).read_bytes)
                        await application.bot.send_voice(chat_id=chat_id,voice=content)
                    await asyncio.to_thread(transaction,lambda cursor:cursor.execute("UPDATE operator_audio_assets SET metadata_json=metadata_json || '{\"delivery\":\"sent\"}'::jsonb WHERE id=%s",(asset['id'],)))
                except Exception:
                    logger.warning('Operator audio item delivery failed; continuing other items')
        except asyncio.CancelledError:
            return
        except Exception:
            logger.warning('Operator audio delivery failed; retrying without message content')
        await asyncio.sleep(3)


async def deliver_plan_previews(application,host):
    def pending(cursor):
        cursor.execute("""SELECT j.*,p.telegram_id FROM operator_async_jobs j
            JOIN telegramcontrolpreferences p ON p.user_id=j.user_id
            WHERE j.kind='content_plan_revision' AND j.status IN ('completed','failed')
            AND j.payload_json->>'channel'='telegram' AND NOT (j.payload_json ? 'telegram_delivered')
            ORDER BY j.created_at LIMIT 10""")
        return [_row(cursor,value) for value in cursor.fetchall()]
    jobs=await asyncio.to_thread(transaction,pending)
    for job in jobs:
        chat_id=job['telegram_id']
        business=await asyncio.to_thread(host._control_scope_business_context,str(chat_id))
        if not business or business['business_id']!=job['business_id'] or business['user_id']!=job['user_id']:
            delivery='scope_changed'
        else:
            try:await asyncio.to_thread(transaction,lambda cursor:authorize_actor(cursor,job['user_id'],job['business_id']))
            except PermissionError:delivery='access_revoked'
            else:
                result=job.get('result_json') or {'status':'failed','chat_response':'Подготовить изменение плана не удалось. План остался прежним.'}
                await application.bot.send_message(chat_id=chat_id,text=result['chat_response'][:3500]+('\nПолный предпросмотр сохранён в диалоге Оператора в приложении.' if len(result['chat_response'])>3500 else ''),reply_markup=host._build_operator_result_markup(result))
                delivery='sent'
        await asyncio.to_thread(transaction,lambda cursor:cursor.execute("UPDATE operator_async_jobs SET payload_json=payload_json || %s::jsonb WHERE id=%s",(json.dumps({'telegram_delivered':delivery}),job['id'])))


async def deliver_voice_progress(application):
    """Transport-only receipt updates; never executes the user's command."""
    def pending(cursor):
        cursor.execute("""SELECT j.id,j.user_id,j.business_id,j.status,j.payload_json,
            EXTRACT(EPOCH FROM NOW()-j.created_at) elapsed,
            a.metadata_json audio_metadata,a.status audio_status FROM operator_async_jobs j
            LEFT JOIN operator_audio_assets a ON a.user_id=j.user_id AND a.business_id=j.business_id
                AND a.request_id=j.idempotency_key AND a.kind='transcription' AND a.channel='telegram'
            WHERE j.kind='voice_receive' AND j.created_at>NOW()-INTERVAL '24 hours'
                AND COALESCE(j.payload_json->>'progress_done','false')!='true'
            ORDER BY j.created_at LIMIT 30""")
        return [_row(cursor,row) for row in cursor.fetchall()]
    for job in await asyncio.to_thread(transaction,pending):
        try:
            metadata=job['payload_json']['metadata']
            audio=job.get('audio_metadata') or {}
            if audio.get('result_delivered') or audio.get('delivery')=='sent':
                await asyncio.to_thread(transaction,lambda cursor:cursor.execute(
                    "UPDATE operator_async_jobs SET payload_json=payload_json || '{\"progress_done\":true}'::jsonb WHERE id=%s",(job['id'],)))
                continue
            def permitted(cursor):
                authorize_actor(cursor,job['user_id'],job['business_id'])
                cursor.execute('SELECT telegram_id FROM users WHERE id=%s',(job['user_id'],))
                return str(_row(cursor,cursor.fetchone()).get('telegram_id'))==str(metadata['chat_id'])
            if not await asyncio.to_thread(transaction,permitted):
                continue
            failed=job['status'] in {'failed','cancelled'}
            message=('Не удалось получить запись из Telegram. Отправьте команду текстом или повторите запись.' if failed else
                     'Задание сохранено, ещё выполняется. Повторять сообщение не нужно.' if job['elapsed']>=15 else 'Обрабатываю команду.' if job.get('audio_status') in {'ready','submitted'} else 'Голосовое получено. Распознаю запись.')
            if job['payload_json'].get('progress_text')==message:
                continue
            message_id=metadata.get('status_message_id')
            if message_id:
                await edit_progress(application,metadata['chat_id'],message_id,message)
            else:
                sent=await application.bot.send_message(chat_id=metadata['chat_id'],text=message)
                message_id=sent.message_id
            await asyncio.to_thread(transaction,lambda cursor:cursor.execute(
                "UPDATE operator_async_jobs SET payload_json=jsonb_set(payload_json,'{metadata,status_message_id}',to_jsonb(%s::bigint)) || %s::jsonb WHERE id=%s",
                (message_id,json.dumps({'progress_text':message,'progress_done':failed}),job['id'])))
        except Exception:
            logger.warning('Voice progress delivery pending')


async def edit_progress(application,chat_id,message_id,text,reply_markup=None):
    from telegram.error import BadRequest
    try:
        await application.bot.edit_message_text(chat_id=chat_id,message_id=message_id,text=text,reply_markup=reply_markup)
    except BadRequest:
        import sys
        if 'message is not modified' not in str(sys.exception()).lower():
            raise
