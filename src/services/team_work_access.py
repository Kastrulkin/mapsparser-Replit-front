"""Common team-work rollout; subscription and tenant checks stay in application services."""
import os


def rolled_out():
    return os.getenv('OPERATOR_TEAM_WORK_ENABLED', '').casefold() in {'1', 'true'}


def enabled(business_id, legacy_variable):
    return rolled_out() or business_id in {
        value.strip() for value in os.getenv(legacy_variable, '').split(',') if value.strip()
    }


def allowed(access):
    # Management remains compatible with already prepared entitlement snapshots.
    return bool({'team_work', 'management'} & set(access.get('capabilities') or []))
