"""MAX/Telegram platform outreach using the existing chat approval lifecycle."""
from flask import jsonify, request

from core.auth_helpers import require_auth_from_request
from database_manager import DatabaseManager
from services import operator_platform_outreach
from services.telegram_control_scope import resolve_control_scope


def platform_actor(cursor, actor):
    user_id = str(actor.get('user_id') or actor.get('id') or '')
    business = operator_platform_outreach.require_platform_actor(cursor, user_id, actor)
    scope = resolve_control_scope(cursor, user_id=user_id, requested_kind='platform',
        platform=str(actor.get('messenger_platform') or 'telegram'))
    if not scope or scope.get('kind') != 'platform':
        raise PermissionError('Нет доступа к платформе LocalOS')
    return user_id, str(business['id'])


def search_preview(cursor, *, actor, user_id, business_id, payload):
    from services.operator_chat_service import process_chat
    from services.outreach_continuation import operator_task
    config = {key: payload.get(key) for key in ('audience', 'search_geography', 'target_count')}
    config.update(mode='find_only', search_source='web')
    if payload.get('web_search_provider'):
        config['web_search_provider'] = payload['web_search_provider']
    # Include the exact conditions in the idempotency digest, including provider.
    geography = config.get('search_geography')
    if not isinstance(geography, list) or any(not isinstance(place, str) for place in geography):
        raise ValueError('Укажите географию поиска')
    provider = 'Яндекс' if config.get('web_search_provider') == 'yandex' else 'веб-поиск'
    message = (f"Найти {config.get('target_count')} компаний: {config.get('audience')}. "
               f"Где: {'; '.join(geography)}. Источник: {provider}. Только поиск и проверка, без писем и отправки.")
    def router(_cursor, **context):
        result = operator_task(_cursor, business_id=business_id, user_id=user_id,
            arguments={'operation': 'preview', 'config': config}, actor_context=actor)
        return {**result, 'capability': 'partnerships.continue_outreach'}, {}
    channel = 'max_mini_app' if actor.get('messenger_platform') == 'max' else 'telegram_mini_app'
    return process_chat(cursor, business_id=business_id, user_id=user_id, channel=channel,
        message=message, router=router, actor_context=actor, payload={'request_id': payload.get('request_id')})


def register_platform_outreach_routes(blueprint):
    @blueprint.route('/mobile/outreach', methods=['GET', 'POST'])
    @blueprint.route('/mobile/platform/outreach', methods=['GET', 'POST'])
    def platform_outreach():
        actor = require_auth_from_request()
        if not actor:
            return jsonify({'success': False, 'error': 'Требуется авторизация'}), 401
        db = DatabaseManager()
        try:
            cursor = db.conn.cursor()
            payload = (request.get_json(silent=True) or {}) if request.method == 'POST' else request.args
            if not hasattr(payload, 'get'):
                raise ValueError('Ожидается запрос')
            user_id = str(actor.get('user_id') or actor.get('id') or '')
            legacy = request.path.endswith('/platform/outreach')
            kind = 'platform' if legacy else str(payload.get('scope_kind') or payload.get('scope_type') or '')
            scope = operator_platform_outreach.require_outreach_scope(cursor,user_id=user_id,
                scope_kind=kind,scope_id=payload.get('scope_id'),actor=actor,write=request.method=='POST')
            target = payload.get('target_business_id')
            if target:
                if kind != 'platform' and str(target) != scope['business_id']:
                    raise PermissionError('Недоступный целевой бизнес')
                if kind == 'platform':
                    scope = operator_platform_outreach.require_outreach_scope(cursor,user_id=user_id,
                        scope_kind='business',scope_id=str(target),actor=actor,write=request.method=='POST')
            operator_platform_outreach.require_outreach_capability(scope)
            business_id = scope['business_id']
            current_actor = {**actor, **scope['actor']}
            if request.method == 'GET':
                result = operator_platform_outreach.workspace(cursor, limit=request.args.get('limit', 20),
                    before=request.args.get('cursor'),scope=scope,user_id=user_id)
            else:
                if payload.get('action') == 'sync':
                    result = {'job': operator_platform_outreach.enqueue_reply_sync(cursor,
                        user_id=user_id, request_id=payload.get('request_id'),scope=scope,actor=current_actor)}
                elif payload.get('action') == 'search_preview':
                    result = {'business_id': business_id, 'operator_result': search_preview(cursor,
                        actor=current_actor, user_id=user_id, business_id=business_id, payload=payload)}
                else:
                    raise ValueError('Неизвестное действие')
                db.conn.commit()
            return jsonify({'success': True, **result})
        except PermissionError:
            db.conn.rollback()
            return jsonify({'success': False, 'error': 'Нет доступа к выбранной области LocalOS'}), 403
        except (ValueError, TypeError):
            db.conn.rollback()
            return jsonify({'success': False, 'error': 'Проверьте параметры запроса и условия поиска'}), 400
        except Exception:
            db.conn.rollback()
            return jsonify({'success': False, 'error': 'Не удалось загрузить аутрич. Повторите запрос.'}), 500
        finally:
            db.close()
