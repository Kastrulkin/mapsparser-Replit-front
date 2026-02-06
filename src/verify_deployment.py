#!/usr/bin/env python3
import sqlite3
import subprocess

def check_git_status():
    print("🔍 1. GIthub Status:")
    try:
        # Get last commit message
        msg = subprocess.check_output(["git", "log", "-1", "--pretty=%B"], encoding="utf-8").strip()
        print(f"   Last Commit: {msg}")
        
        # Check specifically for "Services" related changes
        status = subprocess.check_output(["git", "status"], encoding="utf-8")
        print(f"   Git Status: {'Clean' if 'working tree clean' in status else 'Dirty (Uncommitted changes)'}")
    except Exception as e:
        print(f"   ❌ Error checking git: {e}")

def check_file_content():
    print("\n🔍 2. Code Verification:")
    try:
        # Check worker for services_count logic
        with open("src/yandex_business_sync_worker.py", "r") as f:
            content = f.read()
            if "services_count" in content:
                print("   ✅ yandex_business_sync_worker.py contains 'services_count'")
            else:
                print("   ❌ yandex_business_sync_worker.py is OLD (missing 'services_count')")
                
        # Check scraper for parse_products
        with open("src/yandex_maps_scraper.py", "r") as f:
            content = f.read()
            if "parse_products" in content:
                print("   ✅ yandex_maps_scraper.py contains 'parse_products'")
            else:
                print("   ❌ yandex_maps_scraper.py is OLD (missing 'parse_products')")

    except FileNotFoundError as e:
        print(f"   ❌ File not found: {e}")

def check_database():
    print("\n🔍 3. Database Verification:")
    try:
        conn = sqlite3.connect("reports.db")
        cursor = conn.cursor()
        
        # Check MapParseResults columns
        cursor.execute("PRAGMA table_info(MapParseResults)")
        columns = [row[1] for row in cursor.fetchall()]
        if "services_count" in columns and "products" in columns:
            print("   ✅ MapParseResults has 'services_count' & 'products'")
        else:
            print(f"   ❌ MapParseResults missing columns. Found: {columns}")
            
        # Check UserServices table
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='UserServices'")
        if cursor.fetchone():
            cursor.execute("SELECT COUNT(*) FROM UserServices")
            count = cursor.fetchone()[0]
            print(f"   ✅ UserServices table exists (Rows: {count})")
        else:
            print("   ❌ UserServices table MISSING")
            
        conn.close()
    except Exception as e:
        print(f"   ❌ Database error: {e}")

def check_processes():
    print("\n🔍 4. Process Verification:")
    try:
        # Check running python workers
        output = subprocess.check_output(["ps", "aux"], encoding="utf-8")
        workers = [line for line in output.splitlines() if "worker.py" in line]
        print(f"   Running Workers: {len(workers)}")
        for w in workers:
            print(f"   - {w.strip()}")
            
        # Check absolute path of running worker
        if "/root/mapsparser-Replit-front" not in output:
            print("   ⚠️ WARNING: Workers might be running from WRONG directory!")
    except Exception as e:
        print(f"   ❌ Error checking processes: {e}")

if __name__ == "__main__":
    print("🚀 Starting Deployment Verification...\n")
    check_git_status()
    check_file_content()
    check_database()
    check_processes()
    print("\nDone.")
