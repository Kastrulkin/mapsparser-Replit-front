"""Resolve saved client dialogue preferences without legacy schema assumptions."""
import json


def saved_client_settings(raw, agent_type='booking', agent_id=None):
    try:
        configs = json.loads(raw) if isinstance(raw, str) else raw
    except (ValueError, TypeError):
        return None
    if not isinstance(configs, dict):
        return None
    candidates = [(key, value) for key, value in configs.items()
                  if key in ('booking_agent', 'marketing_agent') and isinstance(value, dict)]
    if agent_id:
        candidates = [(key, value) for key, value in candidates if value.get('agent_id') == agent_id or (not value.get('agent_id') and key == agent_type + '_agent')]
    else:
        enabled = [(key, value) for key, value in candidates if value.get('enabled') is True]
        candidates = sorted(enabled, key=lambda item: item[0] != agent_type + '_agent')
    if not candidates:
        return None
    key, value = candidates[0]
    return {'agent_type': key.removesuffix('_agent'), 'agent_id': value.get('agent_id'),
            'tone': value.get('tone') or 'professional', 'language': value.get('language') or 'ru',
            'restrictions': value.get('variables') if isinstance(value.get('variables'), dict) else {}}
