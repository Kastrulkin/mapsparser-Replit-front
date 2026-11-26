"""First setup endpoints on the existing LocalOS chat surface."""
import logging
import re

from flask import Blueprint, jsonify, request, send_file

from core.auth_helpers import require_auth_from_request
from database_manager import DatabaseManager
from services import initial_business_setup as setup
from services.business_permissions import actor_roles, roles_allow


initial_setup_bp = Blueprint('initial_business_setup', __name__, url_prefix='/api/operator/initial-setup')
logger = logging.getLogger(__name__)


def reply(value, status=200):
    response = jsonify(value)
    response.headers['Cache-Control'] = 'no-store'
    return response, status


def payload():
    if request.content_length and request.content_length > 16000:
        raise ValueError('Сообщение слишком длинное.')
    value = request.get_json(silent=True)
    if not isinstance(value, dict):
        raise ValueError('Укажите действие настройки.')
    return value


def setup_for_viewer(cursor, row, profile, can_edit, actor_id):
    if not row:
        return None
    result = setup.status(cursor, row, profile, can_edit)
    result['viewer_is_owner'] = str(profile['owner_id']) == str(actor_id)
    return result


@initial_setup_bp.get('/availability')
def staff_availability():
    actor = require_auth_from_request()
    if not actor or not actor.get('is_superadmin') or actor.get('session_kind') == 'demo':
        return reply({'available': False}, 403)
    if not setup.enabled():
        return reply({'available': False})
    db = DatabaseManager()
    try:
        return reply({'available': setup.installed(db.conn.cursor()), 'business_ids': sorted(setup.targets('BUSINESS')), 'lead_ids': sorted(setup.targets('LEAD'))})
    finally:
        db.rollback_and_close()


@initial_setup_bp.route('/<business_id>', methods=['GET', 'POST'])
def business_setup(business_id):
    actor = require_auth_from_request()
    if not actor or actor.get('session_kind') == 'demo':
        return reply({'error': 'Требуется вход.'}, 401)
    db = DatabaseManager()
    try:
        cursor = db.conn.cursor()
        if not setup.actor_allowed(cursor, business_id, actor):
            return reply({'available': False})
        roles = actor_roles(cursor, business_id, actor)
        if not roles_allow(roles, 'business.read'):
            return reply({'error': 'Нет доступа к компании.'}, 403)
        can_edit = roles_allow(roles, 'business.settings.write')
        if request.method == 'GET':
            row = setup.load(cursor, business_id)
            profile = setup.read_business(cursor, business_id)
            if not profile:
                return reply({'error': 'Компания недоступна.'}, 404)
            return reply({'available': True, 'can_edit': can_edit,
                          'setup': setup_for_viewer(cursor, row, profile, can_edit, actor['user_id'])})
        if not can_edit:
            return reply({'error': 'Настройку может сохранить владелец или сотрудник с правом настройки.'}, 403)
        data = payload()
        profile = setup.read_business(cursor, business_id, lock=True)
        if not profile:
            return reply({'error': 'Компания недоступна.'}, 404)
        row = setup.load(cursor, business_id, lock=True)
        if data.get('action') == 'start':
            if not row:
                row = setup.init(cursor, business_id, 'staff' if actor.get('is_superadmin') else 'owner')
            setup.seed_profile_sources(cursor, row, profile)
            setup.queue_added(cursor, row, actor['user_id'])
            row['data']['started'] = True
            message = 'Подготовка началась. Данные компании уже в карточке.'
            if data.get('message'):
                message += ' ' + setup.intake_message(cursor, row, actor, profile, data)
        elif not row:
            return reply({'error': 'Сначала начните первичную настройку.'}, 409)
        else:
            if data.get('revision') != row['revision']:
                raise setup.Conflict('Данные обновились. Проверьте свежий результат и повторите действие.')
            message = setup.operate(cursor, row, actor, profile, data)
        setup.persist(cursor, row)
        profile = setup.read_business(cursor, business_id)
        result = setup_for_viewer(cursor, row, profile, can_edit, actor['user_id'])
        db.conn.commit()
        return reply({'available': True, 'setup': result, 'message': message})
    except setup.Conflict as error:
        return reply({'error': str(error)}, 409)
    except PermissionError:
        return reply({'error': 'Нет права на это действие.'}, 403)
    except ValueError as error:
        return reply({'error': str(error)}, 400)
    except Exception as error:
        logger.warning('Initial business setup failed: %s', type(error).__name__)
        return reply({'error': 'Не удалось сохранить настройку. Повторите позже.'}, 503)
    finally:
        db.rollback_and_close()


@initial_setup_bp.get('/<business_id>/report')
def download_setup_report(business_id):
    from services.initial_setup_report import render_report

    actor = require_auth_from_request()
    if not actor or actor.get('session_kind') == 'demo':
        return reply({'error': 'Требуется вход.'}, 401)
    db = DatabaseManager()
    try:
        cursor = db.conn.cursor()
        if not setup.actor_allowed(cursor, business_id, actor):
            return reply({'error': 'Отчёт недоступен.'}, 404)
        if not roles_allow(actor_roles(cursor, business_id, actor), 'business.read'):
            return reply({'error': 'Нет доступа к отчёту.'}, 403)
        row = setup.load(cursor, business_id)
        profile = setup.read_business(cursor, business_id)
        if not row or not profile:
            return reply({'error': 'Отчёт ещё не подготовлен.'}, 409)
        state = setup.status(cursor, row, profile, False)
        state['report_follow_up'] = row['data'].get('report_follow_up')
    finally:
        db.rollback_and_close()
    if not state['report_ready']:
        return reply({'error': 'Подождите, пока подготовится отчёт.'}, 409)
    response = send_file(render_report(state), mimetype='application/pdf', as_attachment=True,
                         download_name='localos-initial-setup.pdf')
    response.headers['Cache-Control'] = 'private, no-store'
    return response


