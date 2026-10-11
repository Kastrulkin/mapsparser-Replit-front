"""Authorized maintenance: preserve old versions and prepare a paused candidate.

No approval, activation, dispatch or Telegram send. Execute in app container.
"""
import json
import os
from database_manager import DatabaseManager
from services.agent_blueprint_creation import _content_handoff_draft
from services.agent_version_store import insert_version
from services.compiled_content_program import authorize_contract, contract_for, delivery_context

BLUEPRINT = 'd61580b3-55f9-5cef-97ba-59f702a14216'
ACTOR = 'a453a8b3-3b26-4c4e-81e3-1b973d4b8755'
ANCHOR = 'cb674174-8b3d-41a3-8277-525c849935f2'
SECOND = '0f67ac22-132f-41e7-b473-667c46f364fa'
SCOPE = {
    'business_ids': [ANCHOR, SECOND],
    'recipient_user_ids': [ACTOR, '26e098e5-9fe4-4557-824e-ba1ba3c54b47'],
    'plan_ids': {ANCHOR: ['55d2eb84-7206-4f38-9c8f-89f313226ceb'], SECOND: ['f435003e-f7c8-43f9-ad81-89c9c3999f8d']},
    'renewal': {'period_days': 30, 'reviewer_user_id': ACTOR},
}
DESCRIPTION = 'Энгельса, 154 и Долгоозёрная, ТРК «5 озёр»: ежедневно в 10:00 Europe/Moscow передавать Ирине и Алексею готовые фото и версии Telegram/VK/MAX на следующий день. После последнего пакета каждому филиалу — уведомление Алексею и новый план на 30 дней на свежих данных, только на его проверку. Без публикации на площадках; без повторов и отправки задним числом.'


def main():
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        cursor.execute('SELECT * FROM agent_blueprints WHERE id=%s FOR UPDATE', (BLUEPRINT,))
        previous = dict(cursor.fetchone() or {})
        if previous.get('status') not in {'draft', 'paused'} or str(previous.get('business_id')) != ANCHOR:
            raise ValueError('Pilot changed; inspect before preparing')
        draft = _content_handoff_draft(DESCRIPTION, business_id=ANCHOR, recipient_user_id=ACTOR,
            conditions={'trigger': 'schedule.daily', 'schedule': {'time': '10:00', 'timezone': 'Europe/Moscow'}}, network_scope=SCOPE)
        payload = draft['version_payload']
        contract = contract_for(payload, ANCHOR)
        authorize_contract(cursor, contract, ACTOR)
        context = delivery_context(cursor, contract)
        cursor.execute('SELECT * FROM agent_blueprint_versions WHERE blueprint_id=%s ORDER BY version_number', (BLUEPRINT,))
        versions = [dict(row) for row in cursor.fetchall()]
        backup_path = '/tmp/content-network-pilot-before.json'
        descriptor = os.open(backup_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, 'w') as stream:
            json.dump({'blueprint': previous, 'versions': versions}, stream, default=str, ensure_ascii=False)
        version = insert_version(cursor, BLUEPRINT, payload, {'user_id': ACTOR})
        cursor.execute('UPDATE agent_blueprints SET description=%s,updated_at=NOW() WHERE id=%s', (DESCRIPTION, BLUEPRINT))
        db.conn.commit()
        print(json.dumps({'candidate_version_id': str(version['id']), 'version_number': version['version_number'],
            'targets': [{key: row[key] for key in ['business_name', 'address', 'recipient_name', 'telegram_id']} for row in context['targets']],
            'backup': backup_path, 'activated': False}, ensure_ascii=False))
    finally:
        db.close()


if __name__ == '__main__':
    main()
