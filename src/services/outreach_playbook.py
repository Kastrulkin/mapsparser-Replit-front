"""Approved LocalOS outreach methodology and segment language.

The B2B Telegram corpus supplies reusable methods, never recipient facts.
Owner language is kept as a hypothesis vocabulary and may only be attributed
to a particular lead when separate evidence supports it.
"""

from __future__ import annotations

from typing import Any


PLAYBOOK_VERSION = "localos_outreach_playbook_v1"
CORPUS_TAG = "telegram_b2b"

B2B_METHOD_RULES = (
    "Начинать с проверяемого действия или артефакта получателя, а не с общего комплимента.",
    "Разделять наблюдение, гипотезу и мост к предложению.",
    "Строить оффер как результат, короткий механизм, доказательство и один лёгкий следующий шаг.",
    "Каждым следующим касанием добавлять новый аргумент, а не повторять первое письмо.",
    "Не предлагать звонок слишком рано: сначала дать полезный материал, кейс или понятную идею.",
    "Автоматизировать подготовку и очередь, но оставлять человеку approval и остановку по ответу.",
)

BEAUTY_OWNER_PAINS = (
    {
        "key": "marketing_and_clients",
        "phrases": (
            "Клиентов нет от слова совсем",
            "Ведём соцсети, запускаем рекламу, а записи всё равно нет",
            "Не знаю, что публиковать, и времени постоянно снимать контент нет",
        ),
        "localos_bridge": "Карты, автопостинг и системный поиск локального спроса.",
        "support": "supported",
    },
    {
        "key": "staff_and_processes",
        "phrases": (
            "Мастера уходят и клиентов за собой уводят",
            "Мастера саботируют правила и считают, что салон им должен",
        ),
        "localos_bridge": "КПИ, понятные схемы работы и контроль исполнения.",
        "support": "supported",
    },
    {
        "key": "reviews_and_service",
        "phrases": (
            "Как реагировать на жалобы и не потерять репутацию?",
            "Мастер не понял клиента, а разбираться теперь владельцу",
        ),
        "localos_bridge": "Мониторинг отзывов, очередь ответов и проверяемые сценарии сервиса.",
        "support": "supported",
    },
    {
        "key": "pricing_and_average_ticket",
        "phrases": (
            "Работы много, а средний чек всё равно маленький",
            "Боюсь, что после повышения цены клиенты разбегутся",
        ),
        "localos_bridge": "Аналитика услуг, допродажи, кросс-продажи и партнёрские пакеты.",
        "support": "supported",
    },
    {
        "key": "operations_and_burnout",
        "phrases": (
            "Если не я, то никто",
            "Работаю за администратора, управляющего и бухгалтера",
            "Бизнес есть, команда есть, даже деньги есть - но жить некогда",
        ),
        "localos_bridge": "Автоматизация повторяющихся задач и единый контур контроля.",
        "support": "supported",
    },
    {
        "key": "retention",
        "phrases": (
            "Новых клиентов много, а возвратность низкая",
            "Постоянно привлекать новых клиентов слишком дорого",
        ),
        "localos_bridge": "Сценарии повторных касаний; владение клиентской базой зависит от подключённой CRM.",
        "support": "partial",
    },
    {
        "key": "revenue_without_profit",
        "phrases": (
            "Салон работает, а денег нет",
            "Клиенты есть, мастера заняты, но в конце месяца остаются копейки",
        ),
        "localos_bridge": "Финансовые КПИ, разбор услуг и регулярный контроль показателей.",
        "support": "supported",
    },
)

APPROVED_LOCALOS_PROOFS = (
    "Для салона красоты LocalOS помог поднять запись с 0 до 10 клиентов в день только за счёт карт.",
    "LocalOS применяется более чем в 240 точках малого бизнеса.",
)

APPROVED_FOUNDER_ORIGIN = (
    "Сначала я создавал LocalOS для себя - чтобы меньше тонуть в операционке. "
    "Теперь с его помощью мы освобождаем от повторяющихся задач других предпринимателей."
)


def beauty_outreach_guidance() -> dict[str, Any]:
    """Return prompt-safe guidance without asserting pains about a recipient."""

    return {
        "version": PLAYBOOK_VERSION,
        "method_source": CORPUS_TAG,
        "method_rules": list(B2B_METHOD_RULES),
        "pain_language_status": "segment_hypothesis_only",
        "pain_library": [
            {
                "key": item["key"],
                "phrases": list(item["phrases"]),
                "localos_bridge": item["localos_bridge"],
                "support": item["support"],
            }
            for item in BEAUTY_OWNER_PAINS
        ],
        "approved_founder_origin": APPROVED_FOUNDER_ORIGIN,
        "approved_proofs": list(APPROVED_LOCALOS_PROOFS),
        "constraints": [
            "Не приписывать боль получателю без отдельного evidence.",
            "В одном касании использовать одну боль и один CTA.",
            "Цитировать язык владельцев только как узнаваемую ситуацию сегмента.",
            "Не повторять карточку на картах в каждом follow-up.",
        ],
    }


def beauty_touch_learning_dimensions(angle: str) -> dict[str, Any]:
    """Return explicit dimensions used to compare outcomes of playbook touches."""

    pain_by_angle = {
        "signal": "marketing_and_clients",
        "founder_story": "operations_and_burnout",
        "proof": "marketing_and_clients",
        "audit_step": "integrated_operating_system",
        "phone_handoff": "diagnostic_open_question",
        "respectful_close": "operations_and_burnout",
    }
    return {
        "playbook_version": PLAYBOOK_VERSION,
        "pain_key": pain_by_angle.get(str(angle or "").strip()),
    }
