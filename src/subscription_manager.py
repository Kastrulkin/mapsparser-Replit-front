#!/usr/bin/env python3
"""
Менеджер подписок - проверка доступа к функциям по тарифам.
"""

from datetime import datetime

# Суперадмин email (исключение)
SUPERADMIN_EMAIL = 'demyanovap@yandex.ru'

ACTIVE_SUBSCRIPTION_STATUSES = {'active', 'trialing'}
TIER_ALIASES = {'basic': 'starter', 'pro': 'professional', 'enterprise': 'concierge'}
MAPS_CAPABILITIES = {
    'maps', 'maps.audit', 'maps.services', 'maps.reviews', 'maps.news',
    'maps.photos', 'maps.competitors', 'progress', 'telegram_radar', 'web_analytics',
}
ACQUISITION_CAPABILITIES = MAPS_CAPABILITIES | {
    'acquisition', 'partnerships', 'influencers', 'ai_visibility',
}
MANAGEMENT_CAPABILITIES = ACQUISITION_CAPABILITIES | {
    'management', 'finance', 'average_ticket', 'agents', 'operator', 'chats',
    'social_content', 'automation',
}
TIER_CAPABILITIES = {
    'starter': MAPS_CAPABILITIES,
    'professional': ACQUISITION_CAPABILITIES,
    'concierge': MANAGEMENT_CAPABILITIES,
    'elite': MANAGEMENT_CAPABILITIES,
    'promo': MANAGEMENT_CAPABILITIES,
}
CAPABILITY_MINIMUM_TIER = {capability: 'starter' for capability in MAPS_CAPABILITIES}
CAPABILITY_MINIMUM_TIER.update({capability: 'professional' for capability in ACQUISITION_CAPABILITIES - MAPS_CAPABILITIES})
CAPABILITY_MINIMUM_TIER.update({capability: 'concierge' for capability in MANAGEMENT_CAPABILITIES - ACQUISITION_CAPABILITIES})
TIER_PUBLIC_NAMES = {
    'starter': 'Карты', 'professional': 'Привлечение', 'concierge': 'Управление',
    'elite': 'Elite', 'promo': 'Промо', 'trial': 'Без тарифа', 'none': 'Без тарифа',
}
PAID_TIERS = set(TIER_CAPABILITIES)
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
    return TIER_ALIASES.get(tier, tier or 'none')


def _normalize_status(raw_status) -> str:
    return (raw_status or '').strip().lower() or 'inactive'


def _safe_fromisoformat(value):
    if not value:
        return None
    if isinstance(value, datetime):
        parsed_value = value
    else:
        try:
            parsed_value = datetime.fromisoformat(str(value))
        except Exception:
            return None
    if parsed_value.tzinfo:
        return parsed_value.replace(tzinfo=None)
    return parsed_value


def build_subscription_capabilities(*, tier: str, status: str, subscription_ends_at=None, is_superadmin: bool = False) -> dict:
    normalized_tier = _normalize_tier(tier)
    normalized_status = _normalize_status(status)
    ends_at = _safe_fromisoformat(subscription_ends_at)
    expired = bool(ends_at and ends_at < datetime.now())
    active = bool(
        is_superadmin
        or normalized_tier in TIER_CAPABILITIES
        and normalized_status in ACTIVE_SUBSCRIPTION_STATUSES
        and not expired
    )
    capabilities = set(MANAGEMENT_CAPABILITIES) if is_superadmin else set()
    if active and not is_superadmin:
        capabilities = set(TIER_CAPABILITIES.get(normalized_tier, set()))
    return {
        'tier': normalized_tier,
        'tier_name': TIER_PUBLIC_NAMES.get(normalized_tier, normalized_tier.title()),
        'status': normalized_status,
        'active': active,
        'subscription_expired': expired,
        'capabilities': sorted(capabilities),
        'groups': {
            'maps': 'maps' in capabilities,
            'acquisition': 'acquisition' in capabilities,
            'management': 'management' in capabilities,
        },
    }


def capability_access_payload(access: dict, capability: str) -> dict:
    capability_key = str(capability or '').strip().lower()
    allowed = capability_key in set(access.get('capabilities') or [])
    minimum_tier = CAPABILITY_MINIMUM_TIER.get(capability_key, 'concierge')
    minimum_name = TIER_PUBLIC_NAMES.get(minimum_tier, 'Управление')
    return {
        'allowed': allowed,
        'capability': capability_key,
        'status': 'available' if allowed else 'payment_required',
        'code': None if allowed else 'payment_required',
        'payment_required': not allowed,
        'required_tier': minimum_tier,
        'required_tier_name': minimum_name,
        'cta_label': 'Открыть раздел' if allowed else f'Выбрать тариф «{minimum_name}»',
        'cta_target': {
            'screen': 'current' if allowed else 'settings',
            'url': '/dashboard/profile?focus=subscription#subscription',
        },
        'reason': 'Доступно для текущего тарифа.' if allowed else f'Функция входит в тариф «{minimum_name}».',
    }


