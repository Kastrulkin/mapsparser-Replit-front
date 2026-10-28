"""Platform context for the existing owner dialogues; Telegram is the default.

MAX sets a context only after webhook identity validation. ContextVars also flow
through asyncio.to_thread, without altering a Telegram worker's identity/state.
"""
from collections.abc import MutableMapping
from contextvars import ContextVar
from dataclasses import dataclass, field


@dataclass
class OwnerBotContext:
    external_id: str
    actor: dict | None
    state: dict
    event_key: str
    cursor: object
    request_audit_ids: list = field(default_factory=list)


current_owner_bot = ContextVar('localos_owner_bot_context', default=None)


def owner_bot_platform():
    return 'max' if current_owner_bot.get() is not None else 'telegram'


def owner_bot_channel():
    return 'max_bot' if current_owner_bot.get() is not None else 'telegram'


def owner_bot_user(external_id):
    context = current_owner_bot.get()
    if context is None:
        return None
    if str(external_id) != context.external_id:
        raise PermissionError('Неверная личность мессенджера')
    return context.actor or {}


class OwnerBotStates(MutableMapping):
    """Keep the Telegram mapping API, route MAX state to its durable event scope."""
    def __init__(self):
        self.telegram_states = {}

    def _mapping(self, key):
        context = current_owner_bot.get()
        if context is None:
            return self.telegram_states
        if str(key) != context.external_id:
            raise PermissionError('Чужое состояние диалога')
        return context.state

    def __getitem__(self, key):
        return self._mapping(key)[str(key)]

    def __setitem__(self, key, value):
        self._mapping(key)[str(key)] = value

    def __delitem__(self, key):
        del self._mapping(key)[str(key)]

    def __iter__(self):
        context = current_owner_bot.get()
        return iter(context.state if context is not None else self.telegram_states)

    def __len__(self):
        context = current_owner_bot.get()
        return len(context.state if context is not None else self.telegram_states)


def owner_bot_operation_key():
    import uuid
    context = current_owner_bot.get()
    if context is None:
        return str(uuid.uuid4())
    counter = getattr(context, 'operation_counter', 0) + 1
    context.operation_counter = counter
    return 'max:' + context.event_key + ':' + str(counter)


def owner_bot_request_payload(original):
    context = current_owner_bot.get()
    if context is None:
        return original
    return {**(original or {}), 'request_id': 'max:' + context.event_key, **getattr(context, 'input_payload', {})}


def update_business_setting(cursor, *, user_id, business_id, setting, text):
    from services.business_permissions import require_permission
    from services.operator_conversations import _row
    cursor.execute('SELECT id,is_superadmin,is_active FROM users WHERE id=%s', (user_id,))
    actor = _row(cursor, cursor.fetchone())
    if not actor or actor.get('is_active') is False:
        raise PermissionError('Аккаунт недоступен')
    require_permission(cursor, business_id, actor, 'business.settings.write')
    fields = {'name': 'name', 'address': 'address', 'hours': 'working_hours', 'phone': 'phone', 'maps': 'yandex_url'}
    field_name = fields.get(setting)
    if not field_name or not text.strip() or len(text) > (2048 if setting == 'maps' else 1000):
        raise ValueError('Проверьте новое значение настройки')
    if setting == 'maps':
        from services.telegram_lead_intake import parse_map_links_from_text
        parsed = parse_map_links_from_text(text)
        items = parsed.get('valid_items') or []
        if len(items) != 1 or items[0].get('source') != 'yandex':
            raise ValueError('Пришлите одну ссылку на Яндекс Карты. Остальные источники подключаются в кабинете.')
        text = items[0]['normalized_url']
    cursor.execute('UPDATE businesses SET ' + field_name + '= %s,updated_at=CURRENT_TIMESTAMP WHERE id=%s', (text.strip(), business_id))
