import sys
import os
import sqlite3
import json

# Set up paths
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'src')))
from safe_db_utils import get_db_connection

def cleanup_duplicates():
    print("🧹 Starting cleanup of duplicate reviews...")
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Find duplicates grouping by business_id, author_name, and text
        cursor.execute("""
            SELECT business_id, author_name, text, COUNT(*) as cnt, GROUP_CONCAT(id) as ids
            FROM ExternalBusinessReviews
            GROUP BY business_id, author_name, text
            HAVING cnt > 1
        """)
        
        duplicates = cursor.fetchall()
        print(f"found {len(duplicates)} sets of duplicates.")
        
        total_deleted = 0
        for row in duplicates:
            ids = row['ids'].split(',')
            # Keep the first one, delete others
            ids_to_delete = ids[1:]
            
            placeholders = ', '.join(['?'] * len(ids_to_delete))
            cursor.execute(f"DELETE FROM ExternalBusinessReviews WHERE id IN ({placeholders})", ids_to_delete)
            total_deleted += len(ids_to_delete)
            
        print(f"🗑 Deleted {total_deleted} duplicate reviews.")
        conn.commit()
        
        
        # Recalculate unanswered count for MapParseResults
        cursor.execute("SELECT COUNT(*) FROM ExternalBusinessReviews")
        total = cursor.fetchone()[0]
        print(f"📊 Total reviews in DB: {total}")
        
        cursor.execute("SELECT business_id, COUNT(*) FROM ExternalBusinessReviews GROUP BY business_id")
        rows = cursor.fetchall()
        for r in rows:
            print(f"  Business {r['business_id']}: {r[1]} reviews")

        # We need to find which businesses were affected
        business_ids = set(row['business_id'] for row in duplicates)
        
        for bid in business_ids:
            cursor.execute("""
                SELECT COUNT(*) FROM ExternalBusinessReviews 
                WHERE business_id = ? AND (response_text IS NULL OR response_text = '' OR response_text = '—')
            """, (bid,))
            unanswered = cursor.fetchone()[0]
            
            cursor.execute("""
                UPDATE MapParseResults 
                SET unanswered_reviews_count = ? 
                WHERE business_id = ?
            """, (unanswered, bid))
            print(f"🔄 Updated business {bid}: {unanswered} unanswered reviews.")
            
        conn.commit()
        print("✅ Cleanup complete.")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    cleanup_duplicates()
