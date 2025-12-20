#!/usr/bin/env python3
"""
Telegram-бот для обмена отзывами (@beautyreviewexchange_bot)
Функционал:
- Обмен отзывами между пользователями
- Проверка подписки на канал
- Распределение ссылок на бизнесы
- Ежедневная рассылка в 9 утра
"""
import os
import json
import uuid
import re
from datetime import datetime, time, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from telegram.constants import ChatMemberStatus
from safe_db_utils import get_db_connection
import asyncio
import threading

# Автоматически подгружаем переменные окружения из .env
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("⚠️ Для автоматической загрузки .env установите пакет python-dotenv")

# Токен бота для обмена отзывами
TELEGRAM_REVIEWS_BOT_TOKEN = os.getenv('TELEGRAM_REVIEWS_BOT_TOKEN', '')
API_BASE_URL = os.getenv('API_BASE_URL', 'http://localhost:8000')
CHANNEL_USERNAME = '@beautybotpro'  # Канал для проверки подписки

# Словарь для хранения состояния пользователей (telegram_id -> state)
user_states = {}

def init_review_exchange_tables():
    """Инициализация таблиц для обмена отзывами"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Таблица участников обмена отзывами
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ReviewExchangeParticipants (
                id TEXT PRIMARY KEY,
                telegram_id TEXT UNIQUE NOT NULL,
                telegram_username TEXT,
                name TEXT,
                phone TEXT,
                business_name TEXT,
                business_address TEXT,
                business_url TEXT,
                review_request TEXT,
                consent_personal_data INTEGER DEFAULT 0,
                subscribed_to_channel INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Таблица распределения ссылок (чтобы не отправлять одну ссылку дважды)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ReviewExchangeDistribution (
                id TEXT PRIMARY KEY,
                sender_participant_id TEXT NOT NULL,
                receiver_participant_id TEXT NOT NULL,
                sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                review_confirmed INTEGER DEFAULT 0,
                confirmed_at TIMESTAMP,
                FOREIGN KEY (sender_participant_id) REFERENCES ReviewExchangeParticipants(id) ON DELETE CASCADE,
                FOREIGN KEY (receiver_participant_id) REFERENCES ReviewExchangeParticipants(id) ON DELETE CASCADE,
                UNIQUE(sender_participant_id, receiver_participant_id)
            )
        """)
        
        # Добавляем поле review_confirmed, если его ещё нет (для существующих таблиц)
        try:
            cursor.execute("ALTER TABLE ReviewExchangeDistribution ADD COLUMN review_confirmed INTEGER DEFAULT 0")
        except:
            pass  # Поле уже существует
        
        try:
            cursor.execute("ALTER TABLE ReviewExchangeDistribution ADD COLUMN confirmed_at TIMESTAMP")
        except:
            pass  # Поле уже существует
        
        conn.commit()
        print("✅ Таблицы для обмена отзывами созданы/проверены")
    except Exception as e:
        print(f"❌ Ошибка создания таблиц: {e}")
        conn.rollback()
    finally:
        conn.close()

