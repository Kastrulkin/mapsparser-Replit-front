
import sys
import os

# Add src to path if needed
sys.path.append(os.path.join(os.path.dirname(__file__)))

from init_database_schema import init_database_schema

if __name__ == "__main__":
    print("🚀 Running explicit database schema update...")
    try:
        init_database_schema()
        print("✅ Schema update completed successfully.")
    except Exception as e:
        print(f"❌ Error updating schema: {e}")
