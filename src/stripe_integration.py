#!/usr/bin/env python3
"""
Stripe интеграция для обработки платежей и подписок
"""
import os
import logging
from typing import Any, Dict
try:
    import stripe
except ImportError:
    stripe = None
from flask import Blueprint, request, jsonify
from database_manager import DatabaseManager
from auth_system import verify_session
from datetime import datetime, timedelta
import uuid
from services.checkout_session_service import (
    complete_checkout,
    load_checkout_session,
    mark_checkout_created,
    mark_checkout_failed,
    mark_checkout_paid,
)

# Загружаем переменные окружения
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

STRIPE_SECRET_KEY = os.getenv('STRIPE_SECRET_KEY', '')
STRIPE_PUBLISHABLE_KEY = os.getenv('STRIPE_PUBLISHABLE_KEY', '')
STRIPE_WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET', '')
VERBOSE_OPTIONAL_STARTUP = os.getenv('LOCALOS_VERBOSE_STARTUP_WARNINGS', '').strip().lower() in {'1', 'true', 'yes'}

logger = logging.getLogger(__name__)

# Инициализируем Stripe
if STRIPE_SECRET_KEY and stripe:
    stripe.api_key = STRIPE_SECRET_KEY
elif STRIPE_SECRET_KEY and not stripe:
    logger.warning("Stripe disabled: STRIPE_SECRET_KEY set but python package 'stripe' is not installed.")
elif VERBOSE_OPTIONAL_STARTUP and not stripe:
    logger.info("Stripe integration is not configured in this runtime.")

stripe_bp = Blueprint('stripe', __name__)

# Тарифы
TIERS = {
    'trial': {
        'price_id': None,  # Будет создан в Stripe
        'amount': 500,  # $5.00 в центах
        'name': 'Trial (First Month)',
        'features': ['chatgpt', 'personal_cabinet']
    },
    'starter': {
        # Starter (Начальный) - 5$ или 400₽
        'price_id': 'price_1Sh4wZFtze6qZAEfkLuuUqVV',  # Нужно обновить в Stripe
        'amount': 500,  # $5.00 в центах (400₽ ≈ $4.5)
        'name': 'Starter (Начальный)',
        'display_name': 'Starter',
        'display_price_usd': 5,
        'display_price_rub': 400,
        'features': [
            'Подключение к профессиональной сети BeautyBot',
            'ChatGPT для лидогенерации',
        ]
    },
    'professional': {
        # Professional (Профессиональный) - 5000₽
        'price_id': 'price_1Sh4xqFtze6qZAEfFy3DvFXJ',  # Нужно обновить в Stripe
        'amount': 5500,  # $55.00 в центах (5000₽ ≈ $55)
        'name': 'Professional (Профессиональный)',
        'display_name': 'Профессиональный',
        'display_price_usd': 55,
        'display_price_rub': 5000,
        'features': [
            'Всё из Starter',
            'Полный доступ к личному кабинету',
            'Управление клиентами и автоматизация переписки',
            'Интеграция с CRM',
        ]
    },
    'concierge': {
        # Concierge (Консьерж) - 25000₽
        'price_id': 'price_1Sh4zyFtze6qZAEftqNTRZoD',  # Нужно обновить в Stripe
        'amount': 27500,  # $275.00 в центах (25000₽ ≈ $275)
        'name': 'Concierge (Консьерж)',
        'display_name': 'Консьерж',
        'display_price_usd': 275,
        'display_price_rub': 25000,
        'features': [
            'Мы делаем всё за вас',
            'Персональная настройка и приоритетная поддержка',
            'Стратегия развития бизнеса',
        ]
    },
    'elite': {
        # Elite (Особый) - 7% от оплат привлечённых клиентов
        'price_id': None,  # Специальный тариф, оплата по факту
        'amount': 0,  # Оплата по факту результата
        'name': 'Elite (Особый)',
        'display_name': 'Особый (Elite)',
        'display_price_usd': 0,
        'display_price_rub': 0,
        'display_price_percent': 7,
        'features': [
            'Привлечение клиентов онлайн',
            'Коммуникация с клиентами',
            'Привлечение клиентов оффлайн',
            'Оптимизация бизнес-процессов',
            'Выделенный менеджер',
        ],
        'note': 'Доступно после 3 месяцев подписки или по рекомендации'
    }
}

def require_auth():
    """Проверка авторизации"""
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return None
    token = auth_header.split(' ')[1]
    user_data = verify_session(token)
    return user_data


