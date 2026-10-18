"""Daily team brief on the existing authenticated Operator boundary."""
from flask import request, jsonify
from core.auth_helpers import require_auth_from_request
from database_manager import DatabaseManager
from services import operator_day_brief
from services.operator_conversations import create_pending_operator_action


def register_day_brief_routes(bp):
    def run(handler):
        user = require_auth_from_request()
        if not user:
            return jsonify({'error': 'Требуется авторизация'}), 401
        db = DatabaseManager()
        try:
            payload = request.get_json(silent=True) or {}
            if not isinstance(payload, dict):
                raise ValueError('Проверьте параметры запроса.')
            business = request.args.get('business_id') or payload.get('business_id')
            uid = str(user.get('user_id') or user.get('id') or '')
            if user.get('session_kind') == 'demo':
                raise PermissionError('Планёрка недоступна в демонстрационном сеансе.')
            c = db.conn.cursor()
            value = handler(c, business, uid, payload)
            db.conn.commit()
            response = jsonify(value)
            response.headers['Cache-Control'] = 'no-store'
            return response
        except (ValueError, PermissionError):
            import sys
            error = sys.exception()
            db.conn.rollback()
            return jsonify({'error': str(error)}), 403 if isinstance(error, PermissionError) else 400
        except Exception:
            db.conn.rollback()
            raise
        finally:
            db.close()

    @bp.route('/day-brief', methods=['GET', 'POST'])
    def day_brief():
        def handle(c, b, u, p):
            if request.method == 'GET':
                return operator_day_brief.overview(c, business=b, user=u, day=request.args.get('date'), item_id=request.args.get('item_id'))
            saved = operator_day_brief.save(c, business=b, user=u, payload=p, channel=p.get('channel') or 'web')
            if p.get('transcription_id') and not saved.get('idempotent'):
                from services.operator_audio import consume_transcription
                consume_transcription(c, p['transcription_id'], u, b, p.get('conversation_id'), p.get('focus'))
            return {'draft': saved}
        return run(handle)

    @bp.route('/day-brief/preview', methods=['POST'])
    def day_brief_preview():
        def prepare(c, b, u, p):
            value = operator_day_brief.prepare(c, business=b, user=u, identifier=p.get('record_id'), version=p.get('version'))
            action = create_pending_operator_action(c, conversation_id=p['record_id'], business_id=b, user_id=u,
                capability='work.day_brief', envelope=value['approval']['envelope'])
            value['approval'].update(action_id=action['id'], status=action['status'])
            return value
        return run(prepare)

    @bp.route('/day-brief/task', methods=['POST'])
    def day_brief_task():
        return run(lambda c, b, u, p: operator_day_brief.complete_task(c, business=b, user=u,
            action_id=p.get('action_id'), task_id=p.get('task_id'), version=p.get('version'), done=p.get('done')))
