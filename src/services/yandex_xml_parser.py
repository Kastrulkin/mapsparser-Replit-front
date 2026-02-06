"""
Yandex Business XML Parser
Парсит XML выгрузку из Яндекс.Бизнес (Автоматизация → Выгрузить данные)
"""
import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Optional


def parse_yandex_network_xml(xml_content: str) -> List[Dict[str, Any]]:
    """
    Парсит XML выгрузку сети из Яндекс.Бизнес
    
    Args:
        xml_content: Содержимое XML файла
    
    Returns:
        List of dictionaries with company data:
        {
            'name': str,
            'address': str,
            'latitude': float | None,
            'longitude': float | None,
            'working_hours': str,
            'phone': str,
            'email': str,
            'yandex_org_id': str,
            'yandex_last_sync': str | None
        }
    
    Example XML:
        <companies>
          <company>
            <name lang="ru">Кебаб</name>
            <address lang="ru">Санкт-Петербург, улица Жукова, 3</address>
            <coordinates>
              <lat>59.963053</lat>
              <lon>30.401636</lon>
            </coordinates>
            <working-time>круглосуточно</working-time>
            <phone><number>+7 (812) 997-77-45</number></phone>
            <email>test@example.com</email>
            <company-id>96622411057</company-id>
          </company>
        </companies>
    """
    try:
        tree = ET.fromstring(xml_content)
    except ET.ParseError as e:
        raise ValueError(f"Некорректный XML формат: {e}")
    
    companies = []
    
    for company_elem in tree.findall('.//company'):
        company_data = _parse_company_element(company_elem)
        if company_data:
            companies.append(company_data)
    
    return companies


def _parse_company_element(company: ET.Element) -> Optional[Dict[str, Any]]:
    """Парсит один элемент company из XML"""
    
    # Извлекаем название (приоритет русскому языку)
    name_ru = company.find("./name[@lang='ru']")
    name_en = company.find("./name[@lang='en']")
    name = (name_ru.text if name_ru is not None else 
            name_en.text if name_en is not None else 
            'Без названия')
    
    # Адрес (приоритет русскому)
    address_ru = company.find("./address[@lang='ru']")
    address_en = company.find("./address[@lang='en']")
    address = (address_ru.text if address_ru is not None else 
               address_en.text if address_en is not None else 
               '')
    
    # Координаты
    coords = company.find('./coordinates')
    latitude = None
    longitude = None
    if coords is not None:
        lat_elem = coords.find('lat')
        lon_elem = coords.find('lon')
        try:
            if lat_elem is not None and lat_elem.text:
                latitude = float(lat_elem.text)
            if lon_elem is not None and lon_elem.text:
                longitude = float(lon_elem.text)
        except ValueError:
            pass  # Игнорируем некорректные координаты
    
    # График работы
    working_time = company.find('./working-time')
    working_hours = working_time.text if working_time is not None else ''
    
    # Телефон
    phone_elem = company.find('./phone/number')
    phone = phone_elem.text if phone_elem is not None else ''
    
    # Email
    email_elem = company.find('./email')
    email = email_elem.text if email_elem is not None else ''
    
    # ID компании в Яндекс
    company_id = company.find('./company-id')
    yandex_org_id = company_id.text if company_id is not None else ''
    
    # Дата актуализации
    actualization = company.find('./actualization-date')
    yandex_last_sync = None
    if actualization is not None and actualization.text:
        try:
            # Преобразуем "10.01.2026" -> "2026-01-10"
            date_parts = actualization.text.split('.')
            if len(date_parts) == 3:
                yandex_last_sync = f"{date_parts[2]}-{date_parts[1]}-{date_parts[0]}"
        except:
            pass
    
    return {
        'name': name.strip(),
        'address': address.strip(),
        'latitude': latitude,
        'longitude': longitude,
        'working_hours': working_hours.strip(),
        'phone': phone.strip(),
        'email': email.strip(),
        'yandex_org_id': yandex_org_id.strip(),
        'yandex_last_sync': yandex_last_sync
    }


def validate_xml(xml_content: str) -> tuple[bool, str]:
    """
    Валидирует XML перед парсингом
    
    Returns:
        (is_valid, error_message)
    """
    try:
        tree = ET.fromstring(xml_content)
        
        # Проверяем что есть хотя бы одна компания
        companies = tree.findall('.//company')
        if not companies:
            return False, "XML не содержит компаний (<company> элементов)"
        
        return True, f"Найдено {len(companies)} компаний"
    
    except ET.ParseError as e:
        return False, f"Ошибка парсинга XML: {e}"
    except Exception as e:
        return False, f"Неожиданная ошибка: {e}"
