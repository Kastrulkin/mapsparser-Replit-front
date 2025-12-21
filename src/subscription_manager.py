#!/usr/bin/env python3
"""
Менеджер подписок - проверка доступа к функциям по тарифам
"""
from database_manager import DatabaseManager
from datetime import datetime

# Суперадмин email (исключение)
SUPERADMIN_EMAIL = 'demyanovap@yandex.ru'

def check_access(business_id: str, feature: str) -> bool:
    """
    Проверка доступа к функции по тарифу
    
    Args:
        business_id: ID бизнеса
        feature: Название функции ('chatgpt', 'personal_cabinet', 'crm', 'human_support')
    
    Returns:
        True если доступ разрешён, False если нет
    """
    db = DatabaseManager()
    cursor = db.conn.cursor()
    
    try:
        # Получаем информацию о бизнесе и владельце
        cursor.execute("""
            SELECT b.owner_id, b.subscription_tier, b.subscription_status, 
                   b.trial_ends_at, b.subscription_ends_at, u.email
            FROM Businesses b
            JOIN Users u ON b.owner_id = u.id
            WHERE b.id = ?
        """, (business_id,))
        
        result = cursor.fetchone()
        if not result:
            db.close()
            return False
        
        owner_id, tier, status, trial_ends_at, subscription_ends_at, owner_email = result
        
        # Суперадмин - всегда доступ
        if owner_email == SUPERADMIN_EMAIL:
            db.close()
            return True
        
        # Проверяем статус подписки
        if status not in ['active', 'trialing']:
            db.close()
            return False
        
        # Проверяем, не истёк ли trial период
        if tier == 'trial' and trial_ends_at:
            try:
                trial_end = datetime.fromisoformat(trial_ends_at)
                if datetime.now() > trial_end:
                    # Trial истёк, но подписка ещё активна - проверяем по тарифу
                    # Если trial истёк и не перешли на платный тариф - только chatgpt
                    if feature == 'chatgpt':
                        db.close()
                        return True
                    else:
                        db.close()
                        return False
            except:
                pass
        
        # Проверяем доступ по тарифу
        if tier == 'trial':
            # Trial даёт доступ к chatgpt и personal_cabinet
            if feature in ['chatgpt', 'personal_cabinet']:
                db.close()
                return True
            return False
        
        elif tier == 'basic':
            # Basic - только chatgpt
            if feature == 'chatgpt':
                db.close()
                return True
            return False
        
        elif tier == 'pro':
            # Pro - chatgpt, personal_cabinet, crm
            if feature in ['chatgpt', 'personal_cabinet', 'crm']:
                db.close()
                return True
            return False
        
        elif tier == 'enterprise':
            # Enterprise - всё
            db.close()
            return True
        
        db.close()
        return False
        
    except Exception as e:
        print(f"❌ Ошибка проверки доступа: {e}")
        db.close()
        return False

def get_subscription_info(business_id: str) -> dict:
    """Получить информацию о подписке"""
    db = DatabaseManager()
    cursor = db.conn.cursor()
    
    try:
        cursor.execute("""
            SELECT subscription_tier, subscription_status, 
                   trial_ends_at, subscription_ends_at,
                   stripe_subscription_id
            FROM Businesses
            WHERE id = ?
        """, (business_id,))
        
        result = cursor.fetchone()
        if not result:
            db.close()
            return {}
        
        tier, status, trial_ends_at, subscription_ends_at, subscription_id = result
        
        info = {
            'tier': tier or 'none',
            'status': status or 'inactive',
            'trial_ends_at': trial_ends_at,
            'subscription_ends_at': subscription_ends_at,
            'subscription_id': subscription_id
        }
        
        # Проверяем, истёк ли trial
        if tier == 'trial' and trial_ends_at:
            try:
                trial_end = datetime.fromisoformat(trial_ends_at)
                if datetime.now() > trial_end:
                    info['trial_expired'] = True
                else:
                    info['trial_expired'] = False
            except:
                info['trial_expired'] = False
        
        db.close()
        return info
        
    except Exception as e:
        print(f"❌ Ошибка получения информации о подписке: {e}")
        db.close()
        return {}