def _get_business_subscription_columns(cursor) -> set[str]:
    cursor.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'businesses'
          AND column_name IN ('subscription_tier', 'subscription_status', 'trial_ends_at', 'subscription_ends_at', 'stripe_subscription_id')
        """
    )
    rows = cursor.fetchall() or []
    columns = set()
    for row in rows:
        if hasattr(row, 'keys'):
            columns.add(str(row.get('column_name') or '').strip())
        elif row:
            columns.add(str(row[0] or '').strip())
    return columns


def _fetch_business_subscription_row(cursor, business_id: str):
    columns = _get_business_subscription_columns(cursor)
    select_parts = [
        "b.subscription_tier" if 'subscription_tier' in columns else "'trial' AS subscription_tier",
        "b.subscription_status" if 'subscription_status' in columns else "'inactive' AS subscription_status",
        "b.trial_ends_at" if 'trial_ends_at' in columns else "NULL AS trial_ends_at",
        "b.subscription_ends_at" if 'subscription_ends_at' in columns else "NULL AS subscription_ends_at",
        "b.stripe_subscription_id" if 'stripe_subscription_id' in columns else "NULL AS stripe_subscription_id",
        "u.email AS owner_email",
    ]
    cursor.execute(
        f"""
        SELECT {', '.join(select_parts)}
        FROM businesses b
        JOIN users u ON b.owner_id = u.id
        WHERE b.id = %s
        """,
        (business_id,),
    )
    return cursor.fetchone()


def get_subscription_access(business_id: str) -> dict:
    """
    Возвращает нормализованную информацию о доступе.

    Правило продукта:
    - ручные операции доступны даже без оплаты;
    - автоматизация доступна только после оплаты тарифа.
    """
    from database_manager import DatabaseManager

    db = DatabaseManager()
    cursor = db.conn.cursor()

    try:
        result = _fetch_business_subscription_row(cursor, business_id)
        if not result:
            return {
                'exists': False,
                'manual_access': False,
                'automation_access': False,
                'reason': 'Бизнес не найден.',
            }

        if hasattr(result, 'keys'):
            tier = _normalize_tier(result.get('subscription_tier'))
            status = _normalize_status(result.get('subscription_status'))
            trial_ends_at = _safe_fromisoformat(result.get('trial_ends_at'))
            subscription_ends_at = _safe_fromisoformat(result.get('subscription_ends_at'))
            owner_email = result.get('owner_email')
        else:
            tier = _normalize_tier(result[0])
            status = _normalize_status(result[1])
            trial_ends_at = _safe_fromisoformat(result[2])
            subscription_ends_at = _safe_fromisoformat(result[3])
            owner_email = result[5]

        is_superadmin = owner_email == SUPERADMIN_EMAIL
        now = datetime.now()
        trial_expired = bool(tier == 'trial' and trial_ends_at and now > trial_ends_at)
        subscription_expired = bool(
            tier in PAID_TIERS and subscription_ends_at and now > subscription_ends_at
        )
        capability_contract = build_subscription_capabilities(
            tier=tier,
            status=status,
            subscription_ends_at=subscription_ends_at,
            is_superadmin=is_superadmin,
        )
        is_paid = bool(capability_contract.get('active'))

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
            'automation_access': 'automation' in capability_contract.get('capabilities', []),
            'capabilities': capability_contract.get('capabilities', []),
            'groups': capability_contract.get('groups', {}),
            'tier_name': capability_contract.get('tier_name'),
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


def has_capability(business_id: str, capability: str) -> bool:
    info = get_subscription_access(business_id)
    return str(capability or '').strip().lower() in set(info.get('capabilities') or [])


def get_capability_access(business_id: str, capability: str, is_superadmin: bool = False) -> dict:
    access = get_subscription_access(business_id)
    if is_superadmin:
        access = {
            **access,
            "capabilities": sorted(MANAGEMENT_CAPABILITIES),
            "groups": {"maps": True, "acquisition": True, "management": True},
        }
    return capability_access_payload(access, capability)


def get_automation_block_message(business_id: str) -> str:
    info = get_subscription_access(business_id)
    return info.get('reason') or 'Автоматизация доступна только после оплаты тарифа.'


def get_allowed_content_plan_horizons(business_id: str) -> list[int]:
    info = get_subscription_access(business_id)
    if info.get('is_superadmin'):
        return [14, 30, 60, 90]
    tier = _normalize_tier(info.get('tier'))
    if tier in {'concierge', 'elite'}:
        return [14, 30, 60, 90]
    if tier in {'starter', 'professional', 'promo'}:
        return [14, 30]
    return [14, 30]


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
        legacy_feature_capabilities = {
            'advice': 'management',
            'ai_agents': 'agents',
            'automation': 'automation',
            'news_generation': 'maps.news',
            'review_reply': 'maps.reviews',
            'service_optimization': 'maps.services',
        }
        return legacy_feature_capabilities.get(feature_key, 'management') in set(info.get('capabilities') or [])

    return feature_key in set(info.get('capabilities') or [])


def get_subscription_info(business_id: str) -> dict:
    """Получить информацию о подписке"""
    from database_manager import DatabaseManager

    db = DatabaseManager()
    cursor = db.conn.cursor()

    try:
        result = _fetch_business_subscription_row(cursor, business_id)
        if not result:
            return {}

        access = get_subscription_access(business_id)
        if hasattr(result, 'keys'):
            tier = result.get('subscription_tier')
            status = result.get('subscription_status')
            trial_ends_at = result.get('trial_ends_at')
            subscription_ends_at = result.get('subscription_ends_at')
            subscription_id = result.get('stripe_subscription_id')
        else:
            tier = result[0]
            status = result[1]
            trial_ends_at = result[2]
            subscription_ends_at = result[3]
            subscription_id = result[4]
        return {
            'tier': _normalize_tier(tier),
            'status': _normalize_status(status),
            'trial_ends_at': trial_ends_at,
            'subscription_ends_at': subscription_ends_at,
            'subscription_id': subscription_id,
            'trial_expired': access.get('trial_expired', False),
            'automation_access': access.get('automation_access', False),
            'manual_access': access.get('manual_access', False),
        }
    except Exception as e:
        print(f"❌ Ошибка получения информации о подписке: {e}")
        return {}
    finally:
        db.close()
