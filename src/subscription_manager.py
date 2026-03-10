#!/usr/bin/env python3
"""
Менеджер подписок - проверка доступа к функциям по тарифам.
"""

from datetime import datetime

from database_manager import DatabaseManager

# Суперадмин email (исключение)
SUPERADMIN_EMAIL = 'demyanovap@yandex.ru'

PAID_TIERS = {'starter', 'professional', 'concierge', 'elite', 'promo'}
MANUAL_FEATURES = {
    'chatgpt',
    'crm',
    'human_support',
    'manual_services',
    'manual_transactions',
    'personal_cabinet',
    'profile_edit',
}
AUTOMATION_FEATURES = {
    'advice',
    'ai_agents',
    'automation',
    'news_generation',
    'review_reply',
    'service_optimization',
}


def _normalize_tier(raw_tier) -> str:
    tier = (raw_tier or '').strip().lower()
    tier_mapping = {
        'basic': 'starter',
        'enterprise': 'concierge',
        'pro': 'professional',
    }
    return tier_mapping.get(tier, tier or 'none')


def _normalize_status(raw_status) -> str:
    return (raw_status or '').strip().lower() or 'inactive'


def _safe_fromisoformat(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value))
    except Exception:
        return None


def get_subscription_access(business_id: str) -> dict:
    """
    Возвращает нормализованную информацию о доступе.

    Правило продукта:
    - ручные операции доступны даже без оплаты;
    - автоматизация доступна только после оплаты тарифа.
    """
    db = DatabaseManager()
    cursor = db.conn.cursor()

    try:
        cursor.execute(
            """
            SELECT b.subscription_tier, b.subscription_status, b.trial_ends_at, b.subscription_ends_at, u.email
            FROM Businesses b
            JOIN Users u ON b.owner_id = u.id
            WHERE b.id = %s
            """,
            (business_id,),
        )
        result = cursor.fetchone()
        if not result:
            return {
                'exists': False,
                'manual_access': False,
                'automation_access': False,
                'reason': 'Бизнес не найден.',
            }

        tier = _normalize_tier(result[0])
        status = _normalize_status(result[1])
        trial_ends_at = _safe_fromisoformat(result[2])
        subscription_ends_at = _safe_fromisoformat(result[3])
        owner_email = result[4]

        is_superadmin = owner_email == SUPERADMIN_EMAIL
        now = datetime.now()
        trial_expired = bool(tier == 'trial' and trial_ends_at and now > trial_ends_at)
        subscription_expired = bool(
            tier in PAID_TIERS and subscription_ends_at and now > subscription_ends_at and status not in {'active', 'trialing'}
        )
        is_paid = tier in PAID_TIERS and status in {'active', 'trialing'} and not subscription_expired

        if is_superadmin or is_paid:
            reason = None
        elif trial_expired or tier in {'trial', 'none'} or status not in {'active', 'trialing'}:
            reason = 'Автоматизация доступна только после оплаты тарифа.'
        else:
            reason = 'Автоматизация недоступна для текущего тарифа.'

        return {
            'exists': True,
            'tier': tier,
            'status': status,
            'trial_ends_at': trial_ends_at.isoformat() if trial_ends_at else None,
            'subscription_ends_at': subscription_ends_at.isoformat() if subscription_ends_at else None,
            'trial_expired': trial_expired,
            'subscription_expired': subscription_expired,
            'is_paid': is_paid,
            'is_superadmin': is_superadmin,
            'manual_access': True,
            'automation_access': bool(is_superadmin or is_paid),
            'reason': reason,
        }
    except Exception as e:
        print(f"❌ Ошибка проверки подписки: {e}")
        return {
            'exists': False,
            'manual_access': False,
            'automation_access': False,
            'reason': 'Не удалось проверить подписку.',
        }
    finally:
        db.close()


def has_paid_automation_access(business_id: str) -> bool:
    return bool(get_subscription_access(business_id).get('automation_access'))


def get_automation_block_message(business_id: str) -> str:
    info = get_subscription_access(business_id)
    return info.get('reason') or 'Автоматизация доступна только после оплаты тарифа.'


def check_access(business_id: str, feature: str) -> bool:
    """
    Проверка доступа к функции по тарифу.
    """
    info = get_subscription_access(business_id)
    if not info.get('exists'):
        return False
    if info.get('is_superadmin'):
        return True

    feature_key = (feature or '').strip().lower()
    if feature_key in MANUAL_FEATURES:
        return bool(info.get('manual_access'))
    if feature_key in AUTOMATION_FEATURES:
        return bool(info.get('automation_access'))

    return bool(info.get('automation_access'))


def get_subscription_info(business_id: str) -> dict:
    """Получить информацию о подписке"""
    db = DatabaseManager()
    cursor = db.conn.cursor()

    try:
        cursor.execute(
            """
            SELECT subscription_tier, subscription_status, trial_ends_at, subscription_ends_at, stripe_subscription_id
            FROM Businesses
            WHERE id = %s
            """,
            (business_id,),
        )
        result = cursor.fetchone()
        if not result:
            return {}

        access = get_subscription_access(business_id)
        return {
            'tier': _normalize_tier(result[0]),
            'status': _normalize_status(result[1]),
            'trial_ends_at': result[2],
            'subscription_ends_at': result[3],
            'subscription_id': result[4],
            'trial_expired': access.get('trial_expired', False),
            'automation_access': access.get('automation_access', False),
            'manual_access': access.get('manual_access', False),
        }
    except Exception as e:
        print(f"❌ Ошибка получения информации о подписке: {e}")
        return {}
    finally:
        db.close()