@initial_setup_bp.route('/<business_id>/next-steps', methods=['GET', 'POST'])
def next_steps(business_id):
    from services import setup_content_journey as journey

    actor = require_auth_from_request()
    if not actor or actor.get('session_kind') == 'demo':
        return reply({'error': 'Требуется вход.'}, 401)
    db = DatabaseManager()
    try:
        cursor = db.conn.cursor()
        if not setup.actor_allowed(cursor, business_id, actor):
            return reply({'error': 'Настройка компании недоступна.'}, 404)
        roles = actor_roles(cursor, business_id, actor)
        if not roles_allow(roles, 'business.read'):
            return reply({'error': 'Нет доступа к компании.'}, 403)
        can_edit = roles_allow(roles, 'business.settings.write')
        review = request.method == 'POST'
        if review:
            journey.lock(cursor, business_id)
        profile = setup.read_business(cursor, business_id, lock=review)
        row = setup.load(cursor, business_id, lock=review)
        if not profile or not row or not setup._cabinet_saved(row, profile):
            return reply({'error': 'Сначала сохраните кабинет.'}, 409)
        if review:
            result = journey.update(cursor, row, profile, actor, can_edit, payload())
            db.conn.commit()
        else:
            result = journey.state(cursor, row, profile, actor, can_edit)
        return reply(result)
    except setup.Conflict as error:
        return reply({'error': str(error)}, 409)
    except PermissionError as error:
        return reply({'error': str(error)}, 403)
    except ValueError as error:
        return reply({'error': str(error)}, 400)
    except Exception as error:
        logger.warning('Initial setup content steps failed: %s', type(error).__name__)
        return reply({'error': 'Не удалось загрузить следующие шаги. Попробуйте ещё раз.'}, 503)
    finally:
        db.rollback_and_close()


@initial_setup_bp.route('/lead/<lead_id>', methods=['POST'])
def setup_from_lead(lead_id):
    actor = require_auth_from_request()
    if not actor or actor.get('session_kind') == 'demo':
        return reply({'error': 'Требуется вход.'}, 401)
    if not actor.get('is_superadmin'):
        return reply({'error': 'Нужен доступ к подготовке клиентских аккаунтов.'}, 403)
    # Under an explicit cohort only existing businesses may be used.
    if not setup.lead_allowed(lead_id):
        return reply({'error': 'Подготовка лида сейчас недоступна.'}, 404)
    db = DatabaseManager()
    try:
        cursor = db.conn.cursor()
        if not setup.installed(cursor):
            return reply({'error': 'Подготовка лида сейчас недоступна.'}, 404)
        cursor.execute('SELECT * FROM prospectingleads WHERE id=%s FOR UPDATE', (lead_id,))
        lead = cursor.fetchone()
        if not lead or not setup.clean(lead.get('name'), 250):
            return reply({'error': 'Лид не найден.'}, 404)
        cursor.execute('SELECT business_id FROM initial_business_setups WHERE lead_id=%s', (lead_id,))
        prior = cursor.fetchone()
        if prior:
            return reply({'business_id': prior['business_id']})
        business_id = setup.start_lead(db, cursor, dict(lead), actor['user_id'])
        db.conn.commit()
        return reply({'business_id': business_id}, 201)
    except setup.Conflict as error:
        return reply({'error': str(error)}, 409)
    except ValueError as error:
        return reply({'error': str(error)}, 400)
    except Exception as error:
        logger.warning('Initial setup from lead failed: %s', type(error).__name__)
        return reply({'error': 'Не удалось подготовить кабинет этого лида.'}, 503)
    finally:
        db.rollback_and_close()


@initial_setup_bp.route('/<business_id>/owner', methods=['POST'])
def setup_owner(business_id):
    actor = require_auth_from_request()
    if not actor or actor.get('session_kind') == 'demo':
        return reply({'error': 'Требуется вход.'}, 401)
    if not actor.get('is_superadmin'):
        return reply({'error': 'Нужен доступ к подготовке клиентских аккаунтов.'}, 403)
    db = DatabaseManager()
    try:
        cursor = db.conn.cursor()
        if not setup.actor_allowed(cursor, business_id, actor):
            return reply({'error': 'Подготовка кабинета сейчас недоступна.'}, 404)
        data = payload()
        email = str(data.get('email') or '').strip().lower()
        if len(email) > 254 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email):
            raise ValueError('Укажите email владельца.')
        result = setup.prepare_owner(cursor, business_id, actor['user_id'], email, data.get('revision'))
        db.conn.commit()
        return reply(result)
    except setup.Conflict as error:
        return reply({'error': str(error)}, 409)
    except ValueError as error:
        return reply({'error': str(error)}, 400)
    except Exception as error:
        logger.warning('Initial setup owner assignment failed: %s', type(error).__name__)
        return reply({'error': 'Не удалось подготовить доступ.'}, 503)
    finally:
        db.rollback_and_close()
