"""Profile forms use the same registry, previews and approvals as Operator chat."""
import uuid
import sys
from flask import jsonify, request
from core.auth_helpers import require_auth_from_request, verify_business_access
from database_manager import DatabaseManager


def register_business_management_routes(bp):
    @bp.route('/business-management', methods=['GET', 'POST'])
    def business_management():
        from services.business_settings_registry import public_registry
        from services.business_team_management import role_options
        from services.business_chat_changes import read_profile, owned_businesses
        from services.business_permissions import load_actor, actor_roles, roles_allow
        from services.operator_business_management import preview
        from services.operator_conversations import get_or_create_operator_conversation, create_pending_operator_action
        from services.operator_chat_service import current_request_key
        user = require_auth_from_request()
        if not user:
            return jsonify({'error': 'Требуется авторизация'}), 401
        payload = request.get_json(silent=True) or {} if request.method == 'POST' else {}
        if not isinstance(payload, dict):
            return jsonify({'error': 'Некорректный запрос'}), 400
        business_id = request.args.get('business_id') or payload.get('business_id')
        if not business_id:
            return jsonify({'error': 'Выберите бизнес'}), 400
        db = DatabaseManager()
        try:
            cursor = db.conn.cursor()
            allowed, _ = verify_business_access(cursor, business_id, user)
            if not allowed:
                return jsonify({'error': 'Нет доступа к бизнесу'}), 403
            user_id = user.get('user_id') or user.get('id')
            actor = load_actor(cursor, user_id)
            actor.update({key: user[key] for key in ('session_kind', 'scope_business_id') if key in user})
            roles = actor_roles(cursor, business_id, actor)
            if request.method == 'GET':
                targets = owned_businesses(cursor, actor) if roles_allow(roles, 'team.manage') else []
                if actor.get('session_kind') == 'demo':
                    targets = [item for item in targets if item['id'] == actor.get('scope_business_id')]
                cursor.execute('SELECT n.owner_id FROM networks n JOIN businesses b ON b.network_id=n.id WHERE b.id=%s', (business_id,))
                from services.business_chat_changes import row
                network_owner = row(cursor,cursor.fetchone()).get('owner_id')
                can_manage_network = bool(network_owner and (network_owner == user_id or actor.get('is_superadmin')) and actor.get('session_kind') != 'demo')
                return jsonify({'fields': public_registry(), 'roles': role_options(), 'profile': read_profile(cursor,business_id),
                    'businesses': targets, 'can_manage_network':can_manage_network, 'can_manage_team': roles_allow(roles,'team.manage'), 'can_edit': roles_allow(roles,'business.settings.write')})
            kind = payload.get('kind')
            if kind not in {'settings', 'team'}:
                return jsonify({'error': 'Выберите действие'}), 400
            from services.operator_audio import authorize_actor
            from services.operator_core import operator_subscription_block
            _, access = authorize_actor(cursor, user_id, business_id)
            blocked = operator_subscription_block(access, 'settings.profile')
            if blocked:
                return jsonify({'operator_result': blocked}), 403
            arguments = payload.get('arguments')
            if not isinstance(arguments, dict):
                return jsonify({'error': 'Некорректные настройки'}), 400
            token = current_request_key.set(payload.get('request_id') or str(uuid.uuid4()))
            try:
                result = preview(cursor,business_id,user_id,arguments,kind=kind,channel='web',message='',session=user)
            finally:
                current_request_key.reset(token)
            if result.get('status') == 'approval_required':
                conversation = get_or_create_operator_conversation(cursor,business_id=business_id,user_id=user_id,channel='web',transport_key='business-profile')
                capability = 'team.manage' if kind == 'team' else 'settings.profile'
                action = create_pending_operator_action(cursor,conversation_id=conversation['id'],business_id=business_id,user_id=user_id,
                    capability=capability,envelope=result['approval']['envelope'],request_key=payload.get('request_id') or '')
                result['approval']['action_id'] = action['id']
                cursor.execute("UPDATE operatoractions SET expires_at=COALESCE(expires_at,NOW()+INTERVAL '30 minutes') WHERE id=%s", (action['id'],))
                cursor.execute("UPDATE operatoractions SET status='rejected',updated_at=NOW() WHERE conversation_id=%s AND capability=%s AND status IN ('pending','pending_approval') AND id<>%s", (conversation['id'],capability,action['id']))
            db.conn.commit()
            return jsonify({'operator_result': result})
        except PermissionError:
            db.conn.rollback()
            return jsonify({'error': 'Нет права изменять настройки или пользователей бизнеса'}), 403
        except ValueError:
            error = sys.exception()
            db.conn.rollback()
            return jsonify({'error': str(error)}), 400
        finally:
            db.rollback_and_close()
