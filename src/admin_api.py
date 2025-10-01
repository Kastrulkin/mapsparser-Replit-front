#!/usr/bin/env python3
"""
Административный API для управления всеми 4 таблицами
"""
from flask import Flask, request, jsonify
from database_manager import DatabaseManager
import json

app = Flask(__name__)

def get_db_manager():
    """Получить менеджер базы данных"""
    return DatabaseManager()

# ===== СТАТИСТИКА =====

@app.route('/api/admin/statistics', methods=['GET'])
def get_statistics():
    """Получить статистику системы"""
    try:
        db = get_db_manager()
        stats = db.get_statistics()
        db.close()
        return jsonify(stats), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ===== USERS (Пользователи) =====

@app.route('/api/admin/users', methods=['GET'])
def get_all_users():
    """Получить всех пользователей"""
    try:
        db = get_db_manager()
        users = db.get_all_users()
        db.close()
        return jsonify({"users": users}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/admin/users/<user_id>', methods=['GET'])
def get_user(user_id):
    """Получить пользователя по ID"""
    try:
        db = get_db_manager()
        user = db.get_user_by_id(user_id)
        db.close()
        
        if not user:
            return jsonify({"error": "Пользователь не найден"}), 404
        
        return jsonify(user), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/admin/users/<user_id>', methods=['PUT'])
def update_user(user_id):
    """Обновить пользователя"""
    try:
        data = request.get_json()
        db = get_db_manager()
        
        success = db.update_user(user_id, **data)
        db.close()
        
        if success:
            return jsonify({"message": "Пользователь обновлен"}), 200
        else:
            return jsonify({"error": "Ошибка при обновлении"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/admin/users/<user_id>', methods=['DELETE'])
def delete_user(user_id):
    """Удалить пользователя"""
    try:
        db = get_db_manager()
        success = db.delete_user(user_id)
        db.close()
        
        if success:
            return jsonify({"message": "Пользователь удален"}), 200
        else:
            return jsonify({"error": "Пользователь не найден"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ===== INVITES (Приглашения) =====

@app.route('/api/admin/invites', methods=['GET'])
def get_all_invites():
    """Получить все приглашения"""
    try:
        db = get_db_manager()
        invites = db.get_all_invites()
        db.close()
        return jsonify({"invites": invites}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/admin/invites', methods=['POST'])
def create_invite():
    """Создать приглашение"""
    try:
        data = request.get_json()
        email = data.get('email')
        invited_by = data.get('invited_by')
        expires_days = data.get('expires_days', 7)
        
        if not email or not invited_by:
            return jsonify({"error": "Email и invited_by обязательны"}), 400
        
        db = get_db_manager()
        token = db.create_invite(email, invited_by, expires_days)
        db.close()
        
        return jsonify({"token": token, "message": "Приглашение создано"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/admin/invites/<invite_id>/status', methods=['PUT'])
def update_invite_status(invite_id):
    """Обновить статус приглашения"""
    try:
        data = request.get_json()
        status = data.get('status')
        
        if not status:
            return jsonify({"error": "Статус обязателен"}), 400
        
        db = get_db_manager()
        success = db.update_invite_status(invite_id, status)
        db.close()
        
        if success:
            return jsonify({"message": "Статус обновлен"}), 200
        else:
            return jsonify({"error": "Приглашение не найдено"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/admin/invites/<invite_id>', methods=['DELETE'])
def delete_invite(invite_id):
    """Удалить приглашение"""
    try:
        db = get_db_manager()
        success = db.delete_invite(invite_id)
        db.close()
        
        if success:
            return jsonify({"message": "Приглашение удалено"}), 200
        else:
            return jsonify({"error": "Приглашение не найдено"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ===== PARSEQUEUE (Очередь) =====

@app.route('/api/admin/queue', methods=['GET'])
def get_all_queue():
    """Получить всю очередь"""
    try:
        db = get_db_manager()
        queue = db.get_all_queue_items()
        db.close()
        return jsonify({"queue": queue}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/admin/queue/pending', methods=['GET'])
def get_pending_queue():
    """Получить ожидающие элементы очереди"""
    try:
        db = get_db_manager()
        queue = db.get_pending_queue_items()
        db.close()
        return jsonify({"queue": queue}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/admin/queue/<queue_id>/status', methods=['PUT'])
def update_queue_status(queue_id):
    """Обновить статус элемента очереди"""
    try:
        data = request.get_json()
        status = data.get('status')
        
        if not status:
            return jsonify({"error": "Статус обязателен"}), 400
        
        db = get_db_manager()
        success = db.update_queue_status(queue_id, status)
        db.close()
        
        if success:
            return jsonify({"message": "Статус обновлен"}), 200
        else:
            return jsonify({"error": "Элемент очереди не найден"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/admin/queue/<queue_id>', methods=['DELETE'])
def delete_queue_item(queue_id):
    """Удалить элемент очереди"""
    try:
        db = get_db_manager()
        success = db.delete_queue_item(queue_id)
        db.close()
        
        if success:
            return jsonify({"message": "Элемент очереди удален"}), 200
        else:
            return jsonify({"error": "Элемент очереди не найден"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ===== CARDS (Отчёты) =====

@app.route('/api/admin/cards', methods=['GET'])
def get_all_cards():
    """Получить все карточки"""
    try:
        db = get_db_manager()
        cards = db.get_all_cards()
        db.close()
        return jsonify({"cards": cards}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/admin/cards/<card_id>', methods=['GET'])
def get_card(card_id):
    """Получить карточку по ID"""
    try:
        db = get_db_manager()
        card = db.get_card_by_id(card_id)
        db.close()
        
        if not card:
            return jsonify({"error": "Карточка не найдена"}), 404
        
        return jsonify(card), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/admin/cards/<card_id>', methods=['PUT'])
def update_card(card_id):
    """Обновить карточку"""
    try:
        data = request.get_json()
        db = get_db_manager()
        
        success = db.update_card(card_id, **data)
        db.close()
        
        if success:
            return jsonify({"message": "Карточка обновлена"}), 200
        else:
            return jsonify({"error": "Ошибка при обновлении"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/admin/cards/<card_id>', methods=['DELETE'])
def delete_card(card_id):
    """Удалить карточку"""
    try:
        db = get_db_manager()
        success = db.delete_card(card_id)
        db.close()
        
        if success:
            return jsonify({"message": "Карточка удалена"}), 200
        else:
            return jsonify({"error": "Карточка не найдена"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ===== ПОЛЬЗОВАТЕЛЬСКИЕ ОТЧЁТЫ =====

@app.route('/api/admin/users/<user_id>/reports', methods=['GET'])
def get_user_reports(user_id):
    """Получить отчёты пользователя"""
    try:
        db = get_db_manager()
        cards = db.get_cards_by_user(user_id)
        db.close()
        return jsonify({"reports": cards}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/admin/users/<user_id>/queue', methods=['GET'])
def get_user_queue(user_id):
    """Получить очередь пользователя"""
    try:
        db = get_db_manager()
        queue = db.get_queue_by_user(user_id)
        db.close()
        return jsonify({"queue": queue}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5003, debug=True)
