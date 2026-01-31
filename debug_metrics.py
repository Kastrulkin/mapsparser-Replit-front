import sqlite3
import os
import sys
from datetime import datetime

# Add 'src' to python path so we can import modules
current_dir = os.getcwd()
src_dir = os.path.join(current_dir, 'src')
sys.path.append(src_dir)

try:
    from safe_db_utils import get_db_connection
    print("Successfully imported safe_db_utils")
except ImportError as e:
    print(f"Could not import safe_db_utils: {e}")
    # Fallback to the known path in src
    def get_db_connection():
        db_path = os.path.join(src_dir, 'reports.db')
        print(f"Connecting to fallback DB path: {db_path}")
        return sqlite3.connect(db_path)

def debug_metrics():
    print("=== DEBUGGING METRICS ===")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # 1. Check if MapParseResults exists and has data
        print("\n[1] Checking MapParseResults table...")
        try:
            cursor.execute("SELECT COUNT(*) FROM MapParseResults")
            count = cursor.fetchone()[0]
            print(f"Total rows in MapParseResults: {count}")
            
            if count > 0:
                cursor.execute("SELECT id, business_id, created_at, rating FROM MapParseResults ORDER BY created_at DESC LIMIT 5")
                print("Latest 5 Parse Results:")
                for row in cursor.fetchall():
                    print(f" - ID: {row[0]}, BID: {row[1]}, Date: {row[2]}, Rating: {row[3]}")
        except Exception as e:
            print(f"Error reading MapParseResults: {e}")

        # 2. Check if BusinessMetricsHistory exists and has data
        print("\n[2] Checking BusinessMetricsHistory table...")
        try:
            cursor.execute("SELECT COUNT(*) FROM BusinessMetricsHistory")
            count = cursor.fetchone()[0]
            print(f"Total rows in BusinessMetricsHistory: {count}")
            
            if count > 0:
                cursor.execute("SELECT id, business_id, metric_date, source, rating FROM BusinessMetricsHistory ORDER BY metric_date DESC LIMIT 5")
                print("Latest 5 Metrics History Entries:")
                for row in cursor.fetchall():
                   print(f" - ID: {row[0]}, BID: {row[1]}, Date: {row[2]}, Source: {row[3]}, Rating: {row[4]}")
        except Exception as e:
            print(f"Error reading BusinessMetricsHistory (maybe table missing?): {e}")

        # 3. List all Businesses
        print("\n[3] Businesses:")
        cursor.execute("SELECT id, name FROM Businesses LIMIT 5")
        for row in cursor.fetchall():
            print(f" - Business: string_id='{row[0]}', Name='{row[1]}'")

    except Exception as e:
        print(f"\nCRITICAL ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()

if __name__ == "__main__":
    debug_metrics()
