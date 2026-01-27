
import sqlite3
import os

DB_PATH = 'src/reports.db'

# Define the expected schema (Golden Standard)
# simplified: TableName -> [Required Columns]
EXPECTED_SCHEMA = {
    "Users": ["id", "email", "password_hash", "name", "phone", "telegram_id", "created_at", "updated_at", "is_active", "is_verified", "is_superadmin"],
    "Businesses": ["id", "name", "owner_id", "subscription_tier", "subscription_status", "city", "country", "timezone", "latitude", "longitude", "working_hours_json", "waba_phone_id", "ai_agent_enabled", "ai_agent_type"],
    "UserSessions": ["id", "user_id", "token"],
    "ParseQueue": ["id", "url", "user_id", "business_id", "task_type", "status", "updated_at"],
    "SyncQueue": ["id", "business_id", "source", "status"],
    "ProxyServers": ["id", "proxy_type", "host", "port", "is_active"],
    "MapParseResults": ["id", "business_id", "url", "title", "address", "analysis_json", "created_at"], # Recently fixed
    "BusinessMapLinks": ["id", "business_id", "url"],
    "FinancialTransactions": ["id", "business_id", "amount", "transaction_date"],
    "UserServices": ["id", "business_id", "name", "price"],
    "UserNews": ["id", "user_id", "generated_text", "approved", "updated_at"], # Recently fixed
    "Networks": ["id", "name", "owner_id"],
    "Masters": ["id", "business_id", "name"],
    "TelegramBindTokens": ["id", "user_id", "token"],
    "ReviewExchangeParticipants": ["id", "telegram_id", "is_active"],
    "ExternalBusinessReviews": ["id", "business_id", "source", "text"],
    "ExternalBusinessStats": ["id", "business_id", "source", "date"],
    "ExternalBusinessPosts": ["id", "business_id", "source", "title", "updated_at"], # External fix
    "ExternalBusinessPhotos": ["id", "business_id", "source", "url", "updated_at"], # External fix
    "WordstatKeywords": ["id", "keyword", "views"],
    "BusinessOptimizationWizard": ["id", "business_id", "step"],
    "PricelistOptimizations": ["id", "business_id", "optimized_text"],
    "AIPrompts": ["id", "prompt_type", "prompt_text"],
    "AIAgents": ["id", "name", "type"],
    "BusinessTypes": ["id", "type_key", "label"],
    "GrowthStages": ["id", "business_type_id", "stage_number"],
    "GrowthTasks": ["id", "stage_id", "task_text"]
}

def check_full_integrity():
    if not os.path.exists(DB_PATH):
        print(f"❌ Database not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print(f"🔎 Verifying database integrity for {len(EXPECTED_SCHEMA)} tables...")
    print("-" * 50)
    
    all_good = True
    
    # Get all actual tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    actual_tables = {row[0] for row in cursor.fetchall()}
    
    for table, required_columns in EXPECTED_SCHEMA.items():
        if table not in actual_tables:
            print(f"❌ MISSING TABLE: {table}")
            all_good = False
            continue
            
        # Check columns
        cursor.execute(f"PRAGMA table_info({table})")
        actual_columns = {row[1] for row in cursor.fetchall()}
        
        missing_cols = []
        for col in required_columns:
            if col not in actual_columns:
                missing_cols.append(col)
        
        if missing_cols:
            print(f"❌ TABLE {table} IS MISSING COLUMNS: {', '.join(missing_cols)}")
            all_good = False
        else:
            # print(f"✅ {table} OK")
            pass

    print("-" * 50)
    if all_good:
        print("✅✅✅ ALL CHECKS PASSED! DATABASE IS 100% HEALTHY. ✅✅✅")
    else:
        print("⚠️  INTEGRITY ISSUES FOUND (See above).")

    conn.close()

if __name__ == "__main__":
    check_full_integrity()
