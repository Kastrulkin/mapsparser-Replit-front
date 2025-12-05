#!/usr/bin/env python3
"""
Telegram-бот для управления аккаунтом BeautyBot
Функционал:
- Привязка аккаунта через токен
- Добавление транзакций (фото/текст)
- Оптимизация услуг
- Настройки компании
"""
import os
import json
import uuid
import base64
import requests
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from safe_db_utils import get_db_connection
from services.gigachat_client import analyze_screenshot_with_gigachat, analyze_text_with_gigachat

# Автоматически подгружаем переменные окружения из .env,
# как это сделано в main.py, чтобы GigaChat-ключи и другие
# настройки, заданные в проекте, были доступны и боту.
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("⚠️ Для автоматической загрузки .env установите пакет python-dotenv")

# Токен бота и базовый URL API из переменных окружения
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
API_BASE_URL = os.getenv('API_BASE_URL', 'http://localhost:8000')

# Словарь для хранения состояния пользователей (telegram_id -> state)
user_states = {}

def get_user_id_from_telegram(telegram_id: str):
    """Получить user_id из telegram_id"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM Users WHERE telegram_id = ?", (telegram_id,))
    user_row = cursor.fetchone()
    conn.close()
    return user_row[0] if user_row else None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user_id = str(update.effective_user.id)
    args = context.args
    
    # Если передан токен привязки
    if args and len(args) > 0:
        bind_token = args[0]
        await handle_bind_token(update, context, bind_token, user_id)
        return
    
    # Проверяем, привязан ли аккаунт
    db_user_id = get_user_id_from_telegram(user_id)
    
    if not db_user_id:
        await update.message.reply_text(
            "👋 Привет! Для использования бота нужно связать ваш Telegram-аккаунт с аккаунтом на сайте.\n\n"
            "📱 Перейдите в личный кабинет на сайте и найдите раздел 'Telegram-бот' для получения кода привязки.\n\n"
            "Или отправьте команду:\n/start <ваш_код_привязки>"
        )
        return
    
    # Показываем главное меню
    await show_main_menu(update, context, user_id, db_user_id)

async def handle_bind_token(update: Update, context: ContextTypes.DEFAULT_TYPE, bind_token: str, telegram_id: str):
    """Обработка токена привязки"""
    try:
        # Вызываем API для проверки токена
        response = requests.post(
            f"{API_BASE_URL}/api/telegram/bind/verify",
            json={"token": bind_token, "telegram_id": telegram_id},
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            await update.message.reply_text(
                f"✅ Аккаунт успешно привязан!\n\n"
                f"👤 Пользователь: {data.get('user', {}).get('name', 'Не указано')}\n"
                f"📧 Email: {data.get('user', {}).get('email', 'Не указано')}\n\n"
                f"Теперь вы можете использовать все функции бота!"
            )
            await show_main_menu(update, context, telegram_id, data.get('user', {}).get('id'))
        else:
            error_data = response.json()
            await update.message.reply_text(f"❌ Ошибка привязки: {error_data.get('error', 'Неизвестная ошибка')}")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка подключения к серверу: {str(e)}")

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, telegram_id: str, db_user_id: str = None):
    """Показать главное меню"""
    if not db_user_id:
        db_user_id = get_user_id_from_telegram(telegram_id)
        if not db_user_id:
            await update.message.reply_text("❌ Аккаунт не привязан. Используйте /start <код_привязки>")
            return
    
    keyboard = [
        [InlineKeyboardButton("💰 Добавить транзакцию", callback_data="menu_transaction")],
        [InlineKeyboardButton("📊 Оптимизировать услуги", callback_data="menu_optimize")],
        [InlineKeyboardButton("⚙️ Настройки компании", callback_data="menu_settings")],
        [InlineKeyboardButton("📈 Статистика", callback_data="menu_stats")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = "🏠 *Главное меню*\n\nВыберите действие:"
    
    if hasattr(update, 'message') and update.message:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    elif hasattr(update, 'callback_query') and update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатий на кнопки"""
    query = update.callback_query
    await query.answer()
    
    user_id = str(update.effective_user.id)
    data = query.data
    db_user_id = get_user_id_from_telegram(user_id)
    
    if not db_user_id:
        await query.edit_message_text("❌ Аккаунт не привязан. Используйте /start <код_привязки>")
        return
    
    if data == "menu_transaction":
        await show_business_selection(update, context, user_id, db_user_id, "transaction")
    elif data == "menu_optimize":
        await show_business_selection(update, context, user_id, db_user_id, "optimize")
    elif data == "menu_settings":
        await show_business_selection(update, context, user_id, db_user_id, "settings")
    elif data == "menu_stats":
        await query.edit_message_text("📈 Статистика пока в разработке. Используйте личный кабинет на сайте.")
        await show_main_menu(update, context, user_id, db_user_id)
    elif data.startswith("business_"):
        parts = data.split("_")
        if len(parts) >= 3:
            action = parts[1]  # transaction, optimize, settings
            business_id = "_".join(parts[2:])  # На случай если в ID есть подчеркивания
            
            if action == "transaction":
                user_states[user_id] = {
                    'state': 'waiting_transaction',
                    'business_id': business_id
                }
                await query.edit_message_text(
                    "💰 *Добавление транзакции*\n\n"
                    "Отправьте:\n"
                    "1. 📷 Фото чека/документа, или\n"
                    "2. 📝 Текст в формате:\n"
                    "   Сумма: 1000\n"
                    "   Услуги: Стрижка, Окрашивание\n"
                    "   Мастер: Имя (опционально)\n"
                    "   Дата: YYYY-MM-DD (опционально)\n\n"
                    "Или /cancel для отмены",
                    parse_mode='Markdown'
                )
            elif action == "optimize":
                user_states[user_id] = {
                    'state': 'waiting_optimize',
                    'business_id': business_id
                }
                await query.edit_message_text(
                    "📊 *Оптимизация услуг*\n\n"
                    "Отправьте:\n"
                    "1. 📷 Фото прайс-листа, или\n"
                    "2. 📝 Текст со списком услуг\n\n"
                    "Бот проанализирует и предложит SEO-оптимизированные названия.\n\n"
                    "Или /cancel для отмены",
                    parse_mode='Markdown'
                )
            elif action == "settings":
                await show_settings_menu(update, context, user_id, business_id)
    elif data.startswith("setting_"):
        parts = data.split("_")
        if len(parts) >= 3:
            setting_type = parts[1]  # name, address, maps, etc
            business_id = "_".join(parts[2:])
            user_states[user_id] = {
                'state': f'waiting_setting_{setting_type}',
                'business_id': business_id
            }
            
            setting_names = {
                'name': 'название компании',
                'address': 'адрес',
                'maps': 'ссылку на карты',
                'phone': 'телефон',
                'hours': 'часы работы'
            }
            
            await query.edit_message_text(
                f"⚙️ *Изменение {setting_names.get(setting_type, setting_type)}*\n\n"
                f"Отправьте новое значение:\n\n"
                f"Или /cancel для отмены",
                parse_mode='Markdown'
            )
    elif data == "back_to_menu":
        await show_main_menu(update, context, user_id, db_user_id)

