import json
import sys
import traceback
import uuid
from datetime import datetime, timedelta

from flask import Blueprint, jsonify, request

from auth_system import verify_session
from core.helpers import get_business_owner_id
from database_manager import DatabaseManager


growth_workflow_bp = Blueprint("growth_workflow_api", __name__)


@growth_workflow_bp.route("/api/progress", methods=["GET"])
def get_business_progress():
    """Получить прогресс развития бизнеса"""
    try:
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return jsonify({"error": "Требуется авторизация"}), 401

        token = auth_header.split(" ")[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401

        business_id = request.args.get("business_id")
        if not business_id:
            return jsonify({"error": "Не указан business_id"}), 400

        db = DatabaseManager()
        cursor = db.conn.cursor()

        owner_id = get_business_owner_id(cursor, business_id)
        if not owner_id:
            db.close()
            return jsonify({"error": "Бизнес не найден"}), 404

        if owner_id != user_data["user_id"] and not user_data.get("is_superadmin"):
            db.close()
            return jsonify({"error": "Нет доступа"}), 403

        cursor.execute("SELECT business_type FROM businesses WHERE id = %s", (business_id,))
        row = cursor.fetchone()
        business_type_key = row[0] if row else "other"

        cursor.execute("SELECT id FROM businesstypes WHERE type_key = %s OR id = %s", (business_type_key, business_type_key))
        bt_row = cursor.fetchone()

        if not bt_row:
            cursor.execute("SELECT id FROM businesstypes WHERE type_key = 'other'")
            bt_row = cursor.fetchone()

        business_type_id = bt_row[0] if bt_row else None

        if not business_type_id:
            db.close()
            return jsonify({"stages": [], "current_step": 1})

        cursor.execute("SELECT step FROM businessoptimizationwizard WHERE business_id = %s", (business_id,))
        wiz_row = cursor.fetchone()
        current_step = wiz_row[0] if wiz_row else 1

        cursor.execute(
            """
            SELECT id, stage_number, title, description, goal, expected_result, duration, is_permanent
            FROM GrowthStages
            WHERE business_type_id = %s
            ORDER BY stage_number
            """,
            (business_type_id,),
        )
        stages_rows = cursor.fetchall()

        stages = []
        for stage_row in stages_rows:
            stage_id = stage_row[0]
            stage_number = stage_row[1]

            cursor.execute(
                """
                SELECT id, task_number, task_text
                FROM GrowthTasks
                WHERE stage_id = %s
                ORDER BY task_number
                """,
                (stage_id,),
            )
            tasks_rows = cursor.fetchall()

            is_completed = stage_number < current_step
            is_current = stage_number == current_step

            tasks = []
            for task_row in tasks_rows:
                tasks.append(
                    {
                        "id": task_row[0],
                        "number": task_row[1],
                        "text": task_row[2],
                        "is_completed": is_completed,
                    }
                )

            stages.append(
                {
                    "id": stage_id,
                    "stage_number": stage_number,
                    "title": stage_row[2],
                    "description": stage_row[3],
                    "goal": stage_row[4],
                    "expected_result": stage_row[5],
                    "duration": stage_row[6],
                    "is_permanent": bool(stage_row[7]),
                    "status": "completed" if is_completed else ("current" if is_current else "locked"),
                    "tasks": tasks,
                }
            )

        db.close()

        return jsonify(
            {
                "success": True,
                "current_step": current_step,
                "stages": stages,
            }
        )

    except Exception:
        error = sys.exc_info()[1]
        print(f"❌ Ошибка api/progress: {error}")
        return jsonify({"error": str(error)}), 500


@growth_workflow_bp.route("/api/business/<business_id>/optimization-wizard", methods=["POST", "GET", "OPTIONS"])
def business_optimization_wizard(business_id):
    """Сохранить или получить данные мастера оптимизации бизнеса"""
    try:
        if request.method == "OPTIONS":
            return ("", 204)

        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return jsonify({"error": "Требуется авторизация"}), 401

        token = auth_header.split(" ")[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401

        db = DatabaseManager()
        cursor = db.conn.cursor()

        owner_id = get_business_owner_id(cursor, business_id)
        if not owner_id:
            db.close()
            return jsonify({"error": "Бизнес не найден"}), 404

        if owner_id != user_data["user_id"] and not user_data.get("is_superadmin"):
            db.close()
            return jsonify({"error": "Нет доступа к этому бизнесу"}), 403

        if request.method == "POST":
            data = request.get_json(silent=True) or {}
            wizard_data = {
                "experience": data.get("experience", ""),
                "clients": data.get("clients", ""),
                "crm": data.get("crm", ""),
                "location": data.get("location", ""),
                "average_check": data.get("average_check", ""),
                "revenue": data.get("revenue", ""),
            }

            cursor.execute("SELECT id FROM businessoptimizationwizard WHERE business_id = %s", (business_id,))
            existing = cursor.fetchone()

            if existing:
                cursor.execute(
                    """
                    UPDATE BusinessOptimizationWizard
                    SET data = %s, completed = 1, updated_at = CURRENT_TIMESTAMP
                    WHERE business_id = %s
                    """,
                    (json.dumps(wizard_data, ensure_ascii=False), business_id),
                )
            else:
                wizard_id = str(uuid.uuid4())
                cursor.execute(
                    """
                    INSERT INTO BusinessOptimizationWizard (id, business_id, step, data, completed)
                    VALUES (%s, %s, 3, %s, 1)
                    """,
                    (wizard_id, business_id, json.dumps(wizard_data, ensure_ascii=False)),
                )

            db.conn.commit()
            db.close()

            return jsonify(
                {
                    "success": True,
                    "message": "Данные мастера оптимизации сохранены",
                }
            )

        cursor.execute(
            """
            SELECT data, completed FROM BusinessOptimizationWizard
            WHERE business_id = %s
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            (business_id,),
        )
        row = cursor.fetchone()

        db.close()

        if row:
            wizard_data = json.loads(row[0]) if row[0] else {}
            return jsonify(
                {
                    "success": True,
                    "data": wizard_data,
                    "completed": row[1] == 1,
                }
            )

        return jsonify(
            {
                "success": True,
                "data": {},
                "completed": False,
            }
        )

    except Exception:
        error = sys.exc_info()[1]
        print(f"❌ Ошибка работы с мастером оптимизации: {error}")
        traceback.print_exc()
        return jsonify({"error": str(error)}), 500


@growth_workflow_bp.route("/api/business/<business_id>/sprint", methods=["GET", "POST", "OPTIONS"])
def business_sprint(business_id):
    """Получить или сгенерировать спринт для бизнеса"""
    try:
        if request.method == "OPTIONS":
            return ("", 204)

        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return jsonify({"error": "Требуется авторизация"}), 401

        token = auth_header.split(" ")[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401

        db = DatabaseManager()
        cursor = db.conn.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS BusinessSprints (
                id TEXT PRIMARY KEY,
                business_id TEXT NOT NULL,
                week_start DATE NOT NULL,
                tasks TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (business_id) REFERENCES Businesses (id) ON DELETE CASCADE
            )
            """
        )

        owner_id = get_business_owner_id(cursor, business_id)
        if not owner_id:
            db.close()
            return jsonify({"error": "Бизнес не найден"}), 404

        if owner_id != user_data["user_id"] and not user_data.get("is_superadmin"):
            db.close()
            return jsonify({"error": "Нет доступа к этому бизнесу"}), 403

        today = datetime.now().date()
        days_since_monday = today.weekday()
        week_start = today - timedelta(days=days_since_monday)

        if request.method == "POST":
            cursor.execute(
                """
                SELECT data FROM BusinessOptimizationWizard
                WHERE business_id = %s AND completed = 1
                ORDER BY updated_at DESC
                LIMIT 1
                """,
                (business_id,),
            )
            wizard_row = cursor.fetchone()

            wizard_data = {}
            if wizard_row and wizard_row[0]:
                wizard_data = json.loads(wizard_row[0])

            tasks = [
                {
                    "id": str(uuid.uuid4()),
                    "title": "Оптимизировать описание услуг на картах",
                    "description": "Обновить формулировки услуг для лучшего SEO",
                    "expected_effect": "+5% к выручке",
                    "deadline": "Пт",
                    "status": "pending",
                }
            ]

            if wizard_data.get("clients"):
                tasks.append(
                    {
                        "id": str(uuid.uuid4()),
                        "title": "Настроить систему напоминаний для постоянных клиентов",
                        "description": f'Использовать CRM ({wizard_data.get("crm", "любую")}) для автоматических напоминаний',
                        "expected_effect": "+10% к повторным визитам",
                        "deadline": "Пт",
                        "status": "pending",
                    }
                )

            if wizard_data.get("average_check"):
                tasks.append(
                    {
                        "id": str(uuid.uuid4()),
                        "title": "Проанализировать и оптимизировать ценообразование",
                        "description": f'Текущий средний чек: {wizard_data.get("average_check")}₽. Проверить конкурентов и оптимизировать',
                        "expected_effect": "+7% к среднему чеку",
                        "deadline": "Пт",
                        "status": "pending",
                    }
                )

            if wizard_data.get("revenue"):
                revenue = int(wizard_data.get("revenue", 0)) if str(wizard_data.get("revenue", "")).isdigit() else 0
                if revenue > 0:
                    target_increase = int(revenue * 0.1)
                    tasks.append(
                        {
                            "id": str(uuid.uuid4()),
                            "title": "Увеличить выручку на 10%",
                            "description": f"Текущая выручка: {revenue}₽. Цель: +{target_increase}₽ за месяц",
                            "expected_effect": f"+{target_increase}₽ к выручке",
                            "deadline": "Пт",
                            "status": "pending",
                        }
                    )

            sprint_id = str(uuid.uuid4())
            cursor.execute(
                """
                INSERT INTO businesssprints (id, business_id, week_start, tasks, updated_at)
                VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (id) DO UPDATE SET
                    business_id = EXCLUDED.business_id,
                    week_start = EXCLUDED.week_start,
                    tasks = EXCLUDED.tasks,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (sprint_id, business_id, week_start.isoformat(), json.dumps(tasks, ensure_ascii=False)),
            )

            db.conn.commit()
            db.close()

            return jsonify(
                {
                    "success": True,
                    "sprint": {
                        "id": sprint_id,
                        "week_start": week_start.isoformat(),
                        "tasks": tasks,
                    },
                }
            )

        cursor.execute(
            """
            SELECT id, tasks, updated_at FROM BusinessSprints
            WHERE business_id = %s AND week_start = %s
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            (business_id, week_start.isoformat()),
        )
        row = cursor.fetchone()

        db.close()

        if row:
            tasks = json.loads(row[1]) if row[1] else []
            return jsonify(
                {
                    "success": True,
                    "sprint": {
                        "id": row[0],
                        "week_start": week_start.isoformat(),
                        "tasks": tasks,
                    },
                }
            )

        return jsonify({"success": True, "sprint": None})

    except Exception:
        error = sys.exc_info()[1]
        print(f"❌ Ошибка работы со спринтом: {error}")
        traceback.print_exc()
        return jsonify({"error": str(error)}), 500
