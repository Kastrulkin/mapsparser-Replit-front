"""
Определения функций для Function Calling в GigaChat
Эти функции будут переданы в GigaChat API для нативного вызова
"""
from typing import List, Dict, Any

def get_ai_agent_functions() -> List[Dict[str, Any]]:
    """
    Возвращает список функций для Function Calling в GigaChat
    
    Returns:
        List[Dict]: Список определений функций в формате GigaChat API
    """
    return [
        {
            "name": "notify_operator",
            "description": "Уведомить оператора/владельца бизнеса о необходимости его участия в диалоге. Используется когда клиент задает сложный вопрос, требует персонального внимания или когда нужно подтверждение заказа.",
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "Сообщение для оператора с описанием ситуации (например: 'Требуется помощь с заказом', 'Новый заказ от клиента', 'Клиент просит связаться с ним')"
                    }
                },
                "required": ["message"]
            }
        },
        {
            "name": "create_booking",
            "description": "Создать бронирование/заказ на услугу. Используется когда клиент хочет записаться на услугу или сделать заказ.",
            "parameters": {
                "type": "object",
                "properties": {
                    "service_name": {
                        "type": "string",
                        "description": "Название услуги (например: 'Стрижка', 'Маникюр', 'Массаж')"
                    },
                    "booking_date": {
                        "type": "string",
                        "description": "Дата бронирования в формате YYYY-MM-DD (например: '2024-12-25')"
                    },
                    "booking_time": {
                        "type": "string",
                        "description": "Время бронирования в формате HH:MM (например: '14:30')"
                    },
                    "notes": {
                        "type": "string",
                        "description": "Дополнительные заметки или пожелания клиента (опционально)"
                    }
                },
                "required": ["service_name", "booking_date", "booking_time"]
            }
        },
        {
            "name": "send_message",
            "description": "Отправить сообщение клиенту через WhatsApp или Telegram. Используется для отправки подтверждений, напоминаний или дополнительной информации.",
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "Текст сообщения для отправки клиенту"
                    },
                    "channel": {
                        "type": "string",
                        "enum": ["whatsapp", "telegram"],
                        "description": "Канал отправки сообщения"
                    }
                },
                "required": ["message", "channel"]
            }
        },
        {
            "name": "get_client_info",
            "description": "Получить информацию о клиенте: историю предыдущих разговоров, бронирований и предпочтения. Используется для персонализации общения.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        },
        {
            "name": "get_services",
            "description": "Получить список доступных услуг бизнеса с ценами и описаниями. Используется когда клиент спрашивает об услугах или ценах.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        },
        {
            "name": "check_availability",
            "description": "Проверить доступное время для записи на указанную дату. Используется при бронировании для предложения свободных слотов.",
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {
                        "type": "string",
                        "description": "Дата для проверки в формате YYYY-MM-DD (например: '2024-12-25')"
                    },
                    "service_duration": {
                        "type": "integer",
                        "description": "Длительность услуги в минутах (опционально, по умолчанию 30)"
                    }
                },
                "required": ["date"]
            }
        },
        {
            "name": "request_human_support",
            "description": "Призвать в чат представителя салона красоты. Используется когда клиент хочет поговорить с живым человеком, задает сложный вопрос или требует персонального внимания.",
            "parameters": {
                "type": "object",
                "properties": {
                    "salon_id": {
                        "type": "string",
                        "description": "ID салона красоты, представителя которого нужно призвать"
                    },
                    "reason": {
                        "type": "string",
                        "description": "Причина запроса поддержки (например: 'Клиент хочет обсудить детали заказа', 'Сложный вопрос о услугах', 'Требуется консультация')"
                    },
                    "client_message": {
                        "type": "string",
                        "description": "Последнее сообщение клиента для контекста"
                    }
                },
                "required": ["salon_id", "reason"]
            }
        }
    ]