async def check_channel_subscription(bot, user_id: int) -> bool:
    """Проверка подписки пользователя на канал"""
    try:
        member = await bot.get_chat_member(CHANNEL_USERNAME, user_id)
        # Получаем статус как строку для совместимости с разными версиями библиотеки
        status = str(member.status).upper() if hasattr(member.status, 'name') else str(member.status)
        
        # Проверяем все возможные статусы подписки
        # Используем как константы, так и строковые значения для совместимости
        subscribed_statuses = [
            ChatMemberStatus.MEMBER,
            ChatMemberStatus.ADMINISTRATOR,
        ]
        
        # Добавляем CREATOR и OWNER, если они доступны в этой версии библиотеки
        if hasattr(ChatMemberStatus, 'CREATOR'):
            subscribed_statuses.append(ChatMemberStatus.CREATOR)
        if hasattr(ChatMemberStatus, 'OWNER'):
            subscribed_statuses.append(ChatMemberStatus.OWNER)
        
        # Проверяем по константам
        is_subscribed = member.status in subscribed_statuses
        
        # Если не нашли по константам, проверяем строковые значения (для создателя канала)
        if not is_subscribed:
            status_str = status.lower()
            is_subscribed = status_str in ['member', 'administrator', 'creator', 'owner']
        
        print(f"🔍 Проверка подписки для {user_id}: статус={status}, подписан={is_subscribed}")
        return is_subscribed
    except Exception as e:
        print(f"⚠️ Ошибка проверки подписки для {user_id}: {e}")
        # Если ошибка связана с правами бота, пробуем альтернативный способ
        try:
            # Пробуем получить информацию о чате
            chat = await bot.get_chat(CHANNEL_USERNAME)
            print(f"✅ Канал доступен: {chat.title}")
            # Если канал доступен, но проверка не удалась, считаем что подписан (для создателя)
            return True
        except Exception as e2:
            print(f"❌ Не удалось проверить канал: {e2}")
            return False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user_id = str(update.effective_user.id)
    username = update.effective_user.username or ''
    
    # Инициализируем таблицы
    init_review_exchange_tables()
    
    # Проверяем подписку на канал
    is_subscribed = await check_channel_subscription(context.bot, update.effective_user.id)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Проверяем, есть ли пользователь в базе
    cursor.execute("SELECT id, consent_personal_data FROM ReviewExchangeParticipants WHERE telegram_id = ?", (user_id,))
    participant = cursor.fetchone()
    
    if not is_subscribed:
        # Показываем просьбу подписаться
        keyboard = [
            [InlineKeyboardButton("Я подписался. Проверить", callback_data="check_subscription")],
            [InlineKeyboardButton("🔄 Начать заново", callback_data="start_over")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "👋 Привет!\n\n"
            "Отзывы очень важны для продвижения бизнеса, но люди не любят тратить время для оставления хороших отзывов.\n\n"
            "Как помощь мы сделали этот сервис, где владельцы малого бизнеса могут помогать друг другу и обмениваться отзывами.\n\n"
            "📢 Для участия в обмене отзывами необходимо подписаться на наш канал:\n"
            f"👉 {CHANNEL_USERNAME}\n\n"
            "После подписки вы сможете оставить ссылку на ваш бизнес на картах, комментарий, какой отзыв вы хотите увидеть. "
            "Другие участники получат это сообщение и оставят хороший отзыв о вас, а вам придут ссылки на бизнесы других участников и их пожелания.",
            reply_markup=reply_markup
        )
        conn.close()
        return
    
    # Пользователь подписан - проверяем согласие на обработку персональных данных
    if participant:
        participant_id = participant[0]
        consent_given = participant[1] == 1
        
        # Обновляем статус подписки
        cursor.execute("""
            UPDATE ReviewExchangeParticipants 
            SET subscribed_to_channel = 1, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (participant_id,))
        
        if not consent_given:
            # Нужно получить согласие
            keyboard = [[InlineKeyboardButton("✅ Согласен", callback_data="consent_yes")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                "👋 Привет! Рады видеть вас среди нас!\n\n"
                "📋 Для участия в обмене отзывами нам необходимо ваше согласие на обработку персональных данных.\n"
                "Подробнее: https://beautybot.pro/policy",
                reply_markup=reply_markup
            )
            user_states[user_id] = {'state': 'waiting_consent', 'participant_id': participant_id}
            conn.commit()
            conn.close()
            return
    else:
        # Создаём нового участника
        participant_id = str(uuid.uuid4())
        cursor.execute("""
            INSERT INTO ReviewExchangeParticipants 
            (id, telegram_id, telegram_username, subscribed_to_channel)
            VALUES (?, ?, ?, 1)
        """, (participant_id, user_id, username))
        conn.commit()
        
        # Просим согласие
        keyboard = [[InlineKeyboardButton("✅ Согласен", callback_data="consent_yes")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "👋 Привет! Рады видеть вас среди нас!\n\n"
            "📋 Для участия в обмене отзывами нам необходимо ваше согласие на обработку персональных данных.\n"
            "Подробнее: https://beautybot.pro/policy",
            reply_markup=reply_markup
        )
        conn.close()
        user_states[user_id] = {'state': 'waiting_consent', 'participant_id': participant_id}
        return
    
    conn.close()
    
    # Согласие уже дано - просим ссылку
    await update.message.reply_text(
        "👋 Привет! Рады видеть вас среди нас!\n\n"
        "📝 Пожалуйста, отправьте ссылку на карточку вашей компании на картах, где надо будет оставлять отзывы."
    )
    
    user_states[user_id] = {'state': 'waiting_business_url', 'participant_id': participant_id}

async def start_over_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кнопки 'Начать заново'"""
    query = update.callback_query
    await query.answer()
    
    # Создаём фейковый update для вызова start
    class FakeMessage:
        def __init__(self, user):
            self.from_user = user
            self.reply_text = None
    
    class FakeUpdate:
        def __init__(self, query):
            self.effective_user = query.from_user
            self.message = FakeMessage(query.from_user)
            self.callback_query = query
    
    fake_update = FakeUpdate(query)
    # Вызываем start через бота напрямую
    user_id = str(query.from_user.id)
    username = query.from_user.username or ''
    
    # Инициализируем таблицы
    init_review_exchange_tables()
    
    # Проверяем подписку на канал
    is_subscribed = await check_channel_subscription(context.bot, query.from_user.id)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Проверяем, есть ли пользователь в базе
    cursor.execute("SELECT id, consent_personal_data FROM ReviewExchangeParticipants WHERE telegram_id = ?", (user_id,))
    participant = cursor.fetchone()
    
    if not is_subscribed:
        # Показываем просьбу подписаться
        keyboard = [
            [InlineKeyboardButton("Я подписался. Проверить", callback_data="check_subscription")],
            [InlineKeyboardButton("🔄 Начать заново", callback_data="start_over")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "👋 Привет!\n\n"
            "Отзывы очень важны для продвижения бизнеса, но люди не любят тратить время для оставления хороших отзывов.\n\n"
            "Как помощь мы сделали этот сервис, где владельцы малого бизнеса могут помогать друг другу и обмениваться отзывами.\n\n"
            "📢 Для участия в обмене отзывами необходимо подписаться на наш канал:\n"
            f"👉 {CHANNEL_USERNAME}\n\n"
            "После подписки вы сможете оставить ссылку на ваш бизнес на картах, комментарий, какой отзыв вы хотите увидеть. "
            "Другие участники получат это сообщение и оставят хороший отзыв о вас, а вам придут ссылки на бизнесы других участников и их пожелания.",
            reply_markup=reply_markup
        )
        conn.close()
        return
    
    # Пользователь подписан - проверяем согласие на обработку персональных данных
    if participant:
        participant_id = participant[0]
        consent_given = participant[1] == 1
        
        # Обновляем статус подписки
        cursor.execute("""
            UPDATE ReviewExchangeParticipants 
            SET subscribed_to_channel = 1, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (participant_id,))
        
        if not consent_given:
            # Нужно получить согласие
            keyboard = [[InlineKeyboardButton("✅ Согласен", callback_data="consent_yes")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                "👋 Привет! Рады видеть вас среди нас!\n\n"
                "📋 Для участия в обмене отзывами нам необходимо ваше согласие на обработку персональных данных.\n"
                "Подробнее: https://beautybot.pro/policy",
                reply_markup=reply_markup
            )
            user_states[user_id] = {'state': 'waiting_consent', 'participant_id': participant_id}
            conn.commit()
            conn.close()
            return
    else:
        # Создаём нового участника
        participant_id = str(uuid.uuid4())
        cursor.execute("""
            INSERT INTO ReviewExchangeParticipants 
            (id, telegram_id, telegram_username, subscribed_to_channel)
            VALUES (?, ?, ?, 1)
        """, (participant_id, user_id, username))
        conn.commit()
        
        # Просим согласие
        keyboard = [[InlineKeyboardButton("✅ Согласен", callback_data="consent_yes")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "👋 Привет! Рады видеть вас среди нас!\n\n"
            "📋 Для участия в обмене отзывами нам необходимо ваше согласие на обработку персональных данных.\n"
            "Подробнее: https://beautybot.pro/policy",
            reply_markup=reply_markup
        )
        conn.close()
        user_states[user_id] = {'state': 'waiting_consent', 'participant_id': participant_id}
        return
    
    conn.close()
    
    # Согласие уже дано - просим ссылку
    await query.edit_message_text(
        "👋 Привет! Рады видеть вас среди нас!\n\n"
        "📝 Пожалуйста, отправьте ссылку на карточку вашей компании на картах, где надо будет оставлять отзывы."
    )
    
    user_states[user_id] = {'state': 'waiting_business_url', 'participant_id': participant_id}

async def start_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстового сообщения 'Старт' или 'start'"""
    await start(update, context)

async def check_subscription_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кнопки проверки подписки"""
    query = update.callback_query
    await query.answer()
    
    user_id = str(update.effective_user.id)
    
    # Проверяем подписку
    is_subscribed = await check_channel_subscription(context.bot, update.effective_user.id)
    
    if is_subscribed:
        # Пользователь подписан
        conn = get_db_connection()
        cursor = conn.cursor()
        
        username = update.effective_user.username or ''
        cursor.execute("SELECT id, consent_personal_data FROM ReviewExchangeParticipants WHERE telegram_id = ?", (user_id,))
        participant = cursor.fetchone()
        
        if participant:
            participant_id = participant[0]
            consent_given = participant[1] == 1
            cursor.execute("""
                UPDATE ReviewExchangeParticipants 
                SET subscribed_to_channel = 1, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (participant_id,))
        else:
            participant_id = str(uuid.uuid4())
            cursor.execute("""
                INSERT INTO ReviewExchangeParticipants 
                (id, telegram_id, telegram_username, subscribed_to_channel)
                VALUES (?, ?, ?, 1)
            """, (participant_id, user_id, username))
            consent_given = False
        
        conn.commit()
        conn.close()
        
        if not consent_given:
            # Просим согласие
            keyboard = [[InlineKeyboardButton("✅ Согласен", callback_data="consent_yes")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                "✅ Отлично! Вы подписаны на канал.\n\n"
                "📋 Для участия в обмене отзывами нам необходимо ваше согласие на обработку персональных данных.\n"
                "Подробнее: https://beautybot.pro/policy",
                reply_markup=reply_markup
            )
            user_states[user_id] = {'state': 'waiting_consent', 'participant_id': participant_id}
        else:
            await query.edit_message_text(
                "✅ Отлично! Вы подписаны на канал.\n\n"
                "👋 Рады видеть вас среди нас!\n\n"
                "📝 Пожалуйста, отправьте ссылку на карточку вашей компании на картах, где надо будет оставлять отзывы."
            )
            user_states[user_id] = {'state': 'waiting_business_url', 'participant_id': participant_id}
    else:
        # Пользователь не подписан
        keyboard = [[InlineKeyboardButton("Я подписался. Проверить", callback_data="check_subscription")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "❌ Вы ещё не подписаны на канал.\n\n"
            f"📢 Пожалуйста, подпишитесь на {CHANNEL_USERNAME}\n\n"
            "После подписки нажмите кнопку ниже для проверки.",
            reply_markup=reply_markup
        )

async def review_left_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кнопки 'Я оставил отзыв'"""
    query = update.callback_query
    await query.answer()
    
    # Извлекаем distribution_id из callback_data
    distribution_id = query.data.replace("review_left_", "")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Проверяем, что эта запись существует и принадлежит этому пользователю
    cursor.execute("""
        SELECT receiver_participant_id, review_confirmed
        FROM ReviewExchangeDistribution
        WHERE id = ?
    """, (distribution_id,))
    
    result = cursor.fetchone()
    
    if not result:
        await query.edit_message_text("❌ Ошибка: запись не найдена.")
        conn.close()
        return
    
    receiver_participant_id, already_confirmed = result
    
    # Проверяем, что это действительно этот пользователь
    user_id = str(query.from_user.id)
    cursor.execute("""
        SELECT id FROM ReviewExchangeParticipants 
        WHERE telegram_id = ? AND id = ?
    """, (user_id, receiver_participant_id))
    
    participant_check = cursor.fetchone()
    
    if not participant_check:
        await query.edit_message_text("❌ Ошибка: вы не можете подтвердить этот отзыв.")
        conn.close()
        return
    
    if already_confirmed:
        await query.edit_message_text("✅ Вы уже подтвердили этот отзыв ранее. Спасибо!")
        conn.close()
        return
    
    # Отмечаем отзыв как подтверждённый
    cursor.execute("""
        UPDATE ReviewExchangeDistribution 
        SET review_confirmed = 1, confirmed_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (distribution_id,))
    
    conn.commit()
    conn.close()
    
    # Обновляем сообщение
    await query.edit_message_text(
        query.message.text + "\n\n✅ Спасибо! Ваше подтверждение получено. Это откроет вам доступ к следующим ссылкам, а ваша компания также продолжит рассылаться дальше."
    )

async def consent_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик согласия на обработку персональных данных"""
    query = update.callback_query
    await query.answer()
    
    user_id = str(update.effective_user.id)
    
    if user_id not in user_states:
        await query.edit_message_text("❌ Ошибка. Начни с команды /start")
        return
    
    participant_id = user_states[user_id].get('participant_id')
    
    # Сохраняем согласие
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE ReviewExchangeParticipants 
        SET consent_personal_data = 1, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (participant_id,))
    conn.commit()
    conn.close()
    
    await query.edit_message_text(
        "✅ Спасибо за согласие!\n\n"
        "📝 Пожалуйста, отправьте ссылку на карточку вашей компании на картах, где надо будет оставлять отзывы."
    )
    
    user_states[user_id]['state'] = 'waiting_business_url'

async def force_send_links(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда для принудительной отправки ссылок (для тестирования)"""
    user_id = str(update.effective_user.id)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Находим участника
    cursor.execute("SELECT id FROM ReviewExchangeParticipants WHERE telegram_id = ?", (user_id,))
    participant = cursor.fetchone()
    conn.close()
    
    if not participant:
        await update.message.reply_text(
            "❌ Вы не зарегистрированы в системе. Используйте команду /start для начала."
        )
        return
    
    participant_id = participant[0]
    
    # Проверяем, есть ли доступные ссылки перед отправкой
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT COUNT(*) 
        FROM ReviewExchangeParticipants p
        WHERE p.id != ? 
        AND p.is_active = 1
        AND p.business_url IS NOT NULL
        AND p.review_request IS NOT NULL
        AND NOT EXISTS (
            SELECT 1 FROM ReviewExchangeDistribution d
            WHERE d.sender_participant_id = p.id 
            AND d.receiver_participant_id = ?
        )
    """, (participant_id, participant_id))
    
    available_count = cursor.fetchone()[0]
    conn.close()
    
    if available_count == 0:
        await update.message.reply_text(
            "📭 Пока нет новых бизнесов для обмена отзывами. Мы отправим их, как только появятся!"
        )
        return
    
    # Отправляем ссылки (функция send_business_links сама отправит сообщения)
    await send_business_links(update, context, participant_id, user_id, limit=3)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений"""
    user_id = str(update.effective_user.id)
    text = update.message.text
    
    if user_id not in user_states:
        await start(update, context)
        return
    
    state = user_states[user_id].get('state', '')
    participant_id = user_states[user_id].get('participant_id')
    
    if state == 'waiting_consent':
        await update.message.reply_text(
            "Пожалуйста, нажми кнопку '✅ Согласен' для продолжения."
        )
        return
    
    if state == 'waiting_business_url':
        # Проверяем, что это ссылка на карты
        url_pattern = r'(https?://(?:yandex\.ru/maps|maps\.yandex\.ru|maps\.google\.com|google\.ru/maps)/[^\s]+)'
        match = re.search(url_pattern, text)
        
        if not match:
            await update.message.reply_text(
                "❌ Пожалуйста, отправьте корректную ссылку на карточку компании на Яндекс.Картах или Google Maps.\n\n"
                "Пример: https://yandex.ru/maps/org/..."
            )
            return
        
        business_url = match.group(1)
        
        # Сохраняем ссылку и имя пользователя из Telegram
        user_name = update.effective_user.first_name or update.effective_user.username or ''
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE ReviewExchangeParticipants 
            SET business_url = ?, name = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (business_url, user_name, participant_id))
        conn.commit()
        conn.close()
        
        await update.message.reply_text(
            "✅ Ссылка сохранена!\n\n"
            "📝 Теперь отправьте комментарий, какой отзыв вы хотите увидеть.\n\n"
            "Например:\n"
            "• Новый мастер, чудо как хорош\n"
            "• Эта услуга выше всяких похвал\n"
            "• Отличное обслуживание и качество"
        )
        
        user_states[user_id]['state'] = 'waiting_review_request'
    elif state == 'waiting_review_request':
        # Сохраняем пожелание к отзыву
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE ReviewExchangeParticipants 
            SET review_request = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (text, participant_id))
        conn.commit()
        conn.close()
        
        await update.message.reply_text(
            "✅ Пожелание к отзыву сохранено!\n\n"
            "💡 Вы можете изменить его в любой момент, просто отправьте новое сообщение.\n\n"
            "📬 Сейчас вам придут ссылки на бизнесы других участников (до 3 ссылок).\n"
            "Каждый день в 9:00 утра вы будете получать новые ссылки, пока они есть."
        )
        
        # Отправляем ссылки на другие бизнесы
        await send_business_links(update, context, participant_id, user_id)
        
        user_states[user_id]['state'] = 'active'
        
    elif state == 'active':
        # Пользователь может изменить пожелание к отзыву
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE ReviewExchangeParticipants 
            SET review_request = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (text, participant_id))
        conn.commit()
        conn.close()
        
        await update.message.reply_text(
            "✅ Пожелание к отзыву обновлено!\n\n"
            "💡 Вы можете изменить его в любой момент, просто отправьте новое сообщение."
        )

async def send_business_links(update: Update, context: ContextTypes.DEFAULT_TYPE, participant_id: str, user_id: str, limit: int = 3):
    """Отправка ссылок на бизнесы других участников с равномерным распределением"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Получаем участников, которым ещё не отправляли ссылку на этого пользователя
    # И которые ещё не получили слишком много ссылок (равномерное распределение)
    # Сначала проверяем, сколько всего участников
    cursor.execute("""
        SELECT COUNT(*) 
        FROM ReviewExchangeParticipants 
        WHERE is_active = 1 
        AND business_url IS NOT NULL 
        AND review_request IS NOT NULL
    """)
    total_participants = cursor.fetchone()[0]
    
    # Если участников мало (меньше 5), упрощаем логику - просто ищем тех, кому ещё не отправляли
    if total_participants < 5:
        cursor.execute("""
            SELECT p.id, p.business_url, p.review_request, p.business_name, p.business_address
            FROM ReviewExchangeParticipants p
            WHERE p.id != ? 
            AND p.is_active = 1
            AND p.business_url IS NOT NULL
            AND p.review_request IS NOT NULL
            AND NOT EXISTS (
                SELECT 1 FROM ReviewExchangeDistribution d
                WHERE d.sender_participant_id = p.id 
                AND d.receiver_participant_id = ?
            )
            ORDER BY RANDOM()
            LIMIT ?
        """, (participant_id, participant_id, limit))
    else:
        # Для большого количества участников используем равномерное распределение
        cursor.execute("""
            SELECT p.id, p.business_url, p.review_request, p.business_name, p.business_address
            FROM ReviewExchangeParticipants p
            WHERE p.id != ? 
            AND p.is_active = 1
            AND p.business_url IS NOT NULL
            AND p.review_request IS NOT NULL
            AND NOT EXISTS (
                SELECT 1 FROM ReviewExchangeDistribution d
                WHERE d.sender_participant_id = p.id 
                AND d.receiver_participant_id = ?
            )
            AND (
                SELECT COUNT(*) FROM ReviewExchangeDistribution d2
                WHERE d2.sender_participant_id = p.id
            ) < (
                SELECT COALESCE(AVG(sent_count), 0) FROM (
                    SELECT COUNT(*) as sent_count
                    FROM ReviewExchangeDistribution
                    GROUP BY sender_participant_id
                )
            ) + 5
            ORDER BY (
                SELECT COUNT(*) FROM ReviewExchangeDistribution d3
                WHERE d3.sender_participant_id = p.id
            ) ASC, RANDOM()
            LIMIT ?
        """, (participant_id, participant_id, limit))
    
    businesses = cursor.fetchall()
    
    if not businesses:
        message = "📭 Пока нет новых бизнесов для обмена отзывами. Мы отправим их, как только появятся!"
        if update and update.message:
            await update.message.reply_text(message)
        else:
            await context.bot.send_message(chat_id=user_id, text=message)
        conn.close()
        return
    
    # Отправляем ссылки
    for business in businesses:
        other_participant_id, business_url, review_request, business_name, business_address = business
        
        # Записываем, что отправили
        distribution_id = str(uuid.uuid4())
        cursor.execute("""
            INSERT INTO ReviewExchangeDistribution 
            (id, sender_participant_id, receiver_participant_id)
            VALUES (?, ?, ?)
        """, (distribution_id, other_participant_id, participant_id))
        
        message_text = f"📝 Новый бизнес для обмена отзывами:\n\n"
        if business_name:
            message_text += f"🏢 {business_name}\n"
        if business_address:
            message_text += f"📍 {business_address}\n"
        message_text += f"\n🔗 {business_url}\n\n"
        if review_request:
            message_text += f"💬 Пожелание к отзыву:\n{review_request}\n\n"
        message_text += "ℹ️ Пожалуйста, после того, как оставите отзыв, кликните по кнопке, чтобы подтвердить. Это откроет вам доступ к следующим, а ваша компания также продолжит рассылаться дальше."
        
        # Создаём кнопку "Я оставил отзыв" с callback_data, содержащим distribution_id
        keyboard = [[InlineKeyboardButton("✅ Я оставил отзыв", callback_data=f"review_left_{distribution_id}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if update and update.message:
            await update.message.reply_text(message_text, reply_markup=reply_markup)
        else:
            await context.bot.send_message(chat_id=user_id, text=message_text, reply_markup=reply_markup)
    
    conn.commit()
    conn.close()

async def daily_distribution_task(bot):
    """Ежедневная рассылка ссылок в 9:00 утра"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Получаем всех активных участников
    cursor.execute("""
        SELECT id, telegram_id 
        FROM ReviewExchangeParticipants 
        WHERE is_active = 1 
        AND business_url IS NOT NULL
        AND review_request IS NOT NULL
    """)
    
    participants = cursor.fetchall()
    conn.close()
    
    # Создаём контекст для отправки
    class FakeContext:
        def __init__(self, bot):
            self.bot = bot
    
    context = FakeContext(bot)
    
    for participant_id, telegram_id in participants:
        try:
            await send_business_links(None, context, participant_id, telegram_id, limit=3)
        except Exception as e:
            print(f"❌ Ошибка отправки ссылок пользователю {telegram_id}: {e}")

def run_daily_scheduler():
    """Запуск планировщика ежедневной рассылки"""
    import schedule
    import time
    
    def run_distribution():
        if not TELEGRAM_REVIEWS_BOT_TOKEN:
            return
        
        # Создаём приложение для рассылки
        application = Application.builder().token(TELEGRAM_REVIEWS_BOT_TOKEN).build()
        
        # Запускаем рассылку
        asyncio.run(daily_distribution_task(application.bot))
    
    schedule.every().day.at("09:00").do(run_distribution)
    
    while True:
        schedule.run_pending()
        time.sleep(60)  # Проверяем каждую минуту

def main():
    """Запуск бота"""
    if not TELEGRAM_REVIEWS_BOT_TOKEN:
        print("⚠️  TELEGRAM_REVIEWS_BOT_TOKEN не установлен. Бот не будет запущен.")
        print("💡 Установите токен: export TELEGRAM_REVIEWS_BOT_TOKEN='ваш_токен'")
        print("💡 Или добавьте в .env файл: TELEGRAM_REVIEWS_BOT_TOKEN=ваш_токен")
        return
    
    # Инициализируем таблицы
    init_review_exchange_tables()
    
    try:
        application = Application.builder().token(TELEGRAM_REVIEWS_BOT_TOKEN).build()
        
        # Регистрируем обработчики
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("force_send_links", force_send_links))
        application.add_handler(CallbackQueryHandler(check_subscription_callback, pattern="check_subscription"))
        application.add_handler(CallbackQueryHandler(consent_callback, pattern="consent_yes"))
        application.add_handler(CallbackQueryHandler(start_over_callback, pattern="start_over"))
        application.add_handler(CallbackQueryHandler(review_left_callback, pattern="^review_left_"))
        # Обработчик текста "Старт" или "start" (без слэша)
        application.add_handler(MessageHandler(filters.TEXT & filters.Regex(r'^(Старт|старт|start|Start)$'), start_text_handler))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        
        # Запускаем планировщик ежедневной рассылки в отдельном потоке
        try:
            import schedule
            scheduler_thread = threading.Thread(target=run_daily_scheduler, daemon=True)
            scheduler_thread.start()
            print("⏰ Ежедневная рассылка настроена на 9:00 утра")
        except ImportError:
            print("⚠️ Библиотека schedule не установлена. Ежедневная рассылка не будет работать.")
            print("💡 Установите: pip install schedule")
        
        print("🤖 Telegram-бот для обмена отзывами запущен...")
        print(f"📡 API Base URL: {API_BASE_URL}")
        print("✅ Бот готов к работе. Ожидаю сообщения...")
        
        application.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)
    except Exception as e:
        print(f"❌ Ошибка запуска бота: {e}")
        print(f"💡 Проверьте:")
        print(f"   1. Правильность токена TELEGRAM_REVIEWS_BOT_TOKEN")
        print(f"   2. Установлена ли зависимость: pip install python-telegram-bot>=20.0")
        print(f"   3. Доступность интернета для подключения к Telegram API")
        raise

if __name__ == "__main__":
    main()
