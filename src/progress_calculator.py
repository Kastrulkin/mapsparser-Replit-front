#!/usr/bin/env python3
"""
Модуль для расчета прогресса выполнения этапов роста бизнеса
"""
import json
from database_manager import DatabaseManager
from typing import Dict, Any, List


class ProgressCalculator:
    """Калькулятор прогресса выполнения этапов роста"""
    
    def __init__(self, db: DatabaseManager):
        self.db = db
        self.cursor = db.conn.cursor()
    
    def calculate_stage_1_foundation(self, business_id: str) -> Dict[str, Any]:
        """
        Этап 1: Фундамент
        Критерии:
        - Профиль заполнен: email, phone, name, businessName, businessType, address, workingHours (≥80%)
        - Яндекс.Карты профиль: ≥1 mapLink с map_type='yandex'
        - Google Maps профиль: ≥1 mapLink с map_type='google'
        - Фото загружены: ≥7 фото в парсинге
        - Отзывы собраны: ≥10 отзывов, рейтинг ≥4.5
        - Соцсети добавлены: Telegram/WhatsApp в интеграциях
        """
        checks = {}
        
        # 0. Проверка заполненности профиля (как в ProfilePage)
        self.cursor.execute("""
            SELECT email, phone, name, 
                   name AS business_name, business_type, address, working_hours, owner_id
            FROM Businesses WHERE id = ?
        """, (business_id,))
        business_row = self.cursor.fetchone()
        
        profile_fields_filled = 0
        if business_row:
            # email (от владельца через JOIN или напрямую из Businesses)
            if business_row[0] and str(business_row[0]).strip():
                profile_fields_filled += 1
            
            # phone
            if business_row[1] and str(business_row[1]).strip():
                profile_fields_filled += 1
            # name (contact_name - используем owner через Users или name)
            if business_row[2] and str(business_row[2]).strip():
                profile_fields_filled += 1
            # businessName
            if business_row[3] and str(business_row[3]).strip():
                profile_fields_filled += 1
            # businessType
            if business_row[4] and str(business_row[4]).strip():
                profile_fields_filled += 1
            # address
            if business_row[5] and str(business_row[5]).strip():
                profile_fields_filled += 1
            # workingHours
            if business_row[6] and str(business_row[6]).strip():
                profile_fields_filled += 1
        
        profile_completion = round((profile_fields_filled / 7) * 100) if profile_fields_filled > 0 else 0
        checks['profile_completed'] = {'completed': profile_completion >= 80, 'points': 16}
        
        # 1. Проверка Яндекс.Карты
        self.cursor.execute("""
            SELECT COUNT(*) FROM BusinessMapLinks 
            WHERE business_id = ? AND map_type = 'yandex'
        """, (business_id,))
        yandex_count = self.cursor.fetchone()[0]
        checks['yandex_maps_profile'] = {'completed': yandex_count > 0, 'points': 17}
        
        # 2. Проверка Google Maps
        self.cursor.execute("""
            SELECT COUNT(*) FROM BusinessMapLinks 
            WHERE business_id = ? AND map_type = 'google'
        """, (business_id,))
        google_count = self.cursor.fetchone()[0]
        checks['google_maps_profile'] = {'completed': google_count > 0, 'points': 17}
        
        # 3. Проверка фото (из последнего парсинга)
        self.cursor.execute("""
            SELECT photos_count FROM MapParseResults 
            WHERE business_id = ? 
            ORDER BY created_at DESC LIMIT 1
        """, (business_id,))
        photos_row = self.cursor.fetchone()
        photos_count = photos_row[0] if photos_row else 0
        checks['photos_uploaded'] = {'completed': photos_count >= 7, 'points': 17}
        
        # 4. Проверка отзывов и рейтинга
        self.cursor.execute("""
            SELECT reviews_count, rating FROM MapParseResults 
            WHERE business_id = ? 
            ORDER BY created_at DESC LIMIT 1
        """, (business_id,))
        reviews_row = self.cursor.fetchone()
        reviews_count = reviews_row[0] if reviews_row else 0
        rating = float(reviews_row[1]) if reviews_row and reviews_row[1] else 0.0
        checks['reviews_collected'] = {
            'completed': reviews_count >= 10 and rating >= 4.5, 
            'points': 17
        }
        
        # 5. Проверка соцсетей/мессенджеров
        self.cursor.execute("""
            SELECT COUNT(*) FROM ExternalIntegrations 
            WHERE business_id = ? AND type IN ('telegram', 'whatsapp')
        """, (business_id,))
        social_count = self.cursor.fetchone()[0]
        checks['social_links'] = {'completed': social_count > 0, 'points': 16}
        
        # Подсчет общего прогресса
        total_checks = len(checks)
        passed_checks = sum(1 for c in checks.values() if c['completed'])
        percentage = round((passed_checks / total_checks) * 100) if total_checks > 0 else 0
        
        return {
            'stage_number': 1,
            'checks_total': total_checks,
            'checks_passed': passed_checks,
            'percentage': percentage,
            'details': checks
        }
    
    def calculate_stage_2_optimization(self, business_id: str) -> Dict[str, Any]:
        """
        Этап 2: Оптимизация видимости
        Критерии:
        - Виджет записи подключен: ai_agents_config содержит booking агента
        - Автосбор отзывов настроен: проверяем наличие отзывов
        - Прайс-лист добавлен: есть услуги в UserServices
        """
        checks = {}
        
        # 1. Виджет записи (booking агент)
        self.cursor.execute("""
            SELECT ai_agents_config FROM Businesses WHERE id = ?
        """, (business_id,))
        row = self.cursor.fetchone()
        booking_enabled = False
        if row and row[0]:
            try:
                config = json.loads(row[0])
                booking_enabled = config.get('booking_agent', {}).get('enabled', False)
            except:
                pass
        checks['booking_widget'] = {'completed': booking_enabled, 'points': 33}
        
        # 2. Автосбор отзывов (наличие отзывов + регулярность)
        self.cursor.execute("""
            SELECT COUNT(*) FROM MapParseResults 
            WHERE business_id = ? AND created_at >= datetime('now', '-30 days')
        """, (business_id,))
        recent_parses = self.cursor.fetchone()[0]
        checks['auto_reviews'] = {'completed': recent_parses >= 2, 'points': 33}
        
        # 3. Прайс-лист (услуги)
        self.cursor.execute("""
            SELECT COUNT(*) FROM UserServices WHERE business_id = ?
        """, (business_id,))
        services_count = self.cursor.fetchone()[0]
        checks['pricelist_added'] = {'completed': services_count >= 3, 'points': 34}
        
        total_checks = len(checks)
        passed_checks = sum(1 for c in checks.values() if c['completed'])
        percentage = round((passed_checks / total_checks) * 100) if total_checks > 0 else 0
        
        return {
            'stage_number': 2,
            'checks_total': total_checks,
            'checks_passed': passed_checks,
            'percentage': percentage,
            'details': checks
        }
    
    def calculate_stage_3_automation(self, business_id: str) -> Dict[str, Any]:
        """
        Этап 3: Автоматизация процессов
        Критерии:
        - CRM внедрена: UserServices с service_type='crm' и is_active=1
        - База заполнена: достаточное количество услуг
        """
        checks = {}
        
        # 1. CRM внедрена
        self.cursor.execute("""
            SELECT COUNT(*) FROM UserServices 
            WHERE business_id = ? AND service_type = 'crm' AND is_active = 1
        """, (business_id,))
        crm_count = self.cursor.fetchone()[0]
        checks['crm_implemented'] = {'completed': crm_count > 0, 'points': 50}
        
        # 2. База заполнена (услуги)
        self.cursor.execute("""
            SELECT COUNT(*) FROM UserServices WHERE business_id = ?
        """, (business_id,))
        services_count = self.cursor.fetchone()[0]
        checks['database_filled'] = {'completed': services_count >= 5, 'points': 50}
        
        total_checks = len(checks)
        passed_checks = sum(1 for c in checks.values() if c['completed'])
        percentage = round((passed_checks / total_checks) * 100) if total_checks > 0 else 0
        
        return {
            'stage_number': 3,
            'checks_total': total_checks,
            'checks_passed': passed_checks,
            'percentage': percentage,
            'details': checks
        }
    
    def calculate_stage_4_communication_bots(self, business_id: str) -> Dict[str, Any]:
        """
        Этап 4: Автоматизация коммуникаций и боты
        Критерии:
        - Боты подключены: ai_agents_config содержит ≥1 включенного агента
        - Интеграция с CRM: CRM + агенты одновременно
        """
        checks = {}
        
        # 1. Боты подключены
        self.cursor.execute("""
            SELECT ai_agents_config FROM Businesses WHERE id = ?
        """, (business_id,))
        row = self.cursor.fetchone()
        bots_enabled = False
        if row and row[0]:
            try:
                config = json.loads(row[0])
                # Проверяем, есть ли хотя бы один включенный агент
                for agent_key, agent_data in config.items():
                    if agent_data.get('enabled'):
                        bots_enabled = True
                        break
            except:
                pass
        checks['bots_connected'] = {'completed': bots_enabled, 'points': 50}
        
        # 2. Интеграция с CRM
        self.cursor.execute("""
            SELECT COUNT(*) FROM UserServices 
            WHERE business_id = ? AND service_type = 'crm' AND is_active = 1
        """, (business_id,))
        crm_active = self.cursor.fetchone()[0] > 0
        checks['crm_integration'] = {'completed': bots_enabled and crm_active, 'points': 50}
        
        total_checks = len(checks)
        passed_checks = sum(1 for c in checks.values() if c['completed'])
        percentage = round((passed_checks / total_checks) * 100) if total_checks > 0 else 0
        
        return {
            'stage_number': 4,
            'checks_total': total_checks,
            'checks_passed': passed_checks,
            'percentage': percentage,
            'details': checks
        }
    
    def calculate_all_stages(self, business_id: str) -> Dict[str, Any]:
        """Рассчитать прогресс для всех этапов"""
        progress = {}
        
        # Этапы 1-4: автоматический расчет
        progress['stage_1'] = self.calculate_stage_1_foundation(business_id)
        progress['stage_2'] = self.calculate_stage_2_optimization(business_id)
        progress['stage_3'] = self.calculate_stage_3_automation(business_id)
        progress['stage_4'] = self.calculate_stage_4_communication_bots(business_id)
        
        # Этапы 5-16: пока 0% (требуют ручного ввода метрик)
        for stage_num in range(5, 17):
            progress[f'stage_{stage_num}'] = {
                'stage_number': stage_num,
                'checks_total': 0,
                'checks_passed': 0,
                'percentage': 0,
                'details': {}
            }
        
        return progress


def calculate_business_progress(business_id: str) -> Dict[str, Any]:
    """Функция-обертка для расчета прогресса бизнеса"""
    db = DatabaseManager()
    try:
        calculator = ProgressCalculator(db)
        return calculator.calculate_all_stages(business_id)
    finally:
        db.close()