async def show_business_selection(update: Update, context: ContextTypes.DEFAULT_TYPE, telegram_id: str, db_user_id: str, action: str):
    """Показать выбор бизнеса"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name FROM Businesses WHERE owner_id = ?", (db_user_id,))
    businesses = cursor.fetchall()
    conn.close()
    
    if not businesses:
        text = "У вас пока нет бизнесов. Создайте бизнес на сайте."
        if hasattr(update, 'callback_query') and update.callback_query:
            await update.callback_query.edit_message_text(text)
        return
    
    keyboard = []
    for business_id, business_name in businesses:
        keyboard.append([InlineKeyboardButton(
            business_name, 
            callback_data=f"business_{action}_{business_id}"
        )])
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    action_names = {
        "transaction": "добавления транзакции",
        "optimize": "оптимизации услуг",
        "settings": "настроек компании"
    }
    
    text = f"Выберите бизнес для {action_names.get(action, action)}:"
    
    if hasattr(update, 'callback_query') and update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup)

async def show_settings_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, telegram_id: str, business_id: str):
    """Показать меню настроек компании"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name, address, working_hours FROM Businesses WHERE id = ?", (business_id,))
    business = cursor.fetchone()
    conn.close()
    
    if not business:
        await update.callback_query.edit_message_text("❌ Бизнес не найден")
        return
    
    keyboard = [
        [InlineKeyboardButton("📝 Название", callback_data=f"setting_name_{business_id}")],
        [InlineKeyboardButton("📍 Адрес", callback_data=f"setting_address_{business_id}")],
        [InlineKeyboardButton("🗺️ Ссылка на карты", callback_data=f"setting_maps_{business_id}")],
        [InlineKeyboardButton("📞 Телефон", callback_data=f"setting_phone_{business_id}")],
        [InlineKeyboardButton("🕐 Часы работы", callback_data=f"setting_hours_{business_id}")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = f"⚙️ *Настройки компании*\n\n"
    text += f"📝 Название: {business[0] or 'Не указано'}\n"
    text += f"📍 Адрес: {business[1] or 'Не указано'}\n"
    text += f"🕐 Часы работы: {business[2] or 'Не указано'}\n\n"
    text += "Выберите параметр для изменения:"
    
    await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик фото"""
    user_id = str(update.effective_user.id)
    
    if user_id not in user_states:
        await update.message.reply_text("Используйте /start для начала работы")
        return
    
    state = user_states[user_id].get('state', '')
    
    if state == 'waiting_transaction':
        await handle_transaction_photo(update, context, user_id)
    elif state == 'waiting_optimize':
        await handle_optimize_photo(update, context, user_id)
    else:
        await update.message.reply_text("Неожиданное фото. Используйте /start для начала работы")

async def handle_transaction_photo(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: str):
    """Обработка фото транзакции"""
    business_id = user_states[user_id].get('business_id')
    db_user_id = get_user_id_from_telegram(user_id)
    
    if not db_user_id:
        await update.message.reply_text("❌ Аккаунт не привязан")
        return
    
    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    
    await update.message.reply_text("⏳ Обрабатываю фото...")
    
    try:
        photo_bytes = await file.download_as_bytearray()
        image_base64 = base64.b64encode(photo_bytes).decode('utf-8')
        
        # Читаем промпт
        try:
            with open('prompts/transaction-analysis-prompt.txt', 'r', encoding='utf-8') as f:
                prompt = f.read()
        except:
            prompt = "Проанализируй фото и извлеки информацию о транзакции (дата, сумма, услуги, мастер)."
        
        result = analyze_screenshot_with_gigachat(image_base64, prompt)
        
        if 'error' in result:
            await update.message.reply_text(f"❌ Ошибка анализа: {result['error']}")
            return
        
        # Парсим результат
        analysis_result = json.loads(result) if isinstance(result, str) else result
        transactions = analysis_result.get('transactions', [])
        
        if not transactions:
            await update.message.reply_text("❌ Не удалось распознать транзакции на фото")
            return
        
        # Сохраняем транзакции
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Проверяем наличие полей
        cursor.execute("PRAGMA table_info(FinancialTransactions)")
        columns = [row[1] for row in cursor.fetchall()]
        has_master_id = 'master_id' in columns
        has_business_id = 'business_id' in columns
        
        saved_count = 0
        for trans in transactions:
            transaction_id = str(uuid.uuid4())
            
            master_id = None
            if trans.get('master_name') and has_master_id:
                cursor.execute("SELECT id FROM Masters WHERE name = ? AND business_id = ? LIMIT 1", 
                             (trans['master_name'], business_id))
                master_row = cursor.fetchone()
                if master_row:
                    master_id = master_row[0]
            
            if has_master_id and has_business_id:
                cursor.execute("""
                    INSERT INTO FinancialTransactions 
                    (id, user_id, business_id, transaction_date, amount, client_type, services, notes, master_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    transaction_id, db_user_id, business_id,
                    trans.get('transaction_date', datetime.now().strftime('%Y-%m-%d')),
                    trans.get('amount', 0), trans.get('client_type', 'new'),
                    json.dumps(trans.get('services', [])), trans.get('notes', ''),
                    master_id
                ))
            elif has_master_id:
                cursor.execute("""
                    INSERT INTO FinancialTransactions 
                    (id, user_id, transaction_date, amount, client_type, services, notes, master_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    transaction_id, db_user_id,
                    trans.get('transaction_date', datetime.now().strftime('%Y-%m-%d')),
                    trans.get('amount', 0), trans.get('client_type', 'new'),
                    json.dumps(trans.get('services', [])), trans.get('notes', ''),
                    master_id
                ))
            else:
                cursor.execute("""
                    INSERT INTO FinancialTransactions 
                    (id, user_id, transaction_date, amount, client_type, services, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    transaction_id, db_user_id,
                    trans.get('transaction_date', datetime.now().strftime('%Y-%m-%d')),
                    trans.get('amount', 0), trans.get('client_type', 'new'),
                    json.dumps(trans.get('services', [])), trans.get('notes', '')
                ))
            saved_count += 1
        
        conn.commit()
        conn.close()
        
        await update.message.reply_text(
            f"✅ Успешно добавлено {saved_count} транзакций!\n\n"
            f"Используйте /start для возврата в меню"
        )
        
        user_states[user_id] = {'state': 'idle'}
        
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка обработки фото: {str(e)}")

async def handle_optimize_photo(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: str):
    """Обработка фото для оптимизации"""
    business_id = user_states[user_id].get('business_id')
    db_user_id = get_user_id_from_telegram(user_id)
    
    if not db_user_id:
        await update.message.reply_text("❌ Аккаунт не привязан")
        return
    
    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    
    await update.message.reply_text("⏳ Анализирую прайс-лист...")
    
    try:
        photo_bytes = await file.download_as_bytearray()
        image_base64 = base64.b64encode(photo_bytes).decode('utf-8')
        
        # Читаем промпт оптимизации
        try:
            with open('prompts/seo-optimization-prompt.txt', 'r', encoding='utf-8') as f:
                prompt = f.read()
        except:
            prompt = "Оптимизируй прайс-лист услуг для локального SEO."
        
        result = analyze_screenshot_with_gigachat(image_base64, prompt)
        
        if 'error' in result:
            await update.message.reply_text(f"❌ Ошибка анализа: {result['error']}")
            return
        
        # Парсим результат
        analysis_result = json.loads(result) if isinstance(result, str) else result
        services = analysis_result.get('services', [])
        
        if not services:
            await update.message.reply_text("❌ Не удалось распознать услуги на фото")
            return
        
        # Формируем ответ
        text = "📊 *Результаты оптимизации:*\n\n"
        for i, service in enumerate(services[:10], 1):  # Показываем первые 10
            text += f"{i}. *{service.get('original_name', 'N/A')}*\n"
            text += f"   → {service.get('optimized_name', 'N/A')}\n\n"
        
        if len(services) > 10:
            text += f"\n... и ещё {len(services) - 10} услуг\n"
        
        text += "\n💡 Полные результаты доступны в личном кабинете на сайте."
        
        await update.message.reply_text(text, parse_mode='Markdown')
        user_states[user_id] = {'state': 'idle'}
        
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка обработки фото: {str(e)}")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений"""
    user_id = str(update.effective_user.id)
    text = update.message.text
    
    # Обработка команды /cancel
    if text.startswith('/cancel'):
        user_states[user_id] = {'state': 'idle'}
        await update.message.reply_text("❌ Операция отменена. Используйте /start для возврата в меню.")
        return
    
    if user_id not in user_states:
        await update.message.reply_text("Используйте /start для начала работы")
        return
    
    state = user_states[user_id].get('state', '')
    
    if state == 'waiting_transaction':
        await handle_transaction_text(update, context, user_id, text)
    elif state == 'waiting_optimize':
        await handle_optimize_text(update, context, user_id, text)
    elif state.startswith('waiting_setting_'):
        await handle_setting_text(update, context, user_id, text, state)
    else:
        await update.message.reply_text("Неожиданное сообщение. Используйте /start для начала работы")

async def handle_transaction_text(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: str, text: str):
    """Обработка текста транзакции"""
    business_id = user_states[user_id].get('business_id')
    db_user_id = get_user_id_from_telegram(user_id)
    
    if not db_user_id:
        await update.message.reply_text("❌ Аккаунт не привязан")
        return
    
    # Парсим текст
    transaction_data = {
        'transaction_date': datetime.now().strftime('%Y-%m-%d'),
        'amount': 0,
        'client_type': 'new',
        'services': [],
        'master_name': None,
        'notes': ''
    }
    
    lines = text.split('\n')
    for line in lines:
        if ':' in line:
            key, value = line.split(':', 1)
            key = key.strip().lower()
            value = value.strip()
            
            if 'дата' in key:
                transaction_data['transaction_date'] = value
            elif 'сумма' in key:
                try:
                    transaction_data['amount'] = float(value.replace('₽', '').replace('руб', '').strip())
                except:
                    pass
            elif 'услуги' in key:
                transaction_data['services'] = [s.strip() for s in value.split(',')]
            elif 'мастер' in key:
                transaction_data['master_name'] = value
            elif 'тип' in key and 'клиент' in key:
                transaction_data['client_type'] = value if value in ['new', 'returning'] else 'new'
            else:
                transaction_data['notes'] += line + ' '
    
    if transaction_data['amount'] == 0:
        await update.message.reply_text("❌ Пожалуйста, укажите сумму транзакции")
        return
    
    # Сохраняем транзакцию
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Проверяем наличие полей
    cursor.execute("PRAGMA table_info(FinancialTransactions)")
    columns = [row[1] for row in cursor.fetchall()]
    has_master_id = 'master_id' in columns
    has_business_id = 'business_id' in columns
    
    transaction_id = str(uuid.uuid4())
    
    master_id = None
    if transaction_data.get('master_name') and has_master_id:
        cursor.execute("SELECT id FROM Masters WHERE name = ? AND business_id = ? LIMIT 1", 
                     (transaction_data['master_name'], business_id))
        master_row = cursor.fetchone()
        if master_row:
            master_id = master_row[0]
    
    if has_master_id and has_business_id:
        cursor.execute("""
            INSERT INTO FinancialTransactions 
            (id, user_id, business_id, transaction_date, amount, client_type, services, notes, master_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            transaction_id, db_user_id, business_id,
            transaction_data['transaction_date'], transaction_data['amount'],
            transaction_data['client_type'], json.dumps(transaction_data['services']),
            transaction_data['notes'], master_id
        ))
    elif has_master_id:
        cursor.execute("""
            INSERT INTO FinancialTransactions 
            (id, user_id, transaction_date, amount, client_type, services, notes, master_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            transaction_id, db_user_id,
            transaction_data['transaction_date'], transaction_data['amount'],
            transaction_data['client_type'], json.dumps(transaction_data['services']),
            transaction_data['notes'], master_id
        ))
    else:
        cursor.execute("""
            INSERT INTO FinancialTransactions 
            (id, user_id, transaction_date, amount, client_type, services, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            transaction_id, db_user_id,
            transaction_data['transaction_date'], transaction_data['amount'],
            transaction_data['client_type'], json.dumps(transaction_data['services']),
            transaction_data['notes']
        ))
    
    conn.commit()
    conn.close()
    
    await update.message.reply_text(
        f"✅ Транзакция добавлена!\n\n"
        f"💰 Сумма: {transaction_data['amount']} ₽\n"
        f"📅 Дата: {transaction_data['transaction_date']}\n\n"
        f"Используйте /start для возврата в меню"
    )
    
    user_states[user_id] = {'state': 'idle'}

async def handle_optimize_text(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: str, text: str):
    """Обработка текста для оптимизации"""
    await update.message.reply_text("⏳ Анализирую услуги...")
    
    try:
        # Читаем промпт
        try:
            with open('prompts/seo-optimization-prompt.txt', 'r', encoding='utf-8') as f:
                prompt = f.read()
        except:
            prompt = "Оптимизируй список услуг для локального SEO."
        
        full_prompt = f"{prompt}\n\nСписок услуг:\n{text}"
        result = analyze_text_with_gigachat(full_prompt)
        
        if 'error' in result:
            await update.message.reply_text(f"❌ Ошибка анализа: {result['error']}")
            return
        
        # Парсим результат
        analysis_result = json.loads(result) if isinstance(result, str) else result
        services = analysis_result.get('services', [])
        
        if not services:
            await update.message.reply_text("❌ Не удалось распознать услуги")
            return
        
        # Формируем ответ
        response_text = "📊 *Результаты оптимизации:*\n\n"
        for i, service in enumerate(services[:10], 1):
            response_text += f"{i}. *{service.get('original_name', 'N/A')}*\n"
            response_text += f"   → {service.get('optimized_name', 'N/A')}\n\n"
        
        if len(services) > 10:
            response_text += f"\n... и ещё {len(services) - 10} услуг\n"
        
        response_text += "\n💡 Полные результаты доступны в личном кабинете на сайте."
        
        await update.message.reply_text(response_text, parse_mode='Markdown')
        user_states[user_id] = {'state': 'idle'}
        
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка обработки: {str(e)}")

async def handle_setting_text(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: str, text: str, state: str):
    """Обработка изменения настройки компании"""
    business_id = user_states[user_id].get('business_id')
    setting_type = state.replace('waiting_setting_', '')
    db_user_id = get_user_id_from_telegram(user_id)
    
    if not db_user_id:
        await update.message.reply_text("❌ Аккаунт не привязан")
        return
    
    try:
        # Обновляем через API
        update_data = {}
        if setting_type == 'name':
            update_data['businessName'] = text
        elif setting_type == 'address':
            update_data['address'] = text
        elif setting_type == 'maps':
            update_data['yandexUrl'] = text
        elif setting_type == 'phone':
            update_data['phone'] = text
        elif setting_type == 'hours':
            update_data['workingHours'] = text
        
        # Получаем токен сессии для API (упрощенная версия - напрямую в БД)
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if setting_type in ['name', 'address', 'hours']:
            field_map = {
                'name': 'name',
                'address': 'address',
                'hours': 'working_hours'
            }
            field = field_map.get(setting_type)
            if field:
                cursor.execute(f"UPDATE Businesses SET {field} = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", 
                             (text, business_id))
                conn.commit()
        
        conn.close()
        
        setting_names = {
            'name': 'название',
            'address': 'адрес',
            'maps': 'ссылку на карты',
            'phone': 'телефон',
            'hours': 'часы работы'
        }
        
        await update.message.reply_text(
            f"✅ {setting_names.get(setting_type, setting_type).capitalize()} успешно обновлено!\n\n"
            f"Используйте /start для возврата в меню"
        )
        
        user_states[user_id] = {'state': 'idle'}
        
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка обновления: {str(e)}")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /help"""
    help_text = """
🤖 *BeautyBot Telegram-бот*

*Команды:*
/start - Главное меню
/help - Справка
/cancel - Отменить текущую операцию

*Функции:*
💰 Добавление транзакций (фото/текст)
📊 Оптимизация услуг для SEO
⚙️ Настройки компании
📈 Статистика (в разработке)

*Поддержка:*
Если возникли проблемы, обратитесь в поддержку через личный кабинет на сайте.
    """
    await update.message.reply_text(help_text, parse_mode='Markdown')

def main():
    """Запуск бота"""
    if not TELEGRAM_BOT_TOKEN:
        print("⚠️  TELEGRAM_BOT_TOKEN не установлен. Бот не будет запущен.")
        print("💡 Установите токен: export TELEGRAM_BOT_TOKEN='ваш_токен'")
        return
    
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Регистрируем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("cancel", lambda u, c: u.message.reply_text("❌ Операция отменена")))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    print("🤖 Telegram-бот запущен...")
    print(f"📡 API Base URL: {API_BASE_URL}")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
