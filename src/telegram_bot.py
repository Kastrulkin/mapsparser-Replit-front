#!/usr/bin/env python3
"""
Telegram-бот для добавления транзакций через Telegram
"""
import os
import json
import uuid
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from safe_db_utils import get_db_connection
from services.gigachat_client import analyze_screenshot_with_gigachat, analyze_text_with_gigachat

# Токен бота из переменных окружения
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')

# Словарь для хранения состояния пользователей (user_id -> state)
user_states = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user_id = str(update.effective_user.id)
    user_states[user_id] = {'state': 'waiting_business'}
    
    # Получаем список бизнесов пользователя
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Ищем пользователя по telegram_id или создаем связь
    cursor.execute("SELECT id FROM Users WHERE telegram_id = ?", (user_id,))
    user_row = cursor.fetchone()
    
    if not user_row:
        await update.message.reply_text(
            "Привет! Для использования бота нужно сначала связать ваш Telegram-аккаунт с аккаунтом на сайте.\n"
            "Перейдите в личный кабинет на сайте и найдите раздел 'Telegram-бот' для получения кода привязки."
        )
        conn.close()
        return
    
    db_user_id = user_row[0]
    
    # Получаем бизнесы пользователя
    cursor.execute("SELECT id, name FROM Businesses WHERE owner_id = ?", (db_user_id,))
    businesses = cursor.fetchall()
    conn.close()
    
    if not businesses:
        await update.message.reply_text("У вас пока нет бизнесов. Создайте бизнес на сайте.")
        return
    
    # Создаем клавиатуру с бизнесами
    keyboard = []
    for business_id, business_name in businesses:
        keyboard.append([InlineKeyboardButton(business_name, callback_data=f"business_{business_id}")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "Выберите бизнес для добавления транзакции:",
        reply_markup=reply_markup
    )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатий на кнопки"""
    query = update.callback_query
    await query.answer()
    
    user_id = str(update.effective_user.id)
    data = query.data
    
    if data.startswith('business_'):
        business_id = data.replace('business_', '')
        user_states[user_id] = {
            'state': 'waiting_transaction',
            'business_id': business_id
        }
        
        await query.edit_message_text(
            "Отлично! Теперь отправьте:\n"
            "1. Фото чека/документа с транзакцией, или\n"
            "2. Текст с информацией о транзакции в формате:\n"
            "   Дата: YYYY-MM-DD\n"
            "   Сумма: 1000\n"
            "   Услуги: Стрижка, Окрашивание\n"
            "   Мастер: Имя мастера (опционально)\n"
            "   Тип клиента: new/returning (опционально)"
        )
    elif data.startswith('client_type_'):
        client_type = data.replace('client_type_', '')
        if user_id in user_states and 'transaction_data' in user_states[user_id]:
            user_states[user_id]['transaction_data']['client_type'] = client_type
            await save_transaction(update, context, user_id)
        else:
            await query.edit_message_text("Ошибка: данные транзакции не найдены")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик фото"""
    user_id = str(update.effective_user.id)
    
    if user_id not in user_states or user_states[user_id].get('state') != 'waiting_transaction':
        await update.message.reply_text("Сначала выберите бизнес командой /start")
        return
    
    business_id = user_states[user_id].get('business_id')
    
    # Получаем файл фото
    photo = update.message.photo[-1]  # Берем фото наибольшего размера
    file = await context.bot.get_file(photo.file_id)
    
    await update.message.reply_text("Обрабатываю фото...")
    
    # Скачиваем фото
    photo_bytes = await file.download_as_bytearray()
    
    # Анализируем через GigaChat
    try:
        import base64
        image_base64 = base64.b64encode(photo_bytes).decode('utf-8')
        
        # Читаем промпт
        with open('prompts/transaction-analysis-prompt.txt', 'r', encoding='utf-8') as f:
            prompt = f.read()
        
        result = analyze_screenshot_with_gigachat(image_base64, prompt)
        
        if 'error' in result:
            await update.message.reply_text(f"Ошибка анализа: {result['error']}")
            return
        
        # Парсим результат
        analysis_result = json.loads(result) if isinstance(result, str) else result
        transactions = analysis_result.get('transactions', [])
        
        if not transactions:
            await update.message.reply_text("Не удалось распознать транзакции на фото")
            return
        
        # Сохраняем транзакции
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Получаем user_id из telegram_id
        cursor.execute("SELECT id FROM Users WHERE telegram_id = ?", (user_id,))
        user_row = cursor.fetchone()
        if not user_row:
            await update.message.reply_text("Ошибка: пользователь не найден")
            conn.close()
            return
        
        db_user_id = user_row[0]
        
        saved_count = 0
        for trans in transactions:
            transaction_id = str(uuid.uuid4())
            
            # Получаем master_id по имени
            master_id = None
            if trans.get('master_name'):
                cursor.execute("SELECT id FROM Masters WHERE name = ? AND business_id = ? LIMIT 1", 
                             (trans['master_name'], business_id))
                master_row = cursor.fetchone()
                if master_row:
                    master_id = master_row[0]
            
            cursor.execute("""
                INSERT INTO FinancialTransactions 
                (id, user_id, transaction_date, amount, client_type, services, notes, master_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                transaction_id,
                db_user_id,
                trans.get('transaction_date', datetime.now().strftime('%Y-%m-%d')),
                trans.get('amount', 0),
                trans.get('client_type', 'new'),
                json.dumps(trans.get('services', [])),
                trans.get('notes', ''),
                master_id
            ))
            saved_count += 1
        
        conn.commit()
        conn.close()
        
        await update.message.reply_text(
            f"✅ Успешно добавлено {saved_count} транзакций!\n"
            f"Используйте /start для добавления новой транзакции"
        )
        
        # Сбрасываем состояние
        user_states[user_id] = {'state': 'idle'}
        
    except Exception as e:
        await update.message.reply_text(f"Ошибка обработки фото: {str(e)}")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений"""
    user_id = str(update.effective_user.id)
    text = update.message.text
    
    if user_id not in user_states or user_states[user_id].get('state') != 'waiting_transaction':
        await update.message.reply_text("Сначала выберите бизнес командой /start")
        return
    
    business_id = user_states[user_id].get('business_id')
    
    # Парсим текст транзакции
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
                    transaction_data['amount'] = float(value)
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
    
    # Если сумма не указана, просим уточнить
    if transaction_data['amount'] == 0:
        await update.message.reply_text("Пожалуйста, укажите сумму транзакции")
        return
    
    # Сохраняем транзакцию
    user_states[user_id]['transaction_data'] = transaction_data
    await save_transaction(update, context, user_id)

async def save_transaction(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: str):
    """Сохранить транзакцию в БД"""
    if user_id not in user_states or 'transaction_data' not in user_states[user_id]:
        return
    
    transaction_data = user_states[user_id]['transaction_data']
    business_id = user_states[user_id].get('business_id')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Получаем user_id из telegram_id
    cursor.execute("SELECT id FROM Users WHERE telegram_id = ?", (user_id,))
    user_row = cursor.fetchone()
    if not user_row:
        await update.message.reply_text("Ошибка: пользователь не найден")
        conn.close()
        return
    
    db_user_id = user_row[0]
    
    transaction_id = str(uuid.uuid4())
    
    # Получаем master_id по имени
    master_id = None
    if transaction_data.get('master_name'):
        cursor.execute("SELECT id FROM Masters WHERE name = ? AND business_id = ? LIMIT 1", 
                     (transaction_data['master_name'], business_id))
        master_row = cursor.fetchone()
        if master_row:
            master_id = master_row[0]
    
    cursor.execute("""
        INSERT INTO FinancialTransactions 
        (id, user_id, transaction_date, amount, client_type, services, notes, master_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        transaction_id,
        db_user_id,
        transaction_data['transaction_date'],
        transaction_data['amount'],
        transaction_data['client_type'],
        json.dumps(transaction_data['services']),
        transaction_data['notes'],
        master_id
    ))
    
    conn.commit()
    conn.close()
    
    await update.message.reply_text(
        f"✅ Транзакция добавлена!\n"
        f"Сумма: {transaction_data['amount']} ₽\n"
        f"Дата: {transaction_data['transaction_date']}\n"
        f"Используйте /start для добавления новой транзакции"
    )
    
    # Сбрасываем состояние
    user_states[user_id] = {'state': 'idle'}

def main():
    """Запуск бота"""
    if not TELEGRAM_BOT_TOKEN:
        print("⚠️  TELEGRAM_BOT_TOKEN не установлен. Бот не будет запущен.")
        return
    
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Регистрируем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    print("🤖 Telegram-бот запущен...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()

