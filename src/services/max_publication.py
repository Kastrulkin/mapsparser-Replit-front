"""MAX channel publication within the existing immutable social-post approval."""
import json
import os
import sys
import re

from services.max_tls import max_ssl_context
from services.max_transport import MaxTransport, MaxTransportError


def max_publish_enabled(chat_id=None):
    from services.max_webapp_auth import max_enabled
    if not max_enabled():
        return False
    if os.getenv('MAX_PUBLISH_ENABLED', 'false').lower() in {'true', '1', 'yes', 'on'}:
        return True
    allowed = {value.strip() for value in os.getenv('MAX_PUBLISH_CHAT_IDS', '').split(',') if value.strip()}
    return bool(allowed) if chat_id is None else str(chat_id) in allowed


def probe_channel(transport, chat_id):
    if not re.fullmatch(r'-?[0-9]{1,20}', str(chat_id)):
        raise ValueError('Укажите числовой ID канала MAX')
    bot = transport.call('GET', '/me')
    chat = transport.call('GET', '/chats/' + str(chat_id))
    member = transport.call('GET', '/chats/' + str(chat_id) + '/members/me')
    if chat.get('type') != 'channel' or str(chat.get('chat_id')) != str(chat_id):
        raise ValueError('Выберите канал MAX')
    if not bot.get('is_bot') or not bot.get('user_id') or str(member.get('user_id')) != str(bot['user_id']):
        raise ValueError('Не удалось подтвердить бота MAX')
    if not (member.get('is_owner') or (member.get('is_admin') and {'write', 'post_edit_delete_message'}.intersection(member.get('permissions') or []))):
        raise PermissionError('Боту нужно право публикации в канале MAX')
    return {'bot_id': str(bot['user_id']), 'chat_id': str(chat_id), 'title': str(chat.get('title') or chat_id)}


def upload_media(transport, asset):
    from services.social_posts.media_delivery import _media_asset_file, _multipart_form_data
    from core.outbound_network import public_pinned_https_post
    file = _media_asset_file(asset)
    if not file:
        raise ValueError('Выбранное медиа недоступно')
    mime = file['mime_type']
    kind = 'image' if mime.startswith('image/') else 'video' if mime.startswith('video/') else 'audio' if mime.startswith('audio/') else 'file'
    ticket = transport.call('POST', '/uploads', params={'type': kind})
    data, content_type = _multipart_form_data({}, [{**file, 'field_name': 'data'}])
    # Upload URLs are provider-issued; pin the public address, verify TLS and never forward the bot token.
    uploaded = public_pinned_https_post(ticket.get('url') or '', data, {'Content-Type': content_type}, timeout=30, ssl_context=max_ssl_context())
    if not 200 <= uploaded.status_code < 300:
        raise ValueError('Не удалось загрузить медиа в MAX')
    result = json.loads(uploaded.body)
    token = result.get('token') or ticket.get('token')
    if token:
        return {'type': kind, 'payload': {'token': token}}
    if kind == 'image' and isinstance(result.get('photos'), dict) and result['photos']:
        return {'type': kind, 'payload': {'photos': result['photos']}}
    raise ValueError('MAX не подтвердил загрузку медиа')


def publish_max_post(cursor, post, snapshot):
    from services.social_posts.approval_binding import (
        frozen_external_account, _account_auth_data, snapshot_is_well_formed, snapshot_is_sendable,
        current_snapshot_matches, approval_binding_drift_result,
    )
    from services.social_posts.media_delivery import _approved_media_assets
    if not max_publish_enabled():
        return {'status': 'needs_manual_publish', 'last_error': 'Публикация в MAX пока не включена.', 'publish_outcome': 'not_attempted'}
    if not snapshot_is_well_formed(snapshot, post) or not snapshot_is_sendable(snapshot, post) or not current_snapshot_matches(cursor, post, snapshot):
        return approval_binding_drift_result('max_approval_binding_drift')
    account, binding = frozen_external_account(cursor, post, snapshot, 'max')
    if not account or account.get('source') != 'max_bot':
        return approval_binding_drift_result('max_connection_changed')
    if not max_publish_enabled(account.get('external_id')):
        return {'status': 'needs_manual_publish', 'last_error': 'Публикация в этот канал MAX пока не включена.', 'publish_outcome': 'not_attempted'}
    auth = _account_auth_data(account)
    if not auth.get('bot_token'):
        return approval_binding_drift_result('max_credentials_missing')
    text = str(post.get('platform_text') or post.get('base_text') or '').strip()
    if not text or len(text) > 4000:
        return {'status': 'needs_review', 'last_error': 'Для MAX нужен текст от 1 до 4000 символов.', 'publish_outcome': 'not_attempted'}
    media = _approved_media_assets(cursor, post, snapshot)
    if media is None:
        return approval_binding_drift_result('max_approval_media_drift')
    transport = MaxTransport(auth.get('bot_token'))
    attempted = False
    try:
        target = probe_channel(transport, str(account.get('external_id')))
        if target['bot_id'] != str((binding.get('sender') or {}).get('bot_id')):
            return approval_binding_drift_result('max_sender_changed')
        attachments = [upload_media(transport, item) for item in media]
        # Re-read the immutable selection after potentially slow uploads.
        if not current_snapshot_matches(cursor, post, snapshot):
            return approval_binding_drift_result('max_approval_binding_drift')
        probe_channel(transport, target['chat_id'])
        attempted = True
        result = transport.call('POST', '/messages', params={'chat_id': target['chat_id']}, body={'text': text, 'attachments': attachments})
        message = result.get('message') or {}
        mid = str((message.get('body') or {}).get('mid') or '')
        if not mid:
            return {'status': 'failed', 'last_error': 'MAX не подтвердил идентификатор поста. Проверьте канал перед повтором.', 'publish_outcome': 'uncertain'}
        return {'status': 'published', 'provider_post_id': mid, 'provider_post_url': message.get('url') or '',
                'publish_outcome': 'accepted', 'metadata_json': {'provider_status': 'max_published', 'external_publish_performed': True}}
    except MaxTransportError:
        error = sys.exception()
        return {'status': 'failed', 'last_error': 'Не удалось подтвердить публикацию MAX. Проверьте результат в канале.',
                'publish_outcome': 'uncertain' if attempted and error.uncertain else 'rejected' if attempted else 'not_attempted',
                'metadata_json': {'provider_status': error.code}}
    except (ValueError, PermissionError):
        return {'status': 'needs_review', 'last_error': 'Проверьте канал, права бота и выбранные медиа MAX.',
                'publish_outcome': 'uncertain' if attempted else 'not_attempted'}
