from flask import Flask
import os
import sys

# Добавляем src в путь
sys.path.append(os.path.join(os.path.dirname(__file__), '.'))

from api.growth_api import growth_bp
from database_manager import DatabaseManager

app = Flask(__name__)
app.register_blueprint(growth_bp)

def debug_500(business_id):
    print(f"🔍 DEBUG: Testing /api/business/{business_id}/stages")
    
    # 1. Проверка БД
    try:
        db = DatabaseManager()
        cursor = db.conn.cursor()
        print("✅ DB Connection successful")
        
        cursor.execute("SELECT count(*) FROM BusinessTypes")
        print(f"📊 BusinessTypes count: {cursor.fetchone()[0]}")
        
        cursor.execute("SELECT count(*) FROM GrowthStages")
        print(f"📊 GrowthStages count: {cursor.fetchone()[0]}")
        
        cursor.execute("SELECT * FROM Businesses WHERE id = %s", (business_id,))
        biz = cursor.fetchone()
        if biz:
            print(f"🏢 Business found: Type={biz['business_type'] if 'business_type' in biz.keys() else 'Unknown index'}")
            # Try raw tuple access just in case
            print(f"🏢 Business raw: {biz[0]}, {biz[1]}")
        else:
            print("❌ Business NOT found")
            return

        db.close()
    except Exception as e:
        print(f"❌ DB Check Failed: {e}")
        import traceback
        traceback.print_exc()
        return

    # 2. Проверка API (симуляция)
    try:
        # Мы не мокаем verify_session, поэтому просто вызовем функцию если бы могли...
        # Но API требует request context.
        # Создадим фейк контекст
        with app.test_request_context(
            f'/api/business/{business_id}/stages',
            headers={'Authorization': 'Bearer FAKE_TOKEN_FOR_DEBUG'}
        ):
            # ВНИМАНИЕ: auth_system.verify_session будет вызван. 
            # Он упадет если токен фейковый.
            # Поэтому мы просто проверим логику функции get_business_stages БЕЗ декоратора, если получится,
            # но она внутри функции.
            # Вместо этого мы пропатчим verify_session
            import auth_system
            original_verify = auth_system.verify_session
            auth_system.verify_session = lambda token: {'user_id': biz[0], 'is_superadmin': True} # Mock admin
            
            from api.growth_api import get_business_stages
            print("🚀 Calling endpoint function...")
            response = get_business_stages(business_id)
            print(f"🏁 Response: {response}")
            
            # Restore
            auth_system.verify_session = original_verify
            
    except Exception as e:
        print(f"❌ API Call Failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        bid = sys.argv[1]
    else:
        bid = "533c1300-8a54-43a8-aa1f-69a8ed9c24ba" # From user log
    debug_500(bid)