def _normalize_checkout_tariff_for_stripe(tariff_id: str) -> str:
    raw = str(tariff_id or "").strip().lower()
    mapping = {
        "starter": "starter",
        "starter_monthly": "starter",
        "professional": "professional",
        "pro": "professional",
        "pro_monthly": "professional",
        "concierge": "concierge",
        "concierge_monthly": "concierge",
    }
    normalized = mapping.get(raw)
    if not normalized or normalized not in TIERS:
        raise RuntimeError(f"Неверный тариф для Stripe: {tariff_id}")
    return normalized


def create_stripe_checkout_for_checkout_session(session_id: str) -> Dict[str, Any]:
    if not stripe:
        raise RuntimeError("Stripe не настроен. Установите модуль: pip install stripe")
    if not STRIPE_SECRET_KEY:
        raise RuntimeError("Stripe не настроен")

    session = load_checkout_session(session_id)
    if not session:
        raise RuntimeError(f"Checkout session not found: {session_id}")

    stripe_tier = _normalize_checkout_tariff_for_stripe(str(session.get("tariff_id") or ""))
    tier_info = TIERS.get(stripe_tier) or {}
    price_id = str(tier_info.get("price_id") or "").strip()
    if not price_id:
        raise RuntimeError(f"Для тарифа '{stripe_tier}' не настроен price_id")

    frontend_base = (os.getenv("FRONTEND_BASE_URL") or "http://localhost:8000").rstrip("/")
    success_url = f"{frontend_base}/checkout/return?session_id={session_id}&provider=stripe"
    cancel_url = f"{frontend_base}/checkout/return?session_id={session_id}&provider=stripe&status=cancelled"
    metadata = {
        "checkout_session_id": session_id,
        "entry_point": str(session.get("entry_point") or ""),
        "tariff_id": str(session.get("tariff_id") or ""),
        "kind": "checkout_session_payment",
    }
    checkout = stripe.checkout.Session.create(
        payment_method_types=['card'],
        line_items=[{'price': price_id, 'quantity': 1}],
        mode='subscription',
        success_url=success_url,
        cancel_url=cancel_url,
        metadata=metadata,
        subscription_data={'metadata': metadata},
        customer_email=str(session.get("email") or "").strip() or None,
    )
    mark_checkout_created(
        session_id,
        provider_invoice_id=str(checkout.id),
        provider_status=str(getattr(checkout, "status", "") or ""),
        payload_patch={"stripe_tier": stripe_tier},
    )
    return {
        "checkout_id": str(checkout.id),
        "url": str(checkout.url),
        "payment_status": str(getattr(checkout, "payment_status", "") or ""),
    }


def get_stripe_checkout_session_status(checkout_id: str) -> Dict[str, Any]:
    if not stripe:
        raise RuntimeError("Stripe не настроен. Установите модуль: pip install stripe")
    session = stripe.checkout.Session.retrieve(str(checkout_id))
    return {
        "id": str(getattr(session, "id", "") or ""),
        "status": str(getattr(session, "status", "") or ""),
        "payment_status": str(getattr(session, "payment_status", "") or ""),
        "payment_intent": str(getattr(session, "payment_intent", "") or ""),
    }

