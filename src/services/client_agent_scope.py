"""Business ownership guard for saved customer-facing persona selections."""
import json


def validate_selection(cursor, business_id, data):
    ids = set()
    if data.get('ai_agent_id'):
        ids.add(str(data['ai_agent_id']))
    if 'ai_agents_config' in data:
        value = data['ai_agents_config']
        if isinstance(value, str):
            value = json.loads(value)
        if not isinstance(value, dict):
            raise ValueError('Некорректные настройки агентов')
        for config in value.values():
            if not isinstance(config, dict):
                raise ValueError('Некорректные настройки агента')
            if config.get('agent_id'):
                ids.add(str(config['agent_id']))
    for identifier in ids:
        cursor.execute('SELECT id FROM aiagents WHERE id = %s AND business_id = %s', (identifier, business_id))
        if not cursor.fetchone():
            raise ValueError('Агент не принадлежит этому бизнесу')