@stripe_bp.route('/api/stripe/create-checkout', methods=['POST'])
def create_stripe_checkout():
    if not stripe:
        return jsonify({"error": "Stripe не настроен. Установите модуль: pip install stripe"}), 503
    """Создание Stripe Checkout сессии"""
    try:
        if not STRIPE_SECRET_KEY:
            return jsonify({"error": "Stripe не настроен"}), 500
        
        user_data = require_auth()
        if not user_data:
            return jsonify({"error": "Требуется авторизация"}), 401
        
        data = request.get_json()
        business_id = data.get('business_id')
        tier = data.get('tier', 'trial')  # По умолчанию trial
        
        if not business_id:
            return jsonify({"error": "business_id обязателен"}), 400
        
        # Маппинг старых названий на новые
        tier_mapping = {
            'basic': 'starter',
            'pro': 'professional',
            'enterprise': 'concierge'
        }
        if tier in tier_mapping:
            tier = tier_mapping[tier]
        
        if tier not in TIERS:
            return jsonify({"error": f"Неверный тариф: {tier}"}), 400
        
        # Elite тариф не оплачивается через Stripe
        if tier == 'elite':
            return jsonify({"error": "Elite тариф оплачивается по факту результата. Свяжитесь с нами для подключения."}), 400
        
        # Проверяем доступ к бизнесу
        db = DatabaseManager()
        cursor = db.conn.cursor()
        
        cursor.execute("SELECT owner_id, stripe_customer_id FROM Businesses WHERE id = %s", (business_id,))
        business = cursor.fetchone()
        
        if not business:
            db.close()
            return jsonify({"error": "Бизнес не найден"}), 404
        
        if business[0] != user_data['user_id'] and not user_data.get('is_superadmin'):
            db.close()
            return jsonify({"error": "Нет доступа к этому бизнесу"}), 403
        
        owner_id, existing_customer_id = business
        
        # Получаем email пользователя для Stripe
        cursor.execute("SELECT email FROM Users WHERE id = %s", (owner_id,))
        user_email = cursor.fetchone()
        user_email = user_email[0] if user_email else None
        
        db.close()
        
        # Создаём или получаем Stripe customer
        if existing_customer_id:
            try:
                customer = stripe.Customer.retrieve(existing_customer_id)
            except:
                customer = None
        else:
            customer = None
        
        if not customer:
            customer = stripe.Customer.create(
                email=user_email,
                metadata={
                    'business_id': business_id,
                    'user_id': owner_id
                }
            )
            # Сохраняем customer_id в БД
            db = DatabaseManager()
            cursor = db.conn.cursor()
            cursor.execute("""
                UPDATE Businesses 
                SET stripe_customer_id = %s
                WHERE id = %s
            """, (customer.id, business_id))
            db.conn.commit()
            db.close()
        
        # Берём готовую цену из конфигурации (мы используем заранее созданные Price ID)
        tier_info = TIERS[tier]
        price_id = tier_info.get('price_id')
        if not price_id:
            return jsonify({"error": f"Для тарифа '{tier}' не настроен price_id"}), 500
        
        # Создаём Checkout Session
        try:
            checkout_session = stripe.checkout.Session.create(
                customer=customer.id,
                payment_method_types=['card'],
                line_items=[{
                    'price': price_id,
                    'quantity': 1,
                }],
                mode='subscription',
                success_url=f"{os.getenv('FRONTEND_URL', 'http://localhost:8000')}/dashboard?payment=success&session_id={{CHECKOUT_SESSION_ID}}",
                cancel_url=f"{os.getenv('FRONTEND_URL', 'http://localhost:8000')}/dashboard?payment=cancelled",
                metadata={
                    'business_id': business_id,
                    'tier': tier
                },
                subscription_data={
                    'metadata': {
                        'business_id': business_id,
                        'tier': tier
                    }
                }
            )
            
            return jsonify({
                "success": True,
                "session_id": checkout_session.id,
                "url": checkout_session.url
            })
            
        except Exception as e:
            print(f"❌ Ошибка создания Checkout Session: {e}")
            return jsonify({"error": f"Ошибка создания сессии: {str(e)}"}), 500
        
    except Exception as e:
        print(f"❌ Ошибка создания checkout: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@stripe_bp.route('/api/stripe/webhook', methods=['POST'])
def stripe_webhook():
    """Обработка событий от Stripe"""
    try:
        if not STRIPE_WEBHOOK_SECRET:
            return jsonify({"error": "Webhook secret не настроен"}), 500
        
        payload = request.data
        sig_header = request.headers.get('Stripe-Signature')
        
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, STRIPE_WEBHOOK_SECRET
            )
        except ValueError as e:
            print(f"❌ Неверный payload: {e}")
            return jsonify({"error": "Неверный payload"}), 400
        except stripe.error.SignatureVerificationError as e:
            print(f"❌ Неверная подпись: {e}")
            return jsonify({"error": "Неверная подпись"}), 400
        
        # Обрабатываем события
        event_type = event['type']
        data = event['data']['object']
        
        print(f"📨 Получено событие Stripe: {event_type}")
        
        if event_type == 'checkout.session.completed':
            metadata = dict(data.get('metadata') or {})
            checkout_session_id = str(metadata.get('checkout_session_id') or '').strip()
            if checkout_session_id:
                mark_checkout_paid(
                    checkout_session_id,
                    provider_payment_id=str(data.get('payment_intent') or data.get('id') or '').strip() or None,
                    provider_status=str(data.get('payment_status') or data.get('status') or 'paid').strip() or 'paid',
                )
                complete_checkout(checkout_session_id)
            else:
                # Платёж успешен, активируем подписку
                handle_checkout_completed(data)

        elif event_type == 'checkout.session.expired':
            metadata = dict(data.get('metadata') or {})
            checkout_session_id = str(metadata.get('checkout_session_id') or '').strip()
            if checkout_session_id:
                mark_checkout_failed(
                    checkout_session_id,
                    provider_status=str(data.get('status') or 'expired').strip() or 'expired',
                    error_message='checkout expired',
                )

        elif event_type == 'customer.subscription.created':
            # Подписка создана
            handle_subscription_created(data)
        
        elif event_type == 'customer.subscription.updated':
            # Подписка обновлена
            handle_subscription_updated(data)
        
        elif event_type == 'customer.subscription.deleted':
            # Подписка отменена
            handle_subscription_deleted(data)
        
        elif event_type == 'invoice.payment_succeeded':
            # Платёж успешен (продление)
            handle_payment_succeeded(data)
        
        elif event_type == 'invoice.payment_failed':
            # Платёж не удался
            handle_payment_failed(data)
        
        elif event_type == 'invoice.upcoming':
            # Скоро истекает подписка (за неделю)
            handle_invoice_upcoming(data)
        
        return jsonify({"success": True})
        
    except Exception as e:
        print(f"❌ Ошибка обработки webhook: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

def handle_checkout_completed(session):
    """Обработка успешного checkout"""
    try:
        business_id = session.get('metadata', {}).get('business_id')
        tier = session.get('metadata', {}).get('tier', 'trial')
        subscription_id = session.get('subscription')
        
        if not business_id:
            print("⚠️ Нет business_id в metadata")
            return
        
        db = DatabaseManager()
        cursor = db.conn.cursor()
        
        # Обновляем подписку
        trial_ends_at = None
        if tier == 'trial':
            # Первый месяц льготный - заканчивается через 30 дней
            trial_ends_at = (datetime.now() + timedelta(days=30)).isoformat()
        
        cursor.execute("""
            UPDATE Businesses 
            SET stripe_subscription_id = %s,
                subscription_tier = %s,
                subscription_status = 'active',
                trial_ends_at = %s,
                subscription_ends_at = %s
            WHERE id = %s
        """, (
            subscription_id,
            tier,
            trial_ends_at,
            (datetime.now() + timedelta(days=30)).isoformat() if tier == 'trial' else None,
            business_id
        ))
        
        # Логируем платёж
        payment_id = str(uuid.uuid4())
        cursor.execute("""
            INSERT INTO StripePayments 
            (id, business_id, stripe_payment_intent_id, amount, currency, status, subscription_tier)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            payment_id,
            business_id,
            session.get('payment_intent'),
            session.get('amount_total', 0),
            session.get('currency', 'usd'),
            'succeeded',
            tier
        ))
        
        db.conn.commit()
        db.close()
        
        print(f"✅ Подписка активирована для бизнеса {business_id}, тариф: {tier}")
        
    except Exception as e:
        print(f"❌ Ошибка обработки checkout.completed: {e}")
        import traceback
        traceback.print_exc()

def handle_subscription_created(subscription):
    """Обработка создания подписки"""
    try:
        business_id = subscription.get('metadata', {}).get('business_id')
        if not business_id:
            return
        
        db = DatabaseManager()
        cursor = db.conn.cursor()
        
        cursor.execute("""
            UPDATE Businesses 
            SET stripe_subscription_id = %s,
                subscription_status = 'active'
            WHERE id = %s
        """, (subscription['id'], business_id))
        
        db.conn.commit()
        db.close()
        
    except Exception as e:
        print(f"❌ Ошибка обработки subscription.created: {e}")

def handle_subscription_updated(subscription):
    """Обработка обновления подписки"""
    try:
        business_id = subscription.get('metadata', {}).get('business_id')
        if not business_id:
            return
        
        db = DatabaseManager()
        cursor = db.conn.cursor()
        
        status = subscription.get('status', 'active')
        tier = subscription.get('metadata', {}).get('tier')
        
        cursor.execute("""
            UPDATE Businesses 
            SET subscription_status = %s,
                subscription_tier = %s
            WHERE id = %s
        """, (status, tier, business_id))
        
        db.conn.commit()
        db.close()
        
    except Exception as e:
        print(f"❌ Ошибка обработки subscription.updated: {e}")

def handle_subscription_deleted(subscription):
    """Обработка отмены подписки"""
    try:
        business_id = subscription.get('metadata', {}).get('business_id')
        if not business_id:
            return
        
        db = DatabaseManager()
        cursor = db.conn.cursor()
        
        # Блокируем доступ (grace period = 0, сразу блокируем)
        cursor.execute("""
            UPDATE Businesses 
            SET subscription_status = 'cancelled',
                subscription_ends_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (business_id,))
        
        db.conn.commit()
        db.close()
        
        print(f"⚠️ Подписка отменена для бизнеса {business_id}")
        
    except Exception as e:
        print(f"❌ Ошибка обработки subscription.deleted: {e}")

def handle_payment_succeeded(invoice):
    """Обработка успешного платежа (продление)"""
    try:
        subscription_id = invoice.get('subscription')
        if not subscription_id:
            return
        
        db = DatabaseManager()
        cursor = db.conn.cursor()
        
        # Находим бизнес по subscription_id
        cursor.execute("SELECT id FROM Businesses WHERE stripe_subscription_id = %s", (subscription_id,))
        business = cursor.fetchone()
        
        if not business:
            db.close()
            return
        
        business_id = business[0]
        
        # Продлеваем подписку на месяц
        cursor.execute("""
            UPDATE Businesses 
            SET subscription_status = 'active',
                subscription_ends_at = CURRENT_TIMESTAMP + INTERVAL '1 month'
            WHERE id = %s
        """, (business_id,))
        
        # Логируем платёж
        payment_id = str(uuid.uuid4())
        cursor.execute("""
            INSERT INTO StripePayments 
            (id, business_id, stripe_invoice_id, amount, currency, status, subscription_tier)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            payment_id,
            business_id,
            invoice['id'],
            invoice.get('amount_paid', 0),
            invoice.get('currency', 'usd'),
            'succeeded',
            None  # Можно получить из subscription metadata
        ))
        
        db.conn.commit()
        db.close()
        
        print(f"✅ Платёж успешен, подписка продлена для бизнеса {business_id}")
        
    except Exception as e:
        print(f"❌ Ошибка обработки payment.succeeded: {e}")

def handle_payment_failed(invoice):
    """Обработка неудачного платежа"""
    try:
        subscription_id = invoice.get('subscription')
        if not subscription_id:
            return
        
        db = DatabaseManager()
        cursor = db.conn.cursor()
        
        cursor.execute("SELECT id FROM Businesses WHERE stripe_subscription_id = %s", (subscription_id,))
        business = cursor.fetchone()
        
        if not business:
            db.close()
            return
        
        business_id = business[0]
        
        # Помечаем как past_due
        cursor.execute("""
            UPDATE Businesses 
            SET subscription_status = 'past_due'
            WHERE id = %s
        """, (business_id,))
        
        db.conn.commit()
        db.close()
        
        print(f"⚠️ Платёж не удался для бизнеса {business_id}")
        
        # TODO: Отправить уведомление пользователю
        
    except Exception as e:
        print(f"❌ Ошибка обработки payment.failed: {e}")

def handle_invoice_upcoming(invoice):
    """Обработка предупреждения о скором истечении (за неделю)"""
    try:
        subscription_id = invoice.get('subscription')
        if not subscription_id:
            return
        
        db = DatabaseManager()
        cursor = db.conn.cursor()
        
        cursor.execute("SELECT id, owner_id FROM Businesses WHERE stripe_subscription_id = %s", (subscription_id,))
        business = cursor.fetchone()
        
        if not business:
            db.close()
            return
        
        business_id, owner_id = business
        
        # TODO: Отправить уведомление пользователю за неделю до окончания
        
        print(f"📧 Напоминание: подписка истекает через неделю для бизнеса {business_id}")
        
        db.close()
        
    except Exception as e:
        print(f"❌ Ошибка обработки invoice.upcoming: {e}")

@stripe_bp.route('/api/stripe/success', methods=['GET'])
def stripe_success():
    """Страница успешной оплаты"""
    session_id = request.args.get('session_id')
    return jsonify({
        "success": True,
        "message": "Оплата успешна! Подписка активирована.",
        "session_id": session_id
    })

@stripe_bp.route('/api/stripe/cancel', methods=['GET'])
def stripe_cancel():
    """Страница отмены оплаты"""
    return jsonify({
        "success": False,
        "message": "Оплата отменена"
    })
